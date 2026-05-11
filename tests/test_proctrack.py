import json
import os
import signal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tlm.safety.proctrack import (
    ProcInfo,
    kill_all,
    list_processes,
    register_process,
    unregister_process,
)


@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "test_proctrack"
    d.mkdir()
    return d


def test_registration_and_list(temp_dir):
    # Mock _is_running to always True
    with patch("tlm.safety.proctrack._is_running", return_value=True):
        pid = 12345
        pgid = 12345
        argv = ["echo", "hello"]
        
        proc_id = register_process(temp_dir, pid, pgid, argv)
        assert proc_id is not None
        
        procs = list_processes(temp_dir)
        assert len(procs) == 1
        assert procs[0].pid == pid
        assert procs[0].argv == argv
        
        unregister_process(temp_dir, proc_id)
        assert len(list_processes(temp_dir)) == 0


def test_stale_pruning(temp_dir):
    # Register a process that's "running"
    with patch("tlm.safety.proctrack._is_running", return_value=True):
        register_process(temp_dir, 111, 111, ["true"])
    
    # Now mock it as NOT running
    with patch("tlm.safety.proctrack._is_running", return_value=False):
        procs = list_processes(temp_dir)
        assert len(procs) == 0
        # The file should be gone
        assert len(list(temp_dir.glob(".tlm/tmp/procs/*.json"))) == 0


def test_kill_all(temp_dir):
    with patch("tlm.safety.proctrack._is_running", return_value=True):
        register_process(temp_dir, 123, 123, ["long_run"])
        register_process(temp_dir, 456, 456, ["another"])
    
        with patch("os.killpg") as mock_killpg:
            count = kill_all(temp_dir, sig=signal.SIGTERM)
            assert count == 2
            assert mock_killpg.call_count == 2
        
    # Should be empty now
    assert len(list_processes(temp_dir)) == 0
