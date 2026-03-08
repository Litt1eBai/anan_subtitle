import unittest

from PySide6.QtCore import QRect, Qt

from presentation.qt.overlay_window_shell import (
    apply_overlay_window_flags,
    build_overlay_window_refresh_state,
    refresh_overlay_window_shell,
)


class FakeOverlayWindow:
    def __init__(self) -> None:
        self.window_flags = None
        self.attributes: list[tuple[Qt.WidgetAttribute, bool]] = []
        self.geometry = None
        self.show_calls = 0
        self.update_calls = 0

    def setWindowFlags(self, flags) -> None:  # noqa: N802
        self.window_flags = flags

    def setAttribute(self, attribute, enabled) -> None:  # noqa: N802
        self.attributes.append((attribute, enabled))

    def setGeometry(self, geometry) -> None:  # noqa: N802
        self.geometry = QRect(geometry)

    def show(self) -> None:
        self.show_calls += 1

    def update(self) -> None:
        self.update_calls += 1


class BuildOverlayWindowRefreshStateTests(unittest.TestCase):
    def test_copies_geometry_and_flags(self) -> None:
        state = build_overlay_window_refresh_state(
            QRect(1, 2, 300, 200),
            was_visible=True,
            request_update=False,
        )

        self.assertEqual(state.geometry, QRect(1, 2, 300, 200))
        self.assertTrue(state.restore_visibility)
        self.assertFalse(state.request_update)


class ApplyOverlayWindowFlagsTests(unittest.TestCase):
    def test_sets_translucent_background_attribute(self) -> None:
        widget = FakeOverlayWindow()

        apply_overlay_window_flags(
            widget,
            windowed_mode=False,
            stay_on_top=True,
        )

        self.assertTrue(widget.window_flags & Qt.WindowType.Tool)
        self.assertIn((Qt.WidgetAttribute.WA_TranslucentBackground, True), widget.attributes)


class RefreshOverlayWindowShellTests(unittest.TestCase):
    def test_restores_geometry_and_visibility(self) -> None:
        widget = FakeOverlayWindow()

        refresh_overlay_window_shell(
            widget,
            windowed_mode=True,
            stay_on_top=False,
            geometry=QRect(10, 20, 320, 180),
            was_visible=True,
            request_update=False,
        )

        self.assertEqual(widget.geometry, QRect(10, 20, 320, 180))
        self.assertEqual(widget.show_calls, 1)
        self.assertEqual(widget.update_calls, 0)

    def test_requests_update_when_needed(self) -> None:
        widget = FakeOverlayWindow()

        refresh_overlay_window_shell(
            widget,
            windowed_mode=False,
            stay_on_top=True,
            geometry=QRect(0, 0, 300, 100),
            was_visible=False,
            request_update=True,
        )

        self.assertEqual(widget.show_calls, 0)
        self.assertEqual(widget.update_calls, 1)


if __name__ == "__main__":
    unittest.main()
