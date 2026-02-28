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
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap, QLinearGradient, QPen, QBrush
from PySide6.QtWidgets import QApplication, QWidget

from funasr import AutoModel

DEFAULT_CONFIG_PATH = "config/app.yaml"
LOGGER = logging.getLogger("desktop_subtitle")
DEFAULT_CONFIG: dict[str, Any] = {
    "x": 80,
    "y": 80,
    "width": 900,
    "height": 180,
    "lock_size_to_bg": True,
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

    sentence_endings = {"。", "！", "？", "!", "?", ";", "；", "\n"}
    chars = list(text)
    result: list[str] = []
    at_sentence_start = True

    for ch in chars:
        if at_sentence_start and ch.isspace():
            result.append(ch)
            continue
        if at_sentence_start and ch == "我":
            result.append("吾辈")
            at_sentence_start = False
            continue

        result.append(ch)
        if ch in sentence_endings:
            at_sentence_start = True
        elif not ch.isspace():
            at_sentence_start = False

    return "".join(result)


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
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__()
        self._subtitle_text = ""
        self._status_text = "模型加载中..."
        self._drag_origin: QPoint | None = None
        self._win_origin: QPoint | None = None
        self._clear_after_ms = max(0, args.subtitle_clear_ms)
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self.clear_subtitle)
        self._bg_pixmap = QPixmap(args.bg_image) if args.bg_image else QPixmap()
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
        if args.lock_size_to_bg and not self._bg_pixmap.isNull():
            overlay_width = self._bg_pixmap.width()
            overlay_height = self._bg_pixmap.height()
        self.setGeometry(args.x, args.y, overlay_width, overlay_height)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(args.opacity)

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
            if self._bg_pixmap.size() == self.size():
                painter.drawPixmap(self.rect(), self._bg_pixmap)
            else:
                x = (self.width() - self._bg_pixmap.width()) // 2
                y = (self.height() - self._bg_pixmap.height()) // 2
                painter.drawPixmap(x, y, self._bg_pixmap)

        text_rect = self._build_text_rect()
        max_height = QFontMetrics(self._font).lineSpacing() * self._text_max_lines
        text_rect.setHeight(min(text_rect.height(), max_height))
        draw_text = self._subtitle_text if self._subtitle_text else self._status_text
        if not draw_text:
            return
        draw_rect = self._build_centered_draw_rect(text_rect, draw_text)

        if self._subtitle_text and self._text_anim_enable:
            self._draw_reveal_text(painter, draw_rect, draw_text)
            return

        self._draw_text(painter, draw_rect, draw_text, self._text_color)

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

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint()
            self._win_origin = self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_origin is None or self._win_origin is None:
            return
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_origin
            self.move(self._win_origin + delta)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        del event
        self._drag_origin = None
        self._win_origin = None

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)


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
    overlay = SubtitleOverlay(args)
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
        worker.join(timeout=2.0)
        LOGGER.info("Worker stopped")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
