"""Session keyword, resolve, migration."""

from __future__ import annotations

import json

import pytest

from tlm.session import (
    find_by_keyword,
    list_sessions,
    load_session,
    new_session,
    normalize_keyword,
    resolve_session,
    save_session,
    session_path,
)


def test_normalize_keyword_ok() -> None:
    assert normalize_keyword("Work") == "work"
    assert normalize_keyword("foo-bar") == "foo-bar"


def test_normalize_keyword_rejects_space() -> None:
    with pytest.raises(ValueError):
        normalize_keyword("a b")


@pytest.fixture
def iso_data(tmp_path, monkeypatch):
    d = tmp_path / "tlm"
    d.mkdir()
    (d / "sessions").mkdir()

    def _data_dir():
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _sessions_dir():
        sd = d / "sessions"
        sd.mkdir(parents=True, exist_ok=True)
        return sd

    monkeypatch.setattr("tlm.config.data_dir", _data_dir)
    monkeypatch.setattr("tlm.config.sessions_dir", _sessions_dir)
    monkeypatch.setattr("tlm.session.sessions_dir", _sessions_dir)
    monkeypatch.setattr("tlm.session.data_dir", _data_dir)
    return d


def test_resolve_session_by_keyword(iso_data, tmp_path) -> None:
    s = new_session(keyword="alpha")
    save_session(s)
    hit = resolve_session("alpha")
    assert hit is not None
    assert hit.id == s.id
    assert find_by_keyword("alpha") is not None


def test_migration_missing_keyword(iso_data, tmp_path) -> None:
    raw = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "created": "t",
        "updated": "t",
        "title": "My Topic Here",
        "messages": [],
    }
    p = session_path(raw["id"])
    p.write_text(json.dumps(raw), encoding="utf-8")
    s = load_session(raw["id"])
    assert s is not None
    assert s.keyword
    assert normalize_keyword(s.keyword) == s.keyword


def test_list_sessions_lists_newest(iso_data) -> None:
    save_session(new_session(keyword="one"))
    save_session(new_session(keyword="two"))
    assert len(list_sessions()) == 2
