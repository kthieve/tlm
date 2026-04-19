"""Interactive preview + confirm; optional $EDITOR for edits (do line / write payload)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

Decision = Literal["run", "cancel", "dry"]


def edit_text(initial: str) -> str:
    editor = os.environ.get("EDITOR", "nano")
    fd, path = tempfile.mkstemp(prefix="tlm-", suffix=".txt", text=True)
    os.close(fd)
    try:
        Path(path).write_text(initial, encoding="utf-8")
        subprocess.run([editor, path], check=False)  # noqa: S603
        return Path(path).read_text(encoding="utf-8")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def interactive_gate_string(
    body: str,
    *,
    allow_edit: bool,
    dry_run: bool,
    auto_yes: bool,
    can_auto_yes: bool,
) -> tuple[Decision, str]:
    """Print body; return decision and final string (possibly edited)."""
    print(body)
    if dry_run:
        return "dry", body
    if auto_yes:
        if not can_auto_yes:
            raise ValueError("auto-yes not permitted for this action")
        return "run", body
    edited = body
    while True:
        hint = " [y/N/e/?]" if allow_edit else " [y/N/?]"
        try:
            ans = input(f"Proceed?{hint}: ").strip().lower()
        except EOFError:
            return "cancel", edited
        if ans in ("y", "yes"):
            return "run", edited
        if ans in ("n", "no", ""):
            return "cancel", edited
        if allow_edit and ans in ("e", "edit"):
            edited = edit_text(edited).strip()
            print("--- updated preview ---")
            print(edited)
            continue
        if ans in ("?", "h", "help"):
            print("y: approve  n: cancel  e: edit in $EDITOR  ?: help")
            continue
        print("unrecognized; try y, n, e, or ?")
