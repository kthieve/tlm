import time
from unittest.mock import MagicMock, patch

import pytest
from tlm.safety.snapshot import create_snapshot, list_snapshots, restore_snapshot


@pytest.fixture
def temp_workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "file1.txt").write_text("hello")
    return ws


def test_create_snapshot_file_fallback(temp_workspace):
    # Ensure it's NOT a git repo to trigger file fallback
    with patch("tlm.safety.snapshot._is_git_repo", return_value=False):
        sid = create_snapshot(temp_workspace, "test message")
        assert sid is not None
        assert sid.startswith("file-")

        snapshots = list_snapshots(temp_workspace)
        assert len(snapshots) == 1
        assert snapshots[0].id == sid
        assert snapshots[0].message == "test message"
        assert snapshots[0].is_git is False

        # Modify file
        (temp_workspace / "file1.txt").write_text("world")

        # Restore
        ok = restore_snapshot(temp_workspace, sid)
        assert ok is True
        assert (temp_workspace / "file1.txt").read_text() == "hello"


def test_create_snapshot_git_mock(temp_workspace):
    with patch("tlm.safety.snapshot._is_git_repo", return_value=True):
        with patch("subprocess.run") as mock_run:
            # Mock 'git stash create'
            mock_res = MagicMock()
            mock_res.stdout = "abc123sha"
            mock_res.returncode = 0
            mock_run.return_value = mock_res

            sid = create_snapshot(temp_workspace, "git snap")
            assert sid is not None
            assert sid.startswith("git-")

            snapshots = list_snapshots(temp_workspace)
            assert len(snapshots) == 1
            assert snapshots[0].id == sid
            assert snapshots[0].message == "git snap"
            assert snapshots[0].is_git is True

            # Verify SHA storage
            sha_file = temp_workspace / ".tlm" / "snapshots" / f"{sid}.sha"
            assert sha_file.exists()
            assert sha_file.read_text().startswith("abc123sha")


def test_list_snapshots_ordering(temp_workspace):
    with patch("tlm.safety.snapshot._is_git_repo", return_value=False):
        create_snapshot(temp_workspace, "msg1")
        time.sleep(1.1)  # Ensure different timestamps
        create_snapshot(temp_workspace, "msg2")

        snapshots = list_snapshots(temp_workspace)
        assert len(snapshots) == 2
        assert snapshots[0].message == "msg2"  # Newest first
        assert snapshots[1].message == "msg1"


def test_restore_nonexistent(temp_workspace):
    assert restore_snapshot(temp_workspace, "git-999999") is False
    assert restore_snapshot(temp_workspace, "file-999999") is False
