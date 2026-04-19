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
    check_argv_with_network,
    interactive_gate_string,
    normalize_profile,
    overlay_effective_policy,
    path_like_args,
)
from tlm.safety.consent import prompt_escape, session_add_rw, session_rw_paths
from tlm.safety.jail import classify_path
from tlm.safety.permissions import effective_policy
from tlm.safety.profiles import SafetyProfile
from tlm.safety.root_guard import (
    argv_has_elevation,
    check_write_paths,
    is_euid_root,
    log_root_event,
    path_under_system_root,
    prompt_root_trusted,
)
from tlm.safety import sandbox
from tlm.safety.shell import argv_uses_network_tool
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


def _collect_path_checks(
    commands: list[dict[str, Any]],
    default_cwd: Path,
    ep: Any,
) -> tuple[list[tuple[str, str]], bool]:
    """Returns (escape_items as (RW|R, path), has_denied)."""
    items: list[tuple[str, str]] = []
    denied = False
    sess = session_rw_paths()
    for c in commands:
        use_cwd = Path(str(c["cwd"])).expanduser().resolve() if c.get("cwd") else default_cwd.resolve()
        argv = c["argv"]
        for p in [use_cwd, *path_like_args(argv)]:
            k = classify_path(
                p,
                ep,
                use_cwd,
                op="read",
                once_rw=frozenset(),
                session_rw=sess,
            )
            rp = str(Path(p).expanduser().resolve())
            if k == "denied":
                denied = True
            elif k == "escape":
                items.append(("R", rp))
    return items, denied


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
    if is_euid_root() and profile == SafetyProfile.trusted:
        print(
            "tlm: warning: running as root; trusted profile is treated as standard for safety.",
            file=sys.stderr,
        )
        profile = SafetyProfile.standard

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
        if argv_has_elevation(argv):
            print("root guard: elevation helpers (sudo/doas/…) are not allowed in tlm do.", flush=True)
            log_root_event({"argv": argv, "cwd": str(cwd)})
            return DoResult(4)

    ep_base = effective_policy(cwd)
    ep = overlay_effective_policy(ep_base, profile)

    escape_items, denied = _collect_path_checks(commands, cwd, ep)
    if denied:
        print("safety: path denied by permissions (deny_paths).", flush=True)
        return DoResult(4)

    sys_paths = [Path(p) for _, p in escape_items if path_under_system_root(Path(p))]
    if sys_paths:
        ok_root, msg = check_write_paths(sys_paths, profile)
        if not ok_root:
            print(f"root guard: {msg}", flush=True)
            return DoResult(4)
        if profile == SafetyProfile.trusted:
            if not prompt_root_trusted(sys_paths):
                print("cancelled.", flush=True)
                return DoResult(1)
            log_root_event({"paths": [str(p) for p in sys_paths], "cwd": str(cwd)})

    if escape_items:
        pr = prompt_escape(escape_items, profile=profile, auto_yes=auto_yes)
        if pr in ("cancel", "refuse"):
            print("cancelled.", flush=True)
            return DoResult(1)
        if pr == "session":
            for _, p in escape_items:
                session_add_rw(str(Path(p).resolve()))

    nm = ep.network_mode.strip().lower()
    net_approved = nm == "on"
    if nm == "ask":
        need_net = any(argv_uses_network_tool(a) for a in argvs)
        if not need_net:
            net_approved = True
        elif dry_run or auto_yes or not sys.stdin.isatty():
            net_approved = False
        else:
            try:
                ans = input("Allow network tools for this plan? [y/N]: ").strip().lower()
            except EOFError:
                ans = ""
            net_approved = ans in ("y", "yes")

    for argv in argvs:
        ok, reason = check_argv_with_network(argv, network_mode=ep.network_mode, net_approved=net_approved)
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

    base_env = os.environ.copy()
    extra: dict[str, str] = {}
    for k in pass_env:
        if k in base_env:
            extra[k] = base_env[k]
    unshare_net = nm == "off"
    for i, c in enumerate(commands, 1):
        argv = c["argv"]
        use_cwd = Path(str(c["cwd"])).expanduser().resolve() if c.get("cwd") else cwd.resolve()
        env = base_env.copy()
        for ek, ev in c.get("env", {}).items():
            if isinstance(ek, str) and isinstance(ev, str):
                env[ek] = ev
        env.update(extra)
        wrapped = sandbox.wrap_argv(argv, cwd=use_cwd, policy=ep, unshare_net=unshare_net)
        print(f"\n--- running {i}/{len(commands)}: {argv_to_line(argv)} ---", flush=True)
        try:
            proc = subprocess.run(  # noqa: S603
                wrapped,
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
