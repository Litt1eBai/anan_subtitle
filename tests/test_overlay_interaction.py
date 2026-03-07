import unittest

from PySide6.QtCore import QPoint, QRect

from presentation.qt.overlay_interaction import (
    OverlayDragState,
    begin_overlay_drag,
    build_text_handle_rects,
    hit_test_text_interaction,
    resolve_overlay_drag_update,
    resize_text_rect,
)


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


class BeginOverlayDragTests(unittest.TestCase):
    def test_defaults_to_window_move_outside_edit_mode(self) -> None:
        state = begin_overlay_drag(
            global_pos=QPoint(100, 120),
            window_origin=QPoint(50, 60),
            local_pos=QPoint(10, 10),
            edit_mode=False,
            text_rect=QRect(20, 30, 100, 60),
            bg_rect=QRect(0, 0, 300, 100),
            bg_offset=QPoint(5, 6),
            handle_size=10,
        )

        self.assertEqual(state.interaction_mode, "move_window")
        self.assertEqual(state.drag_origin, QPoint(100, 120))
        self.assertEqual(state.window_origin, QPoint(50, 60))

    def test_uses_text_interaction_when_editing(self) -> None:
        state = begin_overlay_drag(
            global_pos=QPoint(100, 120),
            window_origin=QPoint(50, 60),
            local_pos=QPoint(40, 50),
            edit_mode=True,
            text_rect=QRect(20, 30, 100, 60),
            bg_rect=QRect(0, 0, 300, 100),
            bg_offset=QPoint(5, 6),
            handle_size=10,
        )

        self.assertEqual(state.interaction_mode, "text_move")
        self.assertEqual(state.drag_start_text_rect, QRect(20, 30, 100, 60))

    def test_uses_background_move_when_clicking_background(self) -> None:
        state = begin_overlay_drag(
            global_pos=QPoint(100, 120),
            window_origin=QPoint(50, 60),
            local_pos=QPoint(200, 50),
            edit_mode=True,
            text_rect=QRect(20, 30, 100, 60),
            bg_rect=QRect(0, 0, 300, 100),
            bg_offset=QPoint(5, 6),
            handle_size=10,
        )

        self.assertEqual(state.interaction_mode, "move_bg")
        self.assertEqual(state.drag_start_bg_offset, QPoint(5, 6))


class ResolveOverlayDragUpdateTests(unittest.TestCase):
    def test_resolves_window_move(self) -> None:
        update = resolve_overlay_drag_update(
            drag_state=OverlayDragState(
                interaction_mode="move_window",
                drag_origin=QPoint(100, 100),
                window_origin=QPoint(20, 30),
            ),
            delta=QPoint(5, 7),
            overlay_width=400,
            overlay_height=300,
            min_box_size=40,
        )

        self.assertIsNotNone(update)
        self.assertEqual(update.window_pos, QPoint(25, 37))

    def test_resolves_background_move(self) -> None:
        update = resolve_overlay_drag_update(
            drag_state=OverlayDragState(
                interaction_mode="move_bg",
                drag_start_bg_offset=QPoint(5, 6),
            ),
            delta=QPoint(7, 9),
            overlay_width=400,
            overlay_height=300,
            min_box_size=40,
        )

        self.assertIsNotNone(update)
        self.assertEqual(update.bg_offset, QPoint(12, 15))

    def test_resolves_text_resize(self) -> None:
        update = resolve_overlay_drag_update(
            drag_state=OverlayDragState(
                interaction_mode="text_bottom_right",
                drag_start_text_rect=QRect(10, 20, 100, 60),
            ),
            delta=QPoint(20, 30),
            overlay_width=400,
            overlay_height=300,
            min_box_size=40,
        )

        self.assertIsNotNone(update)
        self.assertEqual(update.text_rect, QRect(10, 20, 120, 90))


if __name__ == "__main__":
    unittest.main()
