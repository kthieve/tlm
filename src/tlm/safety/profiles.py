"""Safety profiles: strict / standard / trusted (read-only fast path)."""

from __future__ import annotations

from enum import Enum
import shlex


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
