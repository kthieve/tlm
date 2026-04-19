"""`tlm do` — LLM proposes argv lists; safety gate; subprocess."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tlm.jsonutil import extract_json_object
from tlm.providers.base import LLMProvider
from tlm.safety import (
    allow_do_auto_yes,
    argv_to_line,
    check_argv,
    interactive_gate_string,
    normalize_profile,
)
from tlm.settings import UserSettings, load_settings


_DO_SYSTEM = """You are tlm's execution planner for Linux.
Reply with ONLY a JSON object (no markdown) of this exact shape:
{"commands":[{"argv":["executable","arg1"],"cwd":null,"env":{},"why":"short reason"}],"dangerous":false}
Rules:
- argv MUST be a non-empty list of strings suitable for subprocess (no shell).
- Prefer read-only diagnostic commands when the user only asked for information.
- cwd is optional string path or null for default.
- env is optional mapping of extra env vars (keep empty unless strictly needed).
- If you cannot safely propose commands, return {"commands":[],"dangerous":true}.
"""


@dataclass
class DoResult:
    exit_code: int


def _parse_commands(raw: dict[str, Any]) -> list[dict[str, Any]]:
    cmds = raw.get("commands")
    if not isinstance(cmds, list):
        raise ValueError("invalid JSON: commands must be a list")
    out: list[dict[str, Any]] = []
    for c in cmds:
        if not isinstance(c, dict):
            continue
        argv = c.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            continue
        out.append(
            {
                "argv": list(argv),
                "cwd": c.get("cwd"),
                "env": c.get("env") if isinstance(c.get("env"), dict) else {},
                "why": str(c.get("why", "")),
            }
        )
    return out


def run_do(
    user_text: str,
    *,
    provider: LLMProvider,
    cwd: Path,
    timeout: float,
    pass_env: list[str],
    continue_on_error: bool,
    dry_run: bool,
    auto_yes: bool,
    settings: UserSettings | None = None,
) -> DoResult:
    s = settings or load_settings()
    profile = normalize_profile(s.safety_profile)

    try:
        raw_text = provider.complete(user_text, system=_DO_SYSTEM)
        data = extract_json_object(raw_text)
    except (json.JSONDecodeError, ValueError, RuntimeError) as e:
        print(f"error: failed to plan commands: {e}", flush=True)
        return DoResult(3)
    commands = _parse_commands(data)
    if not commands:
        print("model returned no commands (or unsafe).")
        return DoResult(2)

    argvs = [c["argv"] for c in commands]
    for argv in argvs:
        ok, reason = check_argv(argv)
        if not ok:
            print(f"safety: {reason}\n  argv={argv}")
            return DoResult(4)

    lines = ["--- proposed execution ---"]
    for i, c in enumerate(commands, 1):
        lines.append(f"{i}. argv={c['argv']!r}")
        if c["cwd"]:
            lines.append(f"   cwd={c['cwd']!r}")
        if c["why"]:
            lines.append(f"   why={c['why']}")
    preview = "\n".join(lines)

    can_yes = allow_do_auto_yes(profile, argvs)
    try:
        dec, _ = interactive_gate_string(
            preview,
            allow_edit=True,
            dry_run=dry_run,
            auto_yes=auto_yes,
            can_auto_yes=can_yes,
        )
    except ValueError as e:
        print(f"error: {e}", flush=True)
        return DoResult(2)
    if dec == "cancel":
        print("cancelled.")
        return DoResult(1)
    if dec == "dry":
        print("(dry-run) not executed.")
        return DoResult(0)

    # Re-parse after edit? For do mode edit was on preview text not JSON — gate edits preview string only.
    # MVP: edit path does not change argv list; user must cancel and re-run for complex edits.
    base_env = os.environ.copy()
    extra: dict[str, str] = {}
    for k in pass_env:
        if k in base_env:
            extra[k] = base_env[k]
    for i, c in enumerate(commands, 1):
        argv = c["argv"]
        use_cwd = Path(str(c["cwd"])) if c.get("cwd") else cwd
        env = base_env.copy()
        for ek, ev in c.get("env", {}).items():
            if isinstance(ek, str) and isinstance(ev, str):
                env[ek] = ev
        env.update(extra)
        print(f"\n--- running {i}/{len(commands)}: {argv_to_line(argv)} ---", flush=True)
        try:
            proc = subprocess.run(  # noqa: S603
                argv,
                cwd=str(use_cwd),
                env=env,
                timeout=timeout,
                capture_output=True,
                text=True,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            print(f"error: timeout after {timeout}s")
            return DoResult(3)
        if proc.stdout:
            print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
        if proc.stderr:
            print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)
        if proc.returncode != 0:
            print(f"exit code: {proc.returncode}")
            if not continue_on_error:
                return DoResult(proc.returncode)
    return DoResult(0)
