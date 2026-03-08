from pathlib import Path
import time
from typing import Any, Callable

from core.settings import OVERLAY_PERSIST_KEYS, write_config_values
from presentation.qt.settings_window_models import (
    ModelSelectionState,
    build_model_config_updates,
)


def build_overlay_config_updates(settings: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in settings.items() if key in OVERLAY_PERSIST_KEYS}


def build_settings_config_updates(
    overlay_settings: dict[str, Any],
    *,
    model_profile: str,
    model_download_on_startup: bool,
    selection: ModelSelectionState,
) -> dict[str, Any]:
    updates = build_overlay_config_updates(overlay_settings)
    updates.update(
        build_model_config_updates(
            model_profile,
            model_download_on_startup=model_download_on_startup,
            selection=selection,
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
) -> None:
    write_config_values(
        config_path,
        build_settings_config_updates(
            overlay_settings,
            model_profile=model_profile,
            model_download_on_startup=model_download_on_startup,
            selection=selection,
        ),
    )


def run_model_download_requests(
    downloads: list[dict[str, Any]],
    *,
    model_loader: Callable[..., Any] | None = None,
    perf_counter: Callable[[], float] = time.perf_counter,
) -> float:
    if model_loader is None:
        from funasr import AutoModel

        model_loader = AutoModel

    start = perf_counter()
    for kwargs in downloads:
        model_loader(**kwargs)
    return perf_counter() - start
