"""Two-tier memory: ready (short, auto-injected) and long-term (searchable JSONL)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from tlm.config import data_dir

ITEM_MAX_LEN = 240
READY_FILE = "ready.json"
LONGTERM_FILE = "longterm.jsonl"

# Shown in help / GUI
STORAGE_RULES_TEXT = """What to store
- OS / distro, desktop, locale, timezone (generic)
- CPU / GPU / RAM summary, shell, editor preferences
- Stable project paths the user volunteered, workflow preferences, tool versions

Never store
- API keys, tokens, passwords, private keys, JWTs, bearer strings
- SSH private keys or BEGIN … PRIVATE KEY blocks
- High-entropy KEY=value env-style secrets
- URLs with embedded credentials (user:pass@)

Items are capped in length; obvious secrets are rejected or redacted."""

_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._\-+/=]{20,}", re.I)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_SK_LIKE = re.compile(r"\b(sk|pk|api)[_-]?[a-z0-9]{16,}\b", re.I)
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I)
_ENV_SECRET = re.compile(
    r"(?m)^\s*([A-Z][A-Z0-9_]{2,})\s*=\s*([^\s#].*)$",
)
_URL_CREDS = re.compile(r"[a-z]+://[^/\s]+:[^/\s]+@", re.I)


def memory_dir() -> Path:
    d = data_dir() / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ready_path() -> Path:
    return memory_dir() / READY_FILE


def longterm_path() -> Path:
    return memory_dir() / LONGTERM_FILE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(text: str) -> str:
    """Best-effort redact common secret patterns (still validate with is_safe_to_store)."""
    t = text
    t = _BEARER.sub("[redacted bearer]", t)
    t = _JWT.sub("[redacted jwt]", t)
    t = _PRIVATE_KEY.sub("[redacted key]", t)
    t = _URL_CREDS.sub(lambda m: m.group(0).split("://")[0] + "://[redacted]@", t)
    return t


def _shannon_entropy_bits(s: str) -> float:
    if not s:
        return 0.0
    from math import log2

    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((c / n) * log2(c / n) for c in freq.values())


def is_safe_to_store(text: str) -> tuple[bool, str]:
    """Return (ok, reason)."""
    t = (text or "").strip()
    if not t:
        return False, "empty"
    if len(t) > ITEM_MAX_LEN * 2:
        return False, "too long"
    tl = t.lower()
    if any(
        w in tl
        for w in (
            "api key",
            "apikey",
            "password",
            "passwd",
            "secret",
            "private key",
            "access token",
            "refresh token",
            "authorization:",
        )
    ):
        return False, "mentions sensitive credential wording"
    if _BEARER.search(t) or _JWT.search(t) or _PRIVATE_KEY.search(t):
        return False, "matches secret pattern"
    if _SK_LIKE.search(t):
        return False, "matches sk-/pk-/api- token pattern"
    if _URL_CREDS.search(t):
        return False, "URL with embedded credentials"
    for m in _ENV_SECRET.finditer(t):
        val = (m.group(2) or "").strip().strip('"').strip("'")
        if len(val) >= 24 and _shannon_entropy_bits(val) > 4.0:
            return False, "env-style high-entropy value"
    return True, ""


def _normalize_dedupe_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())[:200]


@dataclass
class LongTermEntry:
    id: str
    text: str
    tags: list[str]
    source_session: str | None
    created: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> LongTermEntry:
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            tags=list(data.get("tags") or []),
            source_session=data.get("source_session"),
            created=str(data.get("created", _utc_now())),
        )


def load_ready() -> list[str]:
    p = ready_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return [str(x).strip() for x in data["items"] if str(x).strip()]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_ready(items: list[str], *, budget_chars: int) -> list[str]:
    """Trim to budget, dedupe, clamp item length; persist."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        s = (raw or "").strip()
        if not s:
            continue
        s = s[:ITEM_MAX_LEN]
        key = _normalize_dedupe_key(s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    out = prune_ready_to_budget(out, budget_chars)
    ready_path().write_text(json.dumps({"items": out}, indent=2), encoding="utf-8")
    return out


def prune_ready_to_budget(items: list[str], budget_chars: int) -> list[str]:
    """Drop from the end until total chars fit (join with newlines heuristic)."""
    if budget_chars <= 0:
        return []
    out: list[str] = []
    total = 0
    for s in items:
        line = s[:ITEM_MAX_LEN]
        add = len(line) + (1 if out else 0)
        if total + add > budget_chars:
            break
        out.append(line)
        total += add
    return out


def append_ready(items: list[str], *, budget_chars: int) -> list[str]:
    cur = load_ready()
    cur.extend(items)
    return save_ready(cur, budget_chars=budget_chars)


def format_ready_for_prompt(items: list[str]) -> str:
    if not items:
        return ""
    lines = "\n".join(f"- {s[:ITEM_MAX_LEN]}" for s in items)
    return f"Ready memory (short facts about the user; do not repeat as secrets):\n{lines}\n"


def iter_longterm() -> Iterator[LongTermEntry]:
    p = longterm_path()
    if not p.is_file():
        return
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield LongTermEntry.from_json(json.loads(line))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue


def _read_all_longterm() -> list[LongTermEntry]:
    return list(iter_longterm())


def _write_all_longterm(entries: list[LongTermEntry]) -> None:
    p = longterm_path()
    lines = [json.dumps(e.to_json(), ensure_ascii=False) for e in entries]
    p.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def add_longterm(
    text: str,
    tags: list[str] | None = None,
    source_session: str | None = None,
    *,
    skip_safety: bool = False,
) -> LongTermEntry | None:
    t = redact((text or "").strip())[:ITEM_MAX_LEN]
    if not skip_safety:
        ok, _ = is_safe_to_store(t)
        if not ok:
            return None
    key = _normalize_dedupe_key(t)
    existing = _read_all_longterm()
    for e in existing:
        if _normalize_dedupe_key(e.text) == key:
            return e
    ent = LongTermEntry(
        id=str(uuid.uuid4()),
        text=t,
        tags=list(tags or []),
        source_session=source_session,
        created=_utc_now(),
    )
    existing.append(ent)
    _write_all_longterm(existing)
    return ent


def update_longterm(entry_id: str, *, text: str | None = None, tags: list[str] | None = None) -> bool:
    entries = _read_all_longterm()
    for i, e in enumerate(entries):
        if e.id == entry_id:
            if text is not None:
                t = redact(text.strip())[:ITEM_MAX_LEN]
                ok, _ = is_safe_to_store(t)
                if not ok:
                    return False
                entries[i] = LongTermEntry(
                    id=e.id,
                    text=t,
                    tags=list(tags) if tags is not None else e.tags,
                    source_session=e.source_session,
                    created=e.created,
                )
            elif tags is not None:
                entries[i] = LongTermEntry(
                    id=e.id,
                    text=e.text,
                    tags=list(tags),
                    source_session=e.source_session,
                    created=e.created,
                )
            _write_all_longterm(entries)
            return True
    return False


def delete_longterm(entry_id: str) -> bool:
    entries = _read_all_longterm()
    new_entries = [e for e in entries if e.id != entry_id]
    if len(new_entries) == len(entries):
        return False
    _write_all_longterm(new_entries)
    return True


def search_longterm(query: str, k: int = 5) -> list[LongTermEntry]:
    q = (query or "").strip().lower()
    if not q:
        return []
    q_tokens = set(re.findall(r"[a-z0-9]+", q))
    scored: list[tuple[float, LongTermEntry]] = []
    for e in _read_all_longterm():
        text_l = e.text.lower()
        tag_l = " ".join(e.tags).lower()
        score = 0.0
        for tok in q_tokens:
            if tok in text_l:
                score += 2.0 + min(3.0, text_l.count(tok) * 0.5)
            if tok in tag_l:
                score += 1.5
        if score > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: (-x[0], x[1].created))
    return [e for _, e in scored[:k]]


def format_search_results_for_prompt(entries: list[LongTermEntry]) -> str:
    if not entries:
        return "(no matching long-term memory entries)"
    lines = []
    for e in entries:
        tag_s = f" tags={e.tags}" if e.tags else ""
        lines.append(f"- {e.text}{tag_s}")
    return "Long-term memory hits:\n" + "\n".join(lines)
