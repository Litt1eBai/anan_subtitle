import argparse
from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, QElapsedTimer, Signal
from PySide6.QtGui import QFont, QCloseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from presentation.model import (
    OverlayRuntimeSettings,
    SubtitleStyleSpec,
    SubtitleViewState,
    advance_animation,
    clear_subtitle_text,
    set_status_text,
    set_subtitle_text,
    resolve_bg_draw_size,
    set_runtime_bg_offset,
    set_runtime_bg_size,
    set_runtime_flag,
    set_runtime_font_size,
    set_runtime_text_box,
)
from presentation.qt.overlay_geometry import (
    build_overlay_bg_rect,
    build_overlay_text_rect,
    export_runtime_settings_snapshot,
)
from presentation.qt.overlay_window_behavior import OverlayWindowAction
from presentation.qt.overlay_window_events import (
    OverlayKeyAction,
    resolve_overlay_close_event_action,
    resolve_overlay_key_action,
    should_emit_settings_after_drag_release,
)
from presentation.qt.overlay_window_shell import (
    apply_overlay_window_flags,
    refresh_overlay_window_shell,
)
from presentation.qt.overlay_interaction import (
    OverlayDragState,
    begin_overlay_drag,
    build_text_handle_rects,
    resolve_overlay_drag_update,
)
from presentation.qt.overlay_window_setup import (
    build_overlay_runtime_settings,
    build_overlay_style_spec,
    build_overlay_text_color,
    resolve_initial_overlay_size,
)
from presentation.qt.overlay_renderer import (
    build_overlay_text_layout,
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
        self._style_spec = build_overlay_style_spec(args)
        self._runtime_settings = build_overlay_runtime_settings(args, self._style_spec)
        self._drag_state = OverlayDragState()
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
        self._text_color = build_overlay_text_color(self._style_spec.text_color)

        self.setWindowTitle("Desktop Subtitle")
        overlay_width, overlay_height = resolve_initial_overlay_size(
            self._runtime_settings,
            lock_size_to_bg=self._lock_size_to_bg,
            bg_native_width=self._bg_pixmap.width(),
            bg_native_height=self._bg_pixmap.height(),
        )
        self._runtime_settings.width = overlay_width
        self._runtime_settings.height = overlay_height
        self.setGeometry(self._runtime_settings.x, self._runtime_settings.y, overlay_width, overlay_height)
        self._apply_window_flags()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(args.opacity)

    def _apply_window_flags(self) -> None:
        apply_overlay_window_flags(
            self,
            windowed_mode=self._runtime_settings.windowed_mode,
            stay_on_top=self._runtime_settings.stay_on_top,
        )

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
        return export_runtime_settings_snapshot(
            geometry=self.geometry(),
            text_rect=self._build_text_rect(),
            settings=self._runtime_settings,
            font_size=self._font.pointSize(),
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
        updated = set_runtime_flag(self._runtime_settings, field_name="stay_on_top", value=enabled)
        if updated is None:
            return
        self._runtime_settings = updated
        refresh_overlay_window_shell(
            self,
            windowed_mode=self._runtime_settings.windowed_mode,
            stay_on_top=self._runtime_settings.stay_on_top,
            geometry=self.geometry(),
            was_visible=self.isVisible(),
            request_update=False,
        )
        self._emit_settings_changed()

    def set_windowed_mode(self, enabled: bool) -> None:
        updated = set_runtime_flag(self._runtime_settings, field_name="windowed_mode", value=enabled)
        if updated is None:
            return
        self._runtime_settings = updated
        refresh_overlay_window_shell(
            self,
            windowed_mode=self._runtime_settings.windowed_mode,
            stay_on_top=self._runtime_settings.stay_on_top,
            geometry=self.geometry(),
            was_visible=self.isVisible(),
            request_update=True,
        )
        self._emit_settings_changed()

    def set_font_size(self, size: int) -> None:
        updated = set_runtime_font_size(self._runtime_settings, size)
        if updated is None:
            return
        self._runtime_settings = updated
        self._style_spec.font_size = updated.font_size
        self._font = QFont(self._font.family(), updated.font_size)
        self.update()
        self._emit_settings_changed()

    def set_bg_offset(self, offset_x: int, offset_y: int) -> None:
        updated = set_runtime_bg_offset(self._runtime_settings, offset_x, offset_y)
        if updated is None:
            return
        self._runtime_settings = updated
        self.update()
        self._emit_settings_changed()

    def set_bg_size(self, width: int, height: int) -> None:
        updated = set_runtime_bg_size(
            self._runtime_settings,
            width,
            height,
            lock_size_to_bg=self._lock_size_to_bg,
            bg_native_width=self._bg_pixmap.width(),
            bg_native_height=self._bg_pixmap.height(),
        )
        if updated is None:
            return
        self._runtime_settings = updated
        if self._lock_size_to_bg and not self._bg_pixmap.isNull():
            self.resize(updated.width, updated.height)
        self.update()
        self._emit_settings_changed()

    def _resolved_bg_size(self) -> tuple[int, int]:
        return resolve_bg_draw_size(
            self._runtime_settings,
            bg_native_width=self._bg_pixmap.width(),
            bg_native_height=self._bg_pixmap.height(),
        )

    def set_text_box(self, x: int, y: int, width: int, height: int) -> None:
        updated = set_runtime_text_box(
            self._runtime_settings,
            x=x,
            y=y,
            width=width,
            height=height,
            overlay_width=self.width(),
            overlay_height=self.height(),
        )
        if updated is None:
            return
        self._runtime_settings = updated
        self.update()
        self._emit_settings_changed()

    def set_subtitle(self, text: str) -> None:
        updated = set_subtitle_text(
            self._view_state,
            text,
            text_anim_enabled=self._style_spec.text_anim_enable,
        )
        if updated is None:
            if text.strip() and self._clear_after_ms > 0:
                self._clear_timer.start(self._clear_after_ms)
            return
        self._view_state = updated
        if self._style_spec.text_anim_enable and self._view_state.animation_progress < 1.0:
            self._start_text_animation(self._view_state.animation_start_progress)
        else:
            self._text_anim_timer.stop()
        if self._clear_after_ms > 0:
            self._clear_timer.start(self._clear_after_ms)
        else:
            self._clear_timer.stop()
        self.update()

    def set_status(self, text: str) -> None:
        updated = set_status_text(self._view_state, text)
        if updated is None:
            return
        self._view_state = updated
        if not self._view_state.subtitle_text:
            self.update()

    def clear_subtitle(self) -> None:
        self._clear_timer.stop()
        self._text_anim_timer.stop()
        updated = clear_subtitle_text(self._view_state)
        if updated is None:
            return
        self._view_state = updated
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
        self._view_state, finished = advance_animation(
            self._view_state,
            elapsed_ms=self._text_anim_clock.elapsed(),
            duration_ms=self._style_spec.text_anim_duration_ms,
        )
        self.update()
        if finished:
            self._text_anim_timer.stop()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        bg_rect = self._build_bg_rect()
        draw_background(painter, bg_rect, self._bg_pixmap)

        text_rect = self._build_text_rect()
        text_layout = build_overlay_text_layout(
            self._font,
            text_rect,
            subtitle_text=self._view_state.subtitle_text,
            status_text=self._view_state.status_text,
            text_max_lines=self._style_spec.text_max_lines,
            text_anim_enable=self._style_spec.text_anim_enable,
        )
        if text_layout is not None:
            if text_layout.use_reveal:
                draw_reveal_text(
                    painter,
                    self._font,
                    text_layout.draw_rect,
                    text_layout.text,
                    self._text_color,
                    self._view_state.animation_progress,
                    self._style_spec.text_anim_fade_px,
                )
            else:
                draw_text(painter, self._font, text_layout.draw_rect, text_layout.text, self._text_color)

        if self._edit_mode:
            guide_text_rect = text_layout.text_rect if text_layout is not None else text_rect
            draw_edit_guides(
                painter,
                self._font,
                self.rect(),
                guide_text_rect,
                list(build_text_handle_rects(guide_text_rect, self._handle_size).values()),
                bg_rect,
                not self._bg_pixmap.isNull(),
            )

    def _build_bg_rect(self) -> QRect:
        draw_w, draw_h = self._resolved_bg_size()
        return build_overlay_bg_rect(
            self._runtime_settings,
            bg_width=draw_w,
            bg_height=draw_h,
        )

    def _build_text_rect(self) -> QRect:
        return build_overlay_text_rect(
            self._runtime_settings,
            overlay_width=self.width(),
            overlay_height=self.height(),
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_state = begin_overlay_drag(
            global_pos=event.globalPosition().toPoint(),
            window_origin=self.frameGeometry().topLeft(),
            local_pos=event.position().toPoint(),
            edit_mode=self._edit_mode,
            text_rect=self._build_text_rect(),
            bg_rect=self._build_bg_rect(),
            bg_offset=QPoint(self._runtime_settings.bg_offset_x, self._runtime_settings.bg_offset_y),
            handle_size=self._handle_size,
        )

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_state.drag_origin is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        delta = event.globalPosition().toPoint() - self._drag_state.drag_origin
        update = resolve_overlay_drag_update(
            drag_state=self._drag_state,
            delta=delta,
            overlay_width=self.width(),
            overlay_height=self.height(),
            min_box_size=self._min_text_box_size,
        )
        if update is None:
            return
        if update.window_pos is not None:
            self.move(update.window_pos)
            return
        if update.bg_offset is not None:
            self.set_bg_offset(update.bg_offset.x(), update.bg_offset.y())
            return
        if update.text_rect is not None:
            self.set_text_box(
                update.text_rect.x(),
                update.text_rect.y(),
                update.text_rect.width(),
                update.text_rect.height(),
            )

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        del event
        if should_emit_settings_after_drag_release(self._drag_state.interaction_mode):
            self._emit_settings_changed()
        self._drag_state = OverlayDragState()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        action = resolve_overlay_key_action(
            int(event.key()),
            hide_to_tray_on_close=self._hide_to_tray_on_close,
        )
        if action == OverlayKeyAction.HIDE:
            self.hide()
            self._emit_settings_changed()
            return
        if action == OverlayKeyAction.CLOSE:
            self.close()
            return
        if action == OverlayKeyAction.TOGGLE_EDIT:
            self.set_edit_mode(not self._edit_mode)
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        action = resolve_overlay_close_event_action(hide_to_tray_on_close=self._hide_to_tray_on_close)
        if action == OverlayWindowAction.HIDE:
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
