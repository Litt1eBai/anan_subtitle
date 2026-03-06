from PySide6.QtCore import QPoint, QRect


def build_text_handle_rects(text_rect: QRect, handle_size: int) -> dict[str, QRect]:
    half = handle_size // 2
    cx = text_rect.center().x()
    cy = text_rect.center().y()
    left = text_rect.left()
    right = text_rect.right()
    top = text_rect.top()
    bottom = text_rect.bottom()
    return {
        "top_left": QRect(left - half, top - half, handle_size, handle_size),
        "top": QRect(cx - half, top - half, handle_size, handle_size),
        "top_right": QRect(right - half, top - half, handle_size, handle_size),
        "right": QRect(right - half, cy - half, handle_size, handle_size),
        "bottom_right": QRect(right - half, bottom - half, handle_size, handle_size),
        "bottom": QRect(cx - half, bottom - half, handle_size, handle_size),
        "bottom_left": QRect(left - half, bottom - half, handle_size, handle_size),
        "left": QRect(left - half, cy - half, handle_size, handle_size),
    }


def hit_test_text_interaction(position: QPoint, text_rect: QRect, handle_size: int) -> str | None:
    for name, handle in build_text_handle_rects(text_rect, handle_size).items():
        if handle.contains(position):
            return name
    if text_rect.contains(position):
        return "move"
    return None


def resize_text_rect(
    start_rect: QRect,
    handle: str,
    delta: QPoint,
    overlay_width: int,
    overlay_height: int,
    min_box_size: int,
) -> QRect:
    left = start_rect.left()
    right = start_rect.right()
    top = start_rect.top()
    bottom = start_rect.bottom()
    dx = delta.x()
    dy = delta.y()

    if handle in {"left", "top_left", "bottom_left"}:
        left += dx
    if handle in {"right", "top_right", "bottom_right"}:
        right += dx
    if handle in {"top", "top_left", "top_right"}:
        top += dy
    if handle in {"bottom", "bottom_left", "bottom_right"}:
        bottom += dy

    overlay_right = max(0, overlay_width - 1)
    overlay_bottom = max(0, overlay_height - 1)
    left = max(0, min(left, overlay_right))
    right = max(0, min(right, overlay_right))
    top = max(0, min(top, overlay_bottom))
    bottom = max(0, min(bottom, overlay_bottom))

    if left > right:
        left, right = right, left
    if top > bottom:
        top, bottom = bottom, top

    if right - left + 1 < min_box_size:
        if handle in {"right", "top_right", "bottom_right"}:
            right = min(overlay_right, left + min_box_size - 1)
            left = max(0, right - min_box_size + 1)
        else:
            left = max(0, right - min_box_size + 1)
            right = min(overlay_right, left + min_box_size - 1)
    if bottom - top + 1 < min_box_size:
        if handle in {"bottom", "bottom_left", "bottom_right"}:
            bottom = min(overlay_bottom, top + min_box_size - 1)
            top = max(0, bottom - min_box_size + 1)
        else:
            top = max(0, bottom - min_box_size + 1)
            bottom = min(overlay_bottom, top + min_box_size - 1)

    return QRect(left, top, right - left + 1, bottom - top + 1)
