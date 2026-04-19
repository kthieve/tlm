"""Interactive jail-escape consent; `--yes` never auto-grants."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from tlm.safety.permissions import load_permissions_file, save_permissions_file
from tlm.safety.profiles import SafetyProfile, normalize_profile

EscapeChoice = Literal["once", "session", "persist", "cancel", "refuse"]

_SESSION_RW: set[str] = set()


def session_rw_paths() -> frozenset[str]:
    return frozenset(_SESSION_RW)


def session_add_rw(realpath: str) -> None:
    _SESSION_RW.add(realpath)


def prompt_escape(
    items: list[tuple[str, str]],
    *,
    profile: str | SafetyProfile,
    auto_yes: bool,
) -> EscapeChoice:
    """items: (rw|r, path). Non-TTY → refuse. auto_yes → refuse (no auto-grant)."""
    if auto_yes or not sys.stdin.isatty():
        print(
            "tlm: paths outside sandbox need explicit consent; refusing (non-interactive or --yes).",
            file=sys.stderr,
        )
        return "refuse"
    prof = profile if isinstance(profile, SafetyProfile) else normalize_profile(str(profile))
    print("tlm: the following paths fall OUTSIDE the sandbox", flush=True)
    for kind, p in items:
        print(f"  {kind.upper():2}  {p}", flush=True)
    if prof == SafetyProfile.strict:
        print("grant access? [once/cancel] (strict: no session/persist)", flush=True)
    else:
        print("grant access? [once/session/persist/cancel]", flush=True)
    while True:
        try:
            ans = input("Choice: ").strip().lower()
        except EOFError:
            return "cancel"
        if ans in ("n", "no", "cancel", ""):
            return "cancel"
        if ans == "once":
            return "once"
        if prof != SafetyProfile.strict:
            if ans == "session":
                return "session"
            if ans == "persist":
                return _confirm_persist(items)
        print("unrecognized; try once" + ("" if prof == SafetyProfile.strict else ", session, persist") + ", cancel")


def _confirm_persist(items: list[tuple[str, str]]) -> EscapeChoice:
    print("--- will append to permissions.toml [escape_grants].paths ---", flush=True)
    for _, p in items:
        print(f"  + {p}", flush=True)
    try:
        c2 = input("Type YES to persist: ").strip()
    except EOFError:
        return "cancel"
    if c2 != "YES":
        print("not persisted.", flush=True)
        return "cancel"
    pf = load_permissions_file()
    existing = set(pf.escape_grants)
    for _, p in items:
        rp = str(Path(p).expanduser().resolve())
        if rp not in existing:
            pf.escape_grants.append(rp)
            existing.add(rp)
    save_permissions_file(pf)
    print("saved escape_grants.", flush=True)
    return "persist"


def apply_once_grants(paths: list[str]) -> frozenset[str]:
    out: set[str] = set()
    for p in paths:
        out.add(str(Path(p).expanduser().resolve()))
    return frozenset(out)
