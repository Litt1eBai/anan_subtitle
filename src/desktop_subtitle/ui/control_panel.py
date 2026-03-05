from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
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

from ..config import write_overlay_settings_to_config
from .overlay import SubtitleOverlay

class OverlayControlPanel(QWidget):
    visibility_changed = Signal(bool)

    def __init__(self, overlay: SubtitleOverlay, config_path: Path) -> None:
        super().__init__()
        self._overlay = overlay
        self._config_path = config_path
        self._syncing = False
        self.setWindowTitle("Subtitle Settings")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self._build_ui()
        self._connect_signals()
        self._sync_from_overlay()

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
            write_overlay_settings_to_config(self._config_path, self._overlay.export_runtime_settings())
            self._status_label.setText(f"已保存: {self._config_path}")
        except Exception as exc:  # pylint: disable=broad-except
            self._status_label.setText(f"保存失败: {exc}")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self.visibility_changed.emit(False)
