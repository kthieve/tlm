"""Brave Web Search API client (JSON). Not used by ask-mode `tlm-web` (Lightpanda-only); kept for tooling/tests."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def format_brave_web_results(payload: dict[str, Any], *, max_items: int = 10) -> str:
    """Turn Brave `res/v1/web/search` JSON into plain text for the model."""
    web = payload.get("web")
    if not isinstance(web, dict):
        return "(Brave API: no web results in response)"
    raw_results = web.get("results")
    if not isinstance(raw_results, list) or not raw_results:
        return "(Brave API: empty result list)"
    lines: list[str] = ["Brave Search API results:"]
    for i, item in enumerate(raw_results[:max_items], 1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        desc = str(item.get("description", "")).strip()
        if not title and not url:
            continue
        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   {url}")
        if desc:
            lines.append(f"   {desc}")
    return "\n".join(lines) if len(lines) > 1 else "(Brave API: no parseable items)"


def brave_web_search(
    q: str,
    api_key: str,
    *,
    timeout: float,
    count: int = 10,
) -> tuple[int, str]:
    """
    GET Brave web search. Returns (exit_code, body) — body is formatted hits or error text.
    exit_code 0 on HTTP 200 and parsed JSON; 1 on failure.
    """
    q = (q or "").strip()
    if not q:
        return 1, "(Brave API: empty query)"
    key = (api_key or "").strip()
    if not key:
        return 1, "(Brave API: missing API key)"
    url = "https://api.search.brave.com/res/v1/web/search?" + urlencode(
        {"q": q, "count": str(max(1, min(count, 20)))}
    )
    req = Request(
        url,
        headers={
            "X-Subscription-Token": key,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:2000]
        except OSError:
            detail = ""
        return 1, f"(Brave API HTTP {e.code}: {detail or e.reason})"
    except URLError as e:
        return 1, f"(Brave API network error: {e.reason})"
    except OSError as e:
        return 1, f"(Brave API error: {e})"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return 1, f"(Brave API: invalid JSON: {e})"
    if not isinstance(data, dict):
        return 1, "(Brave API: unexpected response shape)"
    return 0, format_brave_web_results(data)
