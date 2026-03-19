import logging
import queue
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from funasr import AutoModel
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QRadioButton,
    QSystemTrayIcon,
    QVBoxLayout,
)

from core.model_download import ensure_model_download_ready
from core.runtime_env import apply_runtime_environment, configure_logging
from core.settings import (
    MODEL_PROFILE_PRESETS,
    STORAGE_LOCATION_APP,
    STORAGE_LOCATION_CUSTOM,
    STORAGE_LOCATION_USER,
    apply_model_profile_to_args,
    apply_storage_paths_to_args,
    resolve_data_dir,
    resolve_log_dir,
    write_config_values,
)
from core.models import (
    MODEL_PROFILE_CUSTOM,
    MODEL_PROFILE_HYBRID,
    MODEL_PROFILE_OFFLINE,
    MODEL_PROFILE_REALTIME,
)
from presentation import SubtitlePresentationController
from presentation.qt import OverlayControlPanel, SubtitleOverlay, TrayController
from recognition.engine import ASRWorker


class AppSignals(QObject):
    subtitle = Signal(str)
    status = Signal(str)
    error = Signal(str)


LOGGER = logging.getLogger("desktop_subtitle")


@dataclass
class ApplicationContext:
    qt_app: QApplication
    overlay: SubtitleOverlay
    control_panel: OverlayControlPanel
    tray_controller: TrayController | None
    signals: AppSignals
    stop_event: threading.Event
    audio_queue: queue.Queue[np.ndarray]
    presentation_controller: SubtitlePresentationController
    worker: ASRWorker


def build_model_download_kwargs_list(args: Any) -> list[dict[str, object]]:
    downloads: list[dict[str, object]] = []
    if getattr(args, "model_profile", "") == MODEL_PROFILE_HYBRID:
        downloads.append({"model": args.detector_model, "disable_update": True})

    kwargs: dict[str, object] = {"model": args.model, "disable_update": True}
    if "streaming" not in str(args.model):
        if not args.disable_vad_model:
            kwargs["vad_model"] = args.vad_model
        if not args.disable_punc_model:
            kwargs["punc_model"] = args.punc_model
    downloads.append(kwargs)
    return downloads


