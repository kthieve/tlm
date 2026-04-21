from __future__ import annotations

from tlm.ask_tools import _extract_ran_commands, _needs_machine_diagnostics
from tlm.session import Session


def test_needs_machine_diagnostics_true_for_hardware_queries() -> None:
    assert _needs_machine_diagnostics("what is my cpu and ram usage?")
    assert _needs_machine_diagnostics("show ubuntu kernel version")


def test_needs_machine_diagnostics_false_for_general_queries() -> None:
    assert not _needs_machine_diagnostics("summarize this article")
    assert not _needs_machine_diagnostics("what is the current price of 5070 ti in bangladesh")


def test_extract_ran_commands_from_user_feedback() -> None:
    sess = Session(
        id="s1",
        created="2026-01-01T00:00:00+00:00",
        updated="2026-01-01T00:00:00+00:00",
        title="test",
        keyword="test",
        messages=[
            {"role": "assistant", "content": "I'll run diagnostics"},
            {"role": "user", "content": "$ lscpu\nstdout:\n...\nexit_code: 0"},
            {"role": "user", "content": "User declined: uname -a"},
            {"role": "user", "content": "$ free -h\nstdout:\n...\nexit_code: 0"},
        ],
    )
    ran = _extract_ran_commands(sess)
    assert "lscpu" in ran
    assert "free -h" in ran
    assert "uname -a" not in ran
