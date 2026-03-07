import argparse
import unittest

from presentation.qt.overlay_window_setup import (
    build_overlay_runtime_settings,
    build_overlay_style_spec,
    build_overlay_text_color,
    resolve_initial_overlay_size,
)


class OverlayWindowSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.args = argparse.Namespace(
            subtitle_style="default",
            font_family="Microsoft YaHei",
            font_size=32,
            text_color="#112233",
            text_max_lines=3,
            text_anim_enable=True,
            text_anim_duration_ms=220,
            text_anim_fade_px=24,
            text_anim_offset_y=10,
            x=10,
            y=20,
            width=300,
            height=200,
            windowed_mode=False,
            stay_on_top=True,
            text_x=30,
            text_y=40,
            text_width=120,
            text_height=80,
            bg_width=0,
            bg_height=0,
            bg_offset_x=5,
            bg_offset_y=6,
        )

    def test_build_overlay_style_spec_uses_registered_style(self) -> None:
        style_spec = build_overlay_style_spec(self.args)

        self.assertEqual(style_spec.font_family, "Microsoft YaHei")
        self.assertEqual(style_spec.font_size, 32)
        self.assertEqual(style_spec.text_color, "#112233")

    def test_build_overlay_runtime_settings_uses_style_font_size(self) -> None:
        style_spec = build_overlay_style_spec(self.args)

        settings = build_overlay_runtime_settings(self.args, style_spec)

        self.assertEqual(settings.x, 10)
        self.assertEqual(settings.font_size, 32)
        self.assertEqual(settings.text_width, 120)
        self.assertEqual(settings.bg_offset_y, 6)

    def test_resolve_initial_overlay_size_prefers_locked_background_size(self) -> None:
        style_spec = build_overlay_style_spec(self.args)
        settings = build_overlay_runtime_settings(self.args, style_spec)

        self.assertEqual(
            resolve_initial_overlay_size(
                settings,
                lock_size_to_bg=True,
                bg_native_width=640,
                bg_native_height=360,
            ),
            (640, 360),
        )

    def test_build_overlay_text_color_falls_back_to_black_for_invalid_value(self) -> None:
        color = build_overlay_text_color("not-a-color")

        self.assertEqual(color.red(), 0)
        self.assertEqual(color.green(), 0)
        self.assertEqual(color.blue(), 0)


if __name__ == "__main__":
    unittest.main()
