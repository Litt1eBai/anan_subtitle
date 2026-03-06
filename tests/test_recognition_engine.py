import argparse
import unittest

from asr import ASRWorker as LegacyASRWorker
from recognition.engine import ASRWorker, resolve_worker_mode


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


class LegacyImportCompatibilityTests(unittest.TestCase):
    def test_legacy_asr_import_still_points_to_engine_worker(self) -> None:
        self.assertIs(LegacyASRWorker, ASRWorker)


if __name__ == "__main__":
    unittest.main()
