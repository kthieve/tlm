#!/usr/bin/env python3
"""Development sandbox: isolated XDG + venv under sandboxes/<name>/ (gitignored).

  python sandbox.py env [--sandbox NAME]     # eval "$(python sandbox.py env)"  |  PowerShell: sandbox.py env --pwsh
  python sandbox.py init [--sandbox NAME]    # venv, pip install -e ., tlm init, activation scripts
  python sandbox.py refresh [--sandbox NAME] # wipe config/state; reinstall (keeps [keys] unless --wipe-keys)
  python sandbox.py run [--sandbox NAME] -- tlm ask hello
  python sandbox.py shell [--sandbox NAME] # bash -i or pwsh (same sandbox = resume)
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


def _default_sandboxes_root() -> Path:
    raw = os.environ.get("TLM_SANDBOXES_ROOT")
    return Path(raw).resolve() if raw else REPO_ROOT / "sandboxes"


def sandbox_home(ns: argparse.Namespace) -> Path:
    """Root dir for this named sandbox: <sandboxes-root>/<name>/."""
    root = Path(ns.sandboxes_root).resolve() if ns.sandboxes_root else _default_sandboxes_root()
    name = (ns.sandbox or "default").strip() or "default"
    return root / name


def sandbox_paths(ns: argparse.Namespace) -> dict[str, Path]:
    home = sandbox_home(ns)
    venv = home / ".venv"
    return {
        "home": home,
        "config_home": home / ".config",
        "data_home": home / ".local" / "share",
        "state_home": home / ".local" / "state",
        "venv": venv,
        "config_toml": home / ".config" / "tlm" / "config.toml",
        "activate_sh": home / "activate.sh",
        "activate_ps1": home / "activate.ps1",
    }


def venv_python(paths: dict[str, Path]) -> Path:
    v = paths["venv"]
    if os.name == "nt":
        return v / "Scripts" / "python.exe"
    return v / "bin" / "python"


def venv_scripts_bin(paths: dict[str, Path]) -> Path:
    """Directory containing python/pip/tlm console scripts."""
    return paths["venv"] / ("Scripts" if os.name == "nt" else "bin")


def sandbox_xdg_dict(ns: argparse.Namespace) -> dict[str, str]:
    p = sandbox_paths(ns)
    return {
        "XDG_CONFIG_HOME": str(p["config_home"]),
        "XDG_DATA_HOME": str(p["data_home"]),
        "XDG_STATE_HOME": str(p["state_home"]),
    }


def merged_child_env(ns: argparse.Namespace) -> dict[str, str]:
    e = os.environ.copy()
    e.update(sandbox_xdg_dict(ns))
    e.setdefault("TLM_PROVIDER", "stub")
    p = sandbox_paths(ns)
    if p["venv"].is_dir():
        bin_prefix = venv_scripts_bin(p)
        e["VIRTUAL_ENV"] = str(p["venv"])
        e["PATH"] = str(bin_prefix) + os.pathsep + e.get("PATH", "")
    return e


def _backup_api_keys(config_toml: Path) -> dict[str, str]:
    if not config_toml.is_file():
        return {}
    try:
        data = tomllib.loads(config_toml.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    keys = data.get("keys")
    if not isinstance(keys, dict):
        return {}
    return {str(k): str(v) for k, v in keys.items() if isinstance(v, str)}


def _restore_api_keys(ns: argparse.Namespace, keys: dict[str, str]) -> None:
    if not keys:
        return
    os.environ.update(sandbox_xdg_dict(ns))
    os.environ.setdefault("TLM_PROVIDER", "stub")
    from tlm.settings import load_settings, save_settings

    s = load_settings()
    s.api_keys.update(keys)
    save_settings(s)


def _pwsh_escape(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def cmd_env(ns: argparse.Namespace) -> int:
    paths = sandbox_paths(ns)
    use_pwsh = ns.format_pwsh or (os.name == "nt" and not ns.format_posix)
    use_fish = ns.fish

    xdg = sandbox_xdg_dict(ns)

    if use_fish:
        for k, v in xdg.items():
            print(f"set -gx {k} {__fish_escape(v)}")
        print("set -q TLM_PROVIDER; or set -gx TLM_PROVIDER stub")
        if paths["venv"].is_dir():
            vp = venv_scripts_bin(paths)
            print(f"set -gx VIRTUAL_ENV {__fish_escape(str(paths['venv']))}")
            print(f"set -p PATH {__fish_escape(str(vp))}")
        return 0

    if use_pwsh:
        for k, v in xdg.items():
            print(f"$env:{k} = {_pwsh_escape(v)}")
        print('$if (-not $env:TLM_PROVIDER) { $env:TLM_PROVIDER = "stub" }')
        if paths["venv"].is_dir():
            vp = venv_scripts_bin(paths)
            print(f'$env:VIRTUAL_ENV = {_pwsh_escape(str(paths["venv"]))}')
            print(f'$env:PATH = {_pwsh_escape(str(vp) + ";")} + $env:PATH')
        return 0

    for k, v in xdg.items():
        print(f"export {k}={__sh_escape(v)}")
    print('export TLM_PROVIDER="${TLM_PROVIDER:-stub}"')
    if paths["venv"].is_dir():
        vp = venv_scripts_bin(paths)
        print(f"export VIRTUAL_ENV={__sh_escape(str(paths['venv']))}")
        print(f"export PATH={__sh_escape(str(vp))}:$PATH")
    return 0


def __sh_escape(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def __fish_escape(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "'\\''") + "'"


def _write_activate_scripts(ns: argparse.Namespace, paths: dict[str, Path]) -> None:
    act_posix = paths["venv"] / "bin" / "activate"
    ps1 = paths["venv"] / "Scripts" / "Activate.ps1"
    bin_dir = paths["venv"] / "bin"

    paths["activate_sh"].write_text(
        f"""#!/usr/bin/env bash
