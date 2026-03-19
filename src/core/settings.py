import argparse
import os
from pathlib import Path
import shutil
import sys
from typing import Any

import yaml

from core.models import (
    MODEL_PROFILE_CHOICES,
    MODEL_PROFILE_CUSTOM,
    MODEL_PROFILE_REALTIME,
)

APP_DIR_NAME = "anan_subtitle"
DEFAULT_CONFIG_DIR = "config"
DEFAULT_CONFIG_FILENAME = "app.yaml"
DEFAULT_CONFIG_TEMPLATE_FILENAME = "default.yaml"
DEFAULT_CONFIG_PATH = f"{DEFAULT_CONFIG_DIR}/{DEFAULT_CONFIG_FILENAME}"
DEFAULT_CONFIG_TEMPLATE_PATH = f"{DEFAULT_CONFIG_DIR}/{DEFAULT_CONFIG_TEMPLATE_FILENAME}"

STORAGE_LOCATION_APP = "app"
STORAGE_LOCATION_USER = "user"
STORAGE_LOCATION_CUSTOM = "custom"
STORAGE_LOCATION_CHOICES = (
    STORAGE_LOCATION_APP,
    STORAGE_LOCATION_USER,
    STORAGE_LOCATION_CUSTOM,
)
DEFAULT_DATA_DIR_NAME = "data"
DEFAULT_LOG_DIR_NAME = "logs"

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

def is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_resource_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[2]


def get_app_install_dir() -> Path:
    if is_frozen_runtime():
        return Path(sys.executable).resolve().parent
    return get_resource_root()


def get_user_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if local_app_data:
        return Path(local_app_data).expanduser().resolve() / APP_DIR_NAME
    return Path.home().resolve() / f".{APP_DIR_NAME}"


def get_user_config_dir() -> Path:
    return get_user_data_dir() / DEFAULT_CONFIG_DIR


def get_default_runtime_config_path() -> Path:
    if is_frozen_runtime():
        return (get_user_config_dir() / DEFAULT_CONFIG_FILENAME).resolve()
    return (Path(DEFAULT_CONFIG_PATH).expanduser()).resolve()


def resolve_default_template_path() -> Path:
    return (get_resource_root() / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_TEMPLATE_FILENAME).resolve()


def _iter_image_candidates(normalized: str, config_path: Path) -> list[Path]:
    config_dir = config_path.parent.resolve()
    resource_root = get_resource_root()
    resource_config_dir = (resource_root / DEFAULT_CONFIG_DIR).resolve()
    user_config_dir = get_user_config_dir().resolve()
    candidates: list[Path] = []

    if normalized:
        user_path = Path(normalized).expanduser()
        if user_path.is_absolute():
            candidates.append(user_path)
        else:
            candidates.extend(
                (
                    config_dir / user_path,
                    user_config_dir / user_path,
                    Path.cwd() / user_path,
                    resource_root / user_path,
                    resource_config_dir / user_path,
                )
            )
    else:
        default_name = Path("base.png")
        candidates.extend(
            (
                config_dir / default_name,
                user_config_dir / default_name,
                Path.cwd() / default_name,
                resource_root / default_name,
                resource_config_dir / default_name,
            )
        )

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def parse_storage_location(location: Any) -> str:
    normalized = str(location).strip().lower()
    if normalized not in STORAGE_LOCATION_CHOICES:
        joined = ", ".join(STORAGE_LOCATION_CHOICES)
        raise ValueError(f"Invalid storage location '{location}', expected one of: {joined}")
    return normalized


def resolve_storage_base_dir(location: str, custom_path: str | Path = "") -> Path:
    normalized = parse_storage_location(location)
    if normalized == STORAGE_LOCATION_APP:
        return get_app_install_dir().resolve()
    if normalized == STORAGE_LOCATION_USER:
        return get_user_data_dir().resolve()

    custom = str(custom_path).strip()
    if not custom:
        return get_user_data_dir().resolve()
    return Path(custom).expanduser().resolve()


def resolve_data_dir(location: str, custom_path: str | Path = "") -> Path:
    return (resolve_storage_base_dir(location, custom_path) / DEFAULT_DATA_DIR_NAME).resolve()


def resolve_log_dir(location: str, custom_path: str | Path = "") -> Path:
    return (resolve_storage_base_dir(location, custom_path) / DEFAULT_LOG_DIR_NAME).resolve()


def apply_storage_paths_to_args(args: argparse.Namespace) -> None:
    args.data_dir_location = parse_storage_location(getattr(args, "data_dir_location", STORAGE_LOCATION_USER))
    args.log_dir_location = parse_storage_location(getattr(args, "log_dir_location", STORAGE_LOCATION_USER))
    args.data_dir_custom = str(getattr(args, "data_dir_custom", ""))
    args.log_dir_custom = str(getattr(args, "log_dir_custom", ""))
    args.data_dir = str(resolve_data_dir(args.data_dir_location, args.data_dir_custom))
    args.log_dir = str(resolve_log_dir(args.log_dir_location, args.log_dir_custom))


def ensure_runtime_config_file(path: str | Path) -> Path:
    resolved = ensure_runtime_config_path(path)
    if not resolved.exists():
        write_default_config(resolved)
    return resolved


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
    "data_dir_location": "user",
    "data_dir_custom": "",
    "log_dir_location": "user",
    "log_dir_custom": "",
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
        "data_dir_location",
        "data_dir_custom",
        "log_dir_location",
        "log_dir_custom",
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
        elif key in {"data_dir_location", "log_dir_location"}:
            normalized[key] = parse_storage_location(value)
        elif key in bool_fields:
            normalized[key] = parse_bool(value)
        elif key in str_fields:
            normalized[key] = str(value)
        else:
            normalized[key] = value
    return normalized


