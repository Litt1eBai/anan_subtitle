from PySide6.QtCore import QRect

from presentation.model import OverlayRuntimeSettings, resolve_text_box


def build_overlay_bg_rect(
    settings: OverlayRuntimeSettings,
    *,
    bg_width: int,
    bg_height: int,
) -> QRect:
    if bg_width <= 0 or bg_height <= 0:
        return QRect()
    return QRect(
        settings.bg_offset_x,
        settings.bg_offset_y,
        bg_width,
        bg_height,
    )



def build_overlay_text_rect(
    settings: OverlayRuntimeSettings,
    *,
    overlay_width: int,
    overlay_height: int,
) -> QRect:
    text_x, text_y, text_w, text_h = resolve_text_box(
        settings,
        overlay_width=overlay_width,
        overlay_height=overlay_height,
    )
    return QRect(text_x, text_y, text_w, text_h)



def export_runtime_settings_snapshot(
    *,
    geometry: QRect,
    text_rect: QRect,
    settings: OverlayRuntimeSettings,
    font_size: int,
) -> OverlayRuntimeSettings:
    return OverlayRuntimeSettings(
        x=int(geometry.x()),
        y=int(geometry.y()),
        width=int(geometry.width()),
        height=int(geometry.height()),
        windowed_mode=bool(settings.windowed_mode),
        stay_on_top=bool(settings.stay_on_top),
        font_size=int(font_size),
        text_x=int(text_rect.x()),
        text_y=int(text_rect.y()),
        text_width=int(text_rect.width()),
        text_height=int(text_rect.height()),
        bg_width=int(settings.bg_width),
        bg_height=int(settings.bg_height),
        bg_offset_x=int(settings.bg_offset_x),
        bg_offset_y=int(settings.bg_offset_y),
    )
