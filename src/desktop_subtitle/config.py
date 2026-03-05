import argparse
from pathlib import Path
from typing import Any

import yaml

from .constants import DEFAULT_CONFIG, DEFAULT_CONFIG_PATH, OVERLAY_PERSIST_KEYS

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
