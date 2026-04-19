"""Safety profiles: strict / standard / trusted (read-only fast path)."""

from __future__ import annotations

from dataclasses import replace
from enum import Enum
import shlex

from tlm.safety.permissions import EffectivePolicy


class SafetyProfile(str, Enum):
    strict = "strict"
    standard = "standard"
    trusted = "trusted"


# Commands considered read-only for trusted + --yes on `tlm do`.
_READ_ONLY = frozenset(
    {
        "ls",
        "dir",
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "pwd",
        "echo",
        "which",
        "whereis",
        "file",
        "stat",
        "id",
        "whoami",
        "uname",
        "date",
        "uptime",
        "df",
        "du",
        "free",
        "lscpu",
        "lspci",
        "lsusb",
        "sensors",
        "git",
    }
)


def normalize_profile(raw: str) -> SafetyProfile:
    try:
        return SafetyProfile(str(raw).strip().lower())
    except ValueError:
        return SafetyProfile.standard


def is_readonly_argv(argv: list[str]) -> bool:
    if not argv:
        return False
    if argv[0] in ("sudo", "doas", "su", "pkexec"):
        return False
    cmd = argv[0].split("/")[-1]
    if cmd == "git":
        if len(argv) < 2:
            return False
        return argv[1] in {"status", "diff", "log", "show", "branch"}
    return cmd in _READ_ONLY


def argv_to_line(argv: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in argv)


def all_readonly(argvs: list[list[str]]) -> bool:
    return bool(argvs) and all(is_readonly_argv(a) for a in argvs)


def allow_do_auto_yes(profile: SafetyProfile, argvs: list[list[str]]) -> bool:
    return profile == SafetyProfile.trusted and all_readonly(argvs)


def overlay_effective_policy(ep: EffectivePolicy, profile: str | SafetyProfile) -> EffectivePolicy:
    """Apply safety_profile on top of permissions.toml (stricter profile tightens network/sandbox)."""
    p = profile if isinstance(profile, SafetyProfile) else normalize_profile(profile)
    if p == SafetyProfile.strict:
        return replace(ep, network_mode="off", sandbox_engine="auto" if ep.sandbox_engine != "off" else "off")
    if p == SafetyProfile.standard:
        return ep
    if p == SafetyProfile.trusted:
        return replace(ep, network_mode="on", sandbox_engine="off")
    return ep
