import argparse

from PySide6.QtGui import QColor

from presentation.model import OverlayRuntimeSettings, SubtitleStyleSpec, resolve_bg_draw_size
from presentation.styles import DEFAULT_STYLE_ID, get_style


def build_overlay_style_spec(args: argparse.Namespace) -> SubtitleStyleSpec:
    style = get_style(getattr(args, "subtitle_style", DEFAULT_STYLE_ID))
    return style.build_spec(args)


def build_overlay_runtime_settings(
    args: argparse.Namespace,
    style_spec: SubtitleStyleSpec,
) -> OverlayRuntimeSettings:
    return OverlayRuntimeSettings(
        x=int(args.x),
        y=int(args.y),
        width=max(1, int(args.width)),
        height=max(1, int(args.height)),
        windowed_mode=bool(args.windowed_mode),
        stay_on_top=bool(args.stay_on_top),
        font_size=style_spec.font_size,
        text_x=max(0, args.text_x),
        text_y=max(0, args.text_y),
        text_width=max(0, args.text_width),
        text_height=max(0, args.text_height),
        bg_width=max(0, int(args.bg_width)),
        bg_height=max(0, int(args.bg_height)),
        bg_offset_x=int(args.bg_offset_x),
        bg_offset_y=int(args.bg_offset_y),
    )


def resolve_initial_overlay_size(
    settings: OverlayRuntimeSettings,
    *,
    lock_size_to_bg: bool,
    bg_native_width: int,
    bg_native_height: int,
) -> tuple[int, int]:
    if not lock_size_to_bg:
        return settings.width, settings.height
    draw_w, draw_h = resolve_bg_draw_size(
        settings,
        bg_native_width=bg_native_width,
        bg_native_height=bg_native_height,
    )
    if draw_w <= 0 or draw_h <= 0:
        return settings.width, settings.height
    return draw_w, draw_h


def build_overlay_text_color(color_value: str) -> QColor:
    color = QColor(color_value)
    if color.isValid():
        return color
    return QColor(0, 0, 0)
