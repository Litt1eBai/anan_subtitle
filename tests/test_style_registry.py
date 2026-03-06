import unittest
from argparse import Namespace

from presentation.model import SubtitleStyleSpec
from presentation.styles import DEFAULT_STYLE_ID, get_style, list_styles


class StyleRegistryTests(unittest.TestCase):
    def test_default_style_is_returned_for_missing_style_id(self) -> None:
        self.assertEqual(get_style(None).style_id, DEFAULT_STYLE_ID)
        self.assertEqual(get_style("missing").style_id, DEFAULT_STYLE_ID)

    def test_default_style_builds_expected_spec(self) -> None:
        args = Namespace(
            font_family="Microsoft YaHei",
            font_size=30,
            text_color="#000000",
            text_max_lines=2,
            text_anim_enable=True,
            text_anim_duration_ms=180,
            text_anim_fade_px=24,
            text_anim_offset_y=12,
        )
        spec = get_style(DEFAULT_STYLE_ID).build_spec(args)
        self.assertIsInstance(spec, SubtitleStyleSpec)
        self.assertEqual(spec.font_family, "Microsoft YaHei")
        self.assertEqual(spec.font_size, 30)
        self.assertEqual(spec.text_color, "#000000")

    def test_list_styles_contains_default_style(self) -> None:
        style_ids = [style.style_id for style in list_styles()]
        self.assertIn(DEFAULT_STYLE_ID, style_ids)
