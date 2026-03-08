import argparse
import unittest

from recognition.engine_config import (
    WorkerRuntimeConfig,
    build_offline_model_kwargs,
    build_worker_runtime_config,
    resolve_worker_mode,
)


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


class BuildWorkerRuntimeConfigTests(unittest.TestCase):
    def test_builds_runtime_config_from_args(self) -> None:
        args = argparse.Namespace(
            model_profile="hybrid",
            model="paraformer-zh",
            detector_model="detector",
            silence_ms=750,
            block_ms=100,
            partial_interval_ms=900,
            max_segment_seconds=12.0,
            samplerate=16000,
            chunk_size=[0, 10, 5],
            encoder_chunk_look_back=4,
            decoder_chunk_look_back=1,
        )

        runtime = build_worker_runtime_config(args)

        self.assertEqual(
            runtime,
            WorkerRuntimeConfig(
                mode="hybrid",
                use_hybrid=True,
                use_streaming=False,
                detector_model_name="detector",
                silence_blocks=7,
                partial_blocks=9,
                max_segment_samples=192000,
                chunk_size=[0, 10, 5],
                encoder_chunk_look_back=4,
                decoder_chunk_look_back=1,
                chunk_stride_samples=9600,
            ),
        )


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


if __name__ == "__main__":
    unittest.main()
