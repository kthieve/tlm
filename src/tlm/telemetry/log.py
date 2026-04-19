"""Append-only JSONL request log + rotation."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any

from tlm.config import state_dir

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
    }
)
_REDACT = "[redacted]"
_SK_RE = re.compile(r"\bsk-[a-zA-Z0-9_-]{10,}\b")
_BEARER_RE = re.compile(r"(?i)bearer\s+[a-z0-9._-]{8,}")


def scrub_record(obj: Any) -> Any:
    """Redact secrets for JSONL logging."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in _SENSITIVE_KEYS or lk.endswith("_key") or lk.endswith("_token") or lk.endswith("_secret"):
                out[k] = _REDACT
            else:
                out[k] = scrub_record(v)
        return out
    if isinstance(obj, list):
        return [scrub_record(x) for x in obj]
    if isinstance(obj, str):
        s = _SK_RE.sub(_REDACT, obj)
        s = _BEARER_RE.sub("Bearer " + _REDACT, s)
        return s
    return obj


def scrub_text_line(line: str) -> str:
    """Redact secrets in arbitrary text (e.g. log tail)."""
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        return _SK_RE.sub(_REDACT, _BEARER_RE.sub("Bearer " + _REDACT, line))
    return json.dumps(scrub_record(row), ensure_ascii=False)

MAX_BYTES = 10_000_000
KEEP_ROTATIONS = 3


def requests_log_path() -> Path:
    p = state_dir() / "requests.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _rotate_if_needed(path: Path) -> None:
    if not path.is_file() or path.stat().st_size < MAX_BYTES:
        return
    for i in range(KEEP_ROTATIONS - 1, 0, -1):
        src = path.with_suffix(f".jsonl.{i}")
        dst = path.with_suffix(f".jsonl.{i + 1}")
        if src.is_file():
            shutil.move(str(src), str(dst))
    shutil.move(str(path), str(path.with_suffix(".jsonl.1")))


def log_event(record: dict[str, Any]) -> None:
    path = requests_log_path()
    _rotate_if_needed(path)
    line = json.dumps(scrub_record(record), ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def summarize_usage(*, since_days: int | None) -> str:
    path = requests_log_path()
    if not path.is_file():
        return "no usage data yet"
    cutoff: datetime | None = None
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    totals: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {"in": 0.0, "out": 0.0, "cost": 0.0, "n": 0.0}
    )
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = row.get("ts")
            if cutoff and ts:
                try:
                    t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    if t < cutoff:
                        continue
                except ValueError:
                    pass
            prov = str(row.get("provider", ""))
            model = str(row.get("model", ""))
            k = (prov, model)
            totals[k]["in"] += float(row.get("in_tokens") or 0)
            totals[k]["out"] += float(row.get("out_tokens") or 0)
            c = row.get("cost_usd")
            if c is not None:
                totals[k]["cost"] += float(c)
            totals[k]["n"] += 1
    lines = ["provider\tmodel\trequests\tin_tok\tout_tok\tcost_usd"]
    for (prov, model), v in sorted(totals.items()):
        lines.append(
            f"{prov}\t{model}\t{int(v['n'])}\t{int(v['in'])}\t{int(v['out'])}\t{v['cost']:.4f}"
        )
    return "\n".join(lines)
