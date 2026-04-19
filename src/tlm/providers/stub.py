"""Placeholder provider until HTTP integrations land."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from tlm.config import api_key_for
from tlm.providers.openai_compat import count_tokens_text


@dataclass
class StubProvider:
    id: str

    def chat(self, messages: list[dict[str, str]], *, system: str | None = None) -> str:
        last = messages[-1]["content"] if messages else ""
        return self.complete(last, system=system)

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        key = api_key_for(self.id)
        key_state = "set" if key else "missing (set TLM_API_KEY or TLM_<PROVIDER>_API_KEY)"
        sys_note = ""
        if system:
            sys_note = f"\n[system: {system[:80]}…]" if len(system) > 80 else f"\n[system: {system}]"
        return (
            f"[{self.id}] stub reply — API key {key_state}.{sys_note}\n"
            f"Prompt ({len(prompt)} chars): {prompt[:200]}"
            + ("…" if len(prompt) > 200 else "")
        )

    def stream(self, prompt: str, *, system: str | None = None) -> Iterator[str]:
        yield self.complete(prompt, system=system)

    def count_tokens(self, text: str) -> int:
        return count_tokens_text(text)
