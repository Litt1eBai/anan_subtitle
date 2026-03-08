from dataclasses import dataclass
import argparse
import logging
import queue
import threading
from typing import Any

import numpy as np

from recognition.engine_config import (
    build_offline_model_kwargs,
    build_worker_runtime_config,
)
from recognition.engine_runtime import (
    OfflineLatencyTracker,
    WorkerSignals,
    emit_subtitle,
    timed_transcribe_offline,
    transcribe_streaming,
)
from recognition.offline_session import run_offline_session
from recognition.realtime_session import run_hybrid_session, run_streaming_session


@dataclass(frozen=True)
class LoadedRecognitionModels:
    primary_model: Any | None = None
    detector_model: Any | None = None


LOGGER = logging.getLogger("desktop_subtitle")


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

    report_every = getattr(getattr(worker, "_offline_latency", None), "report_every", 5)
    LOGGER.info(
        "Offline latency probe enabled (summary every %d finalized segments)",
        report_every,
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

        runtime = build_worker_runtime_config(args)
        self.mode = runtime.mode
        self.use_hybrid = runtime.use_hybrid
        self.use_streaming = runtime.use_streaming
        self.detector_model_name = runtime.detector_model_name
        self.silence_blocks = runtime.silence_blocks
        self.partial_blocks = runtime.partial_blocks
        self.max_segment_samples = runtime.max_segment_samples
        self.chunk_size = runtime.chunk_size
        self.encoder_chunk_look_back = runtime.encoder_chunk_look_back
        self.decoder_chunk_look_back = runtime.decoder_chunk_look_back
        self.chunk_stride_samples = runtime.chunk_stride_samples
        self._offline_latency = OfflineLatencyTracker(report_every=5)

    def _emit_subtitle(self, text: str) -> None:
        emit_subtitle(self.signals, text)

    def _load_streaming_model(self, model_name: str) -> Any:
        from funasr import AutoModel

        return AutoModel(model=model_name, disable_update=True)

    def _load_offline_model(self, model_name: str) -> Any:
        from funasr import AutoModel

        return AutoModel(**build_offline_model_kwargs(self.args, model_name))

    def _timed_transcribe(self, model: Any, audio: np.ndarray) -> tuple[str, float]:
        return timed_transcribe_offline(
            model,
            audio,
            samplerate=self.args.samplerate,
            error_signal=self.signals.error,
        )

    def _transcribe_streaming(
        self, model: Any, audio: np.ndarray, cache: dict[str, Any], is_final: bool
    ) -> str:
        return transcribe_streaming(
            model,
            audio,
            cache,
            is_final=is_final,
            samplerate=self.args.samplerate,
            chunk_size=self.chunk_size,
            encoder_chunk_look_back=self.encoder_chunk_look_back,
            decoder_chunk_look_back=self.decoder_chunk_look_back,
            error_signal=self.signals.error,
        )

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
        self._offline_latency.log(
            stage=stage,
            reason=reason,
            speech_started_at=speech_started_at,
            last_audio_at=last_audio_at,
            segment_samples=segment_samples,
            infer_ms=infer_ms,
            chars=chars,
            samplerate=self.args.samplerate,
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
