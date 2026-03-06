import unittest

from presentation.qt import OverlayControlPanel as package_panel
from presentation.qt import SubtitleOverlay as package_overlay
from presentation.qt import TrayController as package_tray
from presentation.qt.overlay_window import SubtitleOverlay
from presentation.qt.settings_window import OverlayControlPanel
from presentation.qt.tray_controller import TrayController
from ui.control_panel import OverlayControlPanel as legacy_panel
from ui.overlay import SubtitleOverlay as legacy_overlay
from ui.tray import TrayController as legacy_tray


class QtImportCompatibilityTests(unittest.TestCase):
    def test_presentation_qt_package_exports_current_classes(self) -> None:
        self.assertIs(package_overlay, SubtitleOverlay)
        self.assertIs(package_panel, OverlayControlPanel)
        self.assertIs(package_tray, TrayController)

    def test_legacy_ui_modules_forward_to_current_classes(self) -> None:
        self.assertIs(legacy_overlay, SubtitleOverlay)
        self.assertIs(legacy_panel, OverlayControlPanel)
        self.assertIs(legacy_tray, TrayController)
