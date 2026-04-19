"""Placeholder provider until HTTP integrations land."""

from __future__ import annotations

from dataclasses import dataclass

from tlm.config import api_key_for


@dataclass
class StubProvider:
    id: str

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        key = api_key_for(self.id)
        key_state = "set" if key else "missing (set TLM_API_KEY or TLM_<PROVIDER>_API_KEY)"
        sys_note = f"\n[system: {system[:80]}…]" if system and len(system) > 80 else ""
        if system and len(system) <= 80:
            sys_note = f"\n[system: {system}]"
        return (
            f"[{self.id}] stub reply — API key {key_state}.{sys_note}\n"
            f"Prompt ({len(prompt)} chars): {prompt[:200]}"
            + ("…" if len(prompt) > 200 else "")
        )
