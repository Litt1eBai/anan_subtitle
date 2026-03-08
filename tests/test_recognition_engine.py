import argparse
import threading
import unittest
from unittest.mock import patch

import queue

from recognition.engine import (
    ASRWorker,
    load_models_for_worker,
    run_worker_loop,
)
from recognition.engine_config import (
    build_offline_model_kwargs,
    resolve_worker_mode,
)
from recognition.engine_loader import LoadedRecognitionModels


class ResolveWorkerModeTests(unittest.TestCase):
    def test_resolve_streaming_mode_from_model_name(self) -> None:
        args = argparse.Namespace(model_profile="realtime", model="paraformer-zh-streaming")
        self.assertEqual(resolve_worker_mode(args), "streaming")

    def test_resolve_offline_mode_from_model_name(self) -> None:
        args = argparse.Namespace(model_profile="offline", model="paraformer-zh")
        self.assertEqual(resolve_worker_mode(args), "offline")

    def test_resolve_hybrid_mode_from_profile(self) -> None:
        args = argparse.Namespace(model_profile="hybrid", model="paraformer-zh-streaming")
        self.assertEqual(resolve_worker_mode(args), "hybrid")


class OfflineModelKwargsTests(unittest.TestCase):
    def test_build_offline_model_kwargs_respects_disable_flags(self) -> None:
        args = argparse.Namespace(
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            disable_vad_model=True,
            disable_punc_model=False,
        )

        kwargs = build_offline_model_kwargs(args, "paraformer-zh")

        self.assertEqual(kwargs["model"], "paraformer-zh")
        self.assertNotIn("vad_model", kwargs)
        self.assertEqual(kwargs["punc_model"], "ct-punc")


class LoadModelsForWorkerTests(unittest.TestCase):
    def _build_worker(self, model_profile: str, model: str) -> ASRWorker:
        args = argparse.Namespace(
            model_profile=model_profile,
            model=model,
            detector_model="detector",
            silence_ms=700,
            block_ms=100,
            partial_interval_ms=900,
            max_segment_seconds=12.0,
            samplerate=16000,
            chunk_size=[0, 10, 5],
            encoder_chunk_look_back=4,
            decoder_chunk_look_back=1,
            disable_vad_model=False,
            disable_punc_model=False,
            vad_model="fsmn-vad",
            punc_model="ct-punc",
        )
        signals = argparse.Namespace(
            subtitle=argparse.Namespace(emit=lambda _: None),
            status=argparse.Namespace(emit=lambda _: None),
            error=argparse.Namespace(emit=lambda _: None),
        )
        return ASRWorker(args, queue.Queue(), signals, threading.Event())

    def test_load_models_for_hybrid_worker(self) -> None:
        worker = self._build_worker("hybrid", "paraformer-zh")
        with patch.object(worker, "_load_streaming_model", return_value="detector-model") as load_streaming, patch.object(
            worker, "_load_offline_model", return_value="offline-model"
        ) as load_offline:
            loaded = load_models_for_worker(worker)

        self.assertEqual(loaded, LoadedRecognitionModels(primary_model="offline-model", detector_model="detector-model"))
        load_streaming.assert_called_once_with("detector")
        load_offline.assert_called_once_with(worker.args, "paraformer-zh")

    def test_load_models_for_streaming_worker(self) -> None:
        worker = self._build_worker("realtime", "paraformer-zh-streaming")
        with patch.object(worker, "_load_streaming_model", return_value="stream-model") as load_streaming:
            loaded = load_models_for_worker(worker)

        self.assertEqual(loaded, LoadedRecognitionModels(primary_model="stream-model"))
        load_streaming.assert_called_once_with("paraformer-zh-streaming")


class RunWorkerLoopTests(unittest.TestCase):
    def _build_worker(self, mode: str) -> argparse.Namespace:
        return argparse.Namespace(
            use_hybrid=(mode == "hybrid"),
            use_streaming=(mode == "streaming"),
            _offline_latency=argparse.Namespace(report_every=5),
        )

    def test_run_worker_loop_dispatches_hybrid(self) -> None:
        worker = self._build_worker("hybrid")
        with patch("recognition.engine.run_hybrid_session") as run_hybrid:
            run_worker_loop(worker, LoadedRecognitionModels(primary_model="offline", detector_model="detector"))
        run_hybrid.assert_called_once_with(worker, "detector", "offline")

    def test_run_worker_loop_dispatches_streaming(self) -> None:
        worker = self._build_worker("streaming")
        with patch("recognition.engine.run_streaming_session") as run_streaming:
            run_worker_loop(worker, LoadedRecognitionModels(primary_model="stream"))
        run_streaming.assert_called_once_with(worker, "stream")

    def test_run_worker_loop_dispatches_offline(self) -> None:
        worker = self._build_worker("offline")
        with patch("recognition.engine.run_offline_session") as run_offline:
            run_worker_loop(worker, LoadedRecognitionModels(primary_model="offline"))
        run_offline.assert_called_once_with(worker, "offline")


if __name__ == "__main__":
    unittest.main()
