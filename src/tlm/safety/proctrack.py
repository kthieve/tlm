"""Multi-process tracking for tlm do."""

from __future__ import annotations

import json
import os
import signal
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProcInfo:
    proc_id: str
    pid: int
    pgid: int
    argv: list[str]
    cwd: str


def _get_proc_dir(base_dir: Path) -> Path:
    d = base_dir / ".tlm" / "tmp" / "procs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def register_process(base_dir: Path, pid: int, pgid: int, argv: list[str]) -> str:
    """Register a new active process."""
    proc_id = str(uuid.uuid4())
    proc_dir = _get_proc_dir(base_dir)
    proc_file = proc_dir / f"{proc_id}.json"
    
    info = {
        "proc_id": proc_id,
        "pid": pid,
        "pgid": pgid,
        "argv": argv,
        "cwd": str(base_dir.resolve()),
    }
    
    proc_file.write_text(json.dumps(info), encoding="utf-8")
    return proc_id


def unregister_process(base_dir: Path, proc_id: str) -> None:
    """Remove a process from the registry."""
    proc_file = _get_proc_dir(base_dir) / f"{proc_id}.json"
    if proc_file.exists():
        proc_file.unlink()


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def list_processes(base_dir: Path) -> list[ProcInfo]:
    """Return all active tracked processes, pruning stale ones."""
    proc_dir = _get_proc_dir(base_dir)
    results: list[ProcInfo] = []
    
    for p in proc_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            pid = data["pid"]
            if _is_running(pid):
                results.append(ProcInfo(**data))
            else:
                p.unlink()  # Stale
        except (json.JSONDecodeError, KeyError, OSError):
            continue
            
    return results


def kill_all(base_dir: Path, sig: int = signal.SIGKILL) -> int:
    """Kill all tracked process groups. Returns count of PIDs signaled."""
    procs = list_processes(base_dir)
    count = 0
    for p in procs:
        try:
            os.killpg(p.pgid, sig)
            count += 1
            unregister_process(base_dir, p.proc_id)
        except OSError:
            pass
    return count
