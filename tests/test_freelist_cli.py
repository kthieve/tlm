"""Freelist CLI mutations."""

from __future__ import annotations

from pathlib import Path

import pytest

from tlm.safety.permissions import add_freelist_path, load_permissions_file, remove_freelist_path


def test_add_remove_global(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "tlm").mkdir(parents=True)
    d = tmp_path / "work"
    d.mkdir()
    add_freelist_path(str(d), read_only=False, project=False, project_root=None)
    pf = load_permissions_file()
    assert str(d.resolve()) in pf.allow_paths
    assert remove_freelist_path(str(d), project=False, project_root=None) is True
    pf2 = load_permissions_file()
    assert str(d.resolve()) not in pf2.allow_paths
