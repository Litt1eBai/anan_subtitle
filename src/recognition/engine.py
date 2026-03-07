from dataclasses import dataclass
import argparse
from collections import deque
import logging
import queue
import threading
import time
from typing import Any, Protocol

import numpy as np

from core.models import MODEL_PROFILE_HYBRID
from core.text_postprocess import extract_text, replace_sentence_initial_wo
from recognition.offline_session import run_offline_session
from recognition.realtime_session import run_hybrid_session, run_streaming_session


class SignalChannel(Protocol):
    def emit(self, value: str) -> None: ...


class WorkerSignals(Protocol):
    subtitle: SignalChannel
    status: SignalChannel
    error: SignalChannel


@dataclass(frozen=True)
class LoadedRecognitionModels:
    primary_model: Any | None = None
    detector_model: Any | None = None


LOGGER = logging.getLogger("desktop_subtitle")


def resolve_worker_mode(args: argparse.Namespace) -> str:
    model_profile = str(getattr(args, "model_profile", "")).strip().lower()
    if model_profile == MODEL_PROFILE_HYBRID:
        return "hybrid"
    if "streaming" in str(args.model):
        return "streaming"
    return "offline"


def build_offline_model_kwargs(args: argparse.Namespace, model_name: str) -> dict[str, Any]:
    model_kwargs: dict[str, Any] = {
        "model": model_name,
        "disable_update": True,
    }
    if not args.disable_vad_model:
        model_kwargs["vad_model"] = args.vad_model
    if not args.disable_punc_model:
        model_kwargs["punc_model"] = args.punc_model
    return model_kwargs


def load_models_for_worker(worker: "ASRWorker") -> LoadedRecognitionModels:
    if worker.use_hybrid:
        return LoadedRecognitionModels(
            primary_model=worker._load_offline_model(worker.args.model),
            detector_model=worker._load_streaming_model(worker.detector_model_name),
        )
    if worker.use_streaming:
        return LoadedRecognitionModels(primary_model=worker._load_streaming_model(worker.args.model))
    return LoadedRecognitionModels(primary_model=worker._load_offline_model(worker.args.model))


def run_worker_loop(worker: "ASRWorker", loaded_models: LoadedRecognitionModels) -> None:
    if worker.use_hybrid:
        LOGGER.info("Hybrid ASR loop running")
        run_hybrid_session(worker, loaded_models.detector_model, loaded_models.primary_model)
        LOGGER.info("Hybrid ASR loop stopped")
        return
    if worker.use_streaming:
        LOGGER.info("Streaming ASR loop running")
        run_streaming_session(worker, loaded_models.primary_model)
        LOGGER.info("Streaming ASR loop stopped")
        return
    LOGGER.info(
        "Offline latency probe enabled (summary every %d finalized segments)",
        worker._offline_report_every,
    )
    LOGGER.info("Offline ASR loop running")
    run_offline_session(worker, loaded_models.primary_model)
    LOGGER.info("Offline ASR loop stopped")


