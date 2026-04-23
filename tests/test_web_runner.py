"""Parallel web fetch runner (Lightpanda batch) and helpers."""

from __future__ import annotations

import time

from tlm.ask_tools import (
    WebConsent,
    _clamp_web_conc,
    _run_web_ops_interactive,
)
from tlm.settings import UserSettings
from tlm.web.runner import (
    FetchJob,
    FetchResult,
    format_web_feedback,
    run_web_batch,
    summarize_fetch_text,
)


def test_summarize_fetch_markdown() -> None:
    body = "# Page Title\n\nSome intro line.\n"
    t, s, n = summarize_fetch_text(body, dump="markdown")
    assert "Page Title" in t or t == "Page Title"
    assert n == len(body)
    assert s


def test_summarize_fetch_html() -> None:
    body = "<html><head><title>  Hi &amp; Co  </title></head><body><p>Para one.</p></body></html>"
    t, s, n = summarize_fetch_text(body, dump="html")
    assert "Hi" in t
    assert n == len(body)


def test_clamp_web_conc() -> None:
    assert _clamp_web_conc(UserSettings(web_concurrency=99)) == 8
    assert _clamp_web_conc(UserSettings(web_concurrency=0)) == 1
    assert _clamp_web_conc(UserSettings(web_concurrency=3)) == 3


def test_user_settings_web_concurrency_defaults() -> None:
    s = UserSettings()
    assert s.web_concurrency == 3
    assert s.web_auto_approve_run is False
    assert s.web_search_obey_robots is False
    assert s.web_obey_robots is True


def test_load_settings_clamps_web_concurrency(monkeypatch, tmp_path) -> None:
    from tlm import settings as st_mod

    p = tmp_path / "config.toml"
    p.write_text("web_concurrency = 200\nweb_auto_approve_run = true\n", encoding="utf-8")
    monkeypatch.setattr(st_mod, "config_file_path", lambda: p)
    s = st_mod.load_settings()
    assert s.web_concurrency == 8
    assert s.web_auto_approve_run is True


def test_format_web_feedback_includes_index() -> None:
    j = FetchJob("k1", "l", "https://a.test", ["/x"], "p", "fetch")
    r1 = FetchResult(j, "done", body="x" * 100, char_count=100, title="T")
    out = format_web_feedback([r1], max_chars=200)
    assert "WEB RESULTS INDEX" in out
    assert "https://a.test" in out


def test_run_web_batch_results_in_plan_order() -> None:
    """As_completed is unordered; we assign by index; output order must match `jobs` order."""
    jobs = [
        FetchJob(
            "1",
            "a",
            "https://a",
            ["/lp", "fetch", "--dump", "markdown", "--log-level", "error", "https://a"],
            "p0",
            "fetch",
        ),
        FetchJob(
            "2",
            "b",
            "https://b",
            ["/lp", "fetch", "--dump", "markdown", "--log-level", "error", "https://b"],
            "p0",
            "fetch",
        ),
    ]

    def run_argv(argv: list[str]) -> tuple[int, str]:
        u = argv[-1]
        if "a" in u:
            time.sleep(0.08)  # finish after b
            return 0, "stdout:\nAAA\n\nexit_code: 0\n"
        return 0, "stdout:\nBBB\n\nexit_code: 0\n"

    res = run_web_batch(
        jobs,
        run_argv=run_argv,
        timeout=5.0,
        env={},
        concurrency=2,
        dump="markdown",
        max_output_chars=10_000,
        pcon=None,
        use_rich=False,
    )
    assert [r.job.key for r in res] == ["1", "2"]
    assert "AAA" in res[0].body
    assert "BBB" in res[1].body


def test_trust_run_skips_input(monkeypatch) -> None:
    called: list[object] = []

    def boom(_: str = "") -> str:  # noqa: ARG001
        called.append(True)
        return "1"

    monkeypatch.setattr("builtins.input", boom)
    monkeypatch.setattr(
        "tlm.ask_tools._run_argv",
        lambda *a, **k: (0, "stdout:\nok\n\nexit_code: 0\n"),
    )
    s = UserSettings(web_enabled=True, web_concurrency=1)
    wc = WebConsent(trust_run=True)
    _run_web_ops_interactive(
        [{"op": "fetch", "url": "https://ex.test/"}],
        settings=s,
        bin_path="/bin/lp",
        timeout=2.0,
        pcon=None,
        RichPanel=None,
        RichConfirm=None,
        use_rich=False,
        web_consent=wc,
    )
    assert not called
