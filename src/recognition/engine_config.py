from dataclasses import dataclass
import argparse
from typing import Any

from core.models import MODEL_PROFILE_HYBRID


@dataclass(frozen=True)
class WorkerRuntimeConfig:
    mode: str
    use_hybrid: bool
    use_streaming: bool
    detector_model_name: str
    silence_blocks: int
    partial_blocks: int
    max_segment_samples: int
    chunk_size: list[int]
    encoder_chunk_look_back: int
    decoder_chunk_look_back: int
    chunk_stride_samples: int


def resolve_worker_mode(args: argparse.Namespace) -> str:
    model_profile = str(getattr(args, "model_profile", "")).strip().lower()
    if model_profile == MODEL_PROFILE_HYBRID:
        return "hybrid"
    if "streaming" in str(args.model):
        return "streaming"
    return "offline"


def build_worker_runtime_config(args: argparse.Namespace) -> WorkerRuntimeConfig:
    mode = resolve_worker_mode(args)
    chunk_size = list(args.chunk_size)
    return WorkerRuntimeConfig(
        mode=mode,
        use_hybrid=(mode == "hybrid"),
        use_streaming=(mode == "streaming"),
        detector_model_name=str(getattr(args, "detector_model", "paraformer-zh-streaming")),
        silence_blocks=max(1, int(args.silence_ms / args.block_ms)),
        partial_blocks=max(1, int(args.partial_interval_ms / args.block_ms)),
        max_segment_samples=int(args.max_segment_seconds * args.samplerate),
        chunk_size=chunk_size,
        encoder_chunk_look_back=args.encoder_chunk_look_back,
        decoder_chunk_look_back=args.decoder_chunk_look_back,
        chunk_stride_samples=max(1, int(args.samplerate * chunk_size[1] * 0.06)),
    )


def build_offline_model_kwargs(args: argparse.Namespace, model_name: str) -> dict[str, Any]:
    model_kwargs: dict[str, Any] = {
        "model": model_name,
        "disable_update": True,
    }
    if not args.disable_vad_model:
        model_kwargs["vad_model"] = args.vad_model
    if not args.disable_punc_model:
        model_kwargs["punc_model"] = args.punc_model
    return model_kwargs
