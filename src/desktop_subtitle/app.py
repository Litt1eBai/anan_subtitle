import logging
import queue
import sys
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .asr import ASRWorker
from .audio import build_audio_callback
from .config import ensure_valid_image, parse_args
from .signals import AppSignals
from .ui import OverlayControlPanel, SubtitleOverlay, TrayController

LOGGER = logging.getLogger("desktop_subtitle")

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
    args.bg_image = ensure_valid_image(args.bg_image, Path(args.config).expanduser())
    LOGGER.info("Starting app with config: %s", config_path)
    LOGGER.info("Background image: %s", args.bg_image or "<none>")
    LOGGER.info("Subtitle auto-clear: %dms", args.subtitle_clear_ms)

    app = QApplication(sys.argv)
    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    if args.tray_icon_enable and tray_available:
        app.setQuitOnLastWindowClosed(False)

    overlay = SubtitleOverlay(args)
    control_panel = OverlayControlPanel(overlay, config_path)
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

    signals.subtitle.connect(overlay.set_subtitle)
    signals.status.connect(overlay.set_status)

    def on_error(msg: str) -> None:
        LOGGER.error(msg)
        overlay.set_status(f"[ERROR] {msg}")
        overlay.clear_subtitle()

    signals.error.connect(on_error)
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
        LOGGER.info("Audio input stream started (samplerate=%d, block_ms=%d)", args.samplerate, args.block_ms)
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