def download_selected_model_combo(args: Any) -> tuple[bool, str]:
    downloads = build_model_download_kwargs_list(args)
    start = time.perf_counter()
    LOGGER.info("Pre-downloading model combo (profile=%s, data_dir=%s)", args.model_profile, getattr(args, "data_dir", ""))
    for kwargs in downloads:
        model_name = str(kwargs.get("model", "<unknown>"))
        prepared_kwargs: dict[str, object] | None = None
        try:
            LOGGER.info("Downloading model: %s", model_name)
            prepared_kwargs = ensure_model_download_ready(
                kwargs,
                modelscope_cache_dir=getattr(args, "modelscope_cache_dir", None),
            )
            AutoModel(**prepared_kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            detail = f"{model_name}: {exc}"
            if prepared_kwargs and prepared_kwargs.get("model_path"):
                detail += f" (model_path={prepared_kwargs.get('model_path')})"
            LOGGER.exception("Model pre-download failed")
            LOGGER.warning("Model pre-download skipped (%s): %s", model_name, exc)
            return False, detail
    elapsed = time.perf_counter() - start
    LOGGER.info("Model combo is ready (elapsed=%.1fs)", elapsed)
    return True, f"模型下载完成（{elapsed:.1f}s）"


def persist_storage_preferences(
    args: Any,
    config_path: Path,
    *,
    data_dir_location: str,
    data_dir_custom: str,
    log_dir_location: str,
    log_dir_custom: str,
) -> None:
    args.data_dir_location = data_dir_location
    args.data_dir_custom = data_dir_custom
    args.log_dir_location = log_dir_location
    args.log_dir_custom = log_dir_custom
    apply_storage_paths_to_args(args)
    write_config_values(
        config_path,
        {
            "data_dir_location": args.data_dir_location,
            "data_dir_custom": args.data_dir_custom,
            "log_dir_location": args.log_dir_location,
            "log_dir_custom": args.log_dir_custom,
        },
    )


def persist_model_profile_selection(args: Any, config_path: Path, selected_profile: str) -> None:
    args.model_profile = selected_profile
    args.model_profile_prompted = True
    apply_model_profile_to_args(args)
    write_config_values(
        config_path,
        {
            "model_profile": args.model_profile,
            "model_profile_prompted": True,
            "model": args.model,
            "detector_model": args.detector_model,
            "vad_model": args.vad_model,
            "punc_model": args.punc_model,
            "disable_vad_model": args.disable_vad_model,
            "disable_punc_model": args.disable_punc_model,
        },
    )
    LOGGER.info("Model profile selected: %s (saved to %s)", args.model_profile, config_path)


def prompt_model_profile_on_first_run_terminal(args: Any, config_path: Path) -> bool:
    current_profile = str(args.model_profile)
    realtime_model = MODEL_PROFILE_PRESETS[MODEL_PROFILE_REALTIME]["model"]
    offline_model = MODEL_PROFILE_PRESETS[MODEL_PROFILE_OFFLINE]["model"]
    hybrid_model = MODEL_PROFILE_PRESETS[MODEL_PROFILE_HYBRID]["model"]
    hybrid_detector = MODEL_PROFILE_PRESETS[MODEL_PROFILE_HYBRID]["detector_model"]
    print("\n[首次启动] 请选择模型组合:")
    print(f"  1) 实时（低延迟）      model={realtime_model}")
    print(f"  2) 非实时（准确率优先） model={offline_model}")
    print(f"  3) 混合（流式起句+离线整句） detector={hybrid_detector}, model={hybrid_model}")
    print(f"  回车默认：{current_profile}")
    answer = input("请输入 1 / 2 / 3: ").strip()

    selected = current_profile
    if answer == "1":
        selected = MODEL_PROFILE_REALTIME
    elif answer == "2":
        selected = MODEL_PROFILE_OFFLINE
    elif answer == "3":
        selected = MODEL_PROFILE_HYBRID

    persist_model_profile_selection(args, config_path, selected)

    if args.model_profile != MODEL_PROFILE_CUSTOM:
        print("是否立即下载所选模型？建议首次选择 yes。")
        download_answer = input("立即下载 [Y/n]: ").strip().lower()
        if download_answer in {"", "y", "yes"}:
            ok, detail = download_selected_model_combo(args)
            if not ok:
                print(f"[WARN] 模型下载失败: {detail}")
                if getattr(args, "log_file", ""):
                    print(f"[WARN] 日志文件: {args.log_file}")
    return True


def _build_storage_location_combo(current_value: str) -> QComboBox:
    combo = QComboBox()
    combo.addItem("软件目录", STORAGE_LOCATION_APP)
    combo.addItem("用户目录", STORAGE_LOCATION_USER)
    combo.addItem("自定义", STORAGE_LOCATION_CUSTOM)
    index = combo.findData(current_value)
    combo.setCurrentIndex(index if index >= 0 else combo.findData(STORAGE_LOCATION_USER))
    return combo


def prompt_model_profile_on_first_run_gui(args: Any, config_path: Path) -> bool:
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)

    dialog = QDialog()
    dialog.setWindowTitle("首次启动设置")
    dialog.setModal(True)
    dialog.resize(560, 420)

    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("首次启动需要选择识别模式。建议保持默认的实时模式。"))
    layout.addWidget(QLabel("你也可以在这里决定模型缓存和日志写到哪里。"))

    options = {
        MODEL_PROFILE_REALTIME: QRadioButton(
            f"实时（低延迟）  model={MODEL_PROFILE_PRESETS[MODEL_PROFILE_REALTIME]['model']}"
        ),
        MODEL_PROFILE_OFFLINE: QRadioButton(
            f"非实时（准确率优先）  model={MODEL_PROFILE_PRESETS[MODEL_PROFILE_OFFLINE]['model']}"
        ),
        MODEL_PROFILE_HYBRID: QRadioButton(
            "混合（流式起句+离线整句）  "
            f"detector={MODEL_PROFILE_PRESETS[MODEL_PROFILE_HYBRID]['detector_model']}, "
            f"model={MODEL_PROFILE_PRESETS[MODEL_PROFILE_HYBRID]['model']}"
        ),
    }
    selected_profile = str(getattr(args, "model_profile", MODEL_PROFILE_REALTIME))
    if selected_profile not in options:
        selected_profile = MODEL_PROFILE_REALTIME
    options[selected_profile].setChecked(True)
    for button in options.values():
        layout.addWidget(button)

    download_checkbox = QCheckBox("立即下载所选模型（推荐）")
    download_checkbox.setChecked(True)
    layout.addWidget(download_checkbox)

    storage_form = QFormLayout()
    data_location_combo = _build_storage_location_combo(str(getattr(args, "data_dir_location", STORAGE_LOCATION_USER)))
    data_custom_edit = QLineEdit(str(getattr(args, "data_dir_custom", "")))
    log_location_combo = _build_storage_location_combo(str(getattr(args, "log_dir_location", STORAGE_LOCATION_USER)))
    log_custom_edit = QLineEdit(str(getattr(args, "log_dir_custom", "")))
    storage_form.addRow("数据目录", data_location_combo)
    storage_form.addRow("数据自定义路径", data_custom_edit)
    storage_form.addRow("日志目录", log_location_combo)
    storage_form.addRow("日志自定义路径", log_custom_edit)
    layout.addLayout(storage_form)

    storage_summary = QLabel("")
    storage_summary.setWordWrap(True)
    layout.addWidget(storage_summary)

    def refresh_storage_summary() -> None:
        data_location = str(data_location_combo.currentData())
        log_location = str(log_location_combo.currentData())
        data_custom = data_custom_edit.text().strip()
        log_custom = log_custom_edit.text().strip()
        data_custom_edit.setEnabled(data_location == STORAGE_LOCATION_CUSTOM)
        log_custom_edit.setEnabled(log_location == STORAGE_LOCATION_CUSTOM)
        storage_summary.setText(
            "数据目录: "
            f"{resolve_data_dir(data_location, data_custom)}\n"
            "日志目录: "
            f"{resolve_log_dir(log_location, log_custom)}"
        )

    data_location_combo.currentIndexChanged.connect(lambda _i: refresh_storage_summary())
    log_location_combo.currentIndexChanged.connect(lambda _i: refresh_storage_summary())
    data_custom_edit.textChanged.connect(lambda _t: refresh_storage_summary())
    log_custom_edit.textChanged.connect(lambda _t: refresh_storage_summary())
    refresh_storage_summary()

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        LOGGER.info("First-run model profile prompt cancelled")
        return False

    persist_storage_preferences(
        args,
        config_path,
        data_dir_location=str(data_location_combo.currentData()),
        data_dir_custom=data_custom_edit.text().strip(),
        log_dir_location=str(log_location_combo.currentData()),
        log_dir_custom=log_custom_edit.text().strip(),
    )
    try:
        apply_runtime_environment(args)
        args.log_file = str(configure_logging(args.log_dir))
    except Exception as exc:  # pylint: disable=broad-except
        QMessageBox.critical(dialog, "目录初始化失败", f"无法准备数据或日志目录：{exc}")
        return False

    chosen = next(profile for profile, button in options.items() if button.isChecked())
    persist_model_profile_selection(args, config_path, chosen)

    if download_checkbox.isChecked():
        progress = QProgressDialog("正在下载所选模型，请稍候...", None, 0, 0, dialog)
        progress.setWindowTitle("初始化模型")
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        qt_app.processEvents()
        downloaded, detail = download_selected_model_combo(args)
        progress.close()
        qt_app.processEvents()
        if not downloaded:
            QMessageBox.warning(
                dialog,
                "模型下载失败",
                "所选模型未能预下载完成。\n\n"
                f"原因: {detail}\n"
                f"日志: {getattr(args, 'log_file', '')}\n\n"
                "你可以稍后在设置面板中重新下载，或检查网络和目录权限后重试。",
            )

    return True


