from dataclasses import dataclass
from typing import Any

from core.models import (
    MODEL_PROFILE_CUSTOM,
    MODEL_PROFILE_HYBRID,
)
from core.settings import MODEL_PROFILE_PRESETS


@dataclass(frozen=True)
class ModelSelectionState:
    model: str
    detector_model: str
    vad_model: str
    punc_model: str
    disable_vad_model: bool
    disable_punc_model: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            'model': self.model,
            'detector_model': self.detector_model,
            'vad_model': self.vad_model,
            'punc_model': self.punc_model,
            'disable_vad_model': self.disable_vad_model,
            'disable_punc_model': self.disable_punc_model,
        }


def build_model_selection_state(
    *,
    model: str,
    detector_model: str,
    vad_model: str,
    punc_model: str,
    disable_vad_model: bool,
    disable_punc_model: bool,
) -> ModelSelectionState:
    return ModelSelectionState(
        model=str(model),
        detector_model=str(detector_model),
        vad_model=str(vad_model),
        punc_model=str(punc_model),
        disable_vad_model=bool(disable_vad_model),
        disable_punc_model=bool(disable_punc_model),
    )


def resolve_model_selection_state(
    profile: str,
    *,
    custom_snapshot: dict[str, Any],
) -> ModelSelectionState:
    if profile == MODEL_PROFILE_CUSTOM:
        return build_model_selection_state(**custom_snapshot)
    preset = MODEL_PROFILE_PRESETS[profile]
    return build_model_selection_state(
        model=preset['model'],
        detector_model=preset.get('detector_model', preset['model']),
        vad_model=preset['vad_model'],
        punc_model=preset['punc_model'],
        disable_vad_model=preset['disable_vad_model'],
        disable_punc_model=preset['disable_punc_model'],
    )


def build_model_profile_summary(profile: str, selection: ModelSelectionState) -> str:
    if profile in MODEL_PROFILE_PRESETS:
        profile_name = str(MODEL_PROFILE_PRESETS[profile]['label'])
    else:
        profile_name = '自定义'
    vad_text = '禁用' if selection.disable_vad_model else selection.vad_model
    punc_text = '禁用' if selection.disable_punc_model else selection.punc_model
    return (
        '当前组合: '
        f'{profile_name} ({profile})\n'
        f'Detector: {selection.detector_model}\n'
        f'ASR: {selection.model}\n'
        f'VAD: {vad_text}\n'
        f'PUNC: {punc_text}'
    )


def build_model_download_requests(profile: str, selection: ModelSelectionState) -> list[dict[str, Any]]:
    downloads: list[dict[str, Any]] = []
    if profile == MODEL_PROFILE_HYBRID:
        downloads.append({'model': selection.detector_model, 'disable_update': True})

    kwargs: dict[str, Any] = {'model': selection.model, 'disable_update': True}
    if 'streaming' not in selection.model:
        if not selection.disable_vad_model:
            kwargs['vad_model'] = selection.vad_model
        if not selection.disable_punc_model:
            kwargs['punc_model'] = selection.punc_model
    downloads.append(kwargs)
    return downloads


def build_model_config_updates(
    profile: str,
    *,
    model_download_on_startup: bool,
    selection: ModelSelectionState,
) -> dict[str, Any]:
    updates = selection.to_dict()
    updates.update(
        {
            'model_profile': profile,
            'model_download_on_startup': bool(model_download_on_startup),
            'model_profile_prompted': True,
        }
    )
    return updates