class ASRWorker(threading.Thread):
    def __init__(
        self,
        args: argparse.Namespace,
        audio_queue: "queue.Queue[np.ndarray]",
        signals: WorkerSignals,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self.args = args
        self.audio_queue = audio_queue
        self.signals = signals
        self.stop_event = stop_event
        self.mode = resolve_worker_mode(args)
        self.use_hybrid = self.mode == "hybrid"
        self.use_streaming = self.mode == "streaming"
        self.detector_model_name = str(getattr(args, "detector_model", "paraformer-zh-streaming"))
        self.silence_blocks = max(1, int(args.silence_ms / args.block_ms))
        self.partial_blocks = max(1, int(args.partial_interval_ms / args.block_ms))
        self.max_segment_samples = int(args.max_segment_seconds * args.samplerate)
        self.chunk_size = args.chunk_size
        self.encoder_chunk_look_back = args.encoder_chunk_look_back
        self.decoder_chunk_look_back = args.decoder_chunk_look_back
        self.chunk_stride_samples = max(1, int(self.args.samplerate * self.chunk_size[1] * 0.06))
        self._offline_report_every = 5
        self._offline_final_count = 0
        self._offline_final_tail_ms: deque[float] = deque(maxlen=200)
        self._offline_final_total_ms: deque[float] = deque(maxlen=200)
        self._offline_final_lag_ms: deque[float] = deque(maxlen=200)

    def _emit_subtitle(self, text: str) -> None:
        converted = replace_sentence_initial_wo(text.strip())
        if converted:
            self.signals.subtitle.emit(converted)

    def _load_streaming_model(self, model_name: str) -> Any:
        from funasr import AutoModel

        return AutoModel(model=model_name, disable_update=True)

    def _load_offline_model(self, model_name: str) -> Any:
        from funasr import AutoModel

        return AutoModel(**build_offline_model_kwargs(self.args, model_name))

    def _transcribe(self, model: Any, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        try:
            result = model.generate(input=audio, batch_size_s=60, fs=self.args.samplerate)
        except TypeError:
            result = model.generate(input=audio, fs=self.args.samplerate)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("ASR failed (offline)")
            self.signals.error.emit(f"ASR failed: {exc}")
            return ""
        return extract_text(result)

    def _transcribe_streaming(
        self, model: Any, audio: np.ndarray, cache: dict[str, Any], is_final: bool
    ) -> str:
        try:
            result = model.generate(
                input=audio,
                cache=cache,
                is_final=is_final,
                fs=self.args.samplerate,
                chunk_size=self.chunk_size,
                encoder_chunk_look_back=self.encoder_chunk_look_back,
                decoder_chunk_look_back=self.decoder_chunk_look_back,
            )
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("ASR failed (streaming)")
            self.signals.error.emit(f"ASR failed: {exc}")
            return ""
        return extract_text(result)

    def _timed_transcribe(self, model: Any, audio: np.ndarray) -> tuple[str, float]:
        begin = time.perf_counter()
        text = self._transcribe(model, audio)
        elapsed_ms = (time.perf_counter() - begin) * 1000.0
        return text, elapsed_ms

    @staticmethod
    def _percentile(values: list[float], ratio: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = int(round((len(ordered) - 1) * ratio))
        index = max(0, min(index, len(ordered) - 1))
        return ordered[index]

    def _log_offline_latency(
        self,
        stage: str,
        reason: str,
        speech_started_at: float | None,
        last_audio_at: float | None,
        segment_samples: int,
        infer_ms: float,
        chars: int,
    ) -> None:
        now = time.perf_counter()
        total_ms = (now - speech_started_at) * 1000.0 if speech_started_at is not None else None
        tail_ms = (now - last_audio_at) * 1000.0 if last_audio_at is not None else None
        audio_ms = segment_samples * 1000.0 / max(1, int(self.args.samplerate))
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

        self._offline_final_count += 1
        self._offline_final_total_ms.append(total_ms)
        self._offline_final_tail_ms.append(tail_ms)
        if lag_ms is not None:
            self._offline_final_lag_ms.append(lag_ms)
        if self._offline_final_count % self._offline_report_every != 0:
            return

        avg_total = sum(self._offline_final_total_ms) / len(self._offline_final_total_ms)
        avg_lag = (
            sum(self._offline_final_lag_ms) / len(self._offline_final_lag_ms)
            if self._offline_final_lag_ms
            else 0.0
        )
        avg_tail = sum(self._offline_final_tail_ms) / len(self._offline_final_tail_ms)
        p95_tail = self._percentile(list(self._offline_final_tail_ms), 0.95)
        LOGGER.info(
            "Offline latency summary: finals=%d avg_total=%.0fms avg_lag=%.0fms avg_tail=%.0fms p95_tail=%.0fms",
            self._offline_final_count,
            avg_total,
            avg_lag,
            avg_tail,
            p95_tail,
        )

    def run(self) -> None:
        LOGGER.info(
            "ASR worker started (mode=%s, model=%s, detector=%s)",
            self.mode,
            self.args.model,
            self.detector_model_name,
        )
        self.signals.status.emit("模型加载中...")
        LOGGER.info("Loading ASR model...")
        try:
            loaded_models = load_models_for_worker(self)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("FunASR model init failed")
            self.signals.status.emit("模型加载失败")
            self.signals.error.emit(f"FunASR model init failed: {exc}")
            return

        LOGGER.info("ASR model ready")
        self.signals.status.emit("")
        run_worker_loop(self, loaded_models)
