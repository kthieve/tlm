"""Request log scrubbing."""

from __future__ import annotations

from tlm.telemetry.log import scrub_record, scrub_text_line


def test_scrub_record_nested_key() -> None:
    r = scrub_record({"a": 1, "api_key": "secret", "nested": {"token": "x"}})
    assert r["api_key"] == "[redacted]"
    assert r["nested"]["token"] == "[redacted]"


def test_scrub_text_line_json() -> None:
    line = '{"api_key":"sk-test12345678901234567890"}'
    out = scrub_text_line(line)
    assert "sk-test" not in out
    assert "redacted" in out.lower() or "[redacted]" in out
