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
    settings: Any = None,
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
    resolved: list[tuple[Path, str, bool, str, int]] = []  # path, contents, exec, rel, mode
    for spec in files:
        rel = spec["path"]
        target = (base / rel).resolve()
        if not _under_base(target, base):
            print(f"error: path escapes base dir: {rel!r}")
            return WriteResult(4)
        old = ""
        current_mode = 0o644
        if target.is_file():
            old = target.read_text(encoding="utf-8")
            current_mode = target.stat().st_mode & 0o777
        elif target.exists():
            print(f"error: exists but is not a file: {rel!r}")
            return WriteResult(4)
        else:
            # new file
            if spec["executable"]:
                current_mode = 0o755

        diff = _diff_text(rel, old, spec["contents"]) if old else f"(new file {rel}, {len(spec['contents'])} bytes)\n"
        previews.append(diff)
        resolved.append((target, spec["contents"], spec["executable"], rel, current_mode))

    for t, _, _, rel, _ in resolved:
        if t.exists() and not overwrite:
            print(f"error: file exists and --overwrite not set: {rel!r}")
            return WriteResult(4)

    # For multi-file writes, we use the mode of the first file as the baseline for the prompt
    # or just ask for a global mode override if desired. For simplicity, we'll prompt for
    # the mode of the first file if there's only one, or just a general "target mode".
    # In a more complex version, we could have per-file modes in the JSON.
    initial_mode_str = oct(resolved[0][4])[2:] if resolved else "644"

    body = "\n".join(["--- proposed writes ---", *previews])
    dec, _, extra_mode = interactive_gate_string(
        body,
        allow_edit=False,
        dry_run=dry_run,
        auto_yes=auto_yes,
        can_auto_yes=True,  # write: --yes allowed after preview (plan)
        extra_prompt=f"Target octal permissions (default {initial_mode_str})",
    )
    if dec == "cancel":
        print("cancelled.")
        return WriteResult(1)
    if dec == "dry":
        print("(dry-run) not written.")
        return WriteResult(0)

    from tlm.settings import load_settings
    from tlm.safety.profiles import SafetyProfile, normalize_profile
    from tlm.safety.snapshot import create_snapshot
    
    s = settings or load_settings()
    profile = normalize_profile(s.safety_profile)
    
    if profile in (SafetyProfile.standard, SafetyProfile.strict):
        sid = create_snapshot(base)
        if sid:
            print(f"snapshot created: {sid}", flush=True)

    final_mode = resolved[0][4]
    if extra_mode:
        try:
            final_mode = int(extra_mode, 8)
        except ValueError:
            print(f"error: invalid octal mode {extra_mode!r}, using default.")

    tlm_tmp = base / ".tlm" / "tmp"
    tlm_tmp.mkdir(parents=True, exist_ok=True)
    staged_files: list[tuple[Path, Path, int, str]] = []
    
    try:
        for target, contents, executable, rel, _ in resolved:
            fd, tmp = tempfile.mkstemp(prefix="write-", dir=str(tlm_tmp), text=True)
            os.close(fd)
            tmp_path = Path(tmp)
            tmp_path.write_text(contents, encoding="utf-8")
            staged_files.append((target, tmp_path, final_mode, rel))
            
        for target, tmp_path, final_mode, rel in staged_files:
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(tmp_path, target)
            except OSError as e:
                # Fallback to copy+unlink if on different mounts
                import shutil
                shutil.copy2(tmp_path, target)
                tmp_path.unlink()
                
            try:
                target.chmod(final_mode)
            except OSError as e:
                print(f"warning: failed to chmod {rel}: {e}")
                
            print(f"wrote {rel} (mode {oct(final_mode)})", flush=True)
    finally:
        # Cleanup any un-moved staged files if we failed halfway
        for _, tmp_path, _, _ in staged_files:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    return WriteResult(0)
