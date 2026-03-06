from pathlib import Path
import threading
import time
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import parse_model_profile, write_config_values
from ..constants import (
    MODEL_PROFILE_CUSTOM,
    MODEL_PROFILE_HYBRID,
    MODEL_PROFILE_OFFLINE,
    MODEL_PROFILE_PRESETS,
    MODEL_PROFILE_REALTIME,
    OVERLAY_PERSIST_KEYS,
)
from .overlay import SubtitleOverlay

class OverlayControlPanel(QWidget):
    visibility_changed = Signal(bool)
    model_download_finished = Signal(bool, str)

    def __init__(self, overlay: SubtitleOverlay, config_path: Path, args: Any) -> None:
        super().__init__()
        self._overlay = overlay
        self._config_path = config_path
        self._syncing = False
        self._download_thread: threading.Thread | None = None
        self._model_profile = parse_model_profile(getattr(args, "model_profile", MODEL_PROFILE_REALTIME))
        self._model_download_on_startup = bool(getattr(args, "model_download_on_startup", False))
        self._model = str(getattr(args, "model", ""))
        self._detector_model = str(getattr(args, "detector_model", "paraformer-zh-streaming"))
        self._vad_model = str(getattr(args, "vad_model", ""))
        self._punc_model = str(getattr(args, "punc_model", ""))
        self._disable_vad_model = bool(getattr(args, "disable_vad_model", False))
        self._disable_punc_model = bool(getattr(args, "disable_punc_model", False))
        self._custom_profile_snapshot = {
            "model": self._model,
            "detector_model": self._detector_model,
            "vad_model": self._vad_model,
            "punc_model": self._punc_model,
            "disable_vad_model": self._disable_vad_model,
            "disable_punc_model": self._disable_punc_model,
        }
        self.setWindowTitle("Subtitle Settings")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self._build_ui()
        self._connect_signals()
        self._sync_from_overlay()
        self._sync_model_controls()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self.setMinimumWidth(360)
        self.resize(400, 560)

        tip = QLabel("F2: 编辑模式。拖拽文本框移动/缩放，拖拽背景调位置。")
        tip.setWordWrap(True)
        root.addWidget(tip)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)

        form_host = QWidget()
        scroll.setWidget(form_host)
        host_layout = QVBoxLayout(form_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(10)

        host_layout.addWidget(self._section_title("窗口"))
        window_form = QFormLayout()
        window_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._stay_on_top_checkbox = QCheckBox("启用")
        window_form.addRow("前台常驻", self._stay_on_top_checkbox)
        self._windowed_mode_checkbox = QCheckBox("启用")
        self._windowed_mode_checkbox.setToolTip("启用后仍为无边框透明背景，仅切换为非 Tool 窗口。")
        window_form.addRow("窗口化模式", self._windowed_mode_checkbox)
        self._edit_mode_checkbox = QCheckBox("启用")
        window_form.addRow("编辑模式", self._edit_mode_checkbox)
        host_layout.addLayout(window_form)

        host_layout.addWidget(self._section_title("字幕"))
        text_form = QFormLayout()
        text_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 120)
        text_form.addRow("字号", self._font_size_spin)

        self._text_x_spin = QSpinBox()
        self._text_x_spin.setRange(0, 5000)
        text_form.addRow("文本框 X", self._text_x_spin)

        self._text_y_spin = QSpinBox()
        self._text_y_spin.setRange(0, 5000)
        text_form.addRow("文本框 Y", self._text_y_spin)

        self._text_w_spin = QSpinBox()
        self._text_w_spin.setRange(1, 5000)
        text_form.addRow("文本框宽", self._text_w_spin)

        self._text_h_spin = QSpinBox()
        self._text_h_spin.setRange(1, 5000)
        text_form.addRow("文本框高", self._text_h_spin)
        host_layout.addLayout(text_form)

        host_layout.addWidget(self._section_title("背景"))
        bg_form = QFormLayout()
        bg_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._bg_x_spin = QSpinBox()
        self._bg_x_spin.setRange(-5000, 5000)
        bg_form.addRow("背景偏移 X", self._bg_x_spin)

        self._bg_y_spin = QSpinBox()
        self._bg_y_spin.setRange(-5000, 5000)
        bg_form.addRow("背景偏移 Y", self._bg_y_spin)

        self._bg_w_spin = QSpinBox()
        self._bg_w_spin.setRange(0, 5000)
        self._bg_w_spin.setSpecialValueText("自动")
        self._bg_w_spin.setToolTip("0 表示使用原图宽度")
        bg_form.addRow("背景宽", self._bg_w_spin)

        self._bg_h_spin = QSpinBox()
        self._bg_h_spin.setRange(0, 5000)
        self._bg_h_spin.setSpecialValueText("自动")
        self._bg_h_spin.setToolTip("0 表示使用原图高度")
        bg_form.addRow("背景高", self._bg_h_spin)
        host_layout.addLayout(bg_form)
        bg_hint = QLabel("提示：背景宽/高填 0 时，使用背景图片原始尺寸。")
        bg_hint.setWordWrap(True)
        host_layout.addWidget(bg_hint)

        host_layout.addWidget(self._section_title("模型"))
        model_form = QFormLayout()
        model_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._model_profile_combo = QComboBox()
        self._model_profile_combo.addItem("实时（低延迟）", MODEL_PROFILE_REALTIME)
        self._model_profile_combo.addItem("非实时（准确率优先）", MODEL_PROFILE_OFFLINE)
        self._model_profile_combo.addItem("混合（流式起句+离线整句）", MODEL_PROFILE_HYBRID)
        self._model_profile_combo.addItem("自定义（使用当前配置）", MODEL_PROFILE_CUSTOM)
        model_form.addRow("模型组合", self._model_profile_combo)
        self._model_download_on_startup_checkbox = QCheckBox("启动时预下载")
        model_form.addRow("自动下载", self._model_download_on_startup_checkbox)
        host_layout.addLayout(model_form)

        self._model_summary_label = QLabel("")
        self._model_summary_label.setWordWrap(True)
        host_layout.addWidget(self._model_summary_label)

        model_action_row = QHBoxLayout()
        self._download_model_button = QPushButton("下载当前组合")
        model_action_row.addWidget(self._download_model_button)
        host_layout.addLayout(model_action_row)
        model_hint = QLabel("提示：模型切换在重启后生效。")
        model_hint.setWordWrap(True)
        host_layout.addWidget(model_hint)

        host_layout.addStretch(1)
        root.addWidget(self._divider())

        action_row = QHBoxLayout()
        self._save_button = QPushButton("保存到配置")
        action_row.addWidget(self._save_button)
        root.addLayout(action_row)

        self._status_label = QLabel("")
        root.addWidget(self._status_label)

    def _connect_signals(self) -> None:
        self._overlay.settings_changed.connect(self._sync_from_overlay)
        self._overlay.edit_mode_changed.connect(self._on_overlay_edit_mode_changed)

        self._stay_on_top_checkbox.toggled.connect(self._on_stay_on_top_changed)
        self._windowed_mode_checkbox.toggled.connect(self._on_windowed_mode_changed)
        self._edit_mode_checkbox.toggled.connect(self._on_edit_mode_changed)
        self._font_size_spin.valueChanged.connect(self._on_font_size_changed)
        self._text_x_spin.valueChanged.connect(self._on_text_box_changed)
        self._text_y_spin.valueChanged.connect(self._on_text_box_changed)
        self._text_w_spin.valueChanged.connect(self._on_text_box_changed)
        self._text_h_spin.valueChanged.connect(self._on_text_box_changed)
        self._bg_x_spin.valueChanged.connect(self._on_bg_offset_changed)
        self._bg_y_spin.valueChanged.connect(self._on_bg_offset_changed)
        self._bg_w_spin.valueChanged.connect(self._on_bg_size_changed)
        self._bg_h_spin.valueChanged.connect(self._on_bg_size_changed)
        self._model_profile_combo.currentIndexChanged.connect(self._on_model_profile_changed)
        self._model_download_on_startup_checkbox.toggled.connect(self._on_model_download_startup_toggled)
        self._download_model_button.clicked.connect(self._on_download_model_clicked)
        self.model_download_finished.connect(self._on_model_download_finished)
        self._save_button.clicked.connect(self._save_to_config)

    def _divider(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.HLine)
        frame.setFrameShadow(QFrame.Shadow.Sunken)
        return frame

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        return label

    def _profile_display_name(self, profile: str) -> str:
        if profile in MODEL_PROFILE_PRESETS:
            return str(MODEL_PROFILE_PRESETS[profile]["label"])
        return "自定义"

    def _current_profile_from_combo(self) -> str:
        data = self._model_profile_combo.currentData()
        if data is None:
            return MODEL_PROFILE_REALTIME
        return parse_model_profile(data)

    def _apply_profile_to_model_fields(self, profile: str) -> None:
        if profile == MODEL_PROFILE_CUSTOM:
            self._model = str(self._custom_profile_snapshot["model"])
            self._detector_model = str(self._custom_profile_snapshot["detector_model"])
            self._vad_model = str(self._custom_profile_snapshot["vad_model"])
            self._punc_model = str(self._custom_profile_snapshot["punc_model"])
            self._disable_vad_model = bool(self._custom_profile_snapshot["disable_vad_model"])
            self._disable_punc_model = bool(self._custom_profile_snapshot["disable_punc_model"])
            return
        preset = MODEL_PROFILE_PRESETS[profile]
        self._model = str(preset["model"])
        self._detector_model = str(preset.get("detector_model", preset["model"]))
        self._vad_model = str(preset["vad_model"])
        self._punc_model = str(preset["punc_model"])
        self._disable_vad_model = bool(preset["disable_vad_model"])
        self._disable_punc_model = bool(preset["disable_punc_model"])

    def _refresh_model_summary(self) -> None:
        vad_text = "禁用" if self._disable_vad_model else self._vad_model
        punc_text = "禁用" if self._disable_punc_model else self._punc_model
        profile_name = self._profile_display_name(self._model_profile)
        self._model_summary_label.setText(
            "当前组合: "
            f"{profile_name} ({self._model_profile})\n"
            f"Detector: {self._detector_model}\n"
            f"ASR: {self._model}\n"
            f"VAD: {vad_text}\n"
            f"PUNC: {punc_text}"
        )

    def _sync_model_controls(self) -> None:
        self._syncing = True
        try:
            target_index = self._model_profile_combo.findData(self._model_profile)
            if target_index < 0:
                target_index = self._model_profile_combo.findData(MODEL_PROFILE_REALTIME)
                self._model_profile = MODEL_PROFILE_REALTIME
            self._model_profile_combo.setCurrentIndex(target_index)
            self._model_download_on_startup_checkbox.setChecked(self._model_download_on_startup)
            self._apply_profile_to_model_fields(self._model_profile)
            self._refresh_model_summary()
        finally:
            self._syncing = False

    def _build_model_download_kwargs_list(self) -> list[dict[str, Any]]:
        downloads: list[dict[str, Any]] = []
        if self._model_profile == MODEL_PROFILE_HYBRID:
            downloads.append({"model": self._detector_model, "disable_update": True})

        kwargs: dict[str, Any] = {"model": self._model, "disable_update": True}
        if "streaming" not in self._model:
            if not self._disable_vad_model:
                kwargs["vad_model"] = self._vad_model
            if not self._disable_punc_model:
                kwargs["punc_model"] = self._punc_model
        downloads.append(kwargs)
        return downloads

    def _on_model_profile_changed(self, _index: int) -> None:
        if self._syncing:
            return
        selected_profile = self._current_profile_from_combo()
        self._model_profile = selected_profile
        self._apply_profile_to_model_fields(self._model_profile)
        self._refresh_model_summary()
        self._status_label.setText("模型组合已切换，保存后重启生效。")

    def _on_model_download_startup_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        self._model_download_on_startup = bool(checked)

    def _on_download_model_clicked(self) -> None:
        if self._download_thread is not None and self._download_thread.is_alive():
            self._status_label.setText("模型下载进行中，请稍候。")
            return
        if not self._model.strip():
            self._status_label.setText("模型配置为空，无法下载。")
            return
        downloads = self._build_model_download_kwargs_list()
        self._download_model_button.setEnabled(False)
        names = ", ".join(str(item.get("model", "")) for item in downloads)
        self._status_label.setText(f"下载中: {names} ...")

        def worker() -> None:
            start = time.perf_counter()
            try:
                from funasr import AutoModel

                for kwargs in downloads:
                    AutoModel(**kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                self.model_download_finished.emit(False, f"模型下载失败: {exc}")
                return
            elapsed = time.perf_counter() - start
            self.model_download_finished.emit(True, f"模型下载完成（{elapsed:.1f}s）")

        self._download_thread = threading.Thread(target=worker, daemon=True)
        self._download_thread.start()

    def _on_model_download_finished(self, ok: bool, message: str) -> None:
        self._download_model_button.setEnabled(True)
        if ok:
            self._status_label.setText(message)
            return
        self._status_label.setText(message)

    def _sync_from_overlay(self, settings: dict[str, Any] | None = None) -> None:
        del settings
        snapshot = self._overlay.export_runtime_settings()
        self._syncing = True
        try:
            self._stay_on_top_checkbox.setChecked(bool(snapshot["stay_on_top"]))
            self._windowed_mode_checkbox.setChecked(bool(snapshot["windowed_mode"]))
            self._edit_mode_checkbox.setChecked(self._overlay.is_edit_mode())
            self._font_size_spin.setValue(int(snapshot["font_size"]))
            self._text_x_spin.setValue(int(snapshot["text_x"]))
            self._text_y_spin.setValue(int(snapshot["text_y"]))
            self._text_w_spin.setValue(int(snapshot["text_width"]))
            self._text_h_spin.setValue(int(snapshot["text_height"]))
            self._bg_x_spin.setValue(int(snapshot["bg_offset_x"]))
            self._bg_y_spin.setValue(int(snapshot["bg_offset_y"]))
            self._bg_w_spin.setValue(int(snapshot["bg_width"]))
            self._bg_h_spin.setValue(int(snapshot["bg_height"]))
        finally:
            self._syncing = False

    def _on_overlay_edit_mode_changed(self, enabled: bool) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            self._edit_mode_checkbox.setChecked(enabled)
        finally:
            self._syncing = False

    def _on_stay_on_top_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._overlay.set_stay_on_top(checked)

    def _on_windowed_mode_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._overlay.set_windowed_mode(checked)

    def _on_edit_mode_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._overlay.set_edit_mode(checked)

    def _on_font_size_changed(self, value: int) -> None:
        if self._syncing:
            return
        self._overlay.set_font_size(value)

    def _on_text_box_changed(self, _value: int) -> None:
        if self._syncing:
            return
        self._overlay.set_text_box(
            self._text_x_spin.value(),
            self._text_y_spin.value(),
            self._text_w_spin.value(),
            self._text_h_spin.value(),
        )

    def _on_bg_offset_changed(self, _value: int) -> None:
        if self._syncing:
            return
        self._overlay.set_bg_offset(self._bg_x_spin.value(), self._bg_y_spin.value())

    def _on_bg_size_changed(self, _value: int) -> None:
        if self._syncing:
            return
        self._overlay.set_bg_size(self._bg_w_spin.value(), self._bg_h_spin.value())

    def _save_to_config(self) -> None:
        try:
            overlay_settings = self._overlay.export_runtime_settings()
            updates: dict[str, Any] = {
                key: value for key, value in overlay_settings.items() if key in OVERLAY_PERSIST_KEYS
            }
            if self._model_profile == MODEL_PROFILE_CUSTOM:
                self._custom_profile_snapshot = {
                    "model": self._model,
                    "detector_model": self._detector_model,
                    "vad_model": self._vad_model,
                    "punc_model": self._punc_model,
                    "disable_vad_model": self._disable_vad_model,
                    "disable_punc_model": self._disable_punc_model,
                }
            updates.update(
                {
                    "model_profile": self._model_profile,
                    "model_download_on_startup": self._model_download_on_startup,
                    "model_profile_prompted": True,
                    "model": self._model,
                    "detector_model": self._detector_model,
                    "vad_model": self._vad_model,
                    "punc_model": self._punc_model,
                    "disable_vad_model": self._disable_vad_model,
                    "disable_punc_model": self._disable_punc_model,
                }
            )
            write_config_values(self._config_path, updates)
            self._status_label.setText(f"已保存: {self._config_path}（模型切换需重启生效）")
        except Exception as exc:  # pylint: disable=broad-except
            self._status_label.setText(f"保存失败: {exc}")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self.visibility_changed.emit(False)
