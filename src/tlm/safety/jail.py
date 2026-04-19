"""Path classification: freelist, jail, escape, denied."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from tlm.safety.permissions import EffectivePolicy

PathKind = Literal["free_rw", "free_ro", "jail", "escape", "denied"]


def _real(p: Path) -> Path:
    try:
        return p.resolve()
    except OSError:
        return Path(os.path.realpath(str(p)))


def _under_prefix(path: Path, prefix: Path) -> bool:
    try:
        path.relative_to(prefix)
        return True
    except ValueError:
        return False


def _any_prefix(path: Path, prefixes: list[str]) -> bool:
    for raw in prefixes:
        pre = _real(Path(os.path.expanduser(raw)))
        if _under_prefix(path, pre) or path == pre:
            return True
    return False


def classify_path(
    path: Path,
    policy: EffectivePolicy,
    jail_root: Path,
    *,
    op: Literal["read", "write"],
    once_rw: frozenset[str] | None = None,
    session_rw: frozenset[str] | None = None,
) -> PathKind:
    """Classify a path. `once_rw` / `session_rw` are extra realpath strings for consent grants."""
    rp = _real(path)
    if _any_prefix(rp, policy.deny_paths):
        return "denied"
    rw_sources = list(policy.allow_paths) + list(policy.escape_grants)
    if once_rw:
        rw_sources.extend(once_rw)
    if session_rw:
        rw_sources.extend(session_rw)
    if _any_prefix(rp, rw_sources):
        return "free_rw"
    if op == "read" and _any_prefix(rp, policy.read_paths):
        return "free_ro"
    if op == "write" and _any_prefix(rp, policy.read_paths):
        return "escape"
    jr = _real(jail_root)
    if _under_prefix(rp, jr):
        return "jail"
    return "escape"


def resolve_jailed_path(
    path: Path,
    policy: EffectivePolicy,
    jail_root: Path,
    *,
    op: Literal["read", "write"],
    once_rw: frozenset[str] | None = None,
    session_rw: frozenset[str] | None = None,
) -> tuple[PathKind, Path]:
    k = classify_path(path, policy, jail_root, op=op, once_rw=once_rw, session_rw=session_rw)
    return k, _real(path)
