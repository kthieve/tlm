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
    extra_prompt: str | None = None,
) -> tuple[Decision, str, str | None]:
    """Print body; return decision, final body string, and optional extra value."""
    print(body)
    if dry_run:
        return "dry", body, None
    if auto_yes:
        if not can_auto_yes:
            raise ValueError("auto-yes not permitted for this action")
        return "run", body, None
    edited = body
    extra = None
    while True:
        hint = " [y/N/e/?]" if allow_edit else " [y/N/?]"
        if extra_prompt:
            hint = hint[:-1] + "p" + hint[-1:]
        try:
            ans = input(f"Proceed?{hint}: ").strip().lower()
        except EOFError:
            return "cancel", edited, extra
        if ans in ("y", "yes"):
            return "run", edited, extra
        if ans in ("n", "no", ""):
            return "cancel", edited, extra
        if allow_edit and ans in ("e", "edit"):
            edited = edit_text(edited).strip()
            print("--- updated preview ---")
            print(edited)
            continue
        if extra_prompt and ans == "p":
            try:
                extra = input(f"{extra_prompt}: ").strip()
            except EOFError:
                pass
            continue
        if ans in ("?", "h", "help"):
            msg = "y: approve  n: cancel  e: edit in $EDITOR"
            if extra_prompt:
                msg += "  p: edit extra setting"
            msg += "  ?: help"
            print(msg)
            continue
        print("unrecognized; try y, n, e, p, or ?")
