"""Lightpanda URL helpers and ```tlm-web``` parsing."""

from __future__ import annotations

from tlm.ask_tools import split_reply_tools
from tlm.web.lightpanda import build_fetch_argv, search_url_for_query, validate_url


def test_validate_url_https() -> None:
    ok, _ = validate_url("https://example.com/path?q=1", allow_http=False)
    assert ok


def test_validate_url_http_blocked_by_default() -> None:
    ok, reason = validate_url("http://example.com/", allow_http=False)
    assert not ok
    assert "http" in reason.lower()


def test_validate_url_http_when_allowed() -> None:
    ok, _ = validate_url("http://example.com/", allow_http=True)
    assert ok


def test_validate_url_rejects_file() -> None:
    ok, reason = validate_url("file:///etc/passwd", allow_http=False)
    assert not ok
    assert "scheme" in reason.lower() or "blocked" in reason.lower()


def test_validate_url_empty() -> None:
    ok, _ = validate_url("", allow_http=False)
    assert not ok


def test_search_url_encodes_query() -> None:
    u = search_url_for_query("a b & c")
    assert "a+b" in u or "%20" in u
    assert "lite.duckduckgo.com" in u


def test_build_fetch_argv_order() -> None:
    argv = build_fetch_argv(
        "/bin/lightpanda",
        "https://ex.test",
        dump="markdown",
        obey_robots=True,
    )
    assert argv[0] == "/bin/lightpanda"
    assert argv[1] == "fetch"
    assert "--obey-robots" in argv
    assert argv[-1] == "https://ex.test"
    i = argv.index("--dump")
    assert argv[i + 1] == "markdown"


def test_build_fetch_argv_no_robots() -> None:
    argv = build_fetch_argv(
        "lp",
        "https://ex.test",
        dump="html",
        obey_robots=False,
    )
    assert "--obey-robots" not in argv
    i = argv.index("--dump")
    assert argv[i + 1] == "html"
    assert argv[-1] == "https://ex.test"


def test_split_reply_tools_web() -> None:
    text = (
        'Hi.\n```tlm-web\n{"op": "fetch", "url": "https://a.example"}\n```\n'
        '```tlm-web\n{"op": "search", "q": "q & x"}\n```\n'
    )
    v, argvs, mems, webs = split_reply_tools(text)
    assert argvs == []
    assert mems == []
    assert len(webs) == 2
    assert webs[0].get("op") == "fetch"
    assert webs[1].get("op") == "search"
    assert "Hi." in v
    assert "tlm-web" not in v


def test_split_invalid_web_keeps_block() -> None:
    text = 'X\n```tlm-web\nnot json\n```'
    v, _, _, webs = split_reply_tools(text)
    assert webs == []
    assert "not json" in v
