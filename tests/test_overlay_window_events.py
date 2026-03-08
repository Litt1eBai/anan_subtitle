import unittest

from PySide6.QtCore import Qt

from presentation.qt.overlay_window_behavior import OverlayWindowAction
from presentation.qt.overlay_window_events import (
    OverlayKeyAction,
    resolve_overlay_close_event_action,
    resolve_overlay_key_action,
    should_emit_settings_after_drag_release,
)


class ResolveOverlayKeyActionTests(unittest.TestCase):
    def test_escape_maps_to_hide_when_tray_enabled(self) -> None:
        self.assertEqual(
            resolve_overlay_key_action(int(Qt.Key.Key_Escape), hide_to_tray_on_close=True),
            OverlayKeyAction.HIDE,
        )

    def test_escape_maps_to_close_when_tray_disabled(self) -> None:
        self.assertEqual(
            resolve_overlay_key_action(int(Qt.Key.Key_Escape), hide_to_tray_on_close=False),
            OverlayKeyAction.CLOSE,
        )

    def test_f2_maps_to_toggle_edit(self) -> None:
        self.assertEqual(
            resolve_overlay_key_action(int(Qt.Key.Key_F2), hide_to_tray_on_close=False),
            OverlayKeyAction.TOGGLE_EDIT,
        )

    def test_other_key_maps_to_none(self) -> None:
        self.assertEqual(
            resolve_overlay_key_action(int(Qt.Key.Key_A), hide_to_tray_on_close=False),
            OverlayKeyAction.NONE,
        )


class ResolveOverlayCloseEventActionTests(unittest.TestCase):
    def test_returns_hide_when_tray_enabled(self) -> None:
        self.assertEqual(
            resolve_overlay_close_event_action(hide_to_tray_on_close=True),
            OverlayWindowAction.HIDE,
        )

    def test_returns_none_when_tray_disabled(self) -> None:
        self.assertEqual(
            resolve_overlay_close_event_action(hide_to_tray_on_close=False),
            OverlayWindowAction.NONE,
        )


class ShouldEmitSettingsAfterDragReleaseTests(unittest.TestCase):
    def test_returns_true_for_window_move(self) -> None:
        self.assertTrue(should_emit_settings_after_drag_release("move_window"))

    def test_returns_false_for_other_modes(self) -> None:
        self.assertFalse(should_emit_settings_after_drag_release("move_background"))
        self.assertFalse(should_emit_settings_after_drag_release(None))


if __name__ == "__main__":
    unittest.main()
