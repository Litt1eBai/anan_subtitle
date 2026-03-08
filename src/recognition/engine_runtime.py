from collections import deque
from dataclasses import dataclass, field
import logging
import time
from typing import Any, Protocol

import numpy as np

from core.text_postprocess import extract_text, replace_sentence_initial_wo


LOGGER = logging.getLogger("desktop_subtitle")


class SignalChannel(Protocol):
    def emit(self, value: str) -> None: ...


class WorkerSignals(Protocol):
    subtitle: SignalChannel
    status: SignalChannel
    error: SignalChannel


@dataclass
class OfflineLatencyTracker:
    report_every: int = 5
    final_count: int = 0
    final_tail_ms: deque[float] = field(default_factory=lambda: deque(maxlen=200))
    final_total_ms: deque[float] = field(default_factory=lambda: deque(maxlen=200))
    final_lag_ms: deque[float] = field(default_factory=lambda: deque(maxlen=200))

    @staticmethod
    def percentile(values: list[float], ratio: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = int(round((len(ordered) - 1) * ratio))
        index = max(0, min(index, len(ordered) - 1))
        return ordered[index]

    def log(
        self,
        *,
        stage: str,
        reason: str,
        speech_started_at: float | None,
        last_audio_at: float | None,
        segment_samples: int,
        infer_ms: float,
        chars: int,
        samplerate: int,
    ) -> None:
        now = time.perf_counter()
        total_ms = (now - speech_started_at) * 1000.0 if speech_started_at is not None else None
        tail_ms = (now - last_audio_at) * 1000.0 if last_audio_at is not None else None
        audio_ms = segment_samples * 1000.0 / max(1, int(samplerate))
        lag_ms = max(0.0, total_ms - audio_ms) if total_ms is not None else None
        rtf = infer_ms / max(1.0, audio_ms)
        total_text = "n/a" if total_ms is None else f"{total_ms:.0f}ms"
        tail_text = "n/a" if tail_ms is None else f"{tail_ms:.0f}ms"
        lag_text = "n/a" if lag_ms is None else f"{lag_ms:.0f}ms"
        LOGGER.info(
            "Offline latency (%s/%s): total=%s lag=%s tail=%s infer=%.0fms audio=%.0fms rtf=%.2f chars=%d",
            stage,
            reason,
            total_text,
            lag_text,
            tail_text,
            infer_ms,
            audio_ms,
            rtf,
            chars,
        )
        if stage != "final" or total_ms is None or tail_ms is None:
            return

        self.final_count += 1
        self.final_total_ms.append(total_ms)
        self.final_tail_ms.append(tail_ms)
        if lag_ms is not None:
            self.final_lag_ms.append(lag_ms)
        if self.final_count % self.report_every != 0:
            return

        avg_total = sum(self.final_total_ms) / len(self.final_total_ms)
        avg_lag = sum(self.final_lag_ms) / len(self.final_lag_ms) if self.final_lag_ms else 0.0
        avg_tail = sum(self.final_tail_ms) / len(self.final_tail_ms)
        p95_tail = self.percentile(list(self.final_tail_ms), 0.95)
        LOGGER.info(
            "Offline latency summary: finals=%d avg_total=%.0fms avg_lag=%.0fms avg_tail=%.0fms p95_tail=%.0fms",
            self.final_count,
            avg_total,
            avg_lag,
            avg_tail,
            p95_tail,
        )


def emit_subtitle(signals: WorkerSignals, text: str) -> None:
    converted = replace_sentence_initial_wo(text.strip())
    if converted:
        signals.subtitle.emit(converted)


def transcribe_offline(
    model: Any,
    audio: np.ndarray,
    *,
    samplerate: int,
    error_signal: SignalChannel,
) -> str:
    if audio.size == 0:
        return ""
    try:
        result = model.generate(input=audio, batch_size_s=60, fs=samplerate)
    except TypeError:
        result = model.generate(input=audio, fs=samplerate)
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("ASR failed (offline)")
        error_signal.emit(f"ASR failed: {exc}")
        return ""
    return extract_text(result)


def transcribe_streaming(
    model: Any,
    audio: np.ndarray,
    cache: dict[str, Any],
    *,
    is_final: bool,
    samplerate: int,
    chunk_size: list[int],
    encoder_chunk_look_back: int,
    decoder_chunk_look_back: int,
    error_signal: SignalChannel,
) -> str:
    try:
        result = model.generate(
            input=audio,
            cache=cache,
            is_final=is_final,
            fs=samplerate,
            chunk_size=chunk_size,
            encoder_chunk_look_back=encoder_chunk_look_back,
            decoder_chunk_look_back=decoder_chunk_look_back,
        )
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("ASR failed (streaming)")
        error_signal.emit(f"ASR failed: {exc}")
        return ""
    return extract_text(result)


def timed_transcribe_offline(
    model: Any,
    audio: np.ndarray,
    *,
    samplerate: int,
    error_signal: SignalChannel,
) -> tuple[str, float]:
    begin = time.perf_counter()
    text = transcribe_offline(model, audio, samplerate=samplerate, error_signal=error_signal)
    elapsed_ms = (time.perf_counter() - begin) * 1000.0
    return text, elapsed_ms
