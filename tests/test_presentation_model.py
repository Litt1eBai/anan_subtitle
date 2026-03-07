import unittest

from presentation.model import (
    OverlayRuntimeSettings,
    SubtitleStyleSpec,
    SubtitleViewState,
    advance_animation,
    calc_animation_start_progress,
    clear_subtitle_text,
    set_status_text,
    set_subtitle_text,
    normalize_text_box,
    resolve_bg_draw_size,
    resolve_text_box,
    set_runtime_bg_offset,
    set_runtime_bg_size,
    set_runtime_flag,
    set_runtime_font_size,
    set_runtime_text_box,
)


class SubtitleViewStateTests(unittest.TestCase):
    def test_to_dict_contains_expected_fields(self) -> None:
        state = SubtitleViewState(subtitle_text="你好", status_text="", animation_progress=0.5)
        self.assertEqual(
            state.to_dict(),
            {
                "subtitle_text": "你好",
                "status_text": "",
                "animation_progress": 0.5,
                "animation_start_progress": 0.0,
            },
        )


class SubtitleStyleSpecTests(unittest.TestCase):
    def test_to_dict_contains_style_tokens(self) -> None:
        spec = SubtitleStyleSpec(
            font_family="Microsoft YaHei",
            font_size=30,
            text_color="#000000",
            text_max_lines=4,
            text_anim_enable=True,
            text_anim_duration_ms=220,
            text_anim_fade_px=24,
            text_anim_offset_y=10,
        )
        self.assertEqual(spec.to_dict()["font_size"], 30)
        self.assertEqual(spec.to_dict()["text_color"], "#000000")


class OverlayRuntimeSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = OverlayRuntimeSettings(
            x=1,
            y=2,
            width=300,
            height=200,
            windowed_mode=False,
            stay_on_top=True,
            font_size=30,
            text_x=10,
            text_y=20,
            text_width=100,
            text_height=80,
            bg_width=0,
            bg_height=0,
            bg_offset_x=5,
            bg_offset_y=6,
        )

    def test_to_dict_contains_runtime_layout_fields(self) -> None:
        self.assertEqual(self.settings.to_dict()["bg_offset_y"], 6)
        self.assertEqual(self.settings.to_dict()["windowed_mode"], False)

    def test_set_runtime_flag_returns_updated_copy(self) -> None:
        updated = set_runtime_flag(self.settings, field_name="windowed_mode", value=True)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.windowed_mode, True)
        self.assertEqual(self.settings.windowed_mode, False)

    def test_set_runtime_font_size_clamps_minimum(self) -> None:
        updated = set_runtime_font_size(self.settings, 3)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.font_size, 8)

    def test_set_runtime_bg_offset_updates_coordinates(self) -> None:
        updated = set_runtime_bg_offset(self.settings, 12, 14)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.bg_offset_x, 12)
        self.assertEqual(updated.bg_offset_y, 14)

    def test_resolve_bg_draw_size_prefers_native_when_unset(self) -> None:
        self.assertEqual(
            resolve_bg_draw_size(self.settings, bg_native_width=640, bg_native_height=360),
            (640, 360),
        )

    def test_set_runtime_bg_size_locks_overlay_size_when_requested(self) -> None:
        updated = set_runtime_bg_size(
            self.settings,
            320,
            180,
            lock_size_to_bg=True,
            bg_native_width=640,
            bg_native_height=360,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.bg_width, 320)
        self.assertEqual(updated.width, 320)
        self.assertEqual(updated.height, 180)

    def test_normalize_text_box_clamps_to_overlay_bounds(self) -> None:
        self.assertEqual(
            normalize_text_box(x=280, y=190, width=50, height=50, overlay_width=300, overlay_height=200),
            (250, 150, 50, 50),
        )

    def test_set_runtime_text_box_returns_updated_copy(self) -> None:
        updated = set_runtime_text_box(
            self.settings,
            x=280,
            y=190,
            width=50,
            height=50,
            overlay_width=300,
            overlay_height=200,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.text_x, 250)
        self.assertEqual(updated.text_y, 150)

    def test_resolve_text_box_uses_available_space_when_unset(self) -> None:
        settings = OverlayRuntimeSettings(
            x=1,
            y=2,
            width=300,
            height=200,
            windowed_mode=False,
            stay_on_top=True,
            font_size=30,
            text_x=20,
            text_y=30,
            text_width=0,
            text_height=0,
            bg_width=0,
            bg_height=0,
            bg_offset_x=0,
            bg_offset_y=0,
        )

        self.assertEqual(
            resolve_text_box(settings, overlay_width=300, overlay_height=200),
            (20, 30, 280, 170),
        )


if __name__ == "__main__":
    unittest.main()


class SubtitleStateUpdateTests(unittest.TestCase):
    def test_calc_animation_start_progress_uses_common_prefix_ratio(self) -> None:
        self.assertEqual(calc_animation_start_progress("你好世界", "你好世界啊"), 0.8)

    def test_set_subtitle_text_updates_animation_state(self) -> None:
        state = SubtitleViewState(subtitle_text="你好世界")

        updated = set_subtitle_text(state, "你好世界啊", text_anim_enabled=True)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.subtitle_text, "你好世界啊")
        self.assertEqual(updated.animation_start_progress, 0.8)
        self.assertEqual(updated.animation_progress, 0.8)

    def test_set_subtitle_text_returns_none_when_unchanged(self) -> None:
        state = SubtitleViewState(subtitle_text="你好")

        self.assertIsNone(set_subtitle_text(state, "你好", text_anim_enabled=True))

    def test_clear_subtitle_text_resets_animation_state(self) -> None:
        state = SubtitleViewState(subtitle_text="你好", animation_progress=0.5, animation_start_progress=0.3)

        updated = clear_subtitle_text(state)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.subtitle_text, "")
        self.assertEqual(updated.animation_progress, 1.0)
        self.assertEqual(updated.animation_start_progress, 0.0)

    def test_set_status_text_updates_only_when_changed(self) -> None:
        state = SubtitleViewState(status_text="旧状态")

        updated = set_status_text(state, "新状态")

        self.assertIsNotNone(updated)
        self.assertEqual(updated.status_text, "新状态")

    def test_advance_animation_completes_when_duration_non_positive(self) -> None:
        state = SubtitleViewState(animation_progress=0.2, animation_start_progress=0.2)

        updated, finished = advance_animation(state, elapsed_ms=10, duration_ms=0)

        self.assertEqual(updated.animation_progress, 1.0)
        self.assertTrue(finished)

    def test_advance_animation_interpolates_progress(self) -> None:
        state = SubtitleViewState(animation_progress=0.0, animation_start_progress=0.25)

        updated, finished = advance_animation(state, elapsed_ms=110, duration_ms=220)

        self.assertAlmostEqual(updated.animation_progress, 0.625)
        self.assertFalse(finished)
