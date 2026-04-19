"""OS sandbox argv wrapping."""

from __future__ import annotations

from pathlib import Path

from tlm.safety.permissions import EffectivePolicy
from tlm.safety import sandbox


def test_wrap_no_engine_returns_argv() -> None:
    ep = EffectivePolicy(
        network_mode="off",
        sandbox_engine="off",
        allow_paths=[],
        read_paths=[],
        deny_paths=[],
        allow_commands=[],
        deny_commands=[],
        escape_grants=[],
        cwd=Path.cwd(),
        project_root=None,
    )
    argv = ["echo", "ok"]
    assert sandbox.wrap_argv(argv, cwd=Path.cwd(), policy=ep, unshare_net=True) == argv
