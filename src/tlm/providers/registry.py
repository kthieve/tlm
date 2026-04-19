"""Register concrete providers; wire HTTP + env keys in later tasks."""

from __future__ import annotations

from typing import Callable

from tlm.config import default_provider
from tlm.providers.base import LLMProvider
from tlm.providers.stub import StubProvider

ProviderFactory = Callable[[], LLMProvider]

_FACTORIES: dict[str, ProviderFactory] = {
    "openai": lambda: StubProvider("openai"),
    "deepseek": lambda: StubProvider("deepseek"),
    "chutes": lambda: StubProvider("chutes"),
    "openrouter": lambda: StubProvider("openrouter"),
    "nano-gpt": lambda: StubProvider("nano-gpt"),
}


def normalize_provider_id(raw: str) -> str:
    s = raw.strip().lower().replace("_", "-")
    if s == "nanogpt":
        return "nano-gpt"
    return s


def list_provider_ids() -> list[str]:
    return sorted(_FACTORIES.keys())


def get_provider(provider_id: str | None = None) -> LLMProvider:
    pid = normalize_provider_id(provider_id or default_provider())
    factory = _FACTORIES.get(pid)
    if factory is None:
        raise ValueError(f"Unknown provider: {provider_id!r}. Known: {list_provider_ids()}")
    return factory()
