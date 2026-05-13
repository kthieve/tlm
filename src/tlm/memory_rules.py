"""Structured management of memory rules (what to store vs never store)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found, no-redef]

from tlm.settings import config_dir


@dataclass
class MemoryRule:
    id: str
    text: str
    type: str  # 'store' or 'never'

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "text": self.text, "type": self.type}


DEFAULT_RULES = [
    MemoryRule("os_info", "OS / distro, desktop, locale, timezone (generic)", "store"),
    MemoryRule("hw_info", "CPU / GPU / RAM summary, shell, editor preferences", "store"),
    MemoryRule("project_paths", "Stable project paths, workflow preferences, tool versions", "store"),
    MemoryRule("api_keys", "API keys, tokens, passwords, private keys, JWTs, bearer strings", "never"),
    MemoryRule("ssh_keys", "SSH private keys or BEGIN ... PRIVATE KEY blocks", "never"),
    MemoryRule("env_secrets", "High-entropy KEY=value env-style secrets", "never"),
    MemoryRule("url_creds", "URLs with embedded credentials (user:pass@)", "never"),
]


def rules_file_path() -> Path:
    return config_dir() / "memory_rules.toml"


def load_memory_rules() -> list[MemoryRule]:
    """Load rules from memory_rules.toml, falling back to defaults if missing or broken."""
    p = rules_file_path()
    if not p.is_file():
        return list(DEFAULT_RULES)

    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        rules_data = data.get("rules", [])
        if not isinstance(rules_data, list):
            return list(DEFAULT_RULES)

        rules = []
        for r in rules_data:
            if isinstance(r, dict) and "id" in r and "text" in r and "type" in r:
                rules.append(MemoryRule(id=str(r["id"]), text=str(r["text"]), type=str(r["type"])))
        return rules if rules else list(DEFAULT_RULES)
    except Exception:
        return list(DEFAULT_RULES)


def save_memory_rules(rules: list[MemoryRule]) -> None:
    """Save rules to memory_rules.toml in TOML format."""
    p = rules_file_path()
    # Simple TOML-like output to avoid extra dependencies for writing
    lines = ["# tlm memory rules configuration", "", "[[rules]]"]
    
    # We'll use a simple formatter since we only have a flat list of rules
    output = ["# tlm memory rules configuration", ""]
    for r in rules:
        output.append("[[rules]]")
        output.append(f'id = "{r.id}"')
        output.append(f'text = "{r.text}"')
        output.append(f'type = "{r.type}"')
        output.append("")
    
    p.write_text("\n".join(output), encoding="utf-8")


def format_rules_for_prompt() -> str:
    """Format active rules for inclusion in a system prompt."""
    rules = load_memory_rules()
    
    store = [r.text for r in rules if r.type == "store"]
    never = [r.text for r in rules if r.type == "never"]
    
    lines = ["What to store"]
    for s in store:
        lines.append(f"- {s}")
    
    lines.append("")
    lines.append("Never store")
    for n in never:
        lines.append(f"- {n}")
    
    lines.append("")
    lines.append("Items are capped in length; obvious secrets are rejected or redacted.")
    
    return "\n".join(lines)
