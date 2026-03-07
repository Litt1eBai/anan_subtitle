import logging
from pathlib import Path

import sounddevice as sd

from recognition.audio_source import build_audio_callback
from core.settings import ensure_valid_image, parse_args
from app.bootstrap import build_application_context, download_selected_model_combo, prompt_model_profile_on_first_run

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
    prompt_model_profile_on_first_run(args, config_path)
    if args.model_download_on_startup:
        download_selected_model_combo(args)

    args.bg_image = ensure_valid_image(args.bg_image, Path(args.config).expanduser())
    LOGGER.info("Starting app with config: %s", config_path)
    LOGGER.info("Model profile: %s (model=%s)", args.model_profile, args.model)
    LOGGER.info("Background image: %s", args.bg_image or "<none>")
    LOGGER.info("Subtitle auto-clear: %dms", args.subtitle_clear_ms)

    context = build_application_context(args, config_path)
    context.worker.start()

    block_size = max(1, int(args.samplerate * args.block_ms / 1000))
    audio_callback = build_audio_callback(context.audio_queue)

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
        context.overlay.show()
        if context.tray_controller is not None:
            context.tray_controller.show()
        if args.show_control_panel:
            context.control_panel.move(context.overlay.x() + context.overlay.width() + 16, context.overlay.y())
            context.control_panel.show()
        LOGGER.info("Overlay window shown")
        return context.qt_app.exec()
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Failed to start audio stream")
        print(f"[ERROR] failed to start audio stream: {exc}")
        return 1
    finally:
        LOGGER.info("Shutting down...")
        context.stop_event.set()
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if context.tray_controller is not None:
            context.tray_controller.hide()
        context.worker.join(timeout=2.0)
        LOGGER.info("Worker stopped")
