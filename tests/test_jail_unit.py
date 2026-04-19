"""Path classification."""

from __future__ import annotations

from pathlib import Path

from tlm.safety.jail import classify_path
from tlm.safety.permissions import EffectivePolicy


def test_classify_jail_under_base(tmp_path: Path) -> None:
    base = tmp_path / "proj"
    base.mkdir()
    ep = EffectivePolicy(
        network_mode="ask",
        sandbox_engine="auto",
        allow_paths=[],
        read_paths=[],
        deny_paths=[],
        allow_commands=[],
        deny_commands=[],
        escape_grants=[],
        cwd=base,
        project_root=None,
    )
    f = base / "a.txt"
    assert classify_path(f, ep, base, op="write") == "jail"


def test_classify_free_rw(tmp_path: Path) -> None:
    base = tmp_path / "proj"
    base.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    ep = EffectivePolicy(
        network_mode="ask",
        sandbox_engine="auto",
        allow_paths=[str(other)],
        read_paths=[],
        deny_paths=[],
        allow_commands=[],
        deny_commands=[],
        escape_grants=[],
        cwd=base,
        project_root=None,
    )
    assert classify_path(other / "x", ep, base, op="write") == "free_rw"
