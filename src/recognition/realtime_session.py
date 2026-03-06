from collections import deque
import logging
import queue
import time
from typing import TYPE_CHECKING, Any

import numpy as np

from core.subtitle_pipeline import merge_incremental_text

if TYPE_CHECKING:
    from recognition.engine import ASRWorker

LOGGER = logging.getLogger("desktop_subtitle")


def run_hybrid_session(worker: "ASRWorker", detector_model: Any, offline_model: Any) -> None:
    detector_cache: dict[str, Any] = {}
    detector_pending = np.empty(0, dtype=np.float32)
    preroll_chunks: deque[np.ndarray] = deque(maxlen=max(1, int(300 / max(1, worker.args.block_ms))))
    in_speech = False
    silence_count = 0
    segment_parts: list[np.ndarray] = []
    segment_samples = 0
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
        detector_pending = np.concatenate((detector_pending, chunk.astype(np.float32, copy=False)))

        detector_triggered = False
        while detector_pending.size >= worker.chunk_stride_samples:
            speech_chunk = detector_pending[: worker.chunk_stride_samples]
            detector_pending = detector_pending[worker.chunk_stride_samples :]
            detector_text = worker._transcribe_streaming(
                detector_model,
                speech_chunk,
                detector_cache,
                is_final=False,
            )
            if detector_text:
                detector_triggered = True

        if detector_triggered and not in_speech:
            in_speech = True
            silence_count = 0
            segment_parts = list(preroll_chunks)
            segment_samples = sum(len(part) for part in segment_parts)
            speech_started_at = chunk_received_at
            last_audio_at = chunk_received_at
            LOGGER.info("Speech started (hybrid detector)")

        if in_speech:
            segment_parts.append(chunk)
            segment_samples += len(chunk)
            if is_voice:
                silence_count = 0
            else:
                silence_count += 1
            last_audio_at = chunk_received_at
        else:
            preroll_chunks.append(chunk)

        if in_speech and (
            silence_count >= worker.silence_blocks or segment_samples >= worker.max_segment_samples
        ):
            final_text, infer_ms = worker._timed_transcribe(offline_model, np.concatenate(segment_parts))
            if final_text:
                worker._emit_subtitle(final_text)
            end_reason = "silence" if silence_count >= worker.silence_blocks else "max-segment-seconds"
            worker._log_offline_latency(
                stage="final",
                reason=f"hybrid-{end_reason}",
                speech_started_at=speech_started_at,
                last_audio_at=last_audio_at,
                segment_samples=segment_samples,
                infer_ms=infer_ms,
                chars=len(final_text),
            )
            LOGGER.info("Speech finalized (%s, chars=%d)", end_reason, len(final_text))
            detector_pending = np.empty(0, dtype=np.float32)
            detector_cache.clear()
            in_speech = False
            silence_count = 0
            segment_parts = []
            segment_samples = 0
            speech_started_at = None
            last_audio_at = None
            preroll_chunks.clear()

    if segment_parts:
        final_text, infer_ms = worker._timed_transcribe(offline_model, np.concatenate(segment_parts))
        if final_text:
            worker._emit_subtitle(final_text)
        worker._log_offline_latency(
            stage="flush",
            reason="hybrid-shutdown",
            speech_started_at=speech_started_at,
            last_audio_at=last_audio_at,
            segment_samples=segment_samples,
            infer_ms=infer_ms,
            chars=len(final_text),
        )
        if final_text:
            LOGGER.info("Speech flushed on shutdown (chars=%d)", len(final_text))


def run_streaming_session(worker: "ASRWorker", model: Any) -> None:
    cache: dict[str, Any] = {}
    pending = np.empty(0, dtype=np.float32)
    in_speech = False
    silence_count = 0
    segment_samples = 0
    current_text = ""

    while not worker.stop_event.is_set():
        try:
            chunk = worker.audio_queue.get(timeout=0.15)
        except queue.Empty:
            continue

        energy = float(np.mean(np.abs(chunk)))
        is_voice = energy >= worker.args.energy_threshold
        if is_voice:
            if not in_speech:
                LOGGER.info("Speech started")
            in_speech = True
            silence_count = 0
        elif in_speech:
            silence_count += 1

        pending = np.concatenate((pending, chunk.astype(np.float32, copy=False)))
        if in_speech:
            segment_samples += len(chunk)

        while pending.size >= worker.chunk_stride_samples:
            speech_chunk = pending[: worker.chunk_stride_samples]
            pending = pending[worker.chunk_stride_samples :]
            text = worker._transcribe_streaming(model, speech_chunk, cache, is_final=False)
            if text:
                if not in_speech:
                    in_speech = True
                    silence_count = 0
                current_text = merge_incremental_text(current_text, text)
                worker._emit_subtitle(current_text)

        if in_speech and (
            silence_count >= worker.silence_blocks or segment_samples >= worker.max_segment_samples
        ):
            final_text = worker._transcribe_streaming(model, pending, cache, is_final=True)
            if final_text:
                current_text = merge_incremental_text(current_text, final_text)
            if current_text:
                worker._emit_subtitle(current_text)
            end_reason = "silence" if silence_count >= worker.silence_blocks else "max-segment-seconds"
            LOGGER.info("Speech finalized (%s, chars=%d)", end_reason, len(current_text))
            pending = np.empty(0, dtype=np.float32)
            current_text = ""
            in_speech = False
            silence_count = 0
            segment_samples = 0

    while True:
        try:
            tail = worker.audio_queue.get_nowait()
            pending = np.concatenate((pending, tail.astype(np.float32, copy=False)))
        except queue.Empty:
            break

    if pending.size > 0 or current_text:
        final_text = worker._transcribe_streaming(model, pending, cache, is_final=True)
        if final_text:
            current_text = merge_incremental_text(current_text, final_text)
        if current_text:
            worker._emit_subtitle(current_text)
            LOGGER.info("Speech flushed on shutdown (chars=%d)", len(current_text))
