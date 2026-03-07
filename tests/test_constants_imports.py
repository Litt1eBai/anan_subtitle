import unittest

from constants import (
    DEFAULT_CONFIG,
    MODEL_PROFILE_CHOICES,
    MODEL_PROFILE_HYBRID,
    MODEL_PROFILE_PRESETS,
)
from core.models import MODEL_PROFILE_CUSTOM, MODEL_PROFILE_OFFLINE, MODEL_PROFILE_REALTIME
from core.settings import OVERLAY_PERSIST_KEYS


class ConstantsImportCompatibilityTests(unittest.TestCase):
    def test_legacy_constants_exports_current_core_values(self) -> None:
        self.assertIn(MODEL_PROFILE_REALTIME, MODEL_PROFILE_CHOICES)
        self.assertIn(MODEL_PROFILE_OFFLINE, MODEL_PROFILE_CHOICES)
        self.assertIn(MODEL_PROFILE_CUSTOM, MODEL_PROFILE_CHOICES)
        self.assertIn(MODEL_PROFILE_HYBRID, MODEL_PROFILE_PRESETS)
        self.assertIn("font_size", DEFAULT_CONFIG)
        self.assertIn("x", OVERLAY_PERSIST_KEYS)