# Generated by sandbox.py — isolated XDG + venv for tlm dev.
export XDG_CONFIG_HOME={__sh_escape(str(paths["config_home"]))}
export XDG_DATA_HOME={__sh_escape(str(paths["data_home"]))}
export XDG_STATE_HOME={__sh_escape(str(paths["state_home"]))}
export TLM_PROVIDER="${{TLM_PROVIDER:-stub}}"
if [[ -f {__sh_escape(str(act_posix))} ]]; then
  # shellcheck source=/dev/null
  . {__sh_escape(str(act_posix))}
elif [[ -d {__sh_escape(str(bin_dir))} ]]; then
  export VIRTUAL_ENV={__sh_escape(str(paths["venv"]))}
  export PATH={__sh_escape(str(bin_dir))}:$PATH
fi
""",
        encoding="utf-8",
        newline="\n",
    )

    win_act = str(ps1.resolve()).replace("'", "''")
    scripts_dir = str((paths["venv"] / "Scripts").resolve()).replace("'", "''")
    ve_esc = str(paths["venv"].resolve()).replace("'", "''")
    paths["activate_ps1"].write_text(
        f"""# Generated by sandbox.py — isolated XDG + venv for tlm dev.
$env:XDG_CONFIG_HOME = {_pwsh_escape(str(paths["config_home"]))}
$env:XDG_DATA_HOME = {_pwsh_escape(str(paths["data_home"]))}
$env:XDG_STATE_HOME = {_pwsh_escape(str(paths["state_home"]))}
if (-not $env:TLM_PROVIDER) {{ $env:TLM_PROVIDER = 'stub' }}
if (Test-Path -LiteralPath '{win_act}') {{
  . '{win_act}'
}} elseif (Test-Path -LiteralPath '{scripts_dir}') {{
  $env:VIRTUAL_ENV = '{ve_esc}'
  $env:PATH = '{scripts_dir};' + $env:PATH
}}
""",
        encoding="utf-8",
        newline="\r\n",
    )


def _ensure_xdg_dirs(paths: dict[str, Path]) -> None:
    paths["config_home"].mkdir(parents=True, exist_ok=True)
    paths["data_home"].mkdir(parents=True, exist_ok=True)
    paths["state_home"].mkdir(parents=True, exist_ok=True)


def cmd_init(ns: argparse.Namespace) -> int:
    paths = sandbox_paths(ns)
    legacy = REPO_ROOT / "sandbox" / ".config"
    if legacy.is_dir() and not paths["config_toml"].parent.is_dir():
        print(
            "hint: legacy sandbox data lives under repo sandbox/.config — "
            "run init here or migrate; see sandbox/README.md.",
            file=sys.stderr,
        )

    _ensure_xdg_dirs(paths)
    if not paths["venv"].is_dir():
        print(f"Creating venv at {paths['venv']} …", file=sys.stderr)
        r = subprocess.run(
            [sys.executable, "-m", "venv", str(paths["venv"])],
            cwd=REPO_ROOT,
            check=False,
        )
        if r.returncode != 0:
            print("error: python -m venv failed", file=sys.stderr)
            return int(r.returncode)

    py = venv_python(paths)
    if not py.is_file():
        print(f"error: missing venv python: {py}", file=sys.stderr)
        return 2

    pip = [str(py), "-m", "pip", "install", "-q", "-e", str(REPO_ROOT)]
    print("pip install -e . …", file=sys.stderr)
    r = subprocess.run(pip, cwd=REPO_ROOT, env=os.environ.copy(), check=False)
    if r.returncode != 0:
        print("error: pip install failed", file=sys.stderr)
        return int(r.returncode)

    r2 = subprocess.run(
        [str(py), "-m", "tlm", "init", "--no-wizard"],
        cwd=REPO_ROOT,
        env=merged_child_env(ns),
        check=False,
    )
    if r2.returncode != 0:
        return int(r2.returncode)

    _write_activate_scripts(ns, paths)
    print(f"Sandbox ready: {paths['home']}", file=sys.stderr)
    print(f"  POSIX/Git Bash: source {paths['activate_sh']}", file=sys.stderr)
    print(f"  PowerShell: . {paths['activate_ps1']}", file=sys.stderr)
    return 0


def cmd_refresh(ns: argparse.Namespace) -> int:
    paths = sandbox_paths(ns)
    config_toml = paths["config_toml"]
    keys = {} if ns.wipe_keys else _backup_api_keys(config_toml)

    if ns.recreate_venv and paths["venv"].is_dir():
        print(f"Removing venv {paths['venv']} …", file=sys.stderr)
        shutil.rmtree(paths["venv"], ignore_errors=True)

    print("Removing sandbox .config and .local …", file=sys.stderr)
    shutil.rmtree(paths["config_home"], ignore_errors=True)
    shutil.rmtree(paths["home"] / ".local", ignore_errors=True)
    _ensure_xdg_dirs(paths)

    if not paths["venv"].is_dir():
        print(f"Creating venv at {paths['venv']} …", file=sys.stderr)
        r0 = subprocess.run(
            [sys.executable, "-m", "venv", str(paths["venv"])],
            cwd=REPO_ROOT,
            check=False,
        )
        if r0.returncode != 0:
            print("error: python -m venv failed", file=sys.stderr)
            return int(r0.returncode)

    py = venv_python(paths)
    pip = [str(py), "-m", "pip", "install", "-q", "-e", str(REPO_ROOT)]
    print("pip install -e . …", file=sys.stderr)
    r = subprocess.run(pip, cwd=REPO_ROOT, env=os.environ.copy(), check=False)
    if r.returncode != 0:
        print("error: pip install failed", file=sys.stderr)
        return r.returncode

    r2 = subprocess.run(
        [str(py), "-m", "tlm", "init", "--no-wizard"],
        cwd=REPO_ROOT,
        env=merged_child_env(ns),
        check=False,
    )
    if r2.returncode != 0:
        return int(r2.returncode)

    _write_activate_scripts(ns, paths)

    if keys:
        _restore_api_keys(ns, keys)
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
    paths = sandbox_paths(ns)
    if not paths["venv"].is_dir():
        print(
            f"error: no venv at {paths['venv']}; run: python sandbox.py init --sandbox {ns.sandbox}",
            file=sys.stderr,
        )
        return 2
    r = subprocess.run(cmd, cwd=REPO_ROOT, env=merged_child_env(ns))
    return int(r.returncode)


def cmd_shell(ns: argparse.Namespace) -> int:
    paths = sandbox_paths(ns)
    if not paths["venv"].is_dir():
        print(
            f"error: no venv at {paths['venv']}; run: python sandbox.py init --sandbox {ns.sandbox}",
            file=sys.stderr,
        )
        return 2
    env = merged_child_env(ns)
    bash = shutil.which("bash")
    if bash:
        os.execve(bash, [bash, "-i"], env)
        return 127  # pragma: no cover

    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh:
        # Prefer subprocess on Windows so stdio attaches reliably.
        try:
            return int(
                subprocess.run(
                    [pwsh, "-NoLogo", "-NoExit"],
                    cwd=REPO_ROOT,
                    env=env,
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                ).returncode
            )
        except OSError as e:
            print(f"error: could not start {pwsh}: {e}", file=sys.stderr)
            return 127

    print("error: need bash (Git Bash) or pwsh/powershell on PATH", file=sys.stderr)
    return 127


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sandbox",
        "-n",
        default=os.environ.get("TLM_SANDBOX_NAME") or "default",
        metavar="NAME",
        help="Sandbox name under sandboxes/ (default: default). Same name = resume.",
    )
    parser.add_argument(
        "--sandboxes-root",
        default=os.environ.get("TLM_SANDBOXES_ROOT"),
        metavar="DIR",
        help=argparse.SUPPRESS,
    )


def build_parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    _common_arguments(parent)

    p = argparse.ArgumentParser(
        prog="sandbox.py",
        description="Isolated XDG + venv under sandboxes/<name>/ (see sandbox/README.md).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_env = sub.add_parser("env", help="Print shell exports for eval / PowerShell", parents=[parent])
    p_env.add_argument("--fish", action="store_true", help="Emit fish set -gx lines")
    p_env.add_argument("--pwsh", dest="format_pwsh", action="store_true", help="Emit PowerShell $env: lines")
    p_env.add_argument(
        "--posix",
        "--bash",
        dest="format_posix",
        action="store_true",
        help="On Windows: force POSIX exports (e.g. Git Bash) instead of pwsh",
    )
    p_env.set_defaults(_fn=cmd_env, format_pwsh=False, format_posix=False)

    sub.add_parser("init", help="Create venv, pip install -e ., tlm init, activation scripts", parents=[parent]).set_defaults(
        _fn=cmd_init
    )

    p_ref = sub.add_parser(
        "refresh",
        help="Wipe sandbox config/state, reinstall package, tlm init; keeps [keys] unless --wipe-keys",
        parents=[parent],
    )
    p_ref.add_argument(
        "--wipe-keys",
        action="store_true",
        help="Do not restore API keys from the previous sandbox config.toml.",
    )
    p_ref.add_argument(
        "--recreate-venv",
        action="store_true",
        help="Remove and recreate .venv (otherwise only .config/.local are wiped).",
    )
    p_ref.set_defaults(_fn=cmd_refresh)

    p_run = sub.add_parser(
        "run",
        help="Run a command with sandbox env + venv PATH",
        parents=[parent],
    )
    p_run.add_argument("cmd", nargs=argparse.REMAINDER, help="command and arguments")
    p_run.set_defaults(_fn=cmd_run)

    sub.add_parser(
        "shell",
        help="Interactive bash -i or PowerShell with sandbox env (Git Bash preferred if on PATH)",
        parents=[parent],
    ).set_defaults(_fn=cmd_shell)

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
