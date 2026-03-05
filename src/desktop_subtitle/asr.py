import argparse
import logging
import queue
import threading
from typing import Any

import numpy as np
from funasr import AutoModel

from .signals import AppSignals
from .text_utils import extract_text, merge_incremental_text, replace_sentence_initial_wo

LOGGER = logging.getLogger("desktop_subtitle")

class ASRWorker(threading.Thread):
    def __init__(
        self,
        args: argparse.Namespace,
        audio_queue: "queue.Queue[np.ndarray]",
        signals: AppSignals,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self.args = args
        self.audio_queue = audio_queue
        self.signals = signals
        self.stop_event = stop_event
        self.use_streaming = "streaming" in args.model
        self.silence_blocks = max(1, int(args.silence_ms / args.block_ms))
        self.partial_blocks = max(1, int(args.partial_interval_ms / args.block_ms))
        self.max_segment_samples = int(args.max_segment_seconds * args.samplerate)
        self.chunk_size = args.chunk_size
        self.encoder_chunk_look_back = args.encoder_chunk_look_back
        self.decoder_chunk_look_back = args.decoder_chunk_look_back
        self.chunk_stride_samples = max(1, int(self.args.samplerate * self.chunk_size[1] * 0.06))

    def _emit_subtitle(self, text: str) -> None:
        converted = replace_sentence_initial_wo(text.strip())
        if converted:
            self.signals.subtitle.emit(converted)

    def run(self) -> None:
        mode = "streaming" if self.use_streaming else "offline"
        LOGGER.info("ASR worker started (mode=%s, model=%s)", mode, self.args.model)
        self.signals.status.emit("模型加载中...")
        LOGGER.info("Loading ASR model...")
        try:
            model = self._load_model()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("FunASR model init failed")
            self.signals.status.emit("模型加载失败")
            self.signals.error.emit(f"FunASR model init failed: {exc}")
            return

        LOGGER.info("ASR model ready")
        self.signals.status.emit("")
        if self.use_streaming:
            LOGGER.info("Streaming ASR loop running")
            self._run_streaming(model)
            LOGGER.info("Streaming ASR loop stopped")
            return
        LOGGER.info("Offline ASR loop running")
        self._run_offline(model)
        LOGGER.info("Offline ASR loop stopped")

    def _run_streaming(self, model: AutoModel) -> None:
        cache: dict[str, Any] = {}
        pending = np.empty(0, dtype=np.float32)
        in_speech = False
        silence_count = 0
        segment_samples = 0
        current_text = ""

        while not self.stop_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.15)
            except queue.Empty:
                continue

            energy = float(np.mean(np.abs(chunk)))
            is_voice = energy >= self.args.energy_threshold
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

            while pending.size >= self.chunk_stride_samples:
                speech_chunk = pending[: self.chunk_stride_samples]
                pending = pending[self.chunk_stride_samples :]
                text = self._transcribe_streaming(model, speech_chunk, cache, is_final=False)
                if text:
                    if not in_speech:
                        in_speech = True
                        silence_count = 0
                    current_text = merge_incremental_text(current_text, text)
                    self._emit_subtitle(current_text)

            if in_speech and (
                silence_count >= self.silence_blocks or segment_samples >= self.max_segment_samples
            ):
                final_text = self._transcribe_streaming(model, pending, cache, is_final=True)
                if final_text:
                    current_text = merge_incremental_text(current_text, final_text)
                if current_text:
                    self._emit_subtitle(current_text)
                end_reason = (
                    "silence"
                    if silence_count >= self.silence_blocks
                    else "max-segment-seconds"
                )
                LOGGER.info("Speech finalized (%s, chars=%d)", end_reason, len(current_text))
                pending = np.empty(0, dtype=np.float32)
                current_text = ""
                in_speech = False
                silence_count = 0
                segment_samples = 0

        while True:
            try:
                tail = self.audio_queue.get_nowait()
                pending = np.concatenate((pending, tail.astype(np.float32, copy=False)))
            except queue.Empty:
                break

        if pending.size > 0 or current_text:
            final_text = self._transcribe_streaming(model, pending, cache, is_final=True)
            if final_text:
                current_text = merge_incremental_text(current_text, final_text)
            if current_text:
                self._emit_subtitle(current_text)
                LOGGER.info("Speech flushed on shutdown (chars=%d)", len(current_text))

    def _run_offline(self, model: AutoModel) -> None:
        in_speech = False
        silence_count = 0
        segment_parts: list[np.ndarray] = []
        segment_samples = 0
        chunks_since_partial = 0

        while not self.stop_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.15)
            except queue.Empty:
                continue

            energy = float(np.mean(np.abs(chunk)))
            is_voice = energy >= self.args.energy_threshold

            if is_voice:
                if not in_speech:
                    LOGGER.info("Speech started")
                    in_speech = True
                    silence_count = 0
                    segment_parts = []
                    segment_samples = 0
                    chunks_since_partial = 0

                segment_parts.append(chunk)
                segment_samples += len(chunk)
                chunks_since_partial += 1
                silence_count = 0

                if chunks_since_partial >= self.partial_blocks:
                    chunks_since_partial = 0
                    partial_text = self._transcribe(model, np.concatenate(segment_parts))
                    if partial_text:
                        self._emit_subtitle(partial_text)

                if segment_samples >= self.max_segment_samples:
                    final_text = self._transcribe(model, np.concatenate(segment_parts))
                    if final_text:
                        self._emit_subtitle(final_text)
                    LOGGER.info("Speech finalized (max-segment-seconds, chars=%d)", len(final_text))
                    in_speech = False
                    silence_count = 0
                    segment_parts = []
                    segment_samples = 0
                    chunks_since_partial = 0

            elif in_speech:
                silence_count += 1
                segment_parts.append(chunk)
                segment_samples += len(chunk)

                if silence_count >= self.silence_blocks:
                    final_text = self._transcribe(model, np.concatenate(segment_parts))
                    if final_text:
                        self._emit_subtitle(final_text)
                    LOGGER.info("Speech finalized (silence, chars=%d)", len(final_text))
                    in_speech = False
                    silence_count = 0
                    segment_parts = []
                    segment_samples = 0
                    chunks_since_partial = 0

        if segment_parts:
            final_text = self._transcribe(model, np.concatenate(segment_parts))
            if final_text:
                self._emit_subtitle(final_text)
                LOGGER.info("Speech flushed on shutdown (chars=%d)", len(final_text))

    def _load_model(self) -> AutoModel:
        if self.use_streaming:
            return AutoModel(model=self.args.model, disable_update=True)

        model_kwargs: dict[str, Any] = {
            "model": self.args.model,
            "disable_update": True,
        }
        if not self.args.disable_vad_model:
            model_kwargs["vad_model"] = self.args.vad_model
        if not self.args.disable_punc_model:
            model_kwargs["punc_model"] = self.args.punc_model
        return AutoModel(**model_kwargs)

    def _transcribe(self, model: AutoModel, audio: np.ndarray) -> str:
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
        self, model: AutoModel, audio: np.ndarray, cache: dict[str, Any], is_final: bool
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
