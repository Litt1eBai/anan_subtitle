import argparse
import logging
import queue
import sys
import threading
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import yaml
from PySide6.QtCore import QPoint, QRect, Qt, Signal, QObject, QTimer, QElapsedTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPixmap,
    QLinearGradient,
    QPen,
    QBrush,
    QIcon,
    QCloseEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
)

from funasr import AutoModel

DEFAULT_CONFIG_PATH = "config/app.yaml"
LOGGER = logging.getLogger("desktop_subtitle")
OVERLAY_PERSIST_KEYS = {
    "x",
    "y",
    "width",
    "height",
    "windowed_mode",
    "stay_on_top",
    "font_size",
    "text_x",
    "text_y",
    "text_width",
    "text_height",
    "bg_width",
    "bg_height",
    "bg_offset_x",
    "bg_offset_y",
}
DEFAULT_CONFIG: dict[str, Any] = {
    "x": 80,
    "y": 80,
    "width": 900,
    "height": 180,
    "lock_size_to_bg": True,
    "windowed_mode": False,
    "stay_on_top": True,
    "opacity": 1.0,
    "font_family": "Microsoft YaHei",
    "font_size": 30,
    "text_color": "#000000",
    "text_x": 120,
    "text_y": 410,
    "text_width": 300,
    "text_height": 180,
    "text_max_lines": 4,
    "text_anim_enable": True,
    "text_anim_duration_ms": 220,
    "text_anim_fade_px": 24,
    "text_anim_offset_y": 10,
    "subtitle_clear_ms": 2200,
    "bg_image": "base.png",
    "bg_width": 0,
    "bg_height": 0,
    "bg_offset_x": 0,
    "bg_offset_y": 0,
    "show_control_panel": False,
    "tray_icon_enable": True,
    "device": None,
    "samplerate": 16000,
    "block_ms": 100,
    "queue_size": 240,
    "energy_threshold": 0.012,
    "silence_ms": 700,
    "partial_interval_ms": 900,
    "max_segment_seconds": 12.0,
    "chunk_size": [0, 10, 5],
    "encoder_chunk_look_back": 4,
    "decoder_chunk_look_back": 1,
    "model": "paraformer-zh-streaming",
    "vad_model": "fsmn-vad",
    "punc_model": "ct-punc",
    "disable_vad_model": False,
    "disable_punc_model": False,
}


def extract_text(result: Any) -> str:
    if result is None:
        return ""

    current = result
    if isinstance(current, list):
        if not current:
            return ""
        current = current[0]

    if isinstance(current, dict):
        text = current.get("text")
        if isinstance(text, str):
            return text.strip()

        sentence_info = current.get("sentence_info")
        if isinstance(sentence_info, list):
            pieces = []
            for item in sentence_info:
                if isinstance(item, dict):
                    sentence_text = item.get("text")
                    if sentence_text:
                        pieces.append(str(sentence_text))
            merged = "".join(pieces).strip()
            if merged:
                return merged

        for key in ("result", "value", "preds"):
            value = current.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return str(current).strip()


def merge_incremental_text(current: str, new_text: str) -> str:
    new_clean = new_text.strip()
    if not new_clean:
        return current
    if not current:
        return new_clean

    if new_clean.startswith(current):
        return new_clean
    if current.endswith(new_clean):
        return current

    max_overlap = min(len(current), len(new_clean))
    for overlap in range(max_overlap, 0, -1):
        if current.endswith(new_clean[:overlap]):
            return current + new_clean[overlap:]
    return current + new_clean


def replace_sentence_initial_wo(text: str) -> str:
    if not text:
        return ""
    return text.replace("我", "吾辈")


def parse_chunk_size(chunk_size: Any) -> list[int]:
    if isinstance(chunk_size, (list, tuple)):
        parts = [str(p).strip() for p in chunk_size]
    elif isinstance(chunk_size, str):
        parts = [p.strip() for p in chunk_size.split(",")]
    else:
        raise ValueError("chunk-size must be string or list, e.g. '0,10,5' or [0,10,5]")

    if len(parts) != 3:
        raise ValueError("chunk-size must have exactly 3 integers, e.g. 0,10,5")
    values = [int(p) for p in parts]
    if values[1] <= 0:
        raise ValueError("chunk-size second value must be > 0")
    return values


def normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(raw.keys()) - set(DEFAULT_CONFIG.keys()))
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"Unknown config keys: {joined}")

    int_fields = {
        "x",
        "y",
        "width",
        "height",
        "font_size",
        "text_x",
        "text_y",
        "text_width",
        "text_height",
        "text_max_lines",
        "text_anim_duration_ms",
        "text_anim_fade_px",
        "text_anim_offset_y",
        "subtitle_clear_ms",
        "bg_width",
        "bg_height",
        "bg_offset_x",
        "bg_offset_y",
        "samplerate",
        "block_ms",
        "queue_size",
        "silence_ms",
        "partial_interval_ms",
        "encoder_chunk_look_back",
        "decoder_chunk_look_back",
    }
    float_fields = {"opacity", "energy_threshold", "max_segment_seconds"}
    bool_fields = {
        "lock_size_to_bg",
        "windowed_mode",
        "stay_on_top",
        "show_control_panel",
        "tray_icon_enable",
        "text_anim_enable",
        "disable_vad_model",
        "disable_punc_model",
    }
    str_fields = {"font_family", "text_color", "bg_image", "model", "vad_model", "punc_model"}

    def parse_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        raise ValueError(f"Invalid boolean value: {value}")

    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        if key == "device":
            normalized[key] = None if value is None else int(value)
        elif key == "chunk_size":
            normalized[key] = parse_chunk_size(value)
        elif key in int_fields:
            normalized[key] = int(value)
        elif key in float_fields:
            normalized[key] = float(value)
        elif key in bool_fields:
            normalized[key] = parse_bool(value)
        elif key in str_fields:
            normalized[key] = str(value)
        else:
            normalized[key] = value
    return normalized


def load_config_from_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("Config file must be a YAML mapping object.")
    return normalize_config(loaded)


def write_default_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    template_path = Path("config/default.yaml")
    if template_path.exists():
        path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
        return
    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(DEFAULT_CONFIG, file, sort_keys=False, allow_unicode=False)


class AppSignals(QObject):
    subtitle = Signal(str)
    status = Signal(str)
    error = Signal(str)


