import unittest

from PySide6.QtCore import QRect
from PySide6.QtGui import QFont, QGuiApplication

from presentation.qt.overlay_renderer import (
    build_centered_draw_rect,
    build_overlay_text_layout,
    clamp_text_rect_to_max_lines,
)


class BuildCenteredDrawRectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QGuiApplication.instance() or QGuiApplication([])

    def test_rect_stays_within_container(self) -> None:
        container = QRect(10, 20, 300, 120)
        result = build_centered_draw_rect(QFont("Microsoft YaHei", 16), container, "你好，世界")

        self.assertGreaterEqual(result.left(), container.left())
        self.assertGreaterEqual(result.top(), container.top())
        self.assertLessEqual(result.right(), container.right())
        self.assertLessEqual(result.bottom(), container.bottom())

    def test_rect_is_non_empty_for_wrapped_text(self) -> None:
        container = QRect(0, 0, 120, 80)
        result = build_centered_draw_rect(QFont("Microsoft YaHei", 14), container, "这是一段需要换行显示的测试文本")

        self.assertGreater(result.width(), 0)
        self.assertGreater(result.height(), 0)


class ClampTextRectToMaxLinesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QGuiApplication.instance() or QGuiApplication([])

    def test_clamps_height_to_line_limit(self) -> None:
        font = QFont("Microsoft YaHei", 14)
        original = QRect(0, 0, 200, 300)

        result = clamp_text_rect_to_max_lines(font, original, 2)

        self.assertLess(result.height(), original.height())


class BuildOverlayTextLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QGuiApplication.instance() or QGuiApplication([])

    def test_prefers_subtitle_text_and_marks_reveal(self) -> None:
        layout = build_overlay_text_layout(
            QFont("Microsoft YaHei", 14),
            QRect(0, 0, 240, 120),
            subtitle_text="字幕",
            status_text="状态",
            text_max_lines=3,
            text_anim_enable=True,
        )

        self.assertIsNotNone(layout)
        assert layout is not None
        self.assertEqual(layout.text, "字幕")
        self.assertTrue(layout.use_reveal)

    def test_uses_status_when_subtitle_is_empty(self) -> None:
        layout = build_overlay_text_layout(
            QFont("Microsoft YaHei", 14),
            QRect(0, 0, 240, 120),
            subtitle_text="",
            status_text="模型加载中...",
            text_max_lines=3,
            text_anim_enable=True,
        )

        self.assertIsNotNone(layout)
        assert layout is not None
        self.assertEqual(layout.text, "模型加载中...")
        self.assertFalse(layout.use_reveal)

    def test_returns_none_when_no_text_exists(self) -> None:
        layout = build_overlay_text_layout(
            QFont("Microsoft YaHei", 14),
            QRect(0, 0, 240, 120),
            subtitle_text="",
            status_text="",
            text_max_lines=3,
            text_anim_enable=True,
        )

        self.assertIsNone(layout)


if __name__ == "__main__":
    unittest.main()
