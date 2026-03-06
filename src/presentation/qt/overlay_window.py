import argparse
from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, QElapsedTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QCloseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from presentation.model import OverlayRuntimeSettings, SubtitleStyleSpec, SubtitleViewState
from presentation.qt.overlay_interaction import build_text_handle_rects, hit_test_text_interaction, resize_text_rect
from presentation.qt.overlay_renderer import (
    build_centered_draw_rect,
    draw_background,
    draw_edit_guides,
    draw_reveal_text,
    draw_text,
)


class SubtitleOverlay(QWidget):
    settings_changed = Signal(dict)
    edit_mode_changed = Signal(bool)
    visibility_changed = Signal(bool)

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__()
        self._view_state = SubtitleViewState()
        self._style_spec = SubtitleStyleSpec(
            font_family=str(args.font_family),
            font_size=max(8, int(args.font_size)),
            text_color=str(args.text_color),
            text_max_lines=max(1, args.text_max_lines),
            text_anim_enable=bool(args.text_anim_enable),
            text_anim_duration_ms=max(0, args.text_anim_duration_ms),
            text_anim_fade_px=max(1, args.text_anim_fade_px),
            text_anim_offset_y=max(0, args.text_anim_offset_y),
        )
        self._runtime_settings = OverlayRuntimeSettings(
            x=int(args.x),
            y=int(args.y),
            width=max(1, int(args.width)),
            height=max(1, int(args.height)),
            windowed_mode=bool(args.windowed_mode),
            stay_on_top=bool(args.stay_on_top),
            font_size=self._style_spec.font_size,
            text_x=max(0, args.text_x),
            text_y=max(0, args.text_y),
            text_width=max(0, args.text_width),
            text_height=max(0, args.text_height),
            bg_width=max(0, int(args.bg_width)),
            bg_height=max(0, int(args.bg_height)),
            bg_offset_x=int(args.bg_offset_x),
            bg_offset_y=int(args.bg_offset_y),
        )
        self._interaction_mode: str | None = None
        self._drag_origin: QPoint | None = None
        self._win_origin: QPoint | None = None
        self._drag_start_text_rect: QRect | None = None
        self._drag_start_bg_offset: QPoint | None = None
        self._min_text_box_size = 40
        self._handle_size = 10
        self._edit_mode = False
        self._hide_to_tray_on_close = bool(args.tray_icon_enable)
        self._clear_after_ms = max(0, args.subtitle_clear_ms)
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self.clear_subtitle)
        self._bg_pixmap = QPixmap(args.bg_image) if args.bg_image else QPixmap()
        self._lock_size_to_bg = bool(args.lock_size_to_bg)
        self._font = QFont(self._style_spec.font_family, self._style_spec.font_size)
        self._text_anim_clock = QElapsedTimer()
        self._text_anim_timer = QTimer(self)
        self._text_anim_timer.setInterval(16)
        self._text_anim_timer.timeout.connect(self._tick_text_animation)
        self._text_color = QColor(self._style_spec.text_color)
        if not self._text_color.isValid():
            self._text_color = QColor(0, 0, 0)

        self.setWindowTitle("Desktop Subtitle")
        overlay_width = self._runtime_settings.width
        overlay_height = self._runtime_settings.height
        if self._lock_size_to_bg and not self._bg_pixmap.isNull():
            overlay_width, overlay_height = self._resolved_bg_size()
            self._runtime_settings.width = overlay_width
            self._runtime_settings.height = overlay_height
        self.setGeometry(self._runtime_settings.x, self._runtime_settings.y, overlay_width, overlay_height)
        self._apply_window_flags()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(args.opacity)

    def _apply_window_flags(self) -> None:
        if self._runtime_settings.windowed_mode:
            flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        else:
            flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self._runtime_settings.stay_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def export_view_state(self) -> SubtitleViewState:
        return SubtitleViewState(**self._view_state.to_dict())

    def apply_view_state(self, view_state: SubtitleViewState) -> None:
        self.set_status(view_state.status_text)
        if view_state.subtitle_text.strip():
            self.set_subtitle(view_state.subtitle_text)
            return
        self.clear_subtitle()

    def export_style_spec(self) -> SubtitleStyleSpec:
        return SubtitleStyleSpec(**self._style_spec.to_dict())

    def export_runtime_settings_model(self) -> OverlayRuntimeSettings:
        geometry = self.geometry()
        text_rect = self._build_text_rect()
        return OverlayRuntimeSettings(
            x=int(geometry.x()),
            y=int(geometry.y()),
            width=int(geometry.width()),
            height=int(geometry.height()),
            windowed_mode=bool(self._runtime_settings.windowed_mode),
            stay_on_top=bool(self._runtime_settings.stay_on_top),
            font_size=int(self._font.pointSize()),
            text_x=int(text_rect.x()),
            text_y=int(text_rect.y()),
            text_width=int(text_rect.width()),
            text_height=int(text_rect.height()),
            bg_width=int(self._runtime_settings.bg_width),
            bg_height=int(self._runtime_settings.bg_height),
            bg_offset_x=int(self._runtime_settings.bg_offset_x),
            bg_offset_y=int(self._runtime_settings.bg_offset_y),
        )

    def export_runtime_settings(self) -> dict[str, Any]:
        return self.export_runtime_settings_model().to_dict()

    def _emit_settings_changed(self) -> None:
        self._runtime_settings = self.export_runtime_settings_model()
        self.settings_changed.emit(self._runtime_settings.to_dict())

    def is_edit_mode(self) -> bool:
        return self._edit_mode

    def is_windowed_mode(self) -> bool:
        return self._runtime_settings.windowed_mode

    def set_edit_mode(self, enabled: bool) -> None:
        target = bool(enabled)
        if self._edit_mode == target:
            return
        self._edit_mode = target
        self.edit_mode_changed.emit(self._edit_mode)
        self.update()

    def set_stay_on_top(self, enabled: bool) -> None:
        target = bool(enabled)
        if self._runtime_settings.stay_on_top == target:
            return
        self._runtime_settings.stay_on_top = target
        geometry = self.geometry()
        was_visible = self.isVisible()
        self._apply_window_flags()
        self.setGeometry(geometry)
        if was_visible:
            self.show()
        self._emit_settings_changed()

    def set_windowed_mode(self, enabled: bool) -> None:
        target = bool(enabled)
        if self._runtime_settings.windowed_mode == target:
            return
        self._runtime_settings.windowed_mode = target
        geometry = self.geometry()
        was_visible = self.isVisible()
        self._apply_window_flags()
        self.setGeometry(geometry)
        if was_visible:
            self.show()
        self.update()
        self._emit_settings_changed()

    def set_font_size(self, size: int) -> None:
        target = max(8, int(size))
        if self._font.pointSize() == target:
            return
        self._style_spec.font_size = target
        self._runtime_settings.font_size = target
        self._font = QFont(self._font.family(), target)
        self.update()
        self._emit_settings_changed()

    def set_bg_offset(self, offset_x: int, offset_y: int) -> None:
        next_x = int(offset_x)
        next_y = int(offset_y)
        if self._runtime_settings.bg_offset_x == next_x and self._runtime_settings.bg_offset_y == next_y:
            return
        self._runtime_settings.bg_offset_x = next_x
        self._runtime_settings.bg_offset_y = next_y
        self.update()
        self._emit_settings_changed()

    def set_bg_size(self, width: int, height: int) -> None:
        next_w = max(0, int(width))
        next_h = max(0, int(height))
        if self._runtime_settings.bg_width == next_w and self._runtime_settings.bg_height == next_h:
            return
        self._runtime_settings.bg_width = next_w
        self._runtime_settings.bg_height = next_h
        if self._lock_size_to_bg and not self._bg_pixmap.isNull():
            draw_w, draw_h = self._resolved_bg_size()
            self.resize(draw_w, draw_h)
            self._runtime_settings.width = draw_w
            self._runtime_settings.height = draw_h
        self.update()
        self._emit_settings_changed()

    def _resolved_bg_size(self) -> tuple[int, int]:
        if self._bg_pixmap.isNull():
            return 0, 0
        draw_w = self._runtime_settings.bg_width if self._runtime_settings.bg_width > 0 else self._bg_pixmap.width()
        draw_h = self._runtime_settings.bg_height if self._runtime_settings.bg_height > 0 else self._bg_pixmap.height()
        return max(1, draw_w), max(1, draw_h)

    def _ensure_explicit_text_box(self, text_rect: QRect) -> None:
        if self._runtime_settings.text_width > 0 and self._runtime_settings.text_height > 0:
            return
        self._runtime_settings.text_x = text_rect.x()
        self._runtime_settings.text_y = text_rect.y()
        self._runtime_settings.text_width = text_rect.width()
        self._runtime_settings.text_height = text_rect.height()

    def set_text_box(self, x: int, y: int, width: int, height: int) -> None:
        overlay_width = max(1, self.width())
        overlay_height = max(1, self.height())
        safe_w = max(1, min(int(width), overlay_width))
        safe_h = max(1, min(int(height), overlay_height))
        safe_x = max(0, min(int(x), overlay_width - safe_w))
        safe_y = max(0, min(int(y), overlay_height - safe_h))

        if (
            self._runtime_settings.text_x == safe_x
            and self._runtime_settings.text_y == safe_y
            and self._runtime_settings.text_width == safe_w
            and self._runtime_settings.text_height == safe_h
        ):
            return
        self._runtime_settings.text_x = safe_x
        self._runtime_settings.text_y = safe_y
        self._runtime_settings.text_width = safe_w
        self._runtime_settings.text_height = safe_h
        self.update()
        self._emit_settings_changed()

    def set_subtitle(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            self.clear_subtitle()
            return
        if cleaned == self._view_state.subtitle_text:
            if self._clear_after_ms > 0:
                self._clear_timer.start(self._clear_after_ms)
            return
        previous = self._view_state.subtitle_text
        self._view_state.subtitle_text = cleaned
        if self._style_spec.text_anim_enable:
            self._start_text_animation(self._calc_start_progress(previous, cleaned))
        else:
            self._text_anim_timer.stop()
            self._view_state.animation_progress = 1.0
        if self._clear_after_ms > 0:
            self._clear_timer.start(self._clear_after_ms)
        else:
            self._clear_timer.stop()
        self.update()

    def set_status(self, text: str) -> None:
        cleaned = text.strip()
        if self._view_state.status_text == cleaned:
            return
        self._view_state.status_text = cleaned
        if not self._view_state.subtitle_text:
            self.update()

    def clear_subtitle(self) -> None:
        self._clear_timer.stop()
        self._text_anim_timer.stop()
        self._view_state.animation_progress = 1.0
        self._view_state.animation_start_progress = 0.0
        if not self._view_state.subtitle_text:
            return
        self._view_state.subtitle_text = ""
        self.update()

    def _start_text_animation(self, start_progress: float = 0.0) -> None:
        if not self._style_spec.text_anim_enable or self._style_spec.text_anim_duration_ms <= 0:
            self._view_state.animation_progress = 1.0
            self._text_anim_timer.stop()
            return
        clamped = min(1.0, max(0.0, start_progress))
        self._view_state.animation_start_progress = clamped
        self._view_state.animation_progress = clamped
        if clamped >= 1.0:
            self._text_anim_timer.stop()
            return
        self._text_anim_clock.restart()
        self._text_anim_timer.start()

    def _tick_text_animation(self) -> None:
        if self._style_spec.text_anim_duration_ms <= 0:
            self._text_anim_timer.stop()
            self._view_state.animation_progress = 1.0
            self.update()
            return
        elapsed_ms = self._text_anim_clock.elapsed()
        linear = min(1.0, max(0.0, elapsed_ms / float(self._style_spec.text_anim_duration_ms)))
        self._view_state.animation_progress = self._view_state.animation_start_progress + (
            1.0 - self._view_state.animation_start_progress
        ) * linear
        self.update()
        if linear >= 1.0:
            self._text_anim_timer.stop()

    @staticmethod
    def _common_prefix_len(a: str, b: str) -> int:
        length = min(len(a), len(b))
        index = 0
        while index < length and a[index] == b[index]:
            index += 1
        return index

    def _calc_start_progress(self, previous: str, current: str) -> float:
        if not previous or not current:
            return 0.0
        common = self._common_prefix_len(previous, current)
        if common <= 0:
            return 0.0
        return min(1.0, common / float(len(current)))

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        bg_rect = self._build_bg_rect()
        draw_background(painter, bg_rect, self._bg_pixmap)

        text_rect = self._build_text_rect()
        max_height = QFontMetrics(self._font).lineSpacing() * self._style_spec.text_max_lines
        text_rect.setHeight(min(text_rect.height(), max_height))
        draw_text_value = self._view_state.subtitle_text if self._view_state.subtitle_text else self._view_state.status_text
        if draw_text_value:
            draw_rect = build_centered_draw_rect(self._font, text_rect, draw_text_value)
            if self._view_state.subtitle_text and self._style_spec.text_anim_enable:
                draw_reveal_text(
                    painter,
                    self._font,
                    draw_rect,
                    draw_text_value,
                    self._text_color,
                    self._view_state.animation_progress,
                    self._style_spec.text_anim_fade_px,
                )
            else:
                draw_text(painter, self._font, draw_rect, draw_text_value, self._text_color)

        if self._edit_mode:
            draw_edit_guides(
                painter,
                self._font,
                self.rect(),
                text_rect,
                list(build_text_handle_rects(text_rect, self._handle_size).values()),
                bg_rect,
                not self._bg_pixmap.isNull(),
            )

    def _build_bg_rect(self) -> QRect:
        if self._bg_pixmap.isNull():
            return QRect()
        draw_w, draw_h = self._resolved_bg_size()
        return QRect(
            self._runtime_settings.bg_offset_x,
            self._runtime_settings.bg_offset_y,
            draw_w,
            draw_h,
        )

    def _build_text_rect(self) -> QRect:
        rect = self.rect()
        max_x = max(0, rect.width() - 1)
        max_y = max(0, rect.height() - 1)
        text_x = min(self._runtime_settings.text_x, max_x)
        text_y = min(self._runtime_settings.text_y, max_y)

        available_w = max(1, rect.width() - text_x)
        available_h = max(1, rect.height() - text_y)
        text_w = self._runtime_settings.text_width if self._runtime_settings.text_width > 0 else available_w
        text_h = self._runtime_settings.text_height if self._runtime_settings.text_height > 0 else available_h

        return QRect(
            text_x,
            text_y,
            max(1, min(text_w, available_w)),
            max(1, min(text_h, available_h)),
        )

    def _hit_test_text_interaction(self, position: QPoint, text_rect: QRect) -> str | None:
        return hit_test_text_interaction(position, text_rect, self._handle_size)

    def _apply_text_resize_delta(self, handle: str, delta: QPoint) -> None:
        if self._drag_start_text_rect is None:
            return

        next_rect = resize_text_rect(
            start_rect=self._drag_start_text_rect,
            handle=handle,
            delta=delta,
            overlay_width=self.width(),
            overlay_height=self.height(),
            min_box_size=self._min_text_box_size,
        )
        self.set_text_box(next_rect.x(), next_rect.y(), next_rect.width(), next_rect.height())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_origin = event.globalPosition().toPoint()
        self._win_origin = self.frameGeometry().topLeft()
        self._interaction_mode = "move_window"
        self._drag_start_text_rect = None
        self._drag_start_bg_offset = None

        if not self._edit_mode:
            return

        local_pos = event.position().toPoint()
        text_rect = self._build_text_rect()
        interaction = self._hit_test_text_interaction(local_pos, text_rect)
        if interaction is not None:
            self._ensure_explicit_text_box(text_rect)
            self._drag_start_text_rect = QRect(
                self._runtime_settings.text_x,
                self._runtime_settings.text_y,
                max(1, self._runtime_settings.text_width),
                max(1, self._runtime_settings.text_height),
            )
            self._interaction_mode = f"text_{interaction}"
            return

        bg_rect = self._build_bg_rect()
        if not bg_rect.isNull() and bg_rect.contains(local_pos):
            self._drag_start_bg_offset = QPoint(self._runtime_settings.bg_offset_x, self._runtime_settings.bg_offset_y)
            self._interaction_mode = "move_bg"

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if (
            self._drag_origin is None
            or self._win_origin is None
            or self._interaction_mode is None
            or not (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            return
        delta = event.globalPosition().toPoint() - self._drag_origin
        if self._interaction_mode == "move_window":
            self.move(self._win_origin + delta)
            return
        if self._interaction_mode == "move_bg":
            if self._drag_start_bg_offset is None:
                return
            self.set_bg_offset(
                self._drag_start_bg_offset.x() + delta.x(),
                self._drag_start_bg_offset.y() + delta.y(),
            )
            return
        if self._interaction_mode == "text_move":
            if self._drag_start_text_rect is None:
                return
            start = self._drag_start_text_rect
            self.set_text_box(
                start.x() + delta.x(),
                start.y() + delta.y(),
                start.width(),
                start.height(),
            )
            return
        if self._interaction_mode.startswith("text_"):
            handle = self._interaction_mode.removeprefix("text_")
            self._apply_text_resize_delta(handle, delta)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        del event
        if self._interaction_mode == "move_window":
            self._emit_settings_changed()
        self._drag_origin = None
        self._win_origin = None
        self._drag_start_text_rect = None
        self._drag_start_bg_offset = None
        self._interaction_mode = None

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            if self._hide_to_tray_on_close:
                self.hide()
                self._emit_settings_changed()
            else:
                self.close()
            return
        if event.key() == Qt.Key.Key_F2:
            self.set_edit_mode(not self._edit_mode)
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._hide_to_tray_on_close:
            event.ignore()
            self.hide()
            self._emit_settings_changed()
            return
        super().closeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self.visibility_changed.emit(False)

