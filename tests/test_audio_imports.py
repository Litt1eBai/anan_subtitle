import unittest

from audio import build_audio_callback as legacy_build_audio_callback
from recognition.audio_source import build_audio_callback


class AudioImportCompatibilityTests(unittest.TestCase):
    def test_legacy_audio_module_forwards_to_recognition_audio_source(self) -> None:
        self.assertIs(legacy_build_audio_callback, build_audio_callback)
