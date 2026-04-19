"""`tlm write` — LLM proposes files; diff preview; atomic writes under a base dir."""

from __future__ import annotations

import difflib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tlm.jsonutil import extract_json_object
from tlm.providers.base import LLMProvider
from tlm.safety import interactive_gate_string


_WRITE_SYSTEM = """You are tlm's code writer for Linux.
Reply with ONLY a JSON object (no markdown) of this shape:
{"files":[{"path":"relative/path.ext","contents":"file body","executable":false}],"notes":"short summary"}
Rules:
- paths must be relative (no leading /, no .. segments).
- keep file set minimal; UTF-8 text only.
"""


@dataclass
class WriteResult:
    exit_code: int


def _under_base(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _parse_files(raw: dict[str, Any]) -> list[dict[str, Any]]:
    files = raw.get("files")
    if not isinstance(files, list):
        raise ValueError("invalid JSON: files must be a list")
    out: list[dict[str, Any]] = []
    for f in files:
        if not isinstance(f, dict):
            continue
        p = f.get("path")
        c = f.get("contents")
        if not isinstance(p, str) or not isinstance(c, str):
            continue
        if p.startswith("/") or ".." in Path(p).parts:
            raise ValueError(f"unsafe path: {p!r}")
        ex = bool(f.get("executable", False))
        out.append({"path": p, "contents": c, "executable": ex})
    return out


def _diff_text(rel: str, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(True),
            new.splitlines(True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
        )
    )


def run_write(
    user_text: str,
    *,
    provider: LLMProvider,
    base_dir: Path,
    overwrite: bool,
    dry_run: bool,
    auto_yes: bool,
) -> WriteResult:
    try:
        raw_text = provider.complete(user_text, system=_WRITE_SYSTEM)
        data = extract_json_object(raw_text)
        files = _parse_files(data)
    except (json.JSONDecodeError, ValueError, RuntimeError) as e:
        print(f"error: failed to plan writes: {e}", flush=True)
        return WriteResult(3)
    if not files:
        print("model returned no files.")
        return WriteResult(2)

    base = base_dir.resolve()
    base.mkdir(parents=True, exist_ok=True)

    previews: list[str] = []
    resolved: list[tuple[Path, str, bool, str]] = []  # path, contents, exec, rel
    for spec in files:
        rel = spec["path"]
        target = (base / rel).resolve()
        if not _under_base(target, base):
            print(f"error: path escapes base dir: {rel!r}")
            return WriteResult(4)
        old = ""
        if target.is_file():
            old = target.read_text(encoding="utf-8")
        elif target.exists():
            print(f"error: exists but is not a file: {rel!r}")
            return WriteResult(4)
        diff = _diff_text(rel, old, spec["contents"]) if old else f"(new file {rel}, {len(spec['contents'])} bytes)\n"
        previews.append(diff)
        resolved.append((target, spec["contents"], spec["executable"], rel))

    for t, _, _, rel in resolved:
        if t.exists() and not overwrite:
            print(f"error: file exists and --overwrite not set: {rel!r}")
            return WriteResult(4)

    body = "\n".join(["--- proposed writes ---", *previews])
    dec, _ = interactive_gate_string(
        body,
        allow_edit=False,
        dry_run=dry_run,
        auto_yes=auto_yes,
        can_auto_yes=True,  # write: --yes allowed after preview (plan)
    )
    if dec == "cancel":
        print("cancelled.")
        return WriteResult(1)
    if dec == "dry":
        print("(dry-run) not written.")
        return WriteResult(0)

    for target, contents, executable, rel in resolved:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tlm-", dir=str(target.parent), text=True)
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            tmp_path.write_text(contents, encoding="utf-8")
            os.replace(tmp_path, target)
        except OSError:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        if executable:
            mode = target.stat().st_mode
            target.chmod(mode | 0o111)
        print(f"wrote {rel}", flush=True)

    return WriteResult(0)
