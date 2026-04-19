"""Root / elevation guard."""

from __future__ import annotations

from pathlib import Path

from tlm.safety.profiles import SafetyProfile
from tlm.safety.root_guard import argv_has_elevation, check_write_paths, path_under_system_root


def test_path_under_etc() -> None:
    assert path_under_system_root(Path("/etc/hosts")) is True


def test_check_write_strict() -> None:
    ok, msg = check_write_paths([Path("/etc/foo")], SafetyProfile.strict)
    assert ok is False
    assert msg is not None


def test_argv_sudo() -> None:
    assert argv_has_elevation(["sudo", "ls"]) is True
    assert argv_has_elevation(["ls"]) is False
