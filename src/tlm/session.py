"""Session persistence (messages + metadata); JSON on disk for v1."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tlm.config import data_dir, sessions_dir

if TYPE_CHECKING:
    from tlm.providers.base import LLMProvider

KEYWORD_MAX_LEN = 24


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_keyword(s: str) -> str:
    """One word: lowercase [a-z0-9-], max KEYWORD_MAX_LEN. Raises ValueError if invalid."""
    raw = (s or "").strip().lower()
    if not raw:
        raise ValueError("keyword must be non-empty")
    if any(c.isspace() for c in raw):
        raise ValueError("keyword must be a single word (no spaces)")
    # Single token after strip — no internal spaces
    parts = raw.split()
    if len(parts) != 1:
        raise ValueError("keyword must be a single word")
    token = parts[0]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", token):
        raise ValueError("keyword may only use a-z, 0-9, and single hyphens between segments")
    if len(token) > KEYWORD_MAX_LEN:
        token = token[:KEYWORD_MAX_LEN].rstrip("-")
    if not token or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", token):
        raise ValueError("keyword too long or invalid after truncation")
    return token


def _slug_from_title(title: str) -> str:
    t = (title or "").strip().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    t = re.sub(r"-+", "-", t).strip("-")
    if not t:
        return ""
    if len(t) > KEYWORD_MAX_LEN:
        t = t[:KEYWORD_MAX_LEN].rstrip("-")
    try:
        return normalize_keyword(t)
    except ValueError:
        return ""


def _keywords_used_by_others(exclude_session_id: str | None) -> set[str]:
    """Keywords already stored on disk (excluding one session id if given)."""
    used: set[str] = set()
    for p in sessions_dir().glob("*.json"):
        if exclude_session_id is not None and p.stem == exclude_session_id:
            continue
        try:
            s = Session.from_json(json.loads(p.read_text(encoding="utf-8")))
            used.add(s.keyword)
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            continue
    return used


def ensure_unique_keyword(base: str, *, exclude_session_id: str | None = None) -> str:
    """Normalize base and append -2, -3, ... if needed to avoid collisions."""
    kw = normalize_keyword(base)
    used = _keywords_used_by_others(exclude_session_id)
    if kw not in used:
        return kw
    n = 2
    while True:
        suffix = f"-{n}"
        stem = kw[: max(1, KEYWORD_MAX_LEN - len(suffix))].rstrip("-")
        candidate = f"{stem}{suffix}"
        try:
            candidate = normalize_keyword(candidate)
        except ValueError:
            stem = "s"
            candidate = f"{stem}{suffix}"
            candidate = normalize_keyword(candidate)
        if candidate not in used:
            return candidate
        n += 1
        if n > 9999:
            raise ValueError("could not allocate unique keyword")


@dataclass
class Session:
    id: str
    created: str
    updated: str
    title: str
    keyword: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_harvested_at: str | None = None
    message_count_at_last_harvest: int = 0

    def touch(self) -> None:
        self.updated = _utc_now()

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Session:
        sid = str(data["id"])
        title = data.get("title", "untitled")
        kw = (data.get("keyword") or "").strip()
        if not kw:
            # Migrate old sessions: title slug, else alphanumeric id prefix (deduped in list_sessions)
            migrated = _slug_from_title(str(title))
            if not migrated:
                migrated = re.sub(r"[^a-z0-9]", "", sid.lower())[:8] or "session"
            try:
                kw = normalize_keyword(migrated)
            except ValueError:
                kw = "session"
        return cls(
            id=sid,
            created=data["created"],
            updated=data["updated"],
            title=title,
            keyword=kw,
            messages=list(data.get("messages", [])),
            last_harvested_at=data.get("last_harvested_at"),
            message_count_at_last_harvest=int(data.get("message_count_at_last_harvest", 0)),
        )


def session_path(session_id: str) -> Path:
    return sessions_dir() / f"{session_id}.json"


def last_session_path() -> Path:
    return data_dir() / "last_session.json"


def read_last_session_id() -> str | None:
    p = last_session_path()
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        sid = data.get("id")
        return str(sid) if sid else None
    except (json.JSONDecodeError, OSError):
        return None


def write_last_session_id(session_id: str) -> None:
    last_session_path().write_text(json.dumps({"id": session_id}), encoding="utf-8")


def new_session(*, keyword: str, title: str | None = None) -> Session:
    """Create a new session with a normalized unique keyword."""
    sid = str(uuid.uuid4())
    now = _utc_now()
    kw = ensure_unique_keyword(keyword)
    tit = (title.strip() if title else "") or kw
    return Session(
        id=sid,
        created=now,
        updated=now,
        title=tit,
        keyword=kw,
        messages=[],
        last_harvested_at=None,
        message_count_at_last_harvest=0,
    )


def load_session(session_id: str) -> Session | None:
    path = session_path(session_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Session.from_json(data)


def save_session(sess: Session) -> None:
    # Persist unique keyword against other files on disk
    used = _keywords_used_by_others(sess.id)
    if sess.keyword in used:
        n = 2
        base = sess.keyword
        while True:
            suffix = f"-{n}"
            stem = base[: max(1, KEYWORD_MAX_LEN - len(suffix))].rstrip("-")
            cand = f"{stem}{suffix}"
            try:
                cand = normalize_keyword(cand)
            except ValueError:
                stem = "s"
                cand = normalize_keyword(f"{stem}{suffix}")
            if cand not in used:
                sess.keyword = cand
                break
            n += 1
    sess.touch()
    path = session_path(sess.id)
    path.write_text(json.dumps(sess.to_json(), indent=2), encoding="utf-8")


def find_by_keyword(keyword: str) -> Session | None:
    try:
        kw = normalize_keyword(keyword)
    except ValueError:
        return None
    for s in list_sessions():
        if s.keyword == kw:
            return load_session(s.id)  # fresh from disk with full migration
    return None


def resolve_session(spec: str) -> Session | None:
    """Resolve by keyword, full UUID, or unique UUID prefix."""
    spec = spec.strip()
    if not spec:
        return None
    hit = find_by_keyword(spec)
    if hit:
        return hit
    if load_session(spec):
        return load_session(spec)
    matches: list[Session] = []
    for s in list_sessions():
        if s.id.startswith(spec):
            matches.append(s)
    if len(matches) == 1:
        return load_session(matches[0].id)
    return None


def delete_session(session_id: str) -> bool:
    p = session_path(session_id)
    if not p.is_file():
        return False
    p.unlink()
    if read_last_session_id() == session_id:
        try:
            last_session_path().unlink()
        except OSError:
            pass
    return True


def rename_session(session_id: str, title: str) -> bool:
    s = load_session(session_id)
    if s is None:
        return False
    s.title = title.strip() or s.title
    save_session(s)
    return True


def set_session_keyword(session_id: str, keyword: str) -> bool:
    """Rename keyword; must stay unique."""
    s = load_session(session_id)
    if s is None:
        return False
    kw = ensure_unique_keyword(keyword, exclude_session_id=session_id)
    s.keyword = kw
    save_session(s)
    return True


def _dedupe_keywords_inplace(sessions: list[Session]) -> None:
    """Ensure keywords are unique (oldest session keeps base, others get -2, -3)."""
    by_created = sorted(sessions, key=lambda s: s.created)
    used: set[str] = set()
    for s in by_created:
        if s.keyword not in used:
            used.add(s.keyword)
            continue
        n = 2
        while True:
            suffix = f"-{n}"
            stem = s.keyword[: max(1, KEYWORD_MAX_LEN - len(suffix))].rstrip("-")
            cand = f"{stem}{suffix}"
            try:
                cand = normalize_keyword(cand)
            except ValueError:
                stem = "s"
                cand = normalize_keyword(f"{stem}{suffix}")
            if cand not in used:
                s.keyword = cand
                used.add(cand)
                break
            n += 1


def list_sessions() -> list[Session]:
    paths = sorted(sessions_dir().glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    out: list[Session] = []
    for p in paths:
        try:
            s = Session.from_json(json.loads(p.read_text(encoding="utf-8")))
            out.append(s)
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            continue
    _dedupe_keywords_inplace(out)
    # Return newest first for UI
    out.sort(key=lambda s: s.updated, reverse=True)
    return out


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    return sum(max(1, len(str(m.get("content", ""))) // 4) for m in messages)


def trim_session_to_budget(sess: Session, max_tokens: int) -> None:
    while sess.messages and estimate_messages_tokens(sess.messages) > max_tokens:
        sess.messages.pop(0)


def append_user(sess: Session, text: str) -> None:
    sess.messages.append({"role": "user", "content": text})
    if sess.title in ("", "untitled") and text.strip():
        sess.title = text.strip().replace("\n", " ")[:60]


def append_assistant(sess: Session, text: str) -> None:
    sess.messages.append({"role": "assistant", "content": text})


def pick_keyword_for(prompt: str, prov: LLMProvider) -> str:
    """Ask the model for one lowercase word; fallback to first alphanumeric token."""
    p = (prompt or "").strip()
    if not p:
        return "chat"
    system = (
        "Reply with exactly one lowercase word (letters, digits, optional single hyphens between segments). "
        "No spaces, no punctuation, no explanation. Summarize the user's topic in that one word."
    )
    try:
        raw = prov.complete(p[:500], system=system).strip()
        # Take first token only
        first = raw.split()[0] if raw.split() else raw
        first = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", first.lower())
        if first:
            return normalize_keyword(first)
    except Exception:
        pass
    # Fallback: first meaningful word from prompt
    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]*", p):
        try:
            return normalize_keyword(token.lower())
        except ValueError:
            continue
    return "chat"