def resolve_runtime_config_path(path: str | Path) -> Path:
    raw = str(path).strip() if isinstance(path, str) else str(path)
    if not raw:
        return get_default_runtime_config_path()
    return Path(path).expanduser().resolve()


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
    path = resolve_runtime_config_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    template_path = resolve_default_template_path()
    if template_path.exists():
        shutil.copyfile(template_path, path)
        return
    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(DEFAULT_CONFIG, file, sort_keys=False, allow_unicode=False)


def parse_args() -> argparse.Namespace:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("--config", type=str, default=str(get_default_runtime_config_path()))
    bootstrap.add_argument(
        "--dump-default-config",
        type=str,
        default="",
        help="write default config YAML to the specified path, then exit",
    )
    bootstrap_args, _ = bootstrap.parse_known_args()

    config_path = ensure_runtime_config_file(bootstrap_args.config)
    defaults = dict(DEFAULT_CONFIG)
    loaded_from_file: dict[str, Any] = {}
    try:
        loaded_from_file = load_config_from_file(config_path)
        defaults.update(loaded_from_file)
    except Exception as exc:  # pylint: disable=broad-except
        raise ValueError(f"Failed to load config file {config_path}: {exc}") from exc

    if (
        config_path.exists()
        and "model_profile" not in loaded_from_file
        and any(
            key in loaded_from_file
            for key in ("model", "vad_model", "punc_model", "disable_vad_model", "disable_punc_model")
        )
    ):
        defaults["model_profile"] = MODEL_PROFILE_CUSTOM
    defaults = apply_model_profile_to_settings(defaults)

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

    parser.add_argument(
        "--data-dir-location",
        type=parse_storage_location,
        choices=STORAGE_LOCATION_CHOICES,
        default=defaults["data_dir_location"],
        help="data/cache storage location: app, user, custom",
    )
    parser.add_argument(
        "--data-dir-custom",
        type=str,
        default=defaults["data_dir_custom"],
        help="custom base path for data/cache storage when data-dir-location=custom",
    )
    parser.add_argument(
        "--log-dir-location",
        type=parse_storage_location,
        choices=STORAGE_LOCATION_CHOICES,
        default=defaults["log_dir_location"],
        help="log storage location: app, user, custom",
    )
    parser.add_argument(
        "--log-dir-custom",
        type=str,
        default=defaults["log_dir_custom"],
        help="custom base path for log storage when log-dir-location=custom",
    )

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
    parser.add_argument("--detector-model", type=str, default=defaults["detector_model"])
    parser.add_argument("--vad-model", type=str, default=defaults["vad_model"])
    parser.add_argument("--punc-model", type=str, default=defaults["punc_model"])
    parser.add_argument(
        "--model-profile",
        type=parse_model_profile,
        choices=MODEL_PROFILE_CHOICES,
        default=defaults["model_profile"],
        help="model combo preset: realtime, offline, hybrid, custom",
    )

    model_download_group = parser.add_mutually_exclusive_group()
    model_download_group.add_argument(
        "--model-download-on-startup",
        dest="model_download_on_startup",
        action="store_true",
        help="pre-download selected model combo when application starts",
    )
    model_download_group.add_argument(
        "--no-model-download-on-startup",
        dest="model_download_on_startup",
        action="store_false",
        help="do not pre-download model combo on startup",
    )
    parser.set_defaults(model_download_on_startup=defaults["model_download_on_startup"])

    model_prompt_group = parser.add_mutually_exclusive_group()
    model_prompt_group.add_argument(
        "--prompt-model-profile",
        dest="model_profile_prompt_on_first_run",
        action="store_true",
        help="prompt model profile selection on first launch",
    )
    model_prompt_group.add_argument(
        "--no-prompt-model-profile",
        dest="model_profile_prompt_on_first_run",
        action="store_false",
        help="disable first-launch model profile prompt",
    )
    parser.set_defaults(model_profile_prompt_on_first_run=defaults["model_profile_prompt_on_first_run"])
    parser.set_defaults(model_profile_prompted=defaults["model_profile_prompted"])

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
    cli_flags = set(sys.argv[1:])
    has_model_override = any(
        flag in cli_flags
        for flag in (
            "--model",
            "--detector-model",
            "--vad-model",
            "--punc-model",
            "--disable-vad-model",
            "--enable-vad-model",
            "--disable-punc-model",
            "--enable-punc-model",
        )
    )
    has_profile_override = "--model-profile" in cli_flags
    if has_model_override and not has_profile_override:
        args.model_profile = MODEL_PROFILE_CUSTOM
    apply_model_profile_to_args(args)
    apply_storage_paths_to_args(args)
    args.config = str(config_path)
    return args


def ensure_valid_image(path: str, config_path: Path) -> str:
    normalized = path.strip()
    candidates = _iter_image_candidates(normalized, config_path)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    if normalized:
        tried = ", ".join(str(candidate) for candidate in candidates)
        print(f"[WARN] bg image not found, tried: {tried}")
    return ""


def write_config_values(config_path: Path, updates: dict[str, Any]) -> None:
    config_path = ensure_runtime_config_path(config_path)
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

    for key, value in updates.items():
        current[key] = value

    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(current, file, sort_keys=False, allow_unicode=True)


def write_overlay_settings_to_config(config_path: Path, settings: dict[str, Any]) -> None:
    overlay_updates: dict[str, Any] = {}
    for key in OVERLAY_PERSIST_KEYS:
        if key in settings:
            overlay_updates[key] = settings[key]
    write_config_values(config_path, overlay_updates)
