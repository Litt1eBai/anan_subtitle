import unittest

from presentation.qt.overlay_window import SubtitleOverlay as QtSubtitleOverlay
from ui.overlay import SubtitleOverlay as LegacySubtitleOverlay


class OverlayImportCompatibilityTests(unittest.TestCase):
    def test_legacy_overlay_import_reexports_qt_overlay(self) -> None:
        self.assertIs(LegacySubtitleOverlay, QtSubtitleOverlay)


if __name__ == "__main__":
    unittest.main()
