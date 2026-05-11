"""Atomic multi-file transaction manager."""

from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class TransactionItem:
    target: Path
    tmp_path: Path
    mode: Optional[int] = None
    backup_path: Optional[Path] = None


class AtomicTransaction:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.tmp_dir = base_dir / ".tlm" / "tmp" / f"txn-{uuid.uuid4()}"
        self.items: Dict[Path, TransactionItem] = {}
        self.applied: list[Path] = []
        self.committed = False
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def stage(self, target: Path, contents: str, mode: Optional[int] = None) -> None:
        """Stage a file write to the transaction."""
        target = target.expanduser().resolve()
        
        # Unique tmp file in our txn dir
        tmp_name = str(uuid.uuid4())
        tmp_path = self.tmp_dir / tmp_name
        
        # Write contents to tmp file
        tmp_path.write_text(contents, encoding="utf-8")
        if mode is not None:
            tmp_path.chmod(mode)
            
        self.items[target] = TransactionItem(target=target, tmp_path=tmp_path, mode=mode)

    def commit(self) -> list[Path]:
        """
        Commit all staged changes. 
        If any step fails, it attempts to roll back to the state before the commit started.
        Returns a list of successfully written target paths.
        """
        if self.committed:
            return []

        # 1. Verify all parent directories exist or create them
        for target in self.items.keys():
            target.parent.mkdir(parents=True, exist_ok=True)

        # 2. Back up existing files if they exist
        backup_dir = self.tmp_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        try:
            for target, item in self.items.items():
                if target.exists():
                    b_path = backup_dir / str(uuid.uuid4())
                    shutil.copy2(target, b_path)
                    item.backup_path = b_path

            # 3. Apply changes (atomically move tmp files to targets)
            for target, item in self.items.items():
                try:
                    os.replace(item.tmp_path, target)
                except OSError:
                    # Fallback for cross-device move
                    shutil.move(item.tmp_path, target)
                self.applied.append(target)

            self.committed = True
            return list(self.items.keys())

        except Exception as e:
            self.rollback()
            raise RuntimeError(f"Transaction failed during commit: {e}") from e

    def rollback(self) -> None:
        """
        Roll back the transaction. 
        Restores any applied changes from backups.
        """
        # Restore any applied files
        for target in reversed(self.applied):
            item = self.items[target]
            if item.backup_path and item.backup_path.exists():
                try:
                    os.replace(item.backup_path, target)
                except OSError:
                    shutil.move(item.backup_path, target)
            elif target.exists():
                # If it didn't exist before, delete it
                target.unlink()
        
        self.applied = []
        self.committed = False

        # Cleanup tmp directory
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def __enter__(self) -> AtomicTransaction:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            # Note: We don't auto-commit here. User must call commit().
            # This is just for safety/cleanup.
            self.rollback() if not self.committed else self.cleanup()

    def cleanup(self) -> None:
        """Final cleanup of tmp files after a successful commit."""
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
