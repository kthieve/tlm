"""Harvest durable facts from session transcripts into memory stores."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from tlm.memory import (
    STORAGE_RULES_TEXT,
    add_longterm,
    append_ready,
    is_safe_to_store,
    redact,
)
from tlm.session import Session, save_session

if TYPE_CHECKING:
    from tlm.providers.base import LLMProvider
    from tlm.settings import UserSettings


def _extract_json_array(text: str) -> list[str]:
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
        s = re.sub(r"\s*```$", "", s)
    s = s.strip()
    if not s.startswith("["):
        i = s.find("[")
        j = s.rfind("]")
        if i == -1 or j == -1 or j <= i:
            return []
        s = s[i : j + 1]
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for x in data:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def extract_harvest_items(
    prov: LLMProvider,
    sess: Session,
    *,
    max_messages: int = 40,
    max_items: int = 8,
) -> list[str]:
    """Ask the model for a JSON array of short durable facts (may be empty)."""
    tail = sess.messages[-max_messages:] if sess.messages else []
    lines: list[str] = []
    for m in tail:
        role = str(m.get("role", ""))
        content = str(m.get("content", ""))[:6000]
        lines.append(f"{role}: {content}")
    blob = "\n".join(lines)[:100_000]
    system = f"""You extract durable facts for a personal memory store.
Return ONLY a JSON array of strings (max {max_items} items). Each string <= 200 characters.
Do not include secrets: no API keys, passwords, tokens, private keys, JWTs, bearer strings.

Storage guidance:
{STORAGE_RULES_TEXT}

If there is nothing worth saving, return [].
"""
    try:
        raw = prov.complete(blob, system=system)
    except Exception:
        return []
    return _extract_json_array(raw)[:max_items]


def apply_harvest_items(
    items: list[str],
    *,
    source_session: str | None,
    settings: UserSettings,
    push_ready_summary: bool = True,
) -> tuple[int, int]:
    """Filter by safety; add to long-term; optionally one-line ready. Returns (longterm_added, skipped)."""
    added = 0
    skipped = 0
    first_summary: str | None = None
    for raw in items:
        t = redact(raw.strip())
        ok, _ = is_safe_to_store(t)
        if not ok or not t:
            skipped += 1
            continue
        ent = add_longterm(t, tags=["harvest"], source_session=source_session)
        if ent:
            added += 1
            if first_summary is None and len(t) <= 160:
                first_summary = t
        else:
            skipped += 1
    if (
        push_ready_summary
        and first_summary
        and settings.memory_enabled
    ):
        append_ready([first_summary], budget_chars=settings.memory_ready_budget_chars)
    return added, skipped


def auto_harvest_session_if_due(
    sess: Session,
    prov: LLMProvider,
    settings: UserSettings,
    *,
    min_delta: int | None = None,
) -> None:
    """Background harvest after asks or on session switch; no per-item prompts."""
    if not settings.memory_enabled:
        return
    thr = settings.memory_auto_harvest_threshold_messages
    delta = min_delta if min_delta is not None else thr
    if len(sess.messages) - sess.message_count_at_last_harvest < delta:
        return
    items = extract_harvest_items(prov, sess)
    if items:
        apply_harvest_items(items, source_session=sess.id, settings=settings, push_ready_summary=True)
    sess.last_harvested_at = datetime.now(timezone.utc).isoformat()
    sess.message_count_at_last_harvest = len(sess.messages)
    save_session(sess)
