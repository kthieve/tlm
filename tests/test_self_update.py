"""Unit tests for GitHub slug / version helpers (no network)."""

from __future__ import annotations

from tlm.self_update import (
    parse_slug_from_github_url,
    resolve_update_ref,
    slug_from_direct_url,
    version_a_gt_b,
)


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
