"""Lightpanda CLI integration: `lightpanda fetch` argv building and URL checks."""

from __future__ import annotations

import shutil
from urllib.parse import quote_plus, urlparse

from tlm.settings import UserSettings

# DuckDuckGo lite HTML (best-effort; markup may change).
DDG_LITE_SEARCH = "https://lite.duckduckgo.com/lite/?q="


def resolve_binary(settings: UserSettings) -> str | None:
    if settings.lightpanda_path:
        p = settings.lightpanda_path.strip()
        return p if p else None
    found = shutil.which("lightpanda")
    return found


def validate_url(url: str, *, allow_http: bool) -> tuple[bool, str]:
    raw = (url or "").strip()
    if not raw:
        return False, "empty url"
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme == "https":
        if not parsed.netloc:
            return False, "https URL missing host"
        return True, ""
    if scheme == "http" and allow_http:
        if not parsed.netloc:
            return False, "http URL missing host"
        return True, ""
    if scheme in ("file", "javascript", "data", "vbscript"):
        return False, f"blocked scheme: {scheme!r}"
    if scheme not in ("http", "https"):
        return False, f"unsupported scheme: {scheme!r} (enable web_allow_http for http)"
    return False, "http not allowed (web_allow_http=false); use https"


def search_url_for_query(q: str) -> str:
    return DDG_LITE_SEARCH + quote_plus(q.strip())


def build_fetch_argv(
    binary: str,
    url: str,
    *,
    dump: str,
    obey_robots: bool,
) -> list[str]:
    d = dump.lower().strip()
    if d not in ("markdown", "html"):
        d = "markdown"
    argv: list[str] = [binary, "fetch"]
    if obey_robots:
        argv.append("--obey-robots")
    argv.extend(["--dump", d, "--log-level", "error", url])
    return argv
