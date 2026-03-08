import argparse
import unittest
from unittest.mock import Mock

from recognition.engine_loader import (
    LoadedRecognitionModels,
    load_models,
    load_offline_model,
    load_streaming_model,
)


class LoadStreamingModelTests(unittest.TestCase):
    def test_delegates_to_loader_with_streaming_kwargs(self) -> None:
        loader = Mock(return_value="stream-model")

        loaded = load_streaming_model("streaming-model", model_loader=loader)

        self.assertEqual(loaded, "stream-model")
        loader.assert_called_once_with(model="streaming-model", disable_update=True)


class LoadOfflineModelTests(unittest.TestCase):
    def test_delegates_to_loader_with_offline_kwargs(self) -> None:
        args = argparse.Namespace(
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            disable_vad_model=False,
            disable_punc_model=True,
        )
        loader = Mock(return_value="offline-model")

        loaded = load_offline_model(args, "paraformer-zh", model_loader=loader)

        self.assertEqual(loaded, "offline-model")
        loader.assert_called_once_with(model="paraformer-zh", disable_update=True, vad_model="fsmn-vad")


class LoadModelsTests(unittest.TestCase):
    def test_loads_hybrid_models(self) -> None:
        args = argparse.Namespace(model="offline-model")
        streaming_loader = Mock(return_value="detector")
        offline_loader = Mock(return_value="offline")

        loaded = load_models(
            use_hybrid=True,
            use_streaming=False,
            args=args,
            detector_model_name="detector-model",
            streaming_loader=streaming_loader,
            offline_loader=offline_loader,
        )

        self.assertEqual(loaded, LoadedRecognitionModels(primary_model="offline", detector_model="detector"))
        streaming_loader.assert_called_once_with("detector-model")
        offline_loader.assert_called_once_with(args, "offline-model")

    def test_loads_streaming_model(self) -> None:
        args = argparse.Namespace(model="stream-model")
        streaming_loader = Mock(return_value="stream")
        offline_loader = Mock()

        loaded = load_models(
            use_hybrid=False,
            use_streaming=True,
            args=args,
            detector_model_name="detector-model",
            streaming_loader=streaming_loader,
            offline_loader=offline_loader,
        )

        self.assertEqual(loaded, LoadedRecognitionModels(primary_model="stream"))
        streaming_loader.assert_called_once_with("stream-model")
        offline_loader.assert_not_called()

    def test_loads_offline_model(self) -> None:
        args = argparse.Namespace(model="offline-model")
        streaming_loader = Mock()
        offline_loader = Mock(return_value="offline")

        loaded = load_models(
            use_hybrid=False,
            use_streaming=False,
            args=args,
            detector_model_name="detector-model",
            streaming_loader=streaming_loader,
            offline_loader=offline_loader,
        )

        self.assertEqual(loaded, LoadedRecognitionModels(primary_model="offline"))
        offline_loader.assert_called_once_with(args, "offline-model")
        streaming_loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
