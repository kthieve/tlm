"""Session persistence (messages + metadata); JSON on disk for v1."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tlm.config import sessions_dir


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
