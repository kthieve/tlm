"""Temporal snapshotting and undo logic for workspace safety."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional


def _is_git_repo(path: Path) -> bool:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(path),
            capture_output=True,
            text=True,
        )
        return res.returncode == 0
    except FileNotFoundError:
        return False


def create_snapshot(path: Path) -> Optional[str]:
    """
    Create a snapshot of the current workspace state.
    Returns a 'snapshot_id' or None if failed.
    """
    if _is_git_repo(path):
        ts = int(time.time())
        tag = f"tlm-snapshot-{ts}"
        try:
            # Create a temporary commit on a detached head or just use a stash
            # For simplicity and non-destructiveness, we use a temporary tag/branch
            subprocess.run(["git", "add", "."], cwd=str(path), check=True)
            subprocess.run(
                ["git", "commit", "-m", f"tlm: automated snapshot {ts}", "--allow-empty"],
                cwd=str(path),
                check=True,
            )
            subprocess.run(["git", "tag", tag], cwd=str(path), check=True)
            return tag
        except subprocess.CalledProcessError:
            return None
    
    # Fallback: file-based backup (simplified for now: just copy changed files?)
    # TODO: Implement robust non-git fallback
    return None


def restore_snapshot(path: Path, snapshot_id: str) -> bool:
    """Restore the workspace to a previous snapshot."""
    if _is_git_repo(path) and snapshot_id.startswith("tlm-snapshot-"):
        try:
            subprocess.run(["git", "reset", "--hard", snapshot_id], cwd=str(path), check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    return False
