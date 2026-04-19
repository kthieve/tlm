"""Memory stores and safety rules."""

from __future__ import annotations

import pytest

from tlm.memory import (
    add_longterm,
    is_safe_to_store,
    prune_ready_to_budget,
    save_ready,
    search_longterm,
)


@pytest.fixture
def iso_mem(tmp_path, monkeypatch):
    d = tmp_path / "tlm"
    d.mkdir()

    def _data_dir():
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr("tlm.config.data_dir", _data_dir)
    return d


def test_is_safe_rejects_secrets() -> None:
    assert is_safe_to_store("MY_API_KEY=sk-123456789012345678901234567890")[0] is False
    tok = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    assert is_safe_to_store(f"token {tok}")[0] is False
    assert is_safe_to_store("-----BEGIN RSA PRIVATE KEY-----")[0] is False


def test_is_safe_allows_benign() -> None:
    ok, _ = is_safe_to_store("User prefers Ubuntu 24.04 and bash.")
    assert ok


def test_prune_ready_budget() -> None:
    items = ["a" * 50, "b" * 50, "c" * 50]
    out = prune_ready_to_budget(items, budget_chars=80)
    assert sum(len(x) for x in out) + max(0, len(out) - 1) <= 80


def test_search_longterm_ranking(iso_mem) -> None:
    add_longterm("Uses Ubuntu 24.04 on desktop", tags=["os"], source_session=None)
    add_longterm("Favorite editor is vim", tags=["editor"], source_session=None)
    hits = search_longterm("ubuntu desktop", k=2)
    assert hits and "ubuntu" in hits[0].text.lower()


def test_save_ready_roundtrip(iso_mem) -> None:
    save_ready(["line a", "line b"], budget_chars=500)
    from tlm.memory import load_ready

    assert load_ready() == ["line a", "line b"]
