"""Resolve provider id + settings → concrete LLM client."""

from __future__ import annotations

from tlm.config import base_url_env, default_model_env, default_provider
from tlm.providers.base import LLMProvider
from tlm.providers.openai_compat import (
    DEFAULT_BASE_URLS,
    DEFAULT_MODELS,
    OpenAICompatProvider,
    fetch_remote_model_ids,
)
from tlm.providers.stub import StubProvider
from tlm.settings import UserSettings, load_settings, merged_api_key

REAL_PROVIDER_IDS = ("openai", "deepseek", "chutes", "openrouter", "nano-gpt")


def normalize_provider_id(raw: str) -> str:
    s = raw.strip().lower().replace("_", "-")
    if s == "nanogpt":
        return "nano-gpt"
    return s


def list_provider_ids() -> list[str]:
    return sorted({"stub", *REAL_PROVIDER_IDS})


def _model_for(pid: str, settings: UserSettings) -> str:
    return (
        default_model_env()
        or settings.models.get(pid)
        or (settings.model or "")
        or DEFAULT_MODELS.get(pid)
        or "gpt-4o-mini"
    )


def resolved_model(provider_id: str, settings: UserSettings | None = None) -> str:
    """Effective model id for *provider_id* given *settings* (env + per-provider + global + built-in default)."""
    return _model_for(normalize_provider_id(provider_id), settings or load_settings())


def list_remote_model_ids(
    provider_id: str,
    *,
    settings: UserSettings | None = None,
    timeout: float = 45.0,
) -> list[str]:
    """Fetch model ids from the provider's ``/v1/models`` endpoint (requires API key)."""
    pid = normalize_provider_id(provider_id)
    if pid == "stub":
        raise ValueError("`stub` has no remote model list.")
    if pid not in REAL_PROVIDER_IDS:
        raise ValueError(f"Unknown provider: {provider_id!r}. Known: {sorted(REAL_PROVIDER_IDS)}")
    s = settings or load_settings()
    key = merged_api_key(pid, s)
    if not key:
        raise ValueError(
            f"No API key for provider {pid!r}. Set `keys` in config or TLM_{pid.upper().replace('-', '_')}_API_KEY."
        )
    base = _base_url_for(pid)
    return fetch_remote_model_ids(provider_id=pid, base_url=base, api_key=key, timeout=timeout)


def _base_url_for(pid: str) -> str:
    u = base_url_env(pid)
    if u:
        return u.rstrip("/")
    if pid in DEFAULT_BASE_URLS:
        return DEFAULT_BASE_URLS[pid]
    raise ValueError(
        f"No base URL for provider {pid!r}; set TLM_{pid.upper().replace('-', '_')}_BASE_URL"
    )


def get_provider(
    provider_id: str | None = None,
    *,
    settings: UserSettings | None = None,
) -> LLMProvider:
    s = settings or load_settings()
    pid = normalize_provider_id(provider_id or s.provider or default_provider())
    if pid == "stub":
        return StubProvider("stub")
    if pid not in REAL_PROVIDER_IDS:
        raise ValueError(f"Unknown provider: {provider_id!r}. Known: {list_provider_ids()}")
    key = merged_api_key(pid, s)
    if not key:
        return StubProvider(pid)
    try:
        base = _base_url_for(pid)
    except ValueError:
        return StubProvider(pid)
    model = _model_for(pid, s)
    return OpenAICompatProvider(
        id=pid,
        base_url=base,
        api_key=key,
        model=model,
        timeout=float(s.timeout),
        temperature=float(s.temperature),
    )


def describe_providers(settings: UserSettings | None = None) -> list[tuple[str, bool, str]]:
    """Rows: provider_id, key_set, model."""
    s = settings or load_settings()
    rows: list[tuple[str, bool, str]] = [("stub", True, "(stub)")]
    for pid in REAL_PROVIDER_IDS:
        key = bool(merged_api_key(pid, s))
        rows.append((pid, key, _model_for(pid, s)))
    return rows
