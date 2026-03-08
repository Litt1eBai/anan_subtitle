from enum import Enum

from PySide6.QtCore import Qt

from presentation.qt.overlay_window_behavior import (
    OverlayWindowAction,
    resolve_close_action,
    resolve_escape_action,
)


class OverlayKeyAction(Enum):
    NONE = "none"
    HIDE = "hide"
    CLOSE = "close"
    TOGGLE_EDIT = "toggle_edit"



def resolve_overlay_key_action(
    key: int,
    *,
    hide_to_tray_on_close: bool,
) -> OverlayKeyAction:
    if key == int(Qt.Key.Key_Escape):
        action = resolve_escape_action(hide_to_tray_on_close=hide_to_tray_on_close)
        if action == OverlayWindowAction.HIDE:
            return OverlayKeyAction.HIDE
        if action == OverlayWindowAction.CLOSE:
            return OverlayKeyAction.CLOSE
    if key == int(Qt.Key.Key_F2):
        return OverlayKeyAction.TOGGLE_EDIT
    return OverlayKeyAction.NONE



def resolve_overlay_close_event_action(*, hide_to_tray_on_close: bool) -> OverlayWindowAction:
    return resolve_close_action(hide_to_tray_on_close=hide_to_tray_on_close)



def should_emit_settings_after_drag_release(interaction_mode: str | None) -> bool:
    return interaction_mode == "move_window"
