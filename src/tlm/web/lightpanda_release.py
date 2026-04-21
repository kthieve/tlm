"""GitHub release metadata and download for Lightpanda (lightpanda-io/browser)."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tlm.config import data_dir
from tlm.settings import UserSettings
from tlm.web.lightpanda import resolve_binary

GITHUB_API_LATEST = "https://api.github.com/repos/lightpanda-io/browser/releases/latest"
RELEASES_PAGE = "https://github.com/lightpanda-io/browser/releases"
_DOWNLOAD_PREFIX = "https://github.com/lightpanda-io/browser/releases/download/"
_USER_AGENT = "tlm-lightpanda-helper/1.0"
_CHUNK = 256 * 1024


def _partial_paths(dest: Path) -> tuple[Path, Path]:
    """Partial download file and sidecar storing the source URL (for resume safety)."""
    part = dest.parent / f"{dest.name}.partial"
    marker = dest.parent / f"{dest.name}.partial.url"
    return part, marker


def _sync_partial_with_url(part: Path, marker: Path, url: str) -> None:
    if marker.is_file():
        try:
            if marker.read_text(encoding="utf-8").strip() != url:
                part.unlink(missing_ok=True)
                marker.unlink(missing_ok=True)
        except OSError:
            pass
    elif part.is_file():
        # Stale partial (e.g. older tlm) — do not resume blindly
        part.unlink(missing_ok=True)


def _parse_content_range(value: str | None) -> tuple[int | None, int | None]:
    """Return (first_byte_index, total_length) from a Content-Range header value."""
    if not value:
        return None, None
    v = value.strip()
    if not v.lower().startswith("bytes "):
        return None, None
    rest = v[6:].strip()
    if "/" not in rest:
        return None, None
    span, total_s = rest.rsplit("/", 1)
    total: int | None
    if total_s == "*":
        total = None
    else:
        try:
            total = int(total_s)
        except ValueError:
            total = None
    if "-" not in span:
        return None, total
    a, _ = span.split("-", 1)
    try:
        first = int(a)
    except ValueError:
        first = None
    return first, total


def preferred_asset_basename() -> str | None:
    """Return release asset filename (e.g. lightpanda-x86_64-linux) for this machine, or None."""
    mach = platform.machine().lower()
    if mach in ("amd64", "x86_64"):
        arch = "x86_64"
    elif mach in ("aarch64", "arm64"):
        arch = "aarch64"
    else:
        return None
    if sys.platform == "linux":
        return f"lightpanda-{arch}-linux"
    if sys.platform == "darwin":
        return f"lightpanda-{arch}-macos"
    return None


def fetch_latest_release(*, timeout: float) -> tuple[bool, dict[str, Any] | str]:
    """GET releases/latest JSON. Returns (ok, data_or_error_message)."""
    req = Request(
        GITHUB_API_LATEST,
        headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
        method="GET",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:500]
        except OSError:
            detail = ""
        return False, f"GitHub HTTP {e.code}: {detail or e.reason}"
    except URLError as e:
        return False, f"network error: {e.reason}"
    except OSError as e:
        return False, str(e)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return False, f"invalid JSON: {e}"
    if not isinstance(data, dict):
        return False, "unexpected API shape"
    return True, data


def pick_asset_download_url(release: dict[str, Any], asset_basename: str) -> tuple[str | None, str | None]:
    """Return (browser_download_url, tag_name) for the named asset."""
    tag = release.get("tag_name")
    tag_s = str(tag) if tag else None
    assets = release.get("assets")
    if not isinstance(assets, list):
        return None, tag_s
    for a in assets:
        if not isinstance(a, dict):
            continue
        name = str(a.get("name", ""))
        if name != asset_basename:
            continue
        url = a.get("browser_download_url")
        if isinstance(url, str) and url.startswith(_DOWNLOAD_PREFIX):
            return url, tag_s
    return None, tag_s


def local_lightpanda_version(bin_path: str, *, timeout: float = 8.0) -> str | None:
    """Best-effort `lightpanda --version` (or -V) first line."""
    for flag in ("--version", "-V"):
        try:
            proc = subprocess.run(
                [bin_path, flag],
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            out = (proc.stdout or proc.stderr or "").strip()
            if out:
                line = out.splitlines()[0].strip()
                if line:
                    return line[:200]
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def describe_local_install(settings: UserSettings) -> str:
    """Human-readable local resolve + version."""
    p = resolve_binary(settings)
    if not p:
        return "Lightpanda: not found (not on PATH and no lightpanda_path)."
    ver = local_lightpanda_version(p)
    if ver:
        return f"Lightpanda: {p}\nVersion: {ver}"
    return f"Lightpanda: {p}\n(version probe failed; try running `{p} --version`)"


def compare_status(settings: UserSettings, release: dict[str, Any]) -> str:
    """Short text: local vs GitHub tag."""
    remote_tag = str(release.get("tag_name", "?"))
    want = preferred_asset_basename()
    if not want:
        return f"GitHub latest tag: {remote_tag} (no prebuilt binary listed for this OS/arch)."

    p = resolve_binary(settings)
    lines = [f"GitHub latest tag: {remote_tag}", f"Expected asset: {want}"]
    if p:
        lv = local_lightpanda_version(p)
        lines.append(f"Local binary: {p}")
        if lv:
            lines.append(f"Local version output: {lv}")
        # Heuristic: nightly tag won't match semver; still inform user
        if remote_tag.lower() == "nightly":
            lines.append("Upstream publishes a single 'nightly' tag; re-download to refresh.")
    else:
        lines.append("Local binary: (none)")
    return "\n".join(lines)


def download_release_binary(
    url: str,
    dest: Path,
    *,
    timeout: float,
    cancel_event: threading.Event | None = None,
    progress: Callable[[int, int | None], None] | None = None,
) -> tuple[bool, str]:
    """
    Download raw release asset with chunked reads; chmod 0755 when complete.
    Supports resume via ``dest.partial`` + ``dest.partial.url`` (same URL only).
    """
    if not url.startswith(_DOWNLOAD_PREFIX):
        return False, "refusing download: URL is not an official Lightpanda release download"

    dest.parent.mkdir(parents=True, exist_ok=True)
    part, marker = _partial_paths(dest)
    _sync_partial_with_url(part, marker, url)
    if marker.is_file() and not part.is_file():
        try:
            marker.unlink(missing_ok=True)
        except OSError:
            pass

    resume_from = part.stat().st_size if part.is_file() else 0
    try:
        marker.write_text(url, encoding="utf-8")
    except OSError as e:
        return False, str(e)

    attempt = 0
    while attempt < 3:
        attempt += 1
        headers = {"User-Agent": _USER_AGENT}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"
        req = Request(url, headers=headers, method="GET")
        try:
            resp = urlopen(req, timeout=timeout)
        except HTTPError as e:
            if e.code == 416 and resume_from > 0:
                try:
                    part.unlink(missing_ok=True)
                    marker.unlink(missing_ok=True)
                except OSError:
                    pass
                resume_from = 0
                try:
                    marker.write_text(url, encoding="utf-8")
                except OSError as err:
                    return False, str(err)
                continue
            try:
                detail = e.read().decode("utf-8", errors="replace")[:300]
            except OSError:
                detail = ""
            return False, f"download HTTP {e.code}: {e.reason} {detail}".strip()
        except URLError as e:
            return False, f"download failed: {e.reason}"
        except OSError as e:
            return False, str(e)

        try:
            code = getattr(resp, "status", None) or resp.getcode()
            if code == 416 and resume_from > 0:
                resp.close()
                try:
                    part.unlink(missing_ok=True)
                    marker.unlink(missing_ok=True)
                except OSError:
                    pass
                resume_from = 0
                try:
                    marker.write_text(url, encoding="utf-8")
                except OSError as err:
                    return False, str(err)
                continue

            if code not in (200, 206):
                try:
                    _ = resp.read(512)
                except OSError:
                    pass
                resp.close()
                return False, f"download HTTP {code}"

            total: int | None
            if code == 200:
                cl = resp.headers.get("Content-Length")
                try:
                    total = int(cl) if cl is not None else None
                except (TypeError, ValueError):
                    total = None
                out = open(part, "wb")
                accum = 0
            else:
                cr = resp.headers.get("Content-Range")
                first_byte, cr_total = _parse_content_range(cr)
                total = cr_total
                cl = resp.headers.get("Content-Length")
                if total is None and cl is not None:
                    try:
                        total = resume_from + int(cl)
                    except (TypeError, ValueError):
                        pass
                if first_byte is not None and first_byte != resume_from:
                    resp.close()
                    try:
                        part.unlink(missing_ok=True)
                    except OSError:
                        pass
                    resume_from = 0
                    continue
                out = open(part, "ab")
                accum = resume_from

            if progress:
                progress(accum, total)

            cancelled = False
            try:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        cancelled = True
                        break
                    chunk = resp.read(_CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    accum += len(chunk)
                    if progress:
                        progress(accum, total)
            finally:
                out.close()
            resp.close()
            if cancelled:
                return False, "Download cancelled — partial file kept; use Download again to resume."
        except HTTPError:
            raise
        except OSError as e:
            return False, str(e)

        try:
            part.chmod(0o755)
            part.replace(dest)
        except OSError as e:
            return False, str(e)
        try:
            marker.unlink(missing_ok=True)
        except OSError:
            pass
        return True, ""

    return False, "download failed after retries (range / server error)."


def default_install_path() -> Path:
    return data_dir() / "bin" / "lightpanda"


def install_latest_to_data_dir(
    settings: UserSettings,
    *,
    timeout: float,
    cancel_event: threading.Event | None = None,
    progress: Callable[[int, int | None], None] | None = None,
) -> tuple[bool, str, Path | None]:
    """
    Fetch latest release, pick asset for this platform, download to data_dir()/bin/lightpanda.
    Returns (ok, message, path_if_ok).
    """
    want = preferred_asset_basename()
    if not want:
        return False, "No GitHub binary asset for this platform (tlm supports Linux/macOS x86_64/aarch64).", None

    ok, got = fetch_latest_release(timeout=timeout)
    if not ok or not isinstance(got, dict):
        return False, str(got), None

    url, _tag = pick_asset_download_url(got, want)
    if not url:
        return False, f"No asset named {want!r} in latest release.", None

    dest = default_install_path()
    ok_d, err = download_release_binary(
        url,
        dest,
        timeout=min(timeout, 600.0),
        cancel_event=cancel_event,
        progress=progress,
    )
    if not ok_d:
        return False, err, None

    settings.lightpanda_path = str(dest)
    return True, f"Installed to {dest} (set lightpanda_path in config).", dest
