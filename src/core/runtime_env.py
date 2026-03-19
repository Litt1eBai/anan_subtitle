import logging
import os
import sys
from pathlib import Path
from typing import Any


def build_model_cache_environment(data_dir: str | Path) -> dict[str, str]:
    root = Path(data_dir).expanduser().resolve()
    modelscope_root = (root / 'modelscope' / 'hub').resolve()
    huggingface_root = (root / 'huggingface').resolve()
    torch_root = (root / 'torch').resolve()
    return {
        'MODELSCOPE_CACHE': str(modelscope_root),
        'HF_HOME': str(huggingface_root),
        'HUGGINGFACE_HUB_CACHE': str((huggingface_root / 'hub').resolve()),
        'TORCH_HOME': str(torch_root),
    }


def apply_runtime_environment(args: Any) -> None:
    data_dir = Path(getattr(args, 'data_dir')).expanduser().resolve()
    log_dir = Path(getattr(args, 'log_dir')).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    env_updates = build_model_cache_environment(data_dir)
    for key, value in env_updates.items():
        os.environ[key] = value

    args.data_dir = str(data_dir)
    args.log_dir = str(log_dir)
    args.modelscope_cache_dir = env_updates['MODELSCOPE_CACHE']
    args.huggingface_cache_dir = env_updates['HUGGINGFACE_HUB_CACHE']
    args.log_file = str((log_dir / 'desktop_subtitle.log').resolve())


def configure_logging(log_dir: str | Path) -> Path:
    target_dir = Path(log_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = (target_dir / 'desktop_subtitle.log').resolve()

    handlers: list[logging.Handler] = [logging.FileHandler(log_file, encoding='utf-8')]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=handlers,
        force=True,
    )
    return log_file
