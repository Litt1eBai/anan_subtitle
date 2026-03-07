from enum import Enum

from PySide6.QtCore import Qt


class OverlayWindowAction(Enum):
    NONE = "none"
    HIDE = "hide"
    CLOSE = "close"


def build_overlay_window_flags(*, windowed_mode: bool, stay_on_top: bool) -> Qt.WindowType:
    if windowed_mode:
        flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
    else:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
    if stay_on_top:
        flags |= Qt.WindowType.WindowStaysOnTopHint
    return flags


def resolve_escape_action(*, hide_to_tray_on_close: bool) -> OverlayWindowAction:
    if hide_to_tray_on_close:
        return OverlayWindowAction.HIDE
    return OverlayWindowAction.CLOSE


def resolve_close_action(*, hide_to_tray_on_close: bool) -> OverlayWindowAction:
    if hide_to_tray_on_close:
        return OverlayWindowAction.HIDE
    return OverlayWindowAction.NONE
