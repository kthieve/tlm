#!/usr/bin/env python3
"""Development sandbox: isolated XDG + refresh without losing API keys by default.

  python sandbox.py              # help
  python sandbox.py env        # print exports for: eval "$(python sandbox.py env)"
  python sandbox.py init       # tlm init under sandbox XDG
  python sandbox.py refresh    # wipe sandbox data, pip install -e ., init (keeps [keys] from config)
  python sandbox.py refresh --wipe-keys   # also drop saved API keys
  python sandbox.py shell      # interactive bash with sandbox env
  python sandbox.py run tlm ask hello      # one-shot command with sandbox env
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SANDBOX_CONFIG = REPO_ROOT / "sandbox" / ".config"
SANDBOX_DATA = REPO_ROOT / "sandbox" / ".local" / "share"
SANDBOX_STATE = REPO_ROOT / "sandbox" / ".local" / "state"
CONFIG_TOML = SANDBOX_CONFIG / "tlm" / "config.toml"


def sandbox_xdg_dict() -> dict[str, str]:
    return {
        "XDG_CONFIG_HOME": str(SANDBOX_CONFIG),
        "XDG_DATA_HOME": str(SANDBOX_DATA),
        "XDG_STATE_HOME": str(SANDBOX_STATE),
    }


def merged_child_env() -> dict[str, str]:
    e = os.environ.copy()
    e.update(sandbox_xdg_dict())
    e.setdefault("TLM_PROVIDER", "stub")
    return e


def _backup_api_keys() -> dict[str, str]:
    if not CONFIG_TOML.is_file():
        return {}
    try:
        data = tomllib.loads(CONFIG_TOML.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    keys = data.get("keys")
    if not isinstance(keys, dict):
        return {}
    return {str(k): str(v) for k, v in keys.items() if isinstance(v, str)}


def _restore_api_keys(keys: dict[str, str]) -> None:
    if not keys:
        return
    # Import after sandbox dirs exist; uses os.environ — caller must set XDG_* first.
    os.environ.update(sandbox_xdg_dict())
    os.environ.setdefault("TLM_PROVIDER", "stub")
    from tlm.settings import load_settings, save_settings

    s = load_settings()
    s.api_keys.update(keys)
    save_settings(s)


def cmd_env(ns: argparse.Namespace) -> int:
    d = sandbox_xdg_dict()
    if ns.fish:
        for k, v in d.items():
            print(f"set -gx {k} {__fish_escape(v)}")
        print("set -q TLM_PROVIDER; or set -gx TLM_PROVIDER stub")
        return 0
    for k, v in d.items():
        print(f"export {k}={__sh_escape(v)}")
    print('export TLM_PROVIDER="${TLM_PROVIDER:-stub}"')
    return 0


def __sh_escape(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def __fish_escape(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "'\\''") + "'"


def cmd_init(_ns: argparse.Namespace) -> int:
    r = subprocess.run(
        [sys.executable, "-m", "tlm", "init", "--no-wizard"],
        cwd=REPO_ROOT,
        env=merged_child_env(),
        check=False,
    )
    return int(r.returncode)


def cmd_refresh(ns: argparse.Namespace) -> int:
    keys = {} if ns.wipe_keys else _backup_api_keys()

    print("Removing sandbox .config and .local …", file=sys.stderr)
    shutil.rmtree(SANDBOX_CONFIG, ignore_errors=True)
    shutil.rmtree(REPO_ROOT / "sandbox" / ".local", ignore_errors=True)

    pip = [sys.executable, "-m", "pip", "install", "-q", "-e", str(REPO_ROOT)]
    print("pip install -e . …", file=sys.stderr)
    r = subprocess.run(pip, cwd=REPO_ROOT, env=os.environ.copy(), check=False)
    if r.returncode != 0:
        print("error: pip install failed", file=sys.stderr)
        return r.returncode

    r2 = subprocess.run(
        [sys.executable, "-m", "tlm", "init", "--no-wizard"],
        cwd=REPO_ROOT,
        env=merged_child_env(),
        check=False,
    )
    if r2.returncode != 0:
        return int(r2.returncode)

    if keys:
        _restore_api_keys(keys)
        print("Restored API keys from previous sandbox config.toml [keys].", file=sys.stderr)
    elif not ns.wipe_keys:
        print("(No saved [keys] to restore.)", file=sys.stderr)

    print("Sandbox refreshed.", file=sys.stderr)
    return 0


def cmd_run(ns: argparse.Namespace) -> int:
    cmd = list(ns.cmd or [])
    if not cmd:
        print("error: pass a command, e.g.  python sandbox.py run tlm ask hi", file=sys.stderr)
        return 2
    r = subprocess.run(cmd, cwd=REPO_ROOT, env=merged_child_env())
    return int(r.returncode)


def cmd_shell(_ns: argparse.Namespace) -> int:
    bash = shutil.which("bash")
    if not bash:
        print("error: bash not found", file=sys.stderr)
        return 127
    env = merged_child_env()
    os.execve(bash, [bash, "-i"], env)
    return 127  # pragma: no cover


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sandbox.py",
        description="Isolated XDG for tlm development (see sandbox/README.md).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_env = sub.add_parser("env", help="Print shell exports (bash/zsh); use: eval \"$(python sandbox.py env)\"")
    p_env.add_argument("--fish", action="store_true", help="Emit fish set -gx lines")
    p_env.set_defaults(_fn=cmd_env)

    sub.add_parser("init", help="Run tlm init under sandbox XDG").set_defaults(_fn=cmd_init)

    p_ref = sub.add_parser(
        "refresh",
        help="Wipe sandbox config/state, reinstall package, tlm init; keeps [keys] unless --wipe-keys",
    )
    p_ref.add_argument(
        "--wipe-keys",
        action="store_true",
        help="Do not restore API keys from the previous sandbox config.toml.",
    )
    p_ref.set_defaults(_fn=cmd_refresh)

    p_run = sub.add_parser("run", help="Run a command with sandbox XDG, e.g.  python sandbox.py run tlm ask hi")
    p_run.add_argument("cmd", nargs=argparse.REMAINDER, help="command and arguments")
    p_run.set_defaults(_fn=cmd_run)

    sub.add_parser("shell", help="Start interactive bash -i with sandbox env").set_defaults(_fn=cmd_shell)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__.strip())
        return 0
    args = build_parser().parse_args(argv)
    fn = args._fn
    return int(fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
