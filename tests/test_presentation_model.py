import unittest

from desktop_subtitle.presentation.model import (
    OverlayRuntimeSettings,
    SubtitleStyleSpec,
    SubtitleViewState,
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
    def test_to_dict_contains_runtime_layout_fields(self) -> None:
        settings = OverlayRuntimeSettings(
            x=1,
            y=2,
            width=3,
            height=4,
            windowed_mode=False,
            stay_on_top=True,
            font_size=30,
            text_x=10,
            text_y=20,
            text_width=300,
            text_height=100,
            bg_width=500,
            bg_height=200,
            bg_offset_x=5,
            bg_offset_y=6,
        )
        self.assertEqual(settings.to_dict()["bg_offset_y"], 6)
        self.assertEqual(settings.to_dict()["windowed_mode"], False)


if __name__ == "__main__":
    unittest.main()
