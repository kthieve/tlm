"""User config at $XDG_CONFIG_HOME/tlm/config.toml (read: tomllib; write: minimal serializer)."""

from __future__ import annotations

import json
import os
import sys
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
    memory_enabled: bool = True
    memory_ready_budget_chars: int = 800
    memory_auto_harvest_threshold_messages: int = 30
    memory_harvest_on_switch: bool = True
    # Lightpanda-backed ask web tools (see tlm.web.lightpanda); off until user installs binary.
    web_enabled: bool = False
    lightpanda_path: str | None = None
    web_dump: str = "markdown"  # "markdown" | "html"
    web_obey_robots: bool = True
    web_max_output_chars: int = 48_000
    web_disable_lightpanda_telemetry: bool = True
    web_allow_http: bool = False


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
    lines.append(f"memory_enabled = {str(bool(s.memory_enabled)).lower()}")
    lines.append(f"memory_ready_budget_chars = {int(s.memory_ready_budget_chars)}")
    lines.append(f"memory_auto_harvest_threshold_messages = {int(s.memory_auto_harvest_threshold_messages)}")
    lines.append(f"memory_harvest_on_switch = {str(bool(s.memory_harvest_on_switch)).lower()}")
    lines.append(f"web_enabled = {str(bool(s.web_enabled)).lower()}")
    if s.lightpanda_path is not None:
        lines.append(f"lightpanda_path = {_toml_escape_str(s.lightpanda_path)}")
    lines.append(f"web_dump = {_toml_escape_str(s.web_dump)}")
    lines.append(f"web_obey_robots = {str(bool(s.web_obey_robots)).lower()}")
    lines.append(f"web_max_output_chars = {int(s.web_max_output_chars)}")
    lines.append(
        f"web_disable_lightpanda_telemetry = {str(bool(s.web_disable_lightpanda_telemetry)).lower()}"
    )
    lines.append(f"web_allow_http = {str(bool(s.web_allow_http)).lower()}")
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
    def _bool(key: str, default: bool) -> bool:
        v = data.get(key)
        if v is None:
            return default
        return bool(v)

    return UserSettings(
        provider=data.get("provider") if isinstance(data.get("provider"), str) else None,
        model=data.get("model") if isinstance(data.get("model"), str) else None,
        models={str(k): str(v) for k, v in models.items() if isinstance(v, str)},
        temperature=float(data.get("temperature", 0.7)),
        timeout=float(data.get("timeout", 120.0)),
        safety_profile=str(data.get("safety_profile", "standard")),
        api_keys={str(k): str(v) for k, v in keys.items() if isinstance(v, str)},
        memory_enabled=_bool("memory_enabled", True),
        memory_ready_budget_chars=int(data.get("memory_ready_budget_chars", 800)),
        memory_auto_harvest_threshold_messages=int(data.get("memory_auto_harvest_threshold_messages", 30)),
        memory_harvest_on_switch=_bool("memory_harvest_on_switch", True),
        web_enabled=_bool("web_enabled", False),
        lightpanda_path=data.get("lightpanda_path") if isinstance(data.get("lightpanda_path"), str) else None,
        web_dump=str(data.get("web_dump", "markdown")),
        web_obey_robots=_bool("web_obey_robots", True),
        web_max_output_chars=int(data.get("web_max_output_chars", 48_000)),
        web_disable_lightpanda_telemetry=_bool("web_disable_lightpanda_telemetry", True),
        web_allow_http=_bool("web_allow_http", False),
    )


def warn_config_permissions() -> None:
    """Warn if config.toml is readable by group/other."""
    p = config_file_path()
    if not p.is_file():
        return
    try:
        mode = p.stat().st_mode & 0o777
    except OSError:
        return
    if mode > 0o600:
        print(
            f"tlm: warning: {p} permissions are {oct(mode)}; recommended chmod 600",
            file=sys.stderr,
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