class SubtitleOverlay(QWidget):
    settings_changed = Signal(dict)
    edit_mode_changed = Signal(bool)
    visibility_changed = Signal(bool)

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__()
        self._subtitle_text = ""
        self._status_text = "模型加载中..."
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
        self._bg_width = max(0, int(args.bg_width))
        self._bg_height = max(0, int(args.bg_height))
        self._bg_offset_x = int(args.bg_offset_x)
        self._bg_offset_y = int(args.bg_offset_y)
        self._windowed_mode = bool(args.windowed_mode)
        self._stay_on_top = bool(args.stay_on_top)
        self._font = QFont(args.font_family, args.font_size)
        self._text_anim_enable = bool(args.text_anim_enable)
        self._text_anim_duration_ms = max(0, args.text_anim_duration_ms)
        self._text_anim_fade_px = max(1, args.text_anim_fade_px)
        self._text_anim_offset_y = max(0, args.text_anim_offset_y)
        self._text_anim_progress = 1.0
        self._text_anim_start_progress = 0.0
        self._text_anim_clock = QElapsedTimer()
        self._text_anim_timer = QTimer(self)
        self._text_anim_timer.setInterval(16)
        self._text_anim_timer.timeout.connect(self._tick_text_animation)
        self._text_color = QColor(args.text_color)
        if not self._text_color.isValid():
            self._text_color = QColor(0, 0, 0)
        self._text_x = max(0, args.text_x)
        self._text_y = max(0, args.text_y)
        self._text_width = max(0, args.text_width)
        self._text_height = max(0, args.text_height)
        self._text_max_lines = max(1, args.text_max_lines)

        self.setWindowTitle("Desktop Subtitle")
        overlay_width = max(1, args.width)
        overlay_height = max(1, args.height)
        if self._lock_size_to_bg and not self._bg_pixmap.isNull():
            overlay_width, overlay_height = self._resolved_bg_size()
        self.setGeometry(args.x, args.y, overlay_width, overlay_height)
        self._apply_window_flags()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(args.opacity)

    def _apply_window_flags(self) -> None:
        if self._windowed_mode:
            flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        else:
            flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self._stay_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def is_edit_mode(self) -> bool:
        return self._edit_mode

    def is_windowed_mode(self) -> bool:
        return self._windowed_mode

    def set_edit_mode(self, enabled: bool) -> None:
        target = bool(enabled)
        if self._edit_mode == target:
            return
        self._edit_mode = target
        self.edit_mode_changed.emit(self._edit_mode)
        self.update()

    def set_stay_on_top(self, enabled: bool) -> None:
        target = bool(enabled)
        if self._stay_on_top == target:
            return
        self._stay_on_top = target
        geometry = self.geometry()
        was_visible = self.isVisible()
        self._apply_window_flags()
        self.setGeometry(geometry)
        if was_visible:
            self.show()
        self._emit_settings_changed()

    def set_windowed_mode(self, enabled: bool) -> None:
        target = bool(enabled)
        if self._windowed_mode == target:
            return
        self._windowed_mode = target
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
        self._font = QFont(self._font.family(), target)
        self.update()
        self._emit_settings_changed()

    def set_bg_offset(self, offset_x: int, offset_y: int) -> None:
        next_x = int(offset_x)
        next_y = int(offset_y)
        if self._bg_offset_x == next_x and self._bg_offset_y == next_y:
            return
        self._bg_offset_x = next_x
        self._bg_offset_y = next_y
        self.update()
        self._emit_settings_changed()

    def set_bg_size(self, width: int, height: int) -> None:
        next_w = max(0, int(width))
        next_h = max(0, int(height))
        if self._bg_width == next_w and self._bg_height == next_h:
            return
        self._bg_width = next_w
        self._bg_height = next_h
        if self._lock_size_to_bg and not self._bg_pixmap.isNull():
            draw_w, draw_h = self._resolved_bg_size()
            self.resize(draw_w, draw_h)
        self.update()
        self._emit_settings_changed()

    def _resolved_bg_size(self) -> tuple[int, int]:
        if self._bg_pixmap.isNull():
            return 0, 0
        draw_w = self._bg_width if self._bg_width > 0 else self._bg_pixmap.width()
        draw_h = self._bg_height if self._bg_height > 0 else self._bg_pixmap.height()
        return max(1, draw_w), max(1, draw_h)

    def _ensure_explicit_text_box(self, text_rect: QRect) -> None:
        if self._text_width > 0 and self._text_height > 0:
            return
        self._text_x = text_rect.x()
        self._text_y = text_rect.y()
        self._text_width = text_rect.width()
        self._text_height = text_rect.height()

    def set_text_box(self, x: int, y: int, width: int, height: int) -> None:
        overlay_width = max(1, self.width())
        overlay_height = max(1, self.height())
        safe_w = max(1, min(int(width), overlay_width))
        safe_h = max(1, min(int(height), overlay_height))
        safe_x = max(0, min(int(x), overlay_width - safe_w))
        safe_y = max(0, min(int(y), overlay_height - safe_h))

        if (
            self._text_x == safe_x
            and self._text_y == safe_y
            and self._text_width == safe_w
            and self._text_height == safe_h
        ):
            return
        self._text_x = safe_x
        self._text_y = safe_y
        self._text_width = safe_w
        self._text_height = safe_h
        self.update()
        self._emit_settings_changed()

    def export_runtime_settings(self) -> dict[str, Any]:
        geometry = self.geometry()
        text_rect = self._build_text_rect()
        return {
            "x": int(geometry.x()),
            "y": int(geometry.y()),
            "width": int(geometry.width()),
            "height": int(geometry.height()),
            "windowed_mode": bool(self._windowed_mode),
            "stay_on_top": bool(self._stay_on_top),
            "font_size": int(self._font.pointSize()),
            "text_x": int(text_rect.x()),
            "text_y": int(text_rect.y()),
            "text_width": int(text_rect.width()),
            "text_height": int(text_rect.height()),
            "bg_width": int(self._bg_width),
            "bg_height": int(self._bg_height),
            "bg_offset_x": int(self._bg_offset_x),
            "bg_offset_y": int(self._bg_offset_y),
        }

    def _emit_settings_changed(self) -> None:
        self.settings_changed.emit(self.export_runtime_settings())

    def set_subtitle(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            self.clear_subtitle()
            return
        if cleaned == self._subtitle_text:
            if self._clear_after_ms > 0:
                self._clear_timer.start(self._clear_after_ms)
            return
        previous = self._subtitle_text
        self._subtitle_text = cleaned
        if self._text_anim_enable:
            self._start_text_animation(self._calc_start_progress(previous, cleaned))
        else:
            self._text_anim_timer.stop()
            self._text_anim_progress = 1.0
        if self._clear_after_ms > 0:
            self._clear_timer.start(self._clear_after_ms)
        else:
            self._clear_timer.stop()
        self.update()

    def set_status(self, text: str) -> None:
        cleaned = text.strip()
        if self._status_text == cleaned:
            return
        self._status_text = cleaned
        if not self._subtitle_text:
            self.update()

    def clear_subtitle(self) -> None:
        self._clear_timer.stop()
        self._text_anim_timer.stop()
        self._text_anim_progress = 1.0
        if not self._subtitle_text:
            return
        self._subtitle_text = ""
        self.update()

    def _start_text_animation(self, start_progress: float = 0.0) -> None:
        if not self._text_anim_enable or self._text_anim_duration_ms <= 0:
            self._text_anim_progress = 1.0
            self._text_anim_timer.stop()
            return
        clamped = min(1.0, max(0.0, start_progress))
        self._text_anim_start_progress = clamped
        self._text_anim_progress = clamped
        if clamped >= 1.0:
            self._text_anim_timer.stop()
            return
        self._text_anim_clock.restart()
        self._text_anim_timer.start()

    def _tick_text_animation(self) -> None:
        if self._text_anim_duration_ms <= 0:
            self._text_anim_timer.stop()
            self._text_anim_progress = 1.0
            self.update()
            return
        elapsed_ms = self._text_anim_clock.elapsed()
        linear = min(1.0, max(0.0, elapsed_ms / float(self._text_anim_duration_ms)))
        self._text_anim_progress = self._text_anim_start_progress + (
            1.0 - self._text_anim_start_progress
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

        if not self._bg_pixmap.isNull():
            bg_rect = self._build_bg_rect()
            painter.drawPixmap(bg_rect, self._bg_pixmap, self._bg_pixmap.rect())

        text_rect = self._build_text_rect()
        max_height = QFontMetrics(self._font).lineSpacing() * self._text_max_lines
        text_rect.setHeight(min(text_rect.height(), max_height))
        draw_text = self._subtitle_text if self._subtitle_text else self._status_text
        if draw_text:
            draw_rect = self._build_centered_draw_rect(text_rect, draw_text)
            if self._subtitle_text and self._text_anim_enable:
                self._draw_reveal_text(painter, draw_rect, draw_text)
            else:
                self._draw_text(painter, draw_rect, draw_text, self._text_color)

        if self._edit_mode:
            self._draw_edit_guides(painter, text_rect)

    def _build_centered_draw_rect(self, container_rect: QRect, text: str) -> QRect:
        metrics = QFontMetrics(self._font)
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

    def _draw_text(self, painter: QPainter, text_rect: QRect, text: str, color: QColor) -> None:
        painter.setPen(color)
        painter.setFont(self._font)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft
            | Qt.TextFlag.TextWordWrap,
            text,
        )

    def _draw_edit_guides(self, painter: QPainter, text_rect: QRect) -> None:
        painter.save()
        guide_pen = QPen(QColor(0, 220, 255, 230), 1, Qt.PenStyle.DashLine)
        painter.setPen(guide_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(text_rect)

        for handle_rect in self._build_text_handle_rects(text_rect).values():
            painter.fillRect(handle_rect, QColor(0, 220, 255, 200))
            painter.drawRect(handle_rect)

        if not self._bg_pixmap.isNull():
            bg_pen = QPen(QColor(255, 200, 0, 220), 1, Qt.PenStyle.DashLine)
            painter.setPen(bg_pen)
            painter.drawRect(self._build_bg_rect())

        painter.setPen(QColor(255, 255, 255, 220))
        painter.setFont(QFont(self._font.family(), max(9, self._font.pointSize() - 5)))
        painter.drawText(
            self.rect().adjusted(8, 6, -8, -6),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "编辑模式: 拖拽文本框可移动/缩放, 拖拽背景可调整位置, F2退出",
        )
        painter.restore()

    def _draw_reveal_text(self, painter: QPainter, text_rect: QRect, text: str) -> None:
        progress = min(1.0, max(0.0, self._text_anim_progress))
        if progress >= 0.999:
            self._draw_text(painter, text_rect, text, self._text_color)
            return

        total_w = max(1, text_rect.width())
        front_w = max(0, min(total_w, int(round(total_w * progress))))
        if front_w <= 0:
            return

        fade_w = max(1, min(self._text_anim_fade_px, front_w))
        solid_w = max(0, front_w - fade_w)

        if solid_w > 0:
            painter.save()
            painter.setClipRect(QRect(text_rect.left(), text_rect.top(), solid_w, text_rect.height()))
            self._draw_text(painter, text_rect, text, self._text_color)
            painter.restore()

        fade_left = text_rect.left() + solid_w
        fade_right = text_rect.left() + front_w
        fade_width = max(1, fade_right - fade_left)
        gradient = QLinearGradient(float(fade_left), 0.0, float(fade_right), 0.0)
        color_opaque = QColor(self._text_color)
        color_transparent = QColor(self._text_color)
        color_transparent.setAlpha(0)
        gradient.setColorAt(0.0, color_opaque)
        gradient.setColorAt(1.0, color_transparent)

        painter.save()
        painter.setClipRect(QRect(fade_left, text_rect.top(), fade_width, text_rect.height()))
        painter.setPen(QPen(QBrush(gradient), 1))
        painter.setFont(self._font)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft
            | Qt.TextFlag.TextWordWrap,
            text,
        )
        painter.restore()

    def _build_bg_rect(self) -> QRect:
        if self._bg_pixmap.isNull():
            return QRect()
        draw_w, draw_h = self._resolved_bg_size()
        return QRect(
            self._bg_offset_x,
            self._bg_offset_y,
            draw_w,
            draw_h,
        )

    def _build_text_rect(self) -> QRect:
        rect = self.rect()
        max_x = max(0, rect.width() - 1)
        max_y = max(0, rect.height() - 1)
        text_x = min(self._text_x, max_x)
        text_y = min(self._text_y, max_y)

        available_w = max(1, rect.width() - text_x)
        available_h = max(1, rect.height() - text_y)
        text_w = self._text_width if self._text_width > 0 else available_w
        text_h = self._text_height if self._text_height > 0 else available_h

        return QRect(
            text_x,
            text_y,
            max(1, min(text_w, available_w)),
            max(1, min(text_h, available_h)),
        )

    def _build_text_handle_rects(self, text_rect: QRect) -> dict[str, QRect]:
        half = self._handle_size // 2
        cx = text_rect.center().x()
        cy = text_rect.center().y()
        left = text_rect.left()
        right = text_rect.right()
        top = text_rect.top()
        bottom = text_rect.bottom()
        return {
            "top_left": QRect(left - half, top - half, self._handle_size, self._handle_size),
            "top": QRect(cx - half, top - half, self._handle_size, self._handle_size),
            "top_right": QRect(right - half, top - half, self._handle_size, self._handle_size),
            "right": QRect(right - half, cy - half, self._handle_size, self._handle_size),
            "bottom_right": QRect(right - half, bottom - half, self._handle_size, self._handle_size),
            "bottom": QRect(cx - half, bottom - half, self._handle_size, self._handle_size),
            "bottom_left": QRect(left - half, bottom - half, self._handle_size, self._handle_size),
            "left": QRect(left - half, cy - half, self._handle_size, self._handle_size),
        }

    def _hit_test_text_interaction(self, position: QPoint, text_rect: QRect) -> str | None:
        for name, handle in self._build_text_handle_rects(text_rect).items():
            if handle.contains(position):
                return name
        if text_rect.contains(position):
            return "move"
        return None

    def _apply_text_resize_delta(self, handle: str, delta: QPoint) -> None:
        if self._drag_start_text_rect is None:
            return

        start = self._drag_start_text_rect
        left = start.left()
        right = start.right()
        top = start.top()
        bottom = start.bottom()
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

        overlay_right = max(0, self.width() - 1)
        overlay_bottom = max(0, self.height() - 1)
        left = max(0, min(left, overlay_right))
        right = max(0, min(right, overlay_right))
        top = max(0, min(top, overlay_bottom))
        bottom = max(0, min(bottom, overlay_bottom))

        if left > right:
            left, right = right, left
        if top > bottom:
            top, bottom = bottom, top

        min_w = self._min_text_box_size
        min_h = self._min_text_box_size
        if right - left + 1 < min_w:
            if handle in {"right", "top_right", "bottom_right"}:
                right = min(overlay_right, left + min_w - 1)
                left = max(0, right - min_w + 1)
            else:
                left = max(0, right - min_w + 1)
                right = min(overlay_right, left + min_w - 1)
        if bottom - top + 1 < min_h:
            if handle in {"bottom", "bottom_left", "bottom_right"}:
                bottom = min(overlay_bottom, top + min_h - 1)
                top = max(0, bottom - min_h + 1)
            else:
                top = max(0, bottom - min_h + 1)
                bottom = min(overlay_bottom, top + min_h - 1)

        self.set_text_box(left, top, right - left + 1, bottom - top + 1)

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
                self._text_x,
                self._text_y,
                max(1, self._text_width),
                max(1, self._text_height),
            )
            self._interaction_mode = f"text_{interaction}"
            return

        bg_rect = self._build_bg_rect()
        if not bg_rect.isNull() and bg_rect.contains(local_pos):
            self._drag_start_bg_offset = QPoint(self._bg_offset_x, self._bg_offset_y)
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


