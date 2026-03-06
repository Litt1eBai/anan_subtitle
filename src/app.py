import logging
import queue
import sys
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from funasr import AutoModel
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from asr import ASRWorker
from audio import build_audio_callback
from config import (
    apply_model_profile_to_args,
    ensure_valid_image,
    parse_args,
    write_config_values,
)
from constants import (
    MODEL_PROFILE_CUSTOM,
    MODEL_PROFILE_HYBRID,
    MODEL_PROFILE_OFFLINE,
    MODEL_PROFILE_PRESETS,
    MODEL_PROFILE_REALTIME,
)
from presentation import SubtitlePresentationController
from signals import AppSignals
from ui import OverlayControlPanel, SubtitleOverlay, TrayController

LOGGER = logging.getLogger("desktop_subtitle")


def _build_model_download_kwargs_list(args) -> list[dict[str, object]]:
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


def _download_selected_model_combo(args) -> None:
    downloads = _build_model_download_kwargs_list(args)
    start = time.perf_counter()
    LOGGER.info("Pre-downloading model combo (profile=%s)", args.model_profile)
    for kwargs in downloads:
        model_name = kwargs.get("model", "<unknown>")
        try:
            LOGGER.info("Downloading model: %s", model_name)
            AutoModel(**kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("Model pre-download failed")
            LOGGER.warning("Model pre-download skipped (%s): %s", model_name, exc)
            return
    elapsed = time.perf_counter() - start
    LOGGER.info("Model combo is ready (elapsed=%.1fs)", elapsed)


def _prompt_model_profile_on_first_run(args, config_path: Path) -> None:
    if not getattr(args, "model_profile_prompt_on_first_run", False) or getattr(
        args, "model_profile_prompted", False
    ):
        return
    if not sys.stdin.isatty():
        LOGGER.info("First-run model profile prompt skipped (non-interactive terminal)")
        return

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

    args.model_profile = selected
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

    if args.model_profile != MODEL_PROFILE_CUSTOM:
        print("是否立即下载所选模型？建议首次选择 yes。")
        download_answer = input("立即下载 [Y/n]: ").strip().lower()
        if download_answer in {"", "y", "yes"}:
            _download_selected_model_combo(args)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        args = parse_args()
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2
    config_path = Path(args.config).expanduser().resolve()
    _prompt_model_profile_on_first_run(args, config_path)
    if args.model_download_on_startup:
        _download_selected_model_combo(args)

    args.bg_image = ensure_valid_image(args.bg_image, Path(args.config).expanduser())
    LOGGER.info("Starting app with config: %s", config_path)
    LOGGER.info("Model profile: %s (model=%s)", args.model_profile, args.model)
    LOGGER.info("Background image: %s", args.bg_image or "<none>")
    LOGGER.info("Subtitle auto-clear: %dms", args.subtitle_clear_ms)

    app = QApplication(sys.argv)
    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    if args.tray_icon_enable and tray_available:
        app.setQuitOnLastWindowClosed(False)

    overlay = SubtitleOverlay(args)
    control_panel = OverlayControlPanel(overlay, config_path, args)
    tray_controller = None
    if args.tray_icon_enable:
        if tray_available:
            tray_controller = TrayController(
                app=app,
                overlay=overlay,
                control_panel=control_panel,
                config_path=config_path,
                icon_path=args.bg_image,
            )
        else:
            LOGGER.warning("System tray is unavailable on this platform; tray icon disabled.")

    signals = AppSignals()
    stop_event = threading.Event()
    audio_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=args.queue_size)

    presentation_controller = SubtitlePresentationController(overlay)
    signals.subtitle.connect(presentation_controller.handle_subtitle)
    signals.status.connect(presentation_controller.handle_status)
    signals.error.connect(presentation_controller.handle_error)
    signals.status.emit("模型加载中...")

    worker = ASRWorker(args, audio_queue, signals, stop_event)
    worker.start()

    block_size = max(1, int(args.samplerate * args.block_ms / 1000))
    audio_callback = build_audio_callback(audio_queue)

    stream = None
    try:
        stream = sd.InputStream(
            samplerate=args.samplerate,
            channels=1,
            dtype="float32",
            callback=audio_callback,
            blocksize=block_size,
            device=args.device,
        )
        stream.start()
        LOGGER.info(
            "Audio input stream started (samplerate=%d, block_ms=%d)",
            args.samplerate,
            args.block_ms,
        )
        overlay.show()
        if tray_controller is not None:
            tray_controller.show()
        if args.show_control_panel:
            control_panel.move(overlay.x() + overlay.width() + 16, overlay.y())
            control_panel.show()
        LOGGER.info("Overlay window shown")
        code = app.exec()
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Failed to start audio stream")
        print(f"[ERROR] failed to start audio stream: {exc}")
        code = 1
    finally:
        LOGGER.info("Shutting down...")
        stop_event.set()
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if tray_controller is not None:
            tray_controller.hide()
        worker.join(timeout=2.0)
        LOGGER.info("Worker stopped")

    return code