def prompt_model_profile_on_first_run(args: Any, config_path: Path) -> bool:
    if not getattr(args, "model_profile_prompt_on_first_run", False) or getattr(
        args, "model_profile_prompted", False
    ):
        return True

    stdin = getattr(sys, "stdin", None)
    if stdin is not None and getattr(stdin, "isatty", lambda: False)():
        return prompt_model_profile_on_first_run_terminal(args, config_path)

    LOGGER.info("First-run model profile prompt using GUI flow")
    return prompt_model_profile_on_first_run_gui(args, config_path)


def build_application_context(args: Any, config_path: Path) -> ApplicationContext:
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)
    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    if args.tray_icon_enable and tray_available:
        qt_app.setQuitOnLastWindowClosed(False)

    overlay = SubtitleOverlay(args)
    control_panel = OverlayControlPanel(overlay, config_path, args)
    tray_controller = None
    if args.tray_icon_enable:
        if tray_available:
            tray_controller = TrayController(
                app=qt_app,
                overlay=overlay,
                control_panel=control_panel,
                config_path=config_path,
                icon_path=args.bg_image,
            )
        else:
            LOGGER.warning("System tray is unavailable on this platform; tray icon disabled.")

    signals = AppSignals()
    stop_event = threading.Event()
    audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=args.queue_size)
    presentation_controller = SubtitlePresentationController(overlay)
    signals.subtitle.connect(presentation_controller.handle_subtitle)
    signals.status.connect(presentation_controller.handle_status)
    signals.error.connect(presentation_controller.handle_error)
    signals.status.emit("模型加载中...")

    worker = ASRWorker(args, audio_queue, signals, stop_event)
    return ApplicationContext(
        qt_app=qt_app,
        overlay=overlay,
        control_panel=control_panel,
        tray_controller=tray_controller,
        signals=signals,
        stop_event=stop_event,
        audio_queue=audio_queue,
        presentation_controller=presentation_controller,
        worker=worker,
    )
