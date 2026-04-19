"""permissions.toml load/save and effective policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from tlm.safety.permissions import effective_policy, load_permissions_file


def test_validate_rejects_root_on_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = tmp_path / "tlm"
    cfg.mkdir()
    (cfg / "permissions.toml").write_text(
        '[global]\nnetwork_mode = "ask"\nsandbox_engine = "auto"\nallow_paths = ["/"]\n'
        'read_paths = []\ndeny_paths = []\nallow_commands = []\ndeny_commands = []\n\n'
        "[escape_grants]\npaths = []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_permissions_file()


def test_effective_policy_merge_escape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = tmp_path / "tlm"
    cfg.mkdir()
    (cfg / "permissions.toml").write_text(
        """
[global]
network_mode = "ask"
sandbox_engine = "auto"
allow_paths = []
read_paths = []
deny_paths = []
allow_commands = []
deny_commands = []

[escape_grants]
paths = ["/tmp/tlm_freelist_test"]
""",
        encoding="utf-8",
    )
    ep = effective_policy(Path("/tmp"))
    assert "/tmp/tlm_freelist_test" in ep.escape_grants
