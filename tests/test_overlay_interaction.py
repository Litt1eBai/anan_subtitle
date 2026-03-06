import unittest

from PySide6.QtCore import QPoint, QRect

from ui.overlay_interaction import build_text_handle_rects, hit_test_text_interaction, resize_text_rect


class BuildTextHandleRectsTests(unittest.TestCase):
    def test_returns_eight_handles(self) -> None:
        handles = build_text_handle_rects(QRect(10, 20, 100, 60), 10)

        self.assertEqual(set(handles.keys()), {
            "top_left",
            "top",
            "top_right",
            "right",
            "bottom_right",
            "bottom",
            "bottom_left",
            "left",
        })


class HitTestTextInteractionTests(unittest.TestCase):
    def test_prefers_resize_handle_over_body(self) -> None:
        text_rect = QRect(10, 20, 100, 60)
        handle = build_text_handle_rects(text_rect, 10)["top_left"]

        result = hit_test_text_interaction(handle.center(), text_rect, 10)

        self.assertEqual(result, "top_left")

    def test_returns_move_inside_text_rect(self) -> None:
        result = hit_test_text_interaction(QPoint(40, 50), QRect(10, 20, 100, 60), 10)

        self.assertEqual(result, "move")

    def test_returns_none_outside(self) -> None:
        result = hit_test_text_interaction(QPoint(0, 0), QRect(10, 20, 100, 60), 10)

        self.assertIsNone(result)


class ResizeTextRectTests(unittest.TestCase):
    def test_resizes_bottom_right_within_overlay(self) -> None:
        result = resize_text_rect(QRect(10, 20, 100, 60), "bottom_right", QPoint(20, 30), 400, 300, 40)

        self.assertEqual(result, QRect(10, 20, 120, 90))

    def test_enforces_minimum_size(self) -> None:
        result = resize_text_rect(QRect(10, 20, 100, 60), "left", QPoint(95, 0), 400, 300, 40)

        self.assertEqual(result.width(), 40)

    def test_clamps_to_overlay_bounds(self) -> None:
        result = resize_text_rect(QRect(10, 20, 100, 60), "top_left", QPoint(-50, -50), 80, 70, 40)

        self.assertGreaterEqual(result.left(), 0)
        self.assertGreaterEqual(result.top(), 0)
        self.assertLessEqual(result.right(), 79)
        self.assertLessEqual(result.bottom(), 69)


if __name__ == "__main__":
    unittest.main()
