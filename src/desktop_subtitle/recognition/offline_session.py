import logging
import queue
import time
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from .engine import ASRWorker

LOGGER = logging.getLogger("desktop_subtitle")


def run_offline_session(worker: "ASRWorker", model: Any) -> None:
    in_speech = False
    silence_count = 0
    segment_parts: list[np.ndarray] = []
    segment_samples = 0
    chunks_since_partial = 0
    speech_started_at: float | None = None
    last_audio_at: float | None = None

    while not worker.stop_event.is_set():
        try:
            chunk = worker.audio_queue.get(timeout=0.15)
        except queue.Empty:
            continue
        chunk_received_at = time.perf_counter()

        energy = float(np.mean(np.abs(chunk)))
        is_voice = energy >= worker.args.energy_threshold

        if is_voice:
            if not in_speech:
                LOGGER.info("Speech started")
                in_speech = True
                silence_count = 0
                segment_parts = []
                segment_samples = 0
                chunks_since_partial = 0
                speech_started_at = chunk_received_at
                last_audio_at = chunk_received_at

            segment_parts.append(chunk)
            segment_samples += len(chunk)
            chunks_since_partial += 1
            silence_count = 0
            last_audio_at = chunk_received_at

            if chunks_since_partial >= worker.partial_blocks:
                chunks_since_partial = 0
                partial_text, infer_ms = worker._timed_transcribe(model, np.concatenate(segment_parts))
                if partial_text:
                    worker._emit_subtitle(partial_text)
                    worker._log_offline_latency(
                        stage="partial",
                        reason="interval",
                        speech_started_at=speech_started_at,
                        last_audio_at=last_audio_at,
                        segment_samples=segment_samples,
                        infer_ms=infer_ms,
                        chars=len(partial_text),
                    )

            if segment_samples >= worker.max_segment_samples:
                final_text, infer_ms = worker._timed_transcribe(model, np.concatenate(segment_parts))
                if final_text:
                    worker._emit_subtitle(final_text)
                worker._log_offline_latency(
                    stage="final",
                    reason="max-segment-seconds",
                    speech_started_at=speech_started_at,
                    last_audio_at=last_audio_at,
                    segment_samples=segment_samples,
                    infer_ms=infer_ms,
                    chars=len(final_text),
                )
                LOGGER.info("Speech finalized (max-segment-seconds, chars=%d)", len(final_text))
                in_speech = False
                silence_count = 0
                segment_parts = []
                segment_samples = 0
                chunks_since_partial = 0
                speech_started_at = None
                last_audio_at = None

        elif in_speech:
            silence_count += 1
            segment_parts.append(chunk)
            segment_samples += len(chunk)
            last_audio_at = chunk_received_at

            if silence_count >= worker.silence_blocks:
                final_text, infer_ms = worker._timed_transcribe(model, np.concatenate(segment_parts))
                if final_text:
                    worker._emit_subtitle(final_text)
                worker._log_offline_latency(
                    stage="final",
                    reason="silence",
                    speech_started_at=speech_started_at,
                    last_audio_at=last_audio_at,
                    segment_samples=segment_samples,
                    infer_ms=infer_ms,
                    chars=len(final_text),
                )
                LOGGER.info("Speech finalized (silence, chars=%d)", len(final_text))
                in_speech = False
                silence_count = 0
                segment_parts = []
                segment_samples = 0
                chunks_since_partial = 0
                speech_started_at = None
                last_audio_at = None

    if segment_parts:
        final_text, infer_ms = worker._timed_transcribe(model, np.concatenate(segment_parts))
        if final_text:
            worker._emit_subtitle(final_text)
        worker._log_offline_latency(
            stage="flush",
            reason="shutdown",
            speech_started_at=speech_started_at,
            last_audio_at=last_audio_at,
            segment_samples=segment_samples,
            infer_ms=infer_ms,
            chars=len(final_text),
        )
        if final_text:
            LOGGER.info("Speech flushed on shutdown (chars=%d)", len(final_text))
