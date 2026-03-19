import os
import time
from pathlib import Path
from typing import Any, Callable

from core.model_download import ensure_model_download_ready
from core.runtime_env import build_model_cache_environment
from core.settings import OVERLAY_PERSIST_KEYS, write_config_values
from presentation.qt.settings_window_models import (
    ModelSelectionState,
    build_model_config_updates,
)


def build_overlay_config_updates(settings: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in settings.items() if key in OVERLAY_PERSIST_KEYS}


def build_storage_config_updates(
    *,
    data_dir_location: str,
    data_dir_custom: str,
    log_dir_location: str,
    log_dir_custom: str,
) -> dict[str, Any]:
    return {
        "data_dir_location": data_dir_location,
        "data_dir_custom": data_dir_custom,
        "log_dir_location": log_dir_location,
        "log_dir_custom": log_dir_custom,
    }


def build_settings_config_updates(
    overlay_settings: dict[str, Any],
    *,
    model_profile: str,
    model_download_on_startup: bool,
    selection: ModelSelectionState,
    data_dir_location: str,
    data_dir_custom: str,
    log_dir_location: str,
    log_dir_custom: str,
) -> dict[str, Any]:
    updates = build_overlay_config_updates(overlay_settings)
    updates.update(
        build_model_config_updates(
            model_profile,
            model_download_on_startup=model_download_on_startup,
            selection=selection,
        )
    )
    updates.update(
        build_storage_config_updates(
            data_dir_location=data_dir_location,
            data_dir_custom=data_dir_custom,
            log_dir_location=log_dir_location,
            log_dir_custom=log_dir_custom,
        )
    )
    return updates


def write_settings_config(
    config_path: Path,
    overlay_settings: dict[str, Any],
    *,
    model_profile: str,
    model_download_on_startup: bool,
    selection: ModelSelectionState,
    data_dir_location: str,
    data_dir_custom: str,
    log_dir_location: str,
    log_dir_custom: str,
) -> None:
    write_config_values(
        config_path,
        build_settings_config_updates(
            overlay_settings,
            model_profile=model_profile,
            model_download_on_startup=model_download_on_startup,
            selection=selection,
            data_dir_location=data_dir_location,
            data_dir_custom=data_dir_custom,
            log_dir_location=log_dir_location,
            log_dir_custom=log_dir_custom,
        ),
    )


def run_model_download_requests(
    downloads: list[dict[str, Any]],
    *,
    data_dir: Path | None = None,
    model_loader: Callable[..., Any] | None = None,
    perf_counter: Callable[[], float] = time.perf_counter,
    download_preparer: Callable[..., dict[str, Any]] = ensure_model_download_ready,
) -> float:
    if data_dir is not None:
        data_dir = Path(data_dir).expanduser().resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        for key, value in build_model_cache_environment(data_dir).items():
            os.environ[key] = value

    if model_loader is None:
        from funasr import AutoModel

        model_loader = AutoModel

    start = perf_counter()
    modelscope_cache_dir = os.environ.get("MODELSCOPE_CACHE", "")
    for kwargs in downloads:
        prepared_kwargs = download_preparer(kwargs, modelscope_cache_dir=modelscope_cache_dir or None)
        model_loader(**prepared_kwargs)
    return perf_counter() - start
