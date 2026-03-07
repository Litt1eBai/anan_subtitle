from dataclasses import asdict, dataclass, replace
from typing import Any


@dataclass
class SubtitleViewState:
    subtitle_text: str = ""
    status_text: str = "模型加载中..."
    animation_progress: float = 1.0
    animation_start_progress: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubtitleStyleSpec:
    font_family: str
    font_size: int
    text_color: str
    text_max_lines: int
    text_anim_enable: bool
    text_anim_duration_ms: int
    text_anim_fade_px: int
    text_anim_offset_y: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OverlayRuntimeSettings:
    x: int
    y: int
    width: int
    height: int
    windowed_mode: bool
    stay_on_top: bool
    font_size: int
    text_x: int
    text_y: int
    text_width: int
    text_height: int
    bg_width: int
    bg_height: int
    bg_offset_x: int
    bg_offset_y: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def set_runtime_flag(
    settings: OverlayRuntimeSettings,
    *,
    field_name: str,
    value: bool,
) -> OverlayRuntimeSettings | None:
    target = bool(value)
    if bool(getattr(settings, field_name)) == target:
        return None
    return replace(settings, **{field_name: target})



def set_runtime_font_size(
    settings: OverlayRuntimeSettings,
    size: int,
) -> OverlayRuntimeSettings | None:
    target = max(8, int(size))
    if settings.font_size == target:
        return None
    return replace(settings, font_size=target)



def set_runtime_bg_offset(
    settings: OverlayRuntimeSettings,
    offset_x: int,
    offset_y: int,
) -> OverlayRuntimeSettings | None:
    next_x = int(offset_x)
    next_y = int(offset_y)
    if settings.bg_offset_x == next_x and settings.bg_offset_y == next_y:
        return None
    return replace(settings, bg_offset_x=next_x, bg_offset_y=next_y)



def resolve_bg_draw_size(
    settings: OverlayRuntimeSettings,
    *,
    bg_native_width: int,
    bg_native_height: int,
) -> tuple[int, int]:
    if bg_native_width <= 0 or bg_native_height <= 0:
        return 0, 0
    draw_w = settings.bg_width if settings.bg_width > 0 else bg_native_width
    draw_h = settings.bg_height if settings.bg_height > 0 else bg_native_height
    return max(1, draw_w), max(1, draw_h)



def set_runtime_bg_size(
    settings: OverlayRuntimeSettings,
    width: int,
    height: int,
    *,
    lock_size_to_bg: bool,
    bg_native_width: int,
    bg_native_height: int,
) -> OverlayRuntimeSettings | None:
    next_w = max(0, int(width))
    next_h = max(0, int(height))
    if settings.bg_width == next_w and settings.bg_height == next_h:
        return None
    updated = replace(settings, bg_width=next_w, bg_height=next_h)
    if lock_size_to_bg:
        draw_w, draw_h = resolve_bg_draw_size(
            updated,
            bg_native_width=bg_native_width,
            bg_native_height=bg_native_height,
        )
        if draw_w > 0 and draw_h > 0:
            updated = replace(updated, width=draw_w, height=draw_h)
    return updated



def normalize_text_box(
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    overlay_width: int,
    overlay_height: int,
) -> tuple[int, int, int, int]:
    safe_w = max(1, min(int(width), max(1, overlay_width)))
    safe_h = max(1, min(int(height), max(1, overlay_height)))
    safe_x = max(0, min(int(x), max(1, overlay_width) - safe_w))
    safe_y = max(0, min(int(y), max(1, overlay_height) - safe_h))
    return safe_x, safe_y, safe_w, safe_h



def set_runtime_text_box(
    settings: OverlayRuntimeSettings,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    overlay_width: int,
    overlay_height: int,
) -> OverlayRuntimeSettings | None:
    safe_x, safe_y, safe_w, safe_h = normalize_text_box(
        x=x,
        y=y,
        width=width,
        height=height,
        overlay_width=overlay_width,
        overlay_height=overlay_height,
    )
    if (
        settings.text_x == safe_x
        and settings.text_y == safe_y
        and settings.text_width == safe_w
        and settings.text_height == safe_h
    ):
        return None
    return replace(
        settings,
        text_x=safe_x,
        text_y=safe_y,
        text_width=safe_w,
        text_height=safe_h,
    )



def resolve_text_box(
    settings: OverlayRuntimeSettings,
    *,
    overlay_width: int,
    overlay_height: int,
) -> tuple[int, int, int, int]:
    max_x = max(0, overlay_width - 1)
    max_y = max(0, overlay_height - 1)
    text_x = min(settings.text_x, max_x)
    text_y = min(settings.text_y, max_y)
    available_w = max(1, overlay_width - text_x)
    available_h = max(1, overlay_height - text_y)
    text_w = settings.text_width if settings.text_width > 0 else available_w
    text_h = settings.text_height if settings.text_height > 0 else available_h
    return (
        text_x,
        text_y,
        max(1, min(text_w, available_w)),
        max(1, min(text_h, available_h)),
    )
