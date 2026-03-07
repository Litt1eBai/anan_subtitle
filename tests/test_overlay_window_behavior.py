import unittest

from PySide6.QtCore import Qt

from presentation.qt.overlay_window_behavior import (
    OverlayWindowAction,
    build_overlay_window_flags,
    resolve_close_action,
    resolve_escape_action,
)


class BuildOverlayWindowFlagsTests(unittest.TestCase):
    def test_windowed_mode_uses_window_flag(self) -> None:
        flags = build_overlay_window_flags(windowed_mode=True, stay_on_top=False)

        self.assertEqual(
            flags,
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint,
        )

    def test_overlay_mode_uses_tool_flag(self) -> None:
        flags = build_overlay_window_flags(windowed_mode=False, stay_on_top=True)

        self.assertTrue(flags & Qt.WindowType.Tool)
        self.assertTrue(flags & Qt.WindowType.WindowStaysOnTopHint)


class OverlayWindowActionResolutionTests(unittest.TestCase):
    def test_escape_hides_when_tray_enabled(self) -> None:
        self.assertEqual(
            resolve_escape_action(hide_to_tray_on_close=True),
            OverlayWindowAction.HIDE,
        )

    def test_escape_closes_when_tray_disabled(self) -> None:
        self.assertEqual(
            resolve_escape_action(hide_to_tray_on_close=False),
            OverlayWindowAction.CLOSE,
        )

    def test_close_hides_when_tray_enabled(self) -> None:
        self.assertEqual(
            resolve_close_action(hide_to_tray_on_close=True),
            OverlayWindowAction.HIDE,
        )

    def test_close_allows_default_when_tray_disabled(self) -> None:
        self.assertEqual(
            resolve_close_action(hide_to_tray_on_close=False),
            OverlayWindowAction.NONE,
        )


if __name__ == "__main__":
    unittest.main()