class OverlayControlPanel(QWidget):
    visibility_changed = Signal(bool)

    def __init__(self, overlay: SubtitleOverlay, config_path: Path) -> None:
        super().__init__()
        self._overlay = overlay
        self._config_path = config_path
        self._syncing = False
        self.setWindowTitle("Subtitle Settings")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self._build_ui()
        self._connect_signals()
        self._sync_from_overlay()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self.setMinimumWidth(360)
        self.resize(400, 560)

        tip = QLabel("F2: 编辑模式。拖拽文本框移动/缩放，拖拽背景调位置。")
        tip.setWordWrap(True)
        root.addWidget(tip)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)

        form_host = QWidget()
        scroll.setWidget(form_host)
        host_layout = QVBoxLayout(form_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(10)

        host_layout.addWidget(self._section_title("窗口"))
        window_form = QFormLayout()
        window_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._stay_on_top_checkbox = QCheckBox("启用")
        window_form.addRow("前台常驻", self._stay_on_top_checkbox)
        self._windowed_mode_checkbox = QCheckBox("启用")
        self._windowed_mode_checkbox.setToolTip("启用后仍为无边框透明背景，仅切换为非 Tool 窗口。")
        window_form.addRow("窗口化模式", self._windowed_mode_checkbox)
        self._edit_mode_checkbox = QCheckBox("启用")
        window_form.addRow("编辑模式", self._edit_mode_checkbox)
        host_layout.addLayout(window_form)

        host_layout.addWidget(self._section_title("字幕"))
        text_form = QFormLayout()
        text_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 120)
        text_form.addRow("字号", self._font_size_spin)

        self._text_x_spin = QSpinBox()
        self._text_x_spin.setRange(0, 5000)
        text_form.addRow("文本框 X", self._text_x_spin)

        self._text_y_spin = QSpinBox()
        self._text_y_spin.setRange(0, 5000)
        text_form.addRow("文本框 Y", self._text_y_spin)

        self._text_w_spin = QSpinBox()
        self._text_w_spin.setRange(1, 5000)
        text_form.addRow("文本框宽", self._text_w_spin)

        self._text_h_spin = QSpinBox()
        self._text_h_spin.setRange(1, 5000)
        text_form.addRow("文本框高", self._text_h_spin)
        host_layout.addLayout(text_form)

        host_layout.addWidget(self._section_title("背景"))
        bg_form = QFormLayout()
        bg_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._bg_x_spin = QSpinBox()
        self._bg_x_spin.setRange(-5000, 5000)
        bg_form.addRow("背景偏移 X", self._bg_x_spin)

        self._bg_y_spin = QSpinBox()
        self._bg_y_spin.setRange(-5000, 5000)
        bg_form.addRow("背景偏移 Y", self._bg_y_spin)

        self._bg_w_spin = QSpinBox()
        self._bg_w_spin.setRange(0, 5000)
        self._bg_w_spin.setSpecialValueText("自动")
        self._bg_w_spin.setToolTip("0 表示使用原图宽度")
        bg_form.addRow("背景宽", self._bg_w_spin)

        self._bg_h_spin = QSpinBox()
        self._bg_h_spin.setRange(0, 5000)
        self._bg_h_spin.setSpecialValueText("自动")
        self._bg_h_spin.setToolTip("0 表示使用原图高度")
        bg_form.addRow("背景高", self._bg_h_spin)
        host_layout.addLayout(bg_form)
        bg_hint = QLabel("提示：背景宽/高填 0 时，使用背景图片原始尺寸。")
        bg_hint.setWordWrap(True)
        host_layout.addWidget(bg_hint)
        host_layout.addStretch(1)
        root.addWidget(self._divider())

        action_row = QHBoxLayout()
        self._save_button = QPushButton("保存到配置")
        action_row.addWidget(self._save_button)
        root.addLayout(action_row)

        self._status_label = QLabel("")
        root.addWidget(self._status_label)

    def _connect_signals(self) -> None:
        self._overlay.settings_changed.connect(self._sync_from_overlay)
        self._overlay.edit_mode_changed.connect(self._on_overlay_edit_mode_changed)

        self._stay_on_top_checkbox.toggled.connect(self._on_stay_on_top_changed)
        self._windowed_mode_checkbox.toggled.connect(self._on_windowed_mode_changed)
        self._edit_mode_checkbox.toggled.connect(self._on_edit_mode_changed)
        self._font_size_spin.valueChanged.connect(self._on_font_size_changed)
        self._text_x_spin.valueChanged.connect(self._on_text_box_changed)
        self._text_y_spin.valueChanged.connect(self._on_text_box_changed)
        self._text_w_spin.valueChanged.connect(self._on_text_box_changed)
        self._text_h_spin.valueChanged.connect(self._on_text_box_changed)
        self._bg_x_spin.valueChanged.connect(self._on_bg_offset_changed)
        self._bg_y_spin.valueChanged.connect(self._on_bg_offset_changed)
        self._bg_w_spin.valueChanged.connect(self._on_bg_size_changed)
        self._bg_h_spin.valueChanged.connect(self._on_bg_size_changed)
        self._save_button.clicked.connect(self._save_to_config)

    def _divider(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.HLine)
        frame.setFrameShadow(QFrame.Shadow.Sunken)
        return frame

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        return label

    def _sync_from_overlay(self, settings: dict[str, Any] | None = None) -> None:
        del settings
        snapshot = self._overlay.export_runtime_settings()
        self._syncing = True
        try:
            self._stay_on_top_checkbox.setChecked(bool(snapshot["stay_on_top"]))
            self._windowed_mode_checkbox.setChecked(bool(snapshot["windowed_mode"]))
            self._edit_mode_checkbox.setChecked(self._overlay.is_edit_mode())
            self._font_size_spin.setValue(int(snapshot["font_size"]))
            self._text_x_spin.setValue(int(snapshot["text_x"]))
            self._text_y_spin.setValue(int(snapshot["text_y"]))
            self._text_w_spin.setValue(int(snapshot["text_width"]))
            self._text_h_spin.setValue(int(snapshot["text_height"]))
            self._bg_x_spin.setValue(int(snapshot["bg_offset_x"]))
            self._bg_y_spin.setValue(int(snapshot["bg_offset_y"]))
            self._bg_w_spin.setValue(int(snapshot["bg_width"]))
            self._bg_h_spin.setValue(int(snapshot["bg_height"]))
        finally:
            self._syncing = False

    def _on_overlay_edit_mode_changed(self, enabled: bool) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            self._edit_mode_checkbox.setChecked(enabled)
        finally:
            self._syncing = False

    def _on_stay_on_top_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._overlay.set_stay_on_top(checked)

    def _on_windowed_mode_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._overlay.set_windowed_mode(checked)

    def _on_edit_mode_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._overlay.set_edit_mode(checked)

    def _on_font_size_changed(self, value: int) -> None:
        if self._syncing:
            return
        self._overlay.set_font_size(value)

    def _on_text_box_changed(self, _value: int) -> None:
        if self._syncing:
            return
        self._overlay.set_text_box(
            self._text_x_spin.value(),
            self._text_y_spin.value(),
            self._text_w_spin.value(),
            self._text_h_spin.value(),
        )

    def _on_bg_offset_changed(self, _value: int) -> None:
        if self._syncing:
            return
        self._overlay.set_bg_offset(self._bg_x_spin.value(), self._bg_y_spin.value())

    def _on_bg_size_changed(self, _value: int) -> None:
        if self._syncing:
            return
        self._overlay.set_bg_size(self._bg_w_spin.value(), self._bg_h_spin.value())

    def _save_to_config(self) -> None:
        try:
            persist_overlay_settings(self._config_path, self._overlay)
            self._status_label.setText(f"已保存: {self._config_path}")
        except Exception as exc:  # pylint: disable=broad-except
            self._status_label.setText(f"保存失败: {exc}")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self.visibility_changed.emit(False)


