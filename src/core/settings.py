import argparse
from pathlib import Path
from typing import Any

from core.models import (
    MODEL_PROFILE_CHOICES,
    MODEL_PROFILE_CUSTOM,
    MODEL_PROFILE_REALTIME,
)

DEFAULT_CONFIG_DIR = "config"
DEFAULT_CONFIG_FILENAME = "app.yaml"
DEFAULT_CONFIG_TEMPLATE_FILENAME = "default.yaml"
DEFAULT_CONFIG_PATH = f"{DEFAULT_CONFIG_DIR}/{DEFAULT_CONFIG_FILENAME}"
DEFAULT_CONFIG_TEMPLATE_PATH = f"{DEFAULT_CONFIG_DIR}/{DEFAULT_CONFIG_TEMPLATE_FILENAME}"

MODEL_PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    "realtime": {
        "label": "实时",
        "model": "paraformer-zh-streaming",
        "detector_model": "paraformer-zh-streaming",
        "vad_model": "fsmn-vad",
        "punc_model": "ct-punc",
        "disable_vad_model": True,
        "disable_punc_model": True,
    },
    "offline": {
        "label": "非实时",
        "model": "paraformer-zh",
        "detector_model": "paraformer-zh-streaming",
        "vad_model": "fsmn-vad",
        "punc_model": "ct-punc",
        "disable_vad_model": False,
        "disable_punc_model": False,
    },
    "hybrid": {
        "label": "混合",
        "model": "paraformer-zh",
        "detector_model": "paraformer-zh-streaming",
        "vad_model": "fsmn-vad",
        "punc_model": "ct-punc",
        "disable_vad_model": False,
        "disable_punc_model": False,
    },
}

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
    "model_profile": "realtime",
    "model_profile_prompt_on_first_run": True,
    "model_profile_prompted": False,
    "model_download_on_startup": False,
    "model": "paraformer-zh-streaming",
    "detector_model": "paraformer-zh-streaming",
    "vad_model": "fsmn-vad",
    "punc_model": "ct-punc",
    "disable_vad_model": False,
    "disable_punc_model": False,
}


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


def parse_model_profile(profile: Any) -> str:
    normalized = str(profile).strip().lower()
    if normalized not in MODEL_PROFILE_CHOICES:
        joined = ", ".join(MODEL_PROFILE_CHOICES)
        raise ValueError(f"Invalid model_profile '{profile}', expected one of: {joined}")
    return normalized


def apply_model_profile_to_settings(settings: dict[str, Any]) -> dict[str, Any]:
    profile = parse_model_profile(settings.get("model_profile", MODEL_PROFILE_REALTIME))
    settings["model_profile"] = profile
    if profile == MODEL_PROFILE_CUSTOM:
        return settings

    preset = MODEL_PROFILE_PRESETS[profile]
    settings["model"] = preset["model"]
    settings["detector_model"] = preset.get("detector_model", settings.get("detector_model", preset["model"]))
    settings["vad_model"] = preset["vad_model"]
    settings["punc_model"] = preset["punc_model"]
    settings["disable_vad_model"] = preset["disable_vad_model"]
    settings["disable_punc_model"] = preset["disable_punc_model"]
    return settings


def apply_model_profile_to_args(args: argparse.Namespace) -> None:
    profile = parse_model_profile(getattr(args, "model_profile", MODEL_PROFILE_REALTIME))
    args.model_profile = profile
    if profile == MODEL_PROFILE_CUSTOM:
        return
    preset = MODEL_PROFILE_PRESETS[profile]
    args.model = str(preset["model"])
    args.detector_model = str(preset.get("detector_model", preset["model"]))
    args.vad_model = str(preset["vad_model"])
    args.punc_model = str(preset["punc_model"])
    args.disable_vad_model = bool(preset["disable_vad_model"])
    args.disable_punc_model = bool(preset["disable_punc_model"])


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
        "model_profile_prompt_on_first_run",
        "model_profile_prompted",
        "model_download_on_startup",
    }
    str_fields = {
        "font_family",
        "text_color",
        "bg_image",
        "model",
        "detector_model",
        "vad_model",
        "punc_model",
        "model_profile",
    }

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
        elif key == "model_profile":
            normalized[key] = parse_model_profile(value)
        elif key in bool_fields:
            normalized[key] = parse_bool(value)
        elif key in str_fields:
            normalized[key] = str(value)
        else:
            normalized[key] = value
    return normalized


def resolve_runtime_config_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def resolve_default_template_path() -> Path:
    return Path(DEFAULT_CONFIG_TEMPLATE_PATH).expanduser().resolve()


def is_template_config_path(path: str | Path) -> bool:
    resolved = resolve_runtime_config_path(path)
    return resolved == resolve_default_template_path()


def ensure_runtime_config_path(path: str | Path) -> Path:
    resolved = resolve_runtime_config_path(path)
    if is_template_config_path(resolved):
        raise ValueError(
            "config/default.yaml is a read-only template. Use config/app.yaml or another runtime config path."
        )
    return resolved
