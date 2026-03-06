from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QBrush, QFont, QFontMetrics, QLinearGradient, QPainter, QPen, QPixmap


def build_centered_draw_rect(font: QFont, container_rect: QRect, text: str) -> QRect:
    metrics = QFontMetrics(font)
    measure_bounds = QRect(0, 0, container_rect.width(), container_rect.height())
    measured = metrics.boundingRect(
        measure_bounds,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
        text,
    )
    draw_width = max(1, min(container_rect.width(), measured.width()))
    draw_height = max(1, min(container_rect.height(), measured.height()))
    draw_x = container_rect.left() + max(0, (container_rect.width() - draw_width) // 2)
    draw_y = container_rect.top() + max(0, (container_rect.height() - draw_height) // 2)
    return QRect(draw_x, draw_y, draw_width, draw_height)


def draw_text(painter: QPainter, font: QFont, text_rect: QRect, text: str, color: QColor) -> None:
    painter.setPen(color)
    painter.setFont(font)
    painter.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
        text,
    )


def draw_edit_guides(
    painter: QPainter,
    font: QFont,
    widget_rect: QRect,
    text_rect: QRect,
    handle_rects: list[QRect],
    bg_rect: QRect,
    has_background: bool,
) -> None:
    painter.save()
    guide_pen = QPen(QColor(0, 220, 255, 230), 1, Qt.PenStyle.DashLine)
    painter.setPen(guide_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(text_rect)

    for handle_rect in handle_rects:
        painter.fillRect(handle_rect, QColor(0, 220, 255, 200))
        painter.drawRect(handle_rect)

    if has_background:
        bg_pen = QPen(QColor(255, 200, 0, 220), 1, Qt.PenStyle.DashLine)
        painter.setPen(bg_pen)
        painter.drawRect(bg_rect)

    painter.setPen(QColor(255, 255, 255, 220))
    painter.setFont(QFont(font.family(), max(9, font.pointSize() - 5)))
    painter.drawText(
        widget_rect.adjusted(8, 6, -8, -6),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        "编辑模式: 拖拽文本框可移动/缩放, 拖拽背景可调整位置, F2退出",
    )
    painter.restore()


def draw_reveal_text(
    painter: QPainter,
    font: QFont,
    text_rect: QRect,
    text: str,
    color: QColor,
    progress: float,
    fade_px: int,
) -> None:
    clamped_progress = min(1.0, max(0.0, progress))
    if clamped_progress >= 0.999:
        draw_text(painter, font, text_rect, text, color)
        return

    total_w = max(1, text_rect.width())
    front_w = max(0, min(total_w, int(round(total_w * clamped_progress))))
    if front_w <= 0:
        return

    fade_w = max(1, min(fade_px, front_w))
    solid_w = max(0, front_w - fade_w)

    if solid_w > 0:
        painter.save()
        painter.setClipRect(QRect(text_rect.left(), text_rect.top(), solid_w, text_rect.height()))
        draw_text(painter, font, text_rect, text, color)
        painter.restore()

    fade_left = text_rect.left() + solid_w
    fade_right = text_rect.left() + front_w
    fade_width = max(1, fade_right - fade_left)
    gradient = QLinearGradient(float(fade_left), 0.0, float(fade_right), 0.0)
    color_opaque = QColor(color)
    color_transparent = QColor(color)
    color_transparent.setAlpha(0)
    gradient.setColorAt(0.0, color_opaque)
    gradient.setColorAt(1.0, color_transparent)

    painter.save()
    painter.setClipRect(QRect(fade_left, text_rect.top(), fade_width, text_rect.height()))
    painter.setPen(QPen(QBrush(gradient), 1))
    painter.setFont(font)
    painter.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
        text,
    )
    painter.restore()


def draw_background(painter: QPainter, bg_rect: QRect, bg_pixmap: QPixmap) -> None:
    if bg_pixmap.isNull():
        return
    painter.drawPixmap(bg_rect, bg_pixmap, bg_pixmap.rect())
