"""
Guardrails for `tlm do` (shell-ish execution).

Preview → explicit user approval → subprocess with timeouts,
no shell=True, cwd restrictions, and deny patterns below.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

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

# Network-capable tools (first argv segment basename).
_NETWORK_TOOLS = frozenset(
    {
        "curl",
        "wget",
        "ssh",
        "scp",
        "rsync",
        "nc",
        "netcat",
        "ncat",
        "telnet",
        "openssl",
    }
)


def check_command_line(line: str) -> tuple[bool, str]:
    """Return (ok, reason). If not ok, do not execute."""
    s = line.strip()
    if not s:
        return False, "empty command"
    for pat in _DENY_RES:
        if pat.search(s):
            return False, f"blocked pattern: {pat.pattern}"
    return True, ""


def argv_uses_network_tool(argv: list[str]) -> bool:
    if not argv:
        return False
    for a in argv:
        base = a.split("/")[-1]
        if base in _NETWORK_TOOLS:
            return True
    return False


def check_network_argv(argv: list[str], network_mode: str, *, approved: bool) -> tuple[bool, str]:
    """network_mode: off | ask | on. When ask, caller must set approved after prompting."""
    if not argv_uses_network_tool(argv):
        return True, ""
    mode = network_mode.strip().lower()
    if mode == "on":
        return True, ""
    if mode == "off":
        return False, "network tools blocked (network_mode=off)"
    if mode == "ask":
        if approved:
            return True, ""
        return False, "network tools need approval (network_mode=ask)"
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


def check_argv_with_network(
    argv: list[str],
    *,
    network_mode: str,
    net_approved: bool,
) -> tuple[bool, str]:
    ok, reason = check_argv(argv)
    if not ok:
        return ok, reason
    return check_network_argv(argv, network_mode, approved=net_approved)


def path_like_args(argv: list[str]) -> list[Path]:
    """Best-effort path tokens for sandbox classification (conservative)."""
    out: list[Path] = []
    for a in argv:
        if a.startswith("--") and "=" in a:
            val = a.split("=", 1)[1]
            if val.startswith(("/", "~")):
                out.append(Path(val))
        elif not a.startswith("-") and (a.startswith("/") or a.startswith("~")):
            out.append(Path(a))
    return out


def split_for_preview(line: str) -> list[str]:
    """Parse like a shell for display; execution path should use same argv."""
    try:
        return shlex.split(line, posix=True)
    except ValueError as e:
        raise ValueError(f"unparseable command: {e}") from e
