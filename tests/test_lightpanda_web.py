"""Lightpanda URL helpers, Brave API formatting, and ```tlm-web``` parsing."""

from __future__ import annotations

import json
from unittest.mock import patch

from tlm.ask_tools import WebConsent, _run_web_ops_interactive, split_reply_tools
from tlm.settings import UserSettings
from tlm.web.brave_search_api import brave_web_search, format_brave_web_results
from tlm.web.lightpanda import (
    build_fetch_argv,
    detect_fetch_capabilities,
    normalize_search_provider,
    search_url_for_query,
    validate_url,
)


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
    u = search_url_for_query("a b & c", provider="duckduckgo")
    assert "a+b" in u or "%20" in u
    assert "lite.duckduckgo.com" in u


def test_search_url_brave_provider() -> None:
    u = search_url_for_query("a b", provider="brave")
    assert "search.brave.com" in u
    assert "q=a+b" in u or "q=a%20b" in u


def test_normalize_search_provider_aliases() -> None:
    assert normalize_search_provider("ddg") == "duckduckgo"
    assert normalize_search_provider("duck") == "duckduckgo"
    assert normalize_search_provider("brave-search") == "brave"
    assert normalize_search_provider("unknown") == "duckduckgo"


def test_user_settings_default_search_provider() -> None:
    s = UserSettings()
    assert s.web_search_provider == "duckduckgo"


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


def test_build_fetch_argv_user_agent_passthrough() -> None:
    argv = build_fetch_argv(
        "lp",
        "https://ex.test",
        dump="markdown",
        obey_robots=False,
        user_agent="Mozilla/5.0 UnitTest",
        supports_user_agent=True,
    )
    i = argv.index("--user-agent")
    assert argv[i + 1] == "Mozilla/5.0 UnitTest"


def test_build_fetch_argv_user_agent_suffix_passthrough() -> None:
    argv = build_fetch_argv(
        "lp",
        "https://ex.test",
        dump="markdown",
        obey_robots=False,
        user_agent_suffix="tlm-test",
        supports_user_agent_suffix=True,
    )
    i = argv.index("--user-agent-suffix")
    assert argv[i + 1] == "tlm-test"


def test_detect_fetch_capabilities_parse_help(monkeypatch) -> None:
    class _Proc:
        stdout = "--user-agent\n--user-agent-suffix\n"
        stderr = ""

    detect_fetch_capabilities.cache_clear()
    monkeypatch.setattr("tlm.web.lightpanda.subprocess.run", lambda *a, **k: _Proc())
    caps = detect_fetch_capabilities("/bin/lightpanda")
    assert caps["user_agent"]
    assert caps["user_agent_suffix"]


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


def test_split_reply_tools_web_json_array() -> None:
    text = (
        "```tlm-web\n"
        '[\n  {"op": "fetch", "url": "https://a.example"},\n'
        '  {"op": "search", "q": "q1"}\n]\n'
        "```\n"
    )
    v, _, _, webs = split_reply_tools(text)
    assert len(webs) == 2
    assert webs[0].get("op") == "fetch"
    assert webs[1].get("op") == "search"
    assert "tlm-web" not in v


def test_web_ops_batch_approve_batch_then_reuse_no_second_prompt(monkeypatch) -> None:
    """Choice [1] approves the batch; same WebConsent has keys, so the second run asks nothing."""
    inputs: list[str] = []

    def fake_input(prompt: str = "") -> str:  # noqa: ARG001
        inputs.append(prompt)
        return "1"  # Approve this batch only

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(
        "tlm.ask_tools._run_argv",
        lambda *a, **k: (0, "stdout:\nok\n\nexit_code: 0\n"),
    )

    s = UserSettings(web_enabled=True, web_search_provider="duckduckgo", web_concurrency=2)
    wc = WebConsent()
    ops = [
        {"op": "fetch", "url": "https://example.com/a"},
        {"op": "fetch", "url": "https://example.com/b"},
    ]
    r1 = _run_web_ops_interactive(
        ops,
        settings=s,
        bin_path="/bin/lightpanda",
        timeout=5.0,
        pcon=None,
        RichPanel=None,
        RichConfirm=None,
        use_rich=False,
        web_consent=wc,
    )
    assert any("WEB RESULTS INDEX" in p for p in r1)
    n_prompts = len(inputs)

    r2 = _run_web_ops_interactive(
        ops,
        settings=s,
        bin_path="/bin/lightpanda",
        timeout=5.0,
        pcon=None,
        RichPanel=None,
        RichConfirm=None,
        use_rich=False,
        web_consent=wc,
    )
    assert any("WEB RESULTS INDEX" in p for p in r2)
    assert len(inputs) == n_prompts


def test_format_brave_web_results_basic() -> None:
    out = format_brave_web_results(
        {"web": {"results": [{"title": "T1", "url": "https://a.test", "description": "D1"}]}}
    )
    assert "T1" in out and "https://a.test" in out and "D1" in out


def test_format_brave_web_results_empty() -> None:
    assert "empty" in format_brave_web_results({"web": {"results": []}}).lower()


def test_brave_web_search_parses_json() -> None:
    payload = {"web": {"results": [{"title": "Hi", "url": "https://z", "description": ""}]}}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(payload).encode()

    with patch("tlm.web.brave_search_api.urlopen", return_value=_Resp()):
        code, body = brave_web_search("q", "secret-key", timeout=5.0)
    assert code == 0
    assert "Hi" in body and "https://z" in body
