"""User config at $XDG_CONFIG_HOME/tlm/config.toml (read: tomllib; write: minimal serializer)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import tomllib


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        p = Path(base).expanduser() / "tlm"
    else:
        p = Path.home() / ".config" / "tlm"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_file_path() -> Path:
    return config_dir() / "config.toml"


@dataclass
class UserSettings:
    provider: str | None = None
    model: str | None = None  # global default model name
    models: dict[str, str] = field(default_factory=dict)
    temperature: float = 0.7
    timeout: float = 120.0
    safety_profile: str = "standard"
    api_keys: dict[str, str] = field(default_factory=dict)


def _toml_escape_str(s: str) -> str:
    return json.dumps(s)


def save_settings(s: UserSettings) -> None:
    path = config_file_path()
    lines: list[str] = []
    if s.provider is not None:
        lines.append(f"provider = {_toml_escape_str(s.provider)}")
    if s.model is not None:
        lines.append(f"model = {_toml_escape_str(s.model)}")
    lines.append(f"temperature = {float(s.temperature)}")
    lines.append(f"timeout = {float(s.timeout)}")
    lines.append(f"safety_profile = {_toml_escape_str(s.safety_profile)}")
    if s.models:
        lines.append("")
        lines.append("[models]")
        for k, v in sorted(s.models.items()):
            lines.append(f"{k} = {_toml_escape_str(v)}")
    if s.api_keys:
        lines.append("")
        lines.append("[keys]")
        for k, v in sorted(s.api_keys.items()):
            lines.append(f"{k} = {_toml_escape_str(v)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_settings() -> UserSettings:
    path = config_file_path()
    if not path.is_file():
        return UserSettings()
    raw = path.read_text(encoding="utf-8")
    data = tomllib.loads(raw)
    if not isinstance(data, dict):
        return UserSettings()
    models = data.get("models") or {}
    keys = data.get("keys") or {}
    if not isinstance(models, dict):
        models = {}
    if not isinstance(keys, dict):
        keys = {}
    return UserSettings(
        provider=data.get("provider") if isinstance(data.get("provider"), str) else None,
        model=data.get("model") if isinstance(data.get("model"), str) else None,
        models={str(k): str(v) for k, v in models.items() if isinstance(v, str)},
        temperature=float(data.get("temperature", 0.7)),
        timeout=float(data.get("timeout", 120.0)),
        safety_profile=str(data.get("safety_profile", "standard")),
        api_keys={str(k): str(v) for k, v in keys.items() if isinstance(v, str)},
    )


def merged_api_key(provider_id: str, settings: UserSettings | None = None) -> str | None:
    """Env overrides file keys."""
    from tlm.config import api_key_for

    envk = api_key_for(provider_id)
    if envk:
        return envk
    s = settings or load_settings()
    pid = provider_id.lower().replace("_", "-")
    return s.api_keys.get(pid) or s.api_keys.get(provider_id)
