"""Jail escape consent."""

from __future__ import annotations

import io

from pytest import MonkeyPatch

from tlm.safety.consent import prompt_escape
from tlm.safety.profiles import SafetyProfile


def test_escape_refuse_non_tty(monkeypatch: MonkeyPatch) -> None:
    import tlm.safety.consent as c

    monkeypatch.setattr(c.sys, "stdin", io.StringIO())
    monkeypatch.setattr(c.sys.stdin, "isatty", lambda: False)
    r = prompt_escape([("R", "/nope")], profile=SafetyProfile.standard, auto_yes=False)
    assert r == "refuse"


def test_escape_refuse_auto_yes(monkeypatch: MonkeyPatch) -> None:
    import tlm.safety.consent as c

    monkeypatch.setattr(c.sys.stdin, "isatty", lambda: True)
    r = prompt_escape([("R", "/nope")], profile=SafetyProfile.standard, auto_yes=True)
    assert r == "refuse"
