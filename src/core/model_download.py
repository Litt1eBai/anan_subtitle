import logging
import os
import shutil
from pathlib import Path
from typing import Any, Callable

from funasr.download.download_model_from_hub import (
    download_model,
    get_or_download_model_dir,
    get_or_download_model_dir_hf,
)
from funasr.download.name_maps_from_hub import name_maps_hf, name_maps_ms

LOGGER = logging.getLogger("desktop_subtitle")


def is_usable_downloaded_model_dir(model_path: str | Path | None) -> bool:
    if not model_path:
        return False
    path = Path(str(model_path)).expanduser()
    return path.exists() and ((path / "configuration.json").exists() or (path / "config.yaml").exists())


def _resolve_modelscope_repo_id(model_name: str) -> str:
    return str(name_maps_ms.get(model_name, model_name))


def _resolve_hf_repo_id(model_name: str) -> str:
    return str(name_maps_hf.get(model_name, model_name))


def _iter_modelscope_cache_paths(model_name: str, modelscope_cache_dir: str | Path | None) -> list[Path]:
    if not modelscope_cache_dir:
        env_value = os.environ.get("MODELSCOPE_CACHE", "")
        if not env_value:
            return []
        modelscope_cache_dir = env_value

    root = Path(str(modelscope_cache_dir)).expanduser().resolve()
    repo_id = _resolve_modelscope_repo_id(model_name)
    if "/" not in repo_id:
        return []

    namespace, repo_name = repo_id.split("/", 1)
    return [
        root / "models" / namespace / repo_name,
        root / "models" / "._____temp" / namespace / repo_name,
        root / ".lock" / f"{namespace}___{repo_name}",
    ]


def cleanup_incomplete_model_cache(model_name: str, modelscope_cache_dir: str | Path | None = None) -> None:
    for path in _iter_modelscope_cache_paths(model_name, modelscope_cache_dir):
        if not path.exists():
            continue
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            LOGGER.info("Removed incomplete model cache: %s", path)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.warning("Failed to remove incomplete model cache %s: %s", path, exc)


def _iter_download_hubs(download_kwargs: dict[str, Any]) -> list[str]:
    requested_hub = str(download_kwargs.get("hub", "")).strip().lower()
    if requested_hub in {"hf", "huggingface"}:
        return ["hf"]
    if requested_hub in {"ms", "modelscope"}:
        hubs = ["ms"]
    else:
        hubs = ["ms"]

    model_name = str(download_kwargs.get("model", ""))
    if model_name in name_maps_hf and "hf" not in hubs:
        hubs.append("hf")
    return hubs


def _download_and_resolve_model(download_kwargs: dict[str, Any], hub: str) -> dict[str, Any]:
    kwargs = dict(download_kwargs)
    if kwargs.get("model_path"):
        kwargs["hub"] = hub
        return download_model(**kwargs)

    model_name = str(kwargs.get("model", ""))
    model_revision = kwargs.get("model_revision", "master")
    is_training = kwargs.get("is_training", False)
    check_latest = kwargs.get("check_latest", True)

    if hub == "hf":
        repo_id = _resolve_hf_repo_id(model_name)
        model_path = get_or_download_model_dir_hf(
            repo_id,
            model_revision=model_revision,
            is_training=is_training,
            check_latest=check_latest,
        )
    else:
        repo_id = _resolve_modelscope_repo_id(model_name)
        model_path = get_or_download_model_dir(
            repo_id,
            model_revision=model_revision,
            is_training=is_training,
            check_latest=check_latest,
        )

    kwargs["hub"] = hub
    kwargs["model_path"] = model_path
    return download_model(**kwargs)


def _ensure_with_single_downloader(
    download_kwargs: dict[str, Any],
    *,
    downloader: Callable[..., dict[str, Any]],
    modelscope_cache_dir: str | Path | None = None,
) -> dict[str, Any]:
    model_name = str(download_kwargs.get("model", "<unknown>"))
    last_resolved: dict[str, Any] | None = None

    for attempt in range(2):
        resolved = downloader(**dict(download_kwargs))
        last_resolved = resolved
        model_path = resolved.get("model_path")
        if is_usable_downloaded_model_dir(model_path):
            return resolved

        if attempt == 0:
            LOGGER.warning(
                "Model cache is incomplete for %s (model_path=%s). Cleaning cache and retrying.",
                model_name,
                model_path,
            )
            cleanup_incomplete_model_cache(model_name, modelscope_cache_dir)

    model_path = "" if last_resolved is None else str(last_resolved.get("model_path", ""))
    detail = f"{model_name}: download did not produce a usable model directory"
    if model_path:
        detail += f" (model_path={model_path})"
    if modelscope_cache_dir:
        detail += f" (modelscope_cache={modelscope_cache_dir})"
    raise RuntimeError(detail)


def ensure_model_download_ready(
    download_kwargs: dict[str, Any],
    *,
    downloader: Callable[..., dict[str, Any]] = download_model,
    modelscope_cache_dir: str | Path | None = None,
) -> dict[str, Any]:
    if downloader is not download_model:
        return _ensure_with_single_downloader(
            download_kwargs,
            downloader=downloader,
            modelscope_cache_dir=modelscope_cache_dir,
        )

    model_name = str(download_kwargs.get("model", "<unknown>"))
    errors: list[str] = []

    for hub in _iter_download_hubs(download_kwargs):
        for attempt in range(2):
            try:
                resolved = _download_and_resolve_model(download_kwargs, hub)
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(f"{hub}: {exc}")
                if hub == "ms" and attempt == 0:
                    LOGGER.warning(
                        "Model download failed for %s via %s. Cleaning cache and retrying once. Error: %s",
                        model_name,
                        hub,
                        exc,
                    )
                    cleanup_incomplete_model_cache(model_name, modelscope_cache_dir)
                    continue
                LOGGER.warning("Model download failed for %s via %s: %s", model_name, hub, exc)
                break

            model_path = str(resolved.get("model_path", ""))
            if is_usable_downloaded_model_dir(model_path):
                if hub == "hf":
                    LOGGER.info("Model download for %s succeeded via Hugging Face fallback.", model_name)
                return resolved

            errors.append(f"{hub}: unusable model directory (model_path={model_path})")
            if hub == "ms" and attempt == 0:
                LOGGER.warning(
                    "Model cache is incomplete for %s (model_path=%s). Cleaning cache and retrying.",
                    model_name,
                    model_path,
                )
                cleanup_incomplete_model_cache(model_name, modelscope_cache_dir)
                continue
            break

    detail = f"{model_name}: download did not produce a usable model directory"
    if modelscope_cache_dir:
        detail += f" (modelscope_cache={modelscope_cache_dir})"
    if errors:
        detail += f" (attempts={' | '.join(errors)})"
    raise RuntimeError(detail)
