"""
Guardrails for `tlm do` (shell-ish execution).

Preview → explicit user approval → subprocess with timeouts,
no shell=True, cwd restrictions, and deny patterns below.
"""

from __future__ import annotations

import re
import shlex

_DENY_RES = [
    re.compile(r"\brm\s+-rf\b", re.I),
    re.compile(r"\bmkfs\b", re.I),
    re.compile(r"\bdd\s+if=", re.I),
    re.compile(r">\s*/dev/", re.I),
    re.compile(r"\bchmod\s+.*777", re.I),
    re.compile(r"curl\s+.*\|\s*(?:ba)?sh", re.I),
    re.compile(r"wget\s+.*\|\s*(?:ba)?sh", re.I),
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bsu\b", re.I),
    re.compile(r"\bdoas\b", re.I),
    re.compile(r"\bpkexec\b", re.I),
    re.compile(r"[>|]\s*/etc/", re.I),
    re.compile(r"[>|]\s*/boot/", re.I),
    re.compile(r"[>|]\s*/sys/", re.I),
    re.compile(r"[>|]\s*/proc/", re.I),
]

_PKG_MANAGERS = frozenset({"apt", "apt-get", "dnf", "yum", "pacman", "zypper", "apk"})


def check_command_line(line: str) -> tuple[bool, str]:
    """Return (ok, reason). If not ok, do not execute."""
    s = line.strip()
    if not s:
        return False, "empty command"
    for pat in _DENY_RES:
        if pat.search(s):
            return False, f"blocked pattern: {pat.pattern}"
    return True, ""


def check_argv(argv: list[str]) -> tuple[bool, str]:
    if not argv:
        return False, "empty argv"
    line = " ".join(shlex.quote(a) for a in argv)
    ok, reason = check_command_line(line)
    if not ok:
        return ok, reason
    cmd = argv[0].split("/")[-1]
    if cmd in _PKG_MANAGERS and "--dry-run" not in argv and "-s" not in argv:
        return False, "package manager without --dry-run (or -s) is blocked"
    return True, ""


def split_for_preview(line: str) -> list[str]:
    """Parse like a shell for display; execution path should use same argv."""
    try:
        return shlex.split(line, posix=True)
    except ValueError as e:
        raise ValueError(f"unparseable command: {e}") from e
