"""
Guardrails for `tlm do` (shell-ish execution).

Full design: preview → explicit user approval → subprocess with timeouts,
no shell=True, cwd restrictions, and deny patterns below.
"""

from __future__ import annotations

import re
import shlex

# High-risk tokens; extend as needed (see AGENT_PLAN security section).
_DENY_RES = [
    re.compile(r"\brm\s+-rf\b", re.I),
    re.compile(r"\bmkfs\b", re.I),
    re.compile(r"\bdd\s+if=", re.I),
    re.compile(r">\s*/dev/", re.I),
    re.compile(r"\bchmod\s+.*777", re.I),
    re.compile(r"curl\s+.*\|\s*(?:ba)?sh", re.I),
]


def check_command_line(line: str) -> tuple[bool, str]:
    """Return (ok, reason). If not ok, do not execute."""
    s = line.strip()
    if not s:
        return False, "empty command"
    for pat in _DENY_RES:
        if pat.search(s):
            return False, f"blocked pattern: {pat.pattern}"
    return True, ""


def split_for_preview(line: str) -> list[str]:
    """Parse like a shell for display; execution path should use same argv."""
    try:
        return shlex.split(line, posix=True)
    except ValueError as e:
        raise ValueError(f"unparseable command: {e}") from e
