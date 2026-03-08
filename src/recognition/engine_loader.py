from dataclasses import dataclass
from typing import Any, Callable

from recognition.engine_config import build_offline_model_kwargs


@dataclass(frozen=True)
class LoadedRecognitionModels:
    primary_model: Any | None = None
    detector_model: Any | None = None


ModelLoader = Callable[..., Any]


def load_streaming_model(model_name: str, *, model_loader: ModelLoader | None = None) -> Any:
    if model_loader is None:
        from funasr import AutoModel

        model_loader = AutoModel
    return model_loader(model=model_name, disable_update=True)


def load_offline_model(args: Any, model_name: str, *, model_loader: ModelLoader | None = None) -> Any:
    if model_loader is None:
        from funasr import AutoModel

        model_loader = AutoModel
    return model_loader(**build_offline_model_kwargs(args, model_name))


def load_models(
    *,
    use_hybrid: bool,
    use_streaming: bool,
    args: Any,
    detector_model_name: str,
    streaming_loader: Callable[[str], Any],
    offline_loader: Callable[[Any, str], Any],
) -> LoadedRecognitionModels:
    if use_hybrid:
        return LoadedRecognitionModels(
            primary_model=offline_loader(args, args.model),
            detector_model=streaming_loader(detector_model_name),
        )
    if use_streaming:
        return LoadedRecognitionModels(primary_model=streaming_loader(args.model))
    return LoadedRecognitionModels(primary_model=offline_loader(args, args.model))
