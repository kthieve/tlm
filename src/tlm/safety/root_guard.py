"""Root / elevation guard for write/do."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Any

from tlm.safety.profiles import SafetyProfile, normalize_profile

SYSTEM_WRITE_PREFIXES = (
    "/etc",
    "/boot",
    "/usr",
    "/opt",
    "/var",
    "/sys",
    "/proc",
    "/lib",
    "/lib64",
    "/root",
    "/srv",
    "/dev",
)

_ELEVATION = frozenset({"sudo", "doas", "su", "pkexec", "runuser"})


def is_euid_root() -> bool:
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def trusted_blocked_when_root() -> bool:
    return is_euid_root()


def argv_has_elevation(argv: list[str]) -> bool:
    if not argv:
        return False
    cmd = argv[0].split("/")[-1]
    if cmd in _ELEVATION:
        return True
    # systemd-run --uid=0
    if cmd == "systemd-run" and any(
        a in ("--uid=0", "-u0") or (a.startswith("--uid=") and a.endswith("0")) for a in argv
    ):
        return True
    if cmd == "machinectl" and "shell" in argv:
        return True
    try:
        st = os.stat(argv[0])
        return bool(st.st_mode & stat.S_ISUID) or bool(st.st_mode & stat.S_ISGID)
    except OSError:
        return False


def path_under_system_root(p: Path) -> bool:
    try:
        s = str(p.resolve())
    except OSError:
        s = str(Path(os.path.realpath(str(p))))
    for pre in SYSTEM_WRITE_PREFIXES:
        if s == pre or s.startswith(pre + "/"):
            return True
    return False


def check_write_paths(
    paths: list[Path],
    profile: str | SafetyProfile,
) -> tuple[bool, str | None]:
    """Returns (ok, error_message)."""
    prof = normalize_profile(str(profile)) if not isinstance(profile, SafetyProfile) else profile
    bad = [p for p in paths if path_under_system_root(p)]
    if not bad:
        return True, None
    if prof in (SafetyProfile.strict, SafetyProfile.standard):
        return False, "root guard: writes under system directories are blocked in strict/standard profile"
    return True, None  # trusted: phrase gate happens in prompt_root_trusted


ROOT_PHRASE = "I accept root risk"


def prompt_root_trusted(paths: list[Path]) -> bool:
    if not sys.stdin.isatty():
        print("tlm: root-risk paths require a TTY to confirm.", file=sys.stderr)
        return False
    print("tlm: the following paths are under system locations (root risk):", flush=True)
    for p in paths:
        print(f"  {p}", flush=True)
    try:
        s = input(f"Type exactly: {ROOT_PHRASE}\n").strip()
    except EOFError:
        return False
    return s == ROOT_PHRASE


def log_root_event(payload: dict[str, Any]) -> None:
    from tlm.telemetry.log import log_event

    log_event({**payload, "kind": "root_guard"})
