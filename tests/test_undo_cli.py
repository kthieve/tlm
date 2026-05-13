import argparse
from pathlib import Path
from unittest.mock import patch
from tlm.cli import cmd_undo_ns
from tlm.safety.snapshot import SnapshotInfo


@patch("tlm.safety.snapshot.list_snapshots")
@patch("tlm.safety.snapshot.restore_snapshot")
@patch("rich.console.Console.print")
def test_undo_list(mock_print, mock_restore, mock_list):
    mock_list.return_value = [
        SnapshotInfo(id="git-123", timestamp=123.0, message="snap1", is_git=True),
        SnapshotInfo(id="file-456", timestamp=456.0, message="snap2", is_git=False),
    ]

    ns = argparse.Namespace(dir=".", snapshot_id=None, list=True, hard=False, dry_run=False)
    assert cmd_undo_ns(ns) == 0
    mock_list.assert_called_once()
    mock_restore.assert_not_called()


@patch("tlm.safety.snapshot.list_snapshots")
@patch("tlm.safety.snapshot.restore_snapshot")
@patch("builtins.input", return_value="y")
def test_undo_specific_confirm(mock_input, mock_restore, mock_list):
    mock_list.return_value = [
        SnapshotInfo(id="git-123", timestamp=123.0, message="snap1", is_git=True),
    ]
    mock_restore.return_value = True

    ns = argparse.Namespace(dir=".", snapshot_id="git-123", list=False, hard=False, dry_run=False)
    assert cmd_undo_ns(ns) == 0
    mock_restore.assert_called_with(Path(".").resolve(), "git-123")


@patch("tlm.safety.snapshot.list_snapshots")
def test_undo_not_found(mock_list):
    mock_list.return_value = []
    ns = argparse.Namespace(dir=".", snapshot_id="missing", list=False, hard=False, dry_run=False)
    assert cmd_undo_ns(ns) == 1


@patch("tlm.safety.snapshot.list_snapshots")
@patch("tlm.safety.snapshot.restore_snapshot")
def test_undo_dry_run(mock_restore, mock_list):
    mock_list.return_value = [
        SnapshotInfo(id="git-123", timestamp=123.0, message="snap1", is_git=True),
    ]
    ns = argparse.Namespace(dir=".", snapshot_id="git-123", list=False, hard=False, dry_run=True)
    assert cmd_undo_ns(ns) == 0
    mock_restore.assert_not_called()


@patch("tlm.safety.snapshot.list_snapshots")
@patch("tlm.safety.snapshot.restore_snapshot")
@patch("builtins.input", side_effect=["1", "y"])
def test_undo_interactive(mock_input, mock_restore, mock_list):
    mock_list.return_value = [
        SnapshotInfo(id="git-123", timestamp=123.0, message="snap1", is_git=True),
    ]
    mock_restore.return_value = True

    ns = argparse.Namespace(dir=".", snapshot_id=None, list=False, hard=False, dry_run=False)
    assert cmd_undo_ns(ns) == 0
    mock_restore.assert_called_with(Path(".").resolve(), "git-123")
