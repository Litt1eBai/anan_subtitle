import unittest

from PySide6.QtCore import QRect

from presentation.model import OverlayRuntimeSettings
from presentation.qt.overlay_geometry import (
    build_overlay_bg_rect,
    build_overlay_text_rect,
    export_runtime_settings_snapshot,
)


class BuildOverlayBgRectTests(unittest.TestCase):
    def test_returns_empty_rect_for_missing_background(self) -> None:
        settings = OverlayRuntimeSettings(0, 0, 300, 200, False, True, 30, 10, 20, 100, 80, 0, 0, 5, 6)

        self.assertTrue(build_overlay_bg_rect(settings, bg_width=0, bg_height=0).isNull())

    def test_builds_background_rect_from_offsets(self) -> None:
        settings = OverlayRuntimeSettings(0, 0, 300, 200, False, True, 30, 10, 20, 100, 80, 0, 0, 5, 6)

        self.assertEqual(build_overlay_bg_rect(settings, bg_width=320, bg_height=180), QRect(5, 6, 320, 180))


class BuildOverlayTextRectTests(unittest.TestCase):
    def test_builds_text_rect_from_runtime_settings(self) -> None:
        settings = OverlayRuntimeSettings(0, 0, 300, 200, False, True, 30, 10, 20, 100, 80, 0, 0, 0, 0)

        self.assertEqual(
            build_overlay_text_rect(settings, overlay_width=300, overlay_height=200),
            QRect(10, 20, 100, 80),
        )

    def test_uses_available_space_when_text_box_is_unset(self) -> None:
        settings = OverlayRuntimeSettings(0, 0, 300, 200, False, True, 30, 20, 30, 0, 0, 0, 0, 0, 0)

        self.assertEqual(
            build_overlay_text_rect(settings, overlay_width=300, overlay_height=200),
            QRect(20, 30, 280, 170),
        )


class ExportRuntimeSettingsSnapshotTests(unittest.TestCase):
    def test_exports_snapshot_from_geometry_and_text_rect(self) -> None:
        settings = OverlayRuntimeSettings(1, 2, 3, 4, False, True, 30, 10, 20, 100, 80, 500, 200, 5, 6)

        snapshot = export_runtime_settings_snapshot(
            geometry=QRect(50, 60, 700, 180),
            text_rect=QRect(30, 40, 300, 100),
            settings=settings,
            font_size=36,
        )

        self.assertEqual(snapshot.x, 50)
        self.assertEqual(snapshot.height, 180)
        self.assertEqual(snapshot.text_width, 300)
        self.assertEqual(snapshot.font_size, 36)
        self.assertEqual(snapshot.bg_offset_y, 6)


if __name__ == "__main__":
    unittest.main()
