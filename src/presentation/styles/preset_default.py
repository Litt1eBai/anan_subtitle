from argparse import Namespace

from presentation.model import SubtitleStyleSpec
from presentation.styles.base import DEFAULT_STYLE_ID


class DefaultSubtitleStyle:
    style_id = DEFAULT_STYLE_ID
    display_name = "默认样式"

    def build_spec(self, args: Namespace) -> SubtitleStyleSpec:
        return SubtitleStyleSpec(
            font_family=str(args.font_family),
            font_size=max(8, int(args.font_size)),
            text_color=str(args.text_color),
            text_max_lines=max(1, int(args.text_max_lines)),
            text_anim_enable=bool(args.text_anim_enable),
            text_anim_duration_ms=max(0, int(args.text_anim_duration_ms)),
            text_anim_fade_px=max(1, int(args.text_anim_fade_px)),
            text_anim_offset_y=max(0, int(args.text_anim_offset_y)),
        )
