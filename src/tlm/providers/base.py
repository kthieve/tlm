"""Provider protocol: completions + optional streaming + token estimate."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    id: str

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Non-streaming completion; raises on HTTP/auth errors."""
        ...

    def chat(self, messages: list[dict[str, str]], *, system: str | None = None) -> str:
        """Multi-turn chat using OpenAI-style message dicts (role/content)."""
        ...

    def stream(self, prompt: str, *, system: str | None = None) -> Iterator[str]:
        """Token/delta stream for terminal UX (optional)."""
        ...

    def count_tokens(self, text: str) -> int:
        """Rough token estimate for context trimming."""
        ...
