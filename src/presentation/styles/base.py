from argparse import Namespace
from typing import Protocol

from presentation.model import SubtitleStyleSpec

DEFAULT_STYLE_ID = "default"


class SubtitleStyle(Protocol):
    style_id: str
    display_name: str

    def build_spec(self, args: Namespace) -> SubtitleStyleSpec:
        ...
