import unittest

from PySide6.QtCore import QRect
from PySide6.QtGui import QFont, QGuiApplication

from ui.overlay_renderer import build_centered_draw_rect


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


if __name__ == "__main__":
    unittest.main()
