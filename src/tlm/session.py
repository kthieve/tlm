"""Session persistence (messages + metadata); JSON on disk for v1."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tlm.config import data_dir, sessions_dir


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Session:
    id: str
    created: str
    updated: str
    title: str
    messages: list[dict[str, Any]] = field(default_factory=list)

    def touch(self) -> None:
        self.updated = _utc_now()

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Session:
        return cls(
            id=data["id"],
            created=data["created"],
            updated=data["updated"],
            title=data.get("title", "untitled"),
            messages=list(data.get("messages", [])),
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


def new_session(title: str = "untitled") -> Session:
    sid = str(uuid.uuid4())
    now = _utc_now()
    return Session(id=sid, created=now, updated=now, title=title, messages=[])


def load_session(session_id: str) -> Session | None:
    path = session_path(session_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Session.from_json(data)


def save_session(sess: Session) -> None:
    sess.touch()
    path = session_path(sess.id)
    path.write_text(json.dumps(sess.to_json(), indent=2), encoding="utf-8")


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


def list_sessions() -> list[Session]:
    out: list[Session] = []
    for p in sorted(sessions_dir().glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            s = Session.from_json(json.loads(p.read_text(encoding="utf-8")))
            out.append(s)
        except (json.JSONDecodeError, OSError, KeyError):
            continue
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
