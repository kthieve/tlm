"""Unit tests for GitHub slug / version helpers (no network)."""

from __future__ import annotations

from tlm.self_update import (
    format_config_header_status,
    format_version_update_status,
    parse_slug_from_github_url,
    resolve_update_ref,
    slug_from_direct_url,
    version_a_gt_b,
)
from tlm.settings import UserSettings


def test_parse_slug_from_github_url() -> None:
    assert parse_slug_from_github_url("https://github.com/foo/bar.git") == "foo/bar"
    assert parse_slug_from_github_url("git+https://github.com/org/repo.git@v0.1") == "org/repo"
    assert parse_slug_from_github_url("http://github.com/a/b") == "a/b"


def test_slug_from_direct_url() -> None:
    assert slug_from_direct_url({"url": "https://github.com/kthieve/tlm.git"}) == "kthieve/tlm"
    assert slug_from_direct_url({}) is None


def test_version_a_gt_b() -> None:
    assert version_a_gt_b("v0.2.0", "0.1.9")
    assert version_a_gt_b("0.2.0b3", "0.2.0b2")
    assert version_a_gt_b("0.2.0b4", "0.2.0b3")
    assert version_a_gt_b("0.2.0b1", "0.2.0.dev99")  # beta train > dev train (PEP 440)
    assert version_a_gt_b("0.2.0.dev1", "0.2.0.dev0")
    assert version_a_gt_b("0.2.0.dev2", "0.2.0.dev1")
    assert version_a_gt_b("0.2.0.dev3", "0.2.0.dev2")
    assert version_a_gt_b("0.2.0.dev4", "0.2.0.dev3")
    assert version_a_gt_b("0.2.0.dev5", "0.2.0.dev4")
    assert not version_a_gt_b("0.2.0b2", "0.2.0b2")
    assert not version_a_gt_b("0.1.0", "0.2.0")


def test_resolve_update_ref_version_arg() -> None:
    ref, err = resolve_update_ref("o/r", ref=None, version="0.2.0b2")
    assert err is None
    assert ref == "v0.2.0b2"
    ref2, err2 = resolve_update_ref("o/r", ref=None, version="v1.0.0")
    assert err2 is None
    assert ref2 == "v1.0.0"


def test_resolve_update_ref_explicit() -> None:
    ref, err = resolve_update_ref("o/r", ref="main", version=None)
    assert err is None
    assert ref == "main"


def test_format_config_header_status() -> None:
    s = UserSettings(check_for_updates=True, github_repo="foo/bar")
    h = format_config_header_status(s)
    assert "foo/bar" in h
    assert "notify on" in h


def test_format_version_update_status_offline() -> None:
    s = UserSettings(github_repo="x/y")
    text = format_version_update_status(s, query_github=False)
    assert "tlm version:" in text
    assert "Install:" in text
    assert "x/y" in text
    assert "Refresh" in text or "query GitHub" in text


def test_format_version_update_status_newer_on_github(monkeypatch) -> None:
    s = UserSettings(github_repo="a/b")
    monkeypatch.setattr("tlm.self_update.fetch_latest_release_tag", lambda _slug, timeout=3.0: "v99.0.0")
    monkeypatch.setattr("tlm.self_update.__version__", "0.0.1")
    text = format_version_update_status(s, query_github=True)
    assert "Update available" in text or "v99" in text
