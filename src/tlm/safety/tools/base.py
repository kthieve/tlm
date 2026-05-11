"""Base interface for modular system tool wrappers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence


class ToolWrapper(ABC):
    """Abstract base for a modular tool wrapper."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The command name (e.g., 'git')."""

    @abstractmethod
    def is_readonly(self, argv: Sequence[str]) -> bool:
        """Determine if the specific invocation is read-only."""

    @abstractmethod
    def validate(self, argv: Sequence[str]) -> tuple[bool, str | None]:
        """Perform additional permission or safety checks. Returns (ok, error_message)."""
        return True, None
