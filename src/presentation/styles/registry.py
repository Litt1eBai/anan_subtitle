from presentation.styles.base import DEFAULT_STYLE_ID, SubtitleStyle
from presentation.styles.preset_default import DefaultSubtitleStyle

_STYLE_REGISTRY: dict[str, SubtitleStyle] = {
    DEFAULT_STYLE_ID: DefaultSubtitleStyle(),
}


def get_style(style_id: str | None) -> SubtitleStyle:
    if style_id and style_id in _STYLE_REGISTRY:
        return _STYLE_REGISTRY[style_id]
    return _STYLE_REGISTRY[DEFAULT_STYLE_ID]


def list_styles() -> list[SubtitleStyle]:
    return list(_STYLE_REGISTRY.values())
