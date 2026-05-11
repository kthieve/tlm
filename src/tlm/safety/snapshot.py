"""Temporal snapshotting and undo logic for workspace safety."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SnapshotInfo:
    id: str
    timestamp: float
    message: str
    is_git: bool


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


def create_snapshot(path: Path, message: str = "") -> Optional[str]:
    """
    Create a snapshot of the current workspace state.
    Returns a 'snapshot_id' or None if failed.
    """
    ts = time.time()
    ts_int = int(ts)
    dot_tlm = path / ".tlm" / "snapshots"
    dot_tlm.mkdir(parents=True, exist_ok=True)

    if _is_git_repo(path):
        try:
            # We want to capture the current state without modifying the user's index/working tree.
            # 'git stash create' returns a commit SHA representing the current dirty state.
            # Note: This captures modified and staged files. To capture untracked, we'd need to stage them.
            # For now, we capture what git knows about.
            res = subprocess.run(
                ["git", "stash", "create"],
                cwd=str(path),
                capture_output=True,
                text=True,
                check=True,
            )
            sha = res.stdout.strip()
            if not sha:
                # If no changes, capture HEAD
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(path),
                    capture_output=True,
                    text=True,
                    check=True,
                )
                sha = res.stdout.strip()

            sid = f"git-{ts_int}"
            sha_file = dot_tlm / f"{sid}.sha"
            msg = message or f"Snapshot at {time.ctime(ts)}"
            sha_file.write_text(f"{sha}\n{msg}\n", encoding="utf-8")
            return sid
        except (subprocess.CalledProcessError, OSError):
            pass

    # Fallback: file-based backup
    sid = f"file-{ts_int}"
    backup_dir = dot_tlm / sid
    try:
        # TODO: Implement a more efficient skip-logic for large/binary files
        # For now, we copy the directory, excluding .tlm itself
        def ignore_func(d, files):
            if Path(d) == path and ".tlm" in files:
                return [".tlm", ".git"]
            return []

        shutil.copytree(path, backup_dir, ignore=ignore_func, dirs_exist_ok=True)
        msg = message or f"File snapshot at {time.ctime(ts)}"
        (backup_dir / ".tlm_msg").write_text(msg, encoding="utf-8")
        return sid
    except (OSError, shutil.Error):
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
        return None


def list_snapshots(path: Path) -> list[SnapshotInfo]:
    """Return a list of available snapshots, newest first."""
    dot_tlm = path / ".tlm" / "snapshots"
    if not dot_tlm.is_dir():
        return []

    results: list[SnapshotInfo] = []
    for p in dot_tlm.iterdir():
        if p.suffix == ".sha":
            sid = p.stem
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
                if len(lines) >= 2:
                    ts = float(sid.split("-")[-1])
                    results.append(SnapshotInfo(id=sid, timestamp=ts, message=lines[1], is_git=True))
            except (ValueError, IndexError, OSError):
                continue
        elif p.is_dir() and p.name.startswith("file-"):
            sid = p.name
            try:
                ts = float(sid.split("-")[-1])
                msg_file = p / ".tlm_msg"
                msg = msg_file.read_text(encoding="utf-8") if msg_file.exists() else f"File snapshot {sid}"
                results.append(SnapshotInfo(id=sid, timestamp=ts, message=msg, is_git=False))
            except (ValueError, IndexError, OSError):
                continue

    return sorted(results, key=lambda x: x.timestamp, reverse=True)


def restore_snapshot(path: Path, snapshot_id: str) -> bool:
    """Restore the workspace to a previous snapshot."""
    dot_tlm = path / ".tlm" / "snapshots"
    
    if snapshot_id.startswith("git-"):
        sha_file = dot_tlm / f"{snapshot_id}.sha"
        if not sha_file.exists():
            return False
        try:
            sha = sha_file.read_text(encoding="utf-8").splitlines()[0].strip()
            # Restore using git checkout for the whole directory
            # This is safer than reset --hard if we want to avoid losing untracked files
            # that weren't in the snapshot.
            subprocess.run(["git", "checkout", sha, "--", "."], cwd=str(path), check=True)
            return True
        except (subprocess.CalledProcessError, IndexError, OSError):
            return False

    if snapshot_id.startswith("file-"):
        backup_dir = dot_tlm / snapshot_id
        if not backup_dir.exists():
            return False
        try:
            # For file restore, we copy back everything EXCEPT the .tlm_msg metadata
            def ignore_func(d, files):
                if ".tlm_msg" in files:
                    return [".tlm_msg"]
                return []
            
            shutil.copytree(backup_dir, path, ignore=ignore_func, dirs_exist_ok=True)
            return True
        except (OSError, shutil.Error):
            return False

    return False
