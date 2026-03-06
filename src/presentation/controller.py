from dataclasses import replace
from typing import Protocol

from presentation.model import SubtitleViewState


class SubtitleView(Protocol):
    def apply_view_state(self, view_state: SubtitleViewState) -> None: ...


class SubtitlePresentationController:
    def __init__(self, view: SubtitleView | None = None) -> None:
        self._view = view
        self._view_state = SubtitleViewState()

    def bind_view(self, view: SubtitleView) -> None:
        self._view = view
        self._push_state()

    def export_view_state(self) -> SubtitleViewState:
        return replace(self._view_state)

    def handle_subtitle(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            self.clear_subtitle()
            return
        if self._view_state.subtitle_text == cleaned:
            self._push_state()
            return
        self._view_state.subtitle_text = cleaned
        self._view_state.animation_start_progress = 0.0
        self._view_state.animation_progress = 1.0
        self._push_state()

    def handle_status(self, text: str) -> None:
        cleaned = text.strip()
        if self._view_state.status_text == cleaned:
            return
        self._view_state.status_text = cleaned
        self._push_state()

    def handle_error(self, message: str) -> None:
        self._view_state.status_text = f"[ERROR] {message}"
        self._view_state.subtitle_text = ""
        self._view_state.animation_start_progress = 0.0
        self._view_state.animation_progress = 1.0
        self._push_state()

    def clear_subtitle(self) -> None:
        if not self._view_state.subtitle_text:
            self._push_state()
            return
        self._view_state.subtitle_text = ""
        self._view_state.animation_start_progress = 0.0
        self._view_state.animation_progress = 1.0
        self._push_state()

    def _push_state(self) -> None:
        if self._view is None:
            return
        self._view.apply_view_state(self.export_view_state())
