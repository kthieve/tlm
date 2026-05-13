"""Generic wrapper for simple read-only system tools."""

from __future__ import annotations

from typing import Sequence
from tlm.safety.tools.base import ToolWrapper


class ReadOnlyToolWrapper(ToolWrapper):
    def __init__(self, command_name: str):
        self._name = command_name

    @property
    def name(self) -> str:
        return self._name

    def is_readonly(self, argv: Sequence[str]) -> bool:
        return True

    def validate(self, argv: Sequence[str]) -> tuple[bool, str | None]:
        return True, None