def build_tray_icon(image_path: str) -> QIcon:
    if image_path:
        pix = QPixmap(image_path)
        if not pix.isNull():
            scaled = pix.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            canvas = QPixmap(32, 32)
            canvas.fill(Qt.GlobalColor.transparent)
            painter = QPainter(canvas)
            x = (32 - scaled.width()) // 2
            y = (32 - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.end()
            return QIcon(canvas)

    fallback = QPixmap(32, 32)
    fallback.fill(Qt.GlobalColor.transparent)
    painter = QPainter(fallback)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(24, 120, 255))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 8, 8)
    painter.setPen(QColor(255, 255, 255))
    painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
    painter.drawText(fallback.rect(), Qt.AlignmentFlag.AlignCenter, "ASR")
    painter.end()
    return QIcon(fallback)


class TrayController(QObject):
    def __init__(
        self,
        app: QApplication,
        overlay: SubtitleOverlay,
        control_panel: OverlayControlPanel,
        config_path: Path,
        icon_path: str,
    ) -> None:
        super().__init__()
        self._app = app
        self._overlay = overlay
        self._control_panel = control_panel
        self._config_path = config_path

        self._tray = QSystemTrayIcon(build_tray_icon(icon_path), self._app)
        self._tray.setToolTip("Desktop Subtitle")
        self._menu = QMenu()
        self._build_menu()
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_activated)

        self._overlay.visibility_changed.connect(self._sync_states)
        self._control_panel.visibility_changed.connect(self._sync_states)
        self._sync_states()

    def _build_menu(self) -> None:
        self._action_toggle_overlay = QAction("", self._menu)
        self._action_toggle_overlay.triggered.connect(self._on_toggle_overlay)
        self._menu.addAction(self._action_toggle_overlay)

        self._action_open_settings = QAction("", self._menu)
        self._action_open_settings.triggered.connect(self._on_open_settings)
        self._menu.addAction(self._action_open_settings)

        self._menu.addSeparator()

        self._action_save = QAction("保存当前设置", self._menu)
        self._action_save.triggered.connect(self._on_save_settings)
        self._menu.addAction(self._action_save)

        self._action_quit = QAction("退出", self._menu)
        self._action_quit.triggered.connect(self._on_quit)
        self._menu.addAction(self._action_quit)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def _sync_states(self, _payload: Any = None) -> None:
        del _payload
        overlay_visible = self._overlay.isVisible()
        panel_visible = self._control_panel.isVisible()
        self._action_toggle_overlay.setText("隐藏字幕窗口" if overlay_visible else "显示字幕窗口")
        self._action_open_settings.setText("聚焦设置面板" if panel_visible else "打开设置面板")

    def _on_toggle_overlay(self) -> None:
        if self._overlay.isVisible():
            self._overlay.hide()
        else:
            self._overlay.show()
            self._overlay.raise_()
            self._overlay.activateWindow()
        self._sync_states()

    def _on_open_settings(self) -> None:
        if not self._overlay.isVisible():
            self._overlay.show()
        self._control_panel.move(self._overlay.x() + self._overlay.width() + 16, self._overlay.y())
        self._control_panel.show()
        self._control_panel.raise_()
        self._control_panel.activateWindow()
        self._sync_states()

    def _on_save_settings(self) -> None:
        try:
            persist_overlay_settings(self._config_path, self._overlay)
            self._tray.showMessage(
                "Desktop Subtitle",
                f"设置已保存到 {self._config_path}",
                QSystemTrayIcon.MessageIcon.Information,
                1800,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._tray.showMessage(
                "Desktop Subtitle",
                f"保存失败: {exc}",
                QSystemTrayIcon.MessageIcon.Critical,
                2800,
            )

    def _on_quit(self) -> None:
        self._app.quit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_toggle_overlay()


class ASRWorker(threading.Thread):
    def __init__(
        self,
        args: argparse.Namespace,
        audio_queue: "queue.Queue[np.ndarray]",
        signals: AppSignals,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self.args = args
        self.audio_queue = audio_queue
        self.signals = signals
        self.stop_event = stop_event
        self.use_streaming = "streaming" in args.model
        self.silence_blocks = max(1, int(args.silence_ms / args.block_ms))
        self.partial_blocks = max(1, int(args.partial_interval_ms / args.block_ms))
        self.max_segment_samples = int(args.max_segment_seconds * args.samplerate)
        self.chunk_size = args.chunk_size
        self.encoder_chunk_look_back = args.encoder_chunk_look_back
        self.decoder_chunk_look_back = args.decoder_chunk_look_back
        self.chunk_stride_samples = max(1, int(self.args.samplerate * self.chunk_size[1] * 0.06))

    def _emit_subtitle(self, text: str) -> None:
        converted = replace_sentence_initial_wo(text.strip())
        if converted:
            self.signals.subtitle.emit(converted)

    def run(self) -> None:
        mode = "streaming" if self.use_streaming else "offline"
        LOGGER.info("ASR worker started (mode=%s, model=%s)", mode, self.args.model)
        self.signals.status.emit("模型加载中...")
        LOGGER.info("Loading ASR model...")
        try:
            model = self._load_model()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("FunASR model init failed")
            self.signals.status.emit("模型加载失败")
            self.signals.error.emit(f"FunASR model init failed: {exc}")
            return

        LOGGER.info("ASR model ready")
        self.signals.status.emit("")
        if self.use_streaming:
            LOGGER.info("Streaming ASR loop running")
            self._run_streaming(model)
            LOGGER.info("Streaming ASR loop stopped")
            return
        LOGGER.info("Offline ASR loop running")
        self._run_offline(model)
        LOGGER.info("Offline ASR loop stopped")

    def _run_streaming(self, model: AutoModel) -> None:
        cache: dict[str, Any] = {}
        pending = np.empty(0, dtype=np.float32)
        in_speech = False
        silence_count = 0
        segment_samples = 0
        current_text = ""

        while not self.stop_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.15)
            except queue.Empty:
                continue

            energy = float(np.mean(np.abs(chunk)))
            is_voice = energy >= self.args.energy_threshold
            if is_voice:
                if not in_speech:
                    LOGGER.info("Speech started")
                in_speech = True
                silence_count = 0
            elif in_speech:
                silence_count += 1

            pending = np.concatenate((pending, chunk.astype(np.float32, copy=False)))
            if in_speech:
                segment_samples += len(chunk)

            while pending.size >= self.chunk_stride_samples:
                speech_chunk = pending[: self.chunk_stride_samples]
                pending = pending[self.chunk_stride_samples :]
                text = self._transcribe_streaming(model, speech_chunk, cache, is_final=False)
                if text:
                    if not in_speech:
                        in_speech = True
                        silence_count = 0
                    current_text = merge_incremental_text(current_text, text)
                    self._emit_subtitle(current_text)

            if in_speech and (
                silence_count >= self.silence_blocks or segment_samples >= self.max_segment_samples
            ):
                final_text = self._transcribe_streaming(model, pending, cache, is_final=True)
                if final_text:
                    current_text = merge_incremental_text(current_text, final_text)
                if current_text:
                    self._emit_subtitle(current_text)
                end_reason = (
                    "silence"
                    if silence_count >= self.silence_blocks
                    else "max-segment-seconds"
                )
                LOGGER.info("Speech finalized (%s, chars=%d)", end_reason, len(current_text))
                pending = np.empty(0, dtype=np.float32)
                current_text = ""
                in_speech = False
                silence_count = 0
                segment_samples = 0

        while True:
            try:
                tail = self.audio_queue.get_nowait()
                pending = np.concatenate((pending, tail.astype(np.float32, copy=False)))
            except queue.Empty:
                break

        if pending.size > 0 or current_text:
            final_text = self._transcribe_streaming(model, pending, cache, is_final=True)
            if final_text:
                current_text = merge_incremental_text(current_text, final_text)
            if current_text:
                self._emit_subtitle(current_text)
                LOGGER.info("Speech flushed on shutdown (chars=%d)", len(current_text))

    def _run_offline(self, model: AutoModel) -> None:
        in_speech = False
        silence_count = 0
        segment_parts: list[np.ndarray] = []
        segment_samples = 0
        chunks_since_partial = 0

        while not self.stop_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.15)
            except queue.Empty:
                continue

            energy = float(np.mean(np.abs(chunk)))
            is_voice = energy >= self.args.energy_threshold

            if is_voice:
                if not in_speech:
                    LOGGER.info("Speech started")
                    in_speech = True
                    silence_count = 0
                    segment_parts = []
                    segment_samples = 0
                    chunks_since_partial = 0

                segment_parts.append(chunk)
                segment_samples += len(chunk)
                chunks_since_partial += 1
                silence_count = 0

                if chunks_since_partial >= self.partial_blocks:
                    chunks_since_partial = 0
                    partial_text = self._transcribe(model, np.concatenate(segment_parts))
                    if partial_text:
                        self._emit_subtitle(partial_text)

                if segment_samples >= self.max_segment_samples:
                    final_text = self._transcribe(model, np.concatenate(segment_parts))
                    if final_text:
                        self._emit_subtitle(final_text)
                    LOGGER.info("Speech finalized (max-segment-seconds, chars=%d)", len(final_text))
                    in_speech = False
                    silence_count = 0
                    segment_parts = []
                    segment_samples = 0
                    chunks_since_partial = 0

            elif in_speech:
                silence_count += 1
                segment_parts.append(chunk)
                segment_samples += len(chunk)

                if silence_count >= self.silence_blocks:
                    final_text = self._transcribe(model, np.concatenate(segment_parts))
                    if final_text:
                        self._emit_subtitle(final_text)
                    LOGGER.info("Speech finalized (silence, chars=%d)", len(final_text))
                    in_speech = False
                    silence_count = 0
                    segment_parts = []
                    segment_samples = 0
                    chunks_since_partial = 0

        if segment_parts:
            final_text = self._transcribe(model, np.concatenate(segment_parts))
            if final_text:
                self._emit_subtitle(final_text)
                LOGGER.info("Speech flushed on shutdown (chars=%d)", len(final_text))

    def _load_model(self) -> AutoModel:
        if self.use_streaming:
            return AutoModel(model=self.args.model, disable_update=True)

        model_kwargs: dict[str, Any] = {
            "model": self.args.model,
            "disable_update": True,
        }
        if not self.args.disable_vad_model:
            model_kwargs["vad_model"] = self.args.vad_model
        if not self.args.disable_punc_model:
            model_kwargs["punc_model"] = self.args.punc_model
        return AutoModel(**model_kwargs)

    def _transcribe(self, model: AutoModel, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        try:
            result = model.generate(input=audio, batch_size_s=60, fs=self.args.samplerate)
        except TypeError:
            result = model.generate(input=audio, fs=self.args.samplerate)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("ASR failed (offline)")
            self.signals.error.emit(f"ASR failed: {exc}")
            return ""
        return extract_text(result)

    def _transcribe_streaming(
        self, model: AutoModel, audio: np.ndarray, cache: dict[str, Any], is_final: bool
    ) -> str:
        try:
            result = model.generate(
                input=audio,
                cache=cache,
                is_final=is_final,
                fs=self.args.samplerate,
                chunk_size=self.chunk_size,
                encoder_chunk_look_back=self.encoder_chunk_look_back,
                decoder_chunk_look_back=self.decoder_chunk_look_back,
            )
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("ASR failed (streaming)")
            self.signals.error.emit(f"ASR failed: {exc}")
            return ""
        return extract_text(result)


def parse_args() -> argparse.Namespace:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("--config", type=str, default=DEFAULT_CONFIG_PATH)
    bootstrap.add_argument(
        "--dump-default-config",
        type=str,
        default="",
        help="write default config YAML to the specified path, then exit",
    )
    bootstrap_args, _ = bootstrap.parse_known_args()

    config_path = Path(bootstrap_args.config).expanduser()
    defaults = dict(DEFAULT_CONFIG)
    try:
        defaults.update(load_config_from_file(config_path))
    except Exception as exc:  # pylint: disable=broad-except
        raise ValueError(f"Failed to load config file {config_path}: {exc}") from exc

    parser = argparse.ArgumentParser(description="Desktop subtitle overlay based on FunASR.")
    parser.add_argument("--config", type=str, default=str(config_path))
    parser.add_argument(
        "--dump-default-config",
        type=str,
        default="",
        help="write default config YAML to the specified path, then exit",
    )
    parser.add_argument("--x", type=int, default=defaults["x"])
    parser.add_argument("--y", type=int, default=defaults["y"])
    parser.add_argument("--width", type=int, default=defaults["width"])
    parser.add_argument("--height", type=int, default=defaults["height"])
    parser.add_argument(
        "--lock-size-to-bg",
        dest="lock_size_to_bg",
        action="store_true",
        help="use background image native width/height as overlay size (1:1 pixels)",
    )
    parser.add_argument(
        "--unlock-size-to-bg",
        dest="lock_size_to_bg",
        action="store_false",
        help="allow custom width/height even with background image",
    )
    parser.set_defaults(lock_size_to_bg=defaults["lock_size_to_bg"])
    window_group = parser.add_mutually_exclusive_group()
    window_group.add_argument(
        "--windowed",
        dest="windowed_mode",
        action="store_true",
        help="use frameless transparent window mode (non-tool window)",
    )
    window_group.add_argument(
        "--frameless",
        dest="windowed_mode",
        action="store_false",
        help="use frameless overlay mode",
    )
    parser.set_defaults(windowed_mode=defaults["windowed_mode"])
    top_group = parser.add_mutually_exclusive_group()
    top_group.add_argument("--stay-on-top", dest="stay_on_top", action="store_true")
    top_group.add_argument("--no-stay-on-top", dest="stay_on_top", action="store_false")
    parser.set_defaults(stay_on_top=defaults["stay_on_top"])
    parser.add_argument("--opacity", type=float, default=defaults["opacity"])
    parser.add_argument("--font-family", type=str, default=defaults["font_family"])
    parser.add_argument("--font-size", type=int, default=defaults["font_size"])
    parser.add_argument("--text-color", type=str, default=defaults["text_color"])
    parser.add_argument("--text-x", type=int, default=defaults["text_x"])
    parser.add_argument("--text-y", type=int, default=defaults["text_y"])
    parser.add_argument("--text-width", type=int, default=defaults["text_width"])
    parser.add_argument("--text-height", type=int, default=defaults["text_height"])
    parser.add_argument("--text-max-lines", type=int, default=defaults["text_max_lines"])
    anim_group = parser.add_mutually_exclusive_group()
    anim_group.add_argument("--enable-text-anim", dest="text_anim_enable", action="store_true")
    anim_group.add_argument("--disable-text-anim", dest="text_anim_enable", action="store_false")
    parser.set_defaults(text_anim_enable=defaults["text_anim_enable"])
    parser.add_argument(
        "--text-anim-duration-ms",
        type=int,
        default=defaults["text_anim_duration_ms"],
        help="subtitle reveal animation duration in milliseconds",
    )
    parser.add_argument(
        "--text-anim-fade-px",
        type=int,
        default=defaults["text_anim_fade_px"],
        help="subtitle reveal front-edge fade width in pixels",
    )
    parser.add_argument(
        "--text-anim-offset-y",
        type=int,
        default=defaults["text_anim_offset_y"],
        help="deprecated; kept for backward compatibility",
    )
    parser.add_argument(
        "--subtitle-clear-ms",
        type=int,
        default=defaults["subtitle_clear_ms"],
        help="clear subtitle after this idle duration in milliseconds; 0 disables auto-clear",
    )
    parser.add_argument("--bg-image", type=str, default=defaults["bg_image"])
    parser.add_argument("--bg-width", type=int, default=defaults["bg_width"])
    parser.add_argument("--bg-height", type=int, default=defaults["bg_height"])
    parser.add_argument("--bg-offset-x", type=int, default=defaults["bg_offset_x"])
    parser.add_argument("--bg-offset-y", type=int, default=defaults["bg_offset_y"])
    panel_group = parser.add_mutually_exclusive_group()
    panel_group.add_argument(
        "--show-control-panel",
        dest="show_control_panel",
        action="store_true",
    )
    panel_group.add_argument(
        "--hide-control-panel",
        dest="show_control_panel",
        action="store_false",
    )
    parser.set_defaults(show_control_panel=defaults["show_control_panel"])
    tray_group = parser.add_mutually_exclusive_group()
    tray_group.add_argument(
        "--enable-tray-icon",
        dest="tray_icon_enable",
        action="store_true",
    )
    tray_group.add_argument(
        "--disable-tray-icon",
        dest="tray_icon_enable",
        action="store_false",
    )
    parser.set_defaults(tray_icon_enable=defaults["tray_icon_enable"])

    parser.add_argument("--device", type=int, default=defaults["device"])
    parser.add_argument("--samplerate", type=int, default=defaults["samplerate"])
    parser.add_argument("--block-ms", type=int, default=defaults["block_ms"])
    parser.add_argument("--queue-size", type=int, default=defaults["queue_size"])
    parser.add_argument("--energy-threshold", type=float, default=defaults["energy_threshold"])
    parser.add_argument("--silence-ms", type=int, default=defaults["silence_ms"])
    parser.add_argument(
        "--partial-interval-ms", type=int, default=defaults["partial_interval_ms"]
    )
    parser.add_argument(
        "--max-segment-seconds", type=float, default=defaults["max_segment_seconds"]
    )
    parser.add_argument(
        "--chunk-size",
        type=parse_chunk_size,
        default=defaults["chunk_size"],
        help="streaming chunk config as left,current,right; e.g. 0,10,5",
    )
    parser.add_argument(
        "--encoder-chunk-look-back",
        type=int,
        default=defaults["encoder_chunk_look_back"],
    )
    parser.add_argument(
        "--decoder-chunk-look-back",
        type=int,
        default=defaults["decoder_chunk_look_back"],
    )

    parser.add_argument("--model", type=str, default=defaults["model"])
    parser.add_argument("--vad-model", type=str, default=defaults["vad_model"])
    parser.add_argument("--punc-model", type=str, default=defaults["punc_model"])

    vad_group = parser.add_mutually_exclusive_group()
    vad_group.add_argument("--disable-vad-model", dest="disable_vad_model", action="store_true")
    vad_group.add_argument("--enable-vad-model", dest="disable_vad_model", action="store_false")
    parser.set_defaults(disable_vad_model=defaults["disable_vad_model"])

    punc_group = parser.add_mutually_exclusive_group()
    punc_group.add_argument(
        "--disable-punc-model",
        dest="disable_punc_model",
        action="store_true",
    )
    punc_group.add_argument("--enable-punc-model", dest="disable_punc_model", action="store_false")
    parser.set_defaults(disable_punc_model=defaults["disable_punc_model"])

    args = parser.parse_args()
    if args.dump_default_config:
        write_default_config(Path(args.dump_default_config).expanduser())
        raise SystemExit(0)
    return args


def build_audio_callback(
    audio_queue: "queue.Queue[np.ndarray]",
) -> Any:
    dropped_chunks = 0

    def callback(indata, frames, time_info, status) -> None:
        nonlocal dropped_chunks
        del frames, time_info, status
        mono = np.squeeze(indata).astype(np.float32, copy=True)
        try:
            audio_queue.put_nowait(mono)
        except queue.Full:
            dropped_chunks += 1
            if dropped_chunks == 1 or dropped_chunks % 50 == 0:
                LOGGER.warning("Audio queue overflow, dropped chunks=%d", dropped_chunks)
            try:
                audio_queue.get_nowait()
                audio_queue.put_nowait(mono)
            except queue.Empty:
                pass

    return callback


def ensure_valid_image(path: str, config_path: Path) -> str:
    normalized = path.strip()
    candidates: list[Path] = []
    if normalized:
        user_path = Path(normalized).expanduser()
        if user_path.is_absolute():
            candidates.append(user_path)
        else:
            candidates.extend((Path.cwd() / user_path, config_path.parent / user_path))
    else:
        default_name = Path("base.png")
        candidates.extend(
            (
                Path.cwd() / default_name,
                config_path.parent / default_name,
                Path.cwd() / "config" / default_name,
            )
        )

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return str(resolved)

    if normalized:
        tried = ", ".join(str(p.resolve()) for p in candidates)
        print(f"[WARN] bg image not found, tried: {tried}")
    return ""


def write_overlay_settings_to_config(config_path: Path, settings: dict[str, Any]) -> None:
    config_path = config_path.expanduser().resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    current: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as file:
            loaded = yaml.safe_load(file)
        if loaded is None:
            current = {}
        elif isinstance(loaded, dict):
            current = loaded
        else:
            raise ValueError("Config file must be a YAML mapping object.")

    for key in OVERLAY_PERSIST_KEYS:
        if key in settings:
            current[key] = settings[key]

    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(current, file, sort_keys=False, allow_unicode=True)


def persist_overlay_settings(config_path: Path, overlay: SubtitleOverlay) -> None:
    write_overlay_settings_to_config(config_path, overlay.export_runtime_settings())


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        args = parse_args()
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2
    config_path = Path(args.config).expanduser().resolve()
    args.bg_image = ensure_valid_image(args.bg_image, Path(args.config).expanduser())
    LOGGER.info("Starting app with config: %s", config_path)
    LOGGER.info("Background image: %s", args.bg_image or "<none>")
    LOGGER.info("Subtitle auto-clear: %dms", args.subtitle_clear_ms)

    app = QApplication(sys.argv)
    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    if args.tray_icon_enable and tray_available:
        app.setQuitOnLastWindowClosed(False)

    overlay = SubtitleOverlay(args)
    control_panel = OverlayControlPanel(overlay, config_path)
    tray_controller = None
    if args.tray_icon_enable:
        if tray_available:
            tray_controller = TrayController(
                app=app,
                overlay=overlay,
                control_panel=control_panel,
                config_path=config_path,
                icon_path=args.bg_image,
            )
        else:
            LOGGER.warning("System tray is unavailable on this platform; tray icon disabled.")

    signals = AppSignals()
    stop_event = threading.Event()
    audio_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=args.queue_size)

    signals.subtitle.connect(overlay.set_subtitle)
    signals.status.connect(overlay.set_status)

    def on_error(msg: str) -> None:
        LOGGER.error(msg)
        overlay.set_status(f"[ERROR] {msg}")
        overlay.clear_subtitle()

    signals.error.connect(on_error)
    signals.status.emit("模型加载中...")

    worker = ASRWorker(args, audio_queue, signals, stop_event)
    worker.start()

    block_size = max(1, int(args.samplerate * args.block_ms / 1000))
    audio_callback = build_audio_callback(audio_queue)

    stream = None
    try:
        stream = sd.InputStream(
            samplerate=args.samplerate,
            channels=1,
            dtype="float32",
            callback=audio_callback,
            blocksize=block_size,
            device=args.device,
        )
        stream.start()
        LOGGER.info("Audio input stream started (samplerate=%d, block_ms=%d)", args.samplerate, args.block_ms)
        overlay.show()
        if tray_controller is not None:
            tray_controller.show()
        if args.show_control_panel:
            control_panel.move(overlay.x() + overlay.width() + 16, overlay.y())
            control_panel.show()
        LOGGER.info("Overlay window shown")
        code = app.exec()
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Failed to start audio stream")
        print(f"[ERROR] failed to start audio stream: {exc}")
        code = 1
    finally:
        LOGGER.info("Shutting down...")
        stop_event.set()
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if tray_controller is not None:
            tray_controller.hide()
        worker.join(timeout=2.0)
        LOGGER.info("Worker stopped")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
