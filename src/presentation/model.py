from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SubtitleViewState:
    subtitle_text: str = ""
    status_text: str = "模型加载中..."
    animation_progress: float = 1.0
    animation_start_progress: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubtitleStyleSpec:
    font_family: str
    font_size: int
    text_color: str
    text_max_lines: int
    text_anim_enable: bool
    text_anim_duration_ms: int
    text_anim_fade_px: int
    text_anim_offset_y: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OverlayRuntimeSettings:
    x: int
    y: int
    width: int
    height: int
    windowed_mode: bool
    stay_on_top: bool
    font_size: int
    text_x: int
    text_y: int
    text_width: int
    text_height: int
    bg_width: int
    bg_height: int
    bg_offset_x: int
    bg_offset_y: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
