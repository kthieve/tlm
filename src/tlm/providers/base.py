"""Provider protocol: map user text → model reply (streaming later)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    id: str

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Non-streaming completion; raises on HTTP/auth errors."""
        ...
