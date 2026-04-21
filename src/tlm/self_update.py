"""GitHub release checks and `tlm update` (pipx or ~/.local/share/tlm-venv)."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from tlm import __version__
from tlm.settings import UserSettings

VENV_DIR = Path.home() / ".local" / "share" / "tlm-venv"
UPDATE_NOTIFY_FILE = "update_notify.json"
CHECK_INTERVAL_SEC = 86400
GH_TIMEOUT = 3.0

_github_slug_re = re.compile(
    r"(?:https?://)?github\.com[/:]([^/]+)/([^/.]+?)(?:\.git)?/?$",
    re.I,
)


def strip_v(s: str) -> str:
    s = s.strip()
    if s and s[0].lower() == "v":
        return s[1:]
    return s


def parse_version_loose(s: str) -> Version | None:
    try:
        return Version(strip_v(s))
    except InvalidVersion:
        return None


def version_a_gt_b(a: str, b: str) -> bool:
    va, vb = parse_version_loose(a), parse_version_loose(b)
    if va is None or vb is None:
        return False
    return va > vb


def parse_slug_from_github_url(url: str) -> str | None:
    base = url.replace("git+", "", 1).split("@", 1)[0]
    m = _github_slug_re.search(base)
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}"


def read_direct_url() -> dict[str, Any] | None:
    try:
        from importlib.metadata import PackageNotFoundError, distribution
    except ImportError:
        return None
    try:
        dist = distribution("tlm")
    except PackageNotFoundError:
        return None
    try:
        raw = dist.read_text("direct_url.json")
    except (FileNotFoundError, OSError, KeyError):
        return None
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return out if isinstance(out, dict) else None


def slug_from_direct_url(data: dict[str, Any]) -> str | None:
    url = data.get("url")
    if not isinstance(url, str):
        return None
    return parse_slug_from_github_url(url)


def is_editable_install(data: dict[str, Any] | None) -> bool:
    if not data:
        return False
    di = data.get("dir_info")
    if isinstance(di, dict):
        return bool(di.get("editable"))
    return False


def resolve_github_slug(settings: UserSettings | None) -> str | None:
    if settings and settings.github_repo:
        s = settings.github_repo.strip()
        if s and "/" in s:
            return s
    env = (os.environ.get("TLM_GITHUB_REPO") or "").strip()
    if env and "/" in env:
        return env
    du = read_direct_url()
    if du and not is_editable_install(du):
        slug = slug_from_direct_url(du)
        if slug:
            return slug
    return None


def fetch_latest_release_tag(slug: str, *, timeout: float = GH_TIMEOUT) -> str | None:
    owner, sep, repo = slug.partition("/")
    if not sep or not owner or not repo:
        return None
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError, json.JSONDecodeError):
        return None
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if isinstance(tag, str) and tag:
        return tag
    return None


def _which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


def pipx_has_tlm() -> bool:
    pipx = _which("pipx")
    if not pipx:
        return False
    try:
        p = subprocess.run(
            [pipx, "list", "--short"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if p.returncode != 0:
        return False
    return any(
        line.strip().startswith("tlm ")
        for line in (p.stdout or "").splitlines()
    )


def current_exe_in_local_tlm_venv() -> bool:
    try:
        exe = Path(sys.executable).resolve()
        base = VENV_DIR.resolve()
    except OSError:
        return False
    try:
        return base in exe.parents or exe == (base / "bin" / "python").resolve()
    except OSError:
        return str(exe).startswith(str(base))


def _running_from_source_tree() -> bool:
    import tlm

    p = Path(tlm.__file__).resolve()
    if "site-packages" in str(p):
        return False
    for ancestor in [p.parent, *p.parents]:
        if ancestor == ancestor.anchor:
            break
        if (ancestor / ".git").is_dir():
            return True
    return False


def infer_install_kind() -> str:
    """Return pipx, tlm_venv, dev, or unknown."""
    du = read_direct_url()
    if is_editable_install(du):
        return "dev"
    if _running_from_source_tree():
        return "dev"
    if pipx_has_tlm():
        return "pipx"
    if current_exe_in_local_tlm_venv() or (VENV_DIR / "bin" / "tlm").is_file():
        return "tlm_venv"
    return "unknown"


def build_git_spec(slug: str, ref: str) -> str:
    owner, sep, repo = slug.partition("/")
    if not sep:
        raise ValueError("invalid slug")
    return f"git+https://github.com/{owner}/{repo}.git@{ref}"


def resolve_update_ref(
    slug: str,
    *,
    ref: str | None,
    version: str | None,
) -> tuple[str | None, str | None]:
    if version:
        v = version.strip()
        r = v if v[:1].lower() == "v" else f"v{v}"
        return r, None
    if ref:
        return ref.strip(), None
    tag = fetch_latest_release_tag(slug)
    if not tag:
        return None, "could not fetch latest release from GitHub (network or no releases)"
    return tag, None


def _git_repo_root() -> Path | None:
    import tlm

    p = Path(tlm.__file__).resolve().parent
    for ancestor in [p, *p.parents]:
        if ancestor == ancestor.anchor:
            break
        if (ancestor / ".git").is_dir():
            return ancestor
    return None


def run_update(*, slug: str, ref: str, yes: bool) -> int:
    kind = infer_install_kind()
    try:
        spec = build_git_spec(slug, ref)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if kind == "dev":
        print(
            "tlm looks like a development / editable checkout; skipping pip/pipx.",
            file=sys.stderr,
        )
        root = _git_repo_root()
        if root is not None:
            print(f"  cd {root} && git pull && pip install -e .", file=sys.stderr)
        else:
            print(
                f"  pipx install {shlex.quote(spec)} --force",
                file=sys.stderr,
            )
        return 2

    if kind == "pipx":
        pipx = _which("pipx")
        if not pipx:
            print("error: pipx not on PATH", file=sys.stderr)
            return 2
        cmd = [pipx, "install", spec, "--force"]
    elif kind == "tlm_venv":
        py = VENV_DIR / "bin" / "python"
        if not py.is_file():
            print(f"error: missing {py}", file=sys.stderr)
            return 2
        cmd = [str(py), "-m", "pip", "install", "-U", spec]
    else:
        print(
            "Could not detect pipx or ~/.local/share/tlm-venv; run one of:",
            file=sys.stderr,
        )
        print(f"  pipx install {shlex.quote(spec)} --force", file=sys.stderr)
        py = VENV_DIR / "bin" / "python"
        if py.is_file():
            print(
                f"  {shlex.quote(str(py))} -m pip install -U {shlex.quote(spec)}",
                file=sys.stderr,
            )
        return 2

    preview = " ".join(shlex.quote(c) for c in cmd)
    print(preview)
    if not yes:
        print("(re-run with --yes to execute)", file=sys.stderr)
        return 0

    p = subprocess.run(cmd, check=False)  # noqa: S603
    rc = p.returncode
    return int(rc if rc is not None else 1)


@dataclass
class UpdateNotifyCache:
    last_check_epoch: float = 0.0
    last_notified_tag: str | None = None


def _notify_cache_path() -> Path:
    from tlm.config import state_dir

    return state_dir() / UPDATE_NOTIFY_FILE


def load_notify_cache() -> UpdateNotifyCache:
    path = _notify_cache_path()
    if not path.is_file():
        return UpdateNotifyCache()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UpdateNotifyCache()
    if not isinstance(data, dict):
        return UpdateNotifyCache()
    tag = data.get("last_notified_tag")
    return UpdateNotifyCache(
        last_check_epoch=float(data.get("last_check_epoch", 0)),
        last_notified_tag=tag if isinstance(tag, str) else None,
    )


def save_notify_cache(c: UpdateNotifyCache) -> None:
    path = _notify_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"last_check_epoch": c.last_check_epoch, "last_notified_tag": c.last_notified_tag}),
        encoding="utf-8",
    )


def format_config_header_status(settings: UserSettings) -> str:
    """One-line summary for TUI / headers (no network)."""
    slug = resolve_github_slug(settings) or "(unset)"
    notify = "on" if settings.check_for_updates else "off"
    return f"v{__version__} · {infer_install_kind()} · repo {slug} · release notify {notify}"


def format_version_update_status(
    settings: UserSettings | None,
    *,
    query_github: bool = False,
    timeout: float = GH_TIMEOUT,
) -> str:
    """Multi-line status for About dialogs and TUI (optional GitHub query for latest tag)."""
    s = settings if settings is not None else UserSettings()
    lines = [
        f"tlm version: {__version__}",
        f"Install: {infer_install_kind()}",
    ]
    slug = resolve_github_slug(s)
    if slug:
        lines.append(f"GitHub repo: {slug}")
    else:
        lines.append(
            "GitHub repo: (not resolved — set `github_repo` in config.toml, `TLM_GITHUB_REPO`, "
            "or install from a git+https://github.com/… URL)"
        )
    lines.append(
        f"Notify on new releases: {bool(s.check_for_updates)} "
        "(stderr hint; suppress with TLM_NO_UPDATE_CHECK=1)"
    )
    if not query_github:
        lines.append("Latest release: (choose Refresh to query GitHub)")
        return "\n".join(lines)
    if not slug:
        lines.append("Latest release: (skipped — no repo slug)")
        return "\n".join(lines)
    tag = fetch_latest_release_tag(slug, timeout=timeout)
    if not tag:
        lines.append("Latest release tag: (unavailable — network, API error, or no releases)")
    elif version_a_gt_b(tag, __version__):
        lines.append(
            f"Update available: {tag} (installed {__version__}). In a terminal: `tlm update` or `tlm update --yes`"
        )
    else:
        lines.append(
            f"Latest published tag: {tag} — up to date or on a dev/local build (installed {__version__})."
        )
    return "\n".join(lines)


def maybe_print_update_notice(settings: UserSettings, *, argv0: str | None = None) -> None:
    if not settings.check_for_updates:
        return
    v = (os.environ.get("TLM_NO_UPDATE_CHECK") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return
    cmd = (argv0 or "").strip().lower()
    if cmd in ("update", "completion", "help"):
        return

    slug = resolve_github_slug(settings)
    if not slug:
        return

    now = time.time()
    cache = load_notify_cache()
    if now - cache.last_check_epoch < CHECK_INTERVAL_SEC:
        return

    cache.last_check_epoch = now
    save_notify_cache(cache)

    tag = fetch_latest_release_tag(slug)
    if not tag or not version_a_gt_b(tag, __version__):
        return
    if cache.last_notified_tag == tag:
        return

    print(
        f"tlm: newer release {tag} available (you have {__version__}). Run: tlm update --yes",
        file=sys.stderr,
    )
    cache.last_notified_tag = tag
    save_notify_cache(cache)


def cmd_update_ns(ns: Namespace, settings: UserSettings) -> int:
    slug = resolve_github_slug(settings)
    if not slug:
        print(
            "error: set github_repo in config.toml or TLM_GITHUB_REPO=owner/repo",
            file=sys.stderr,
        )
        return 2
    ref, err = resolve_update_ref(
        slug,
        ref=getattr(ns, "update_ref", None),
        version=getattr(ns, "update_version", None),
    )
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    assert ref is not None
    return run_update(slug=slug, ref=ref, yes=bool(ns.yes))
