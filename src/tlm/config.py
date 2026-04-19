"""Paths and settings (API keys via env / future GUI)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def xdg_data_home() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base).expanduser()
    return Path.home() / ".local" / "share"


def data_dir() -> Path:
    d = xdg_data_home() / "tlm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sessions_dir() -> Path:
    d = data_dir() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def xdg_state_home() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base).expanduser()
    return Path.home() / ".local" / "state"


def state_dir() -> Path:
    d = xdg_state_home() / "tlm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_provider() -> str:
    return os.environ.get("TLM_PROVIDER", "openrouter").strip().lower()


def api_key_for(provider: str) -> str | None:
    """Read `TLM_<PROVIDER>_API_KEY` or generic `TLM_API_KEY`."""
    p = provider.upper().replace("-", "_")
    return os.environ.get(f"TLM_{p}_API_KEY") or os.environ.get("TLM_API_KEY")


def base_url_env(provider: str) -> str | None:
    p = provider.upper().replace("-", "_")
    return os.environ.get(f"TLM_{p}_BASE_URL")


def default_model_env() -> str | None:
    v = os.environ.get("TLM_MODEL")
    return v.strip() if v else None
