from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt

from presentation.qt.overlay_window_behavior import build_overlay_window_flags


@dataclass(frozen=True)
class OverlayWindowRefreshState:
    geometry: QRect
    restore_visibility: bool
    request_update: bool


def apply_overlay_window_flags(widget, *, windowed_mode: bool, stay_on_top: bool) -> None:
    widget.setWindowFlags(
        build_overlay_window_flags(
            windowed_mode=windowed_mode,
            stay_on_top=stay_on_top,
        )
    )
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)



def build_overlay_window_refresh_state(
    geometry: QRect,
    *,
    was_visible: bool,
    request_update: bool,
) -> OverlayWindowRefreshState:
    return OverlayWindowRefreshState(
        geometry=QRect(geometry),
        restore_visibility=bool(was_visible),
        request_update=bool(request_update),
    )



def refresh_overlay_window_shell(
    widget,
    *,
    windowed_mode: bool,
    stay_on_top: bool,
    geometry: QRect,
    was_visible: bool,
    request_update: bool,
) -> None:
    apply_overlay_window_flags(
        widget,
        windowed_mode=windowed_mode,
        stay_on_top=stay_on_top,
    )
    refresh_state = build_overlay_window_refresh_state(
        geometry,
        was_visible=was_visible,
        request_update=request_update,
    )
    widget.setGeometry(refresh_state.geometry)
    if refresh_state.restore_visibility:
        widget.show()
    if refresh_state.request_update:
        widget.update()
