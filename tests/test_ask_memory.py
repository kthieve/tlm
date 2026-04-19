"""Ask flow: ready memory in system prompt and tlm-mem parsing."""

from __future__ import annotations

from tlm.ask_tools import _build_system_prompt, split_reply_tools
from tlm.memory import save_ready
from tlm.session import Session
from tlm.settings import UserSettings


def test_split_reply_tools_mem_block() -> None:
    text = 'Answer.\n```tlm-mem\n{"op": "search", "q": "foo"}\n```\n'
    v, argvs, mems = split_reply_tools(text)
    assert argvs == []
    assert len(mems) == 1
    assert mems[0].get("op") == "search"
    assert "Answer" in v
    assert "tlm-mem" not in v


def test_ready_memory_in_system_prompt(tmp_path, monkeypatch) -> None:
    d = tmp_path / "tlm"
    d.mkdir()

    def _data_dir():
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr("tlm.config.data_dir", _data_dir)
    monkeypatch.setattr("tlm.memory.data_dir", _data_dir)
    save_ready(["Prefers dark mode"], budget_chars=800)

    st = UserSettings(memory_enabled=True, memory_ready_budget_chars=800)
    from tlm.memory import load_ready

    items = load_ready()
    sys_p = _build_system_prompt(
        tools=False,
        memory_enabled=st.memory_enabled,
        clear_context=False,
        ready_items=items,
        ready_budget=st.memory_ready_budget_chars,
    )
    assert "Ready memory" in sys_p
    assert "dark mode" in sys_p

    sys_clear = _build_system_prompt(
        tools=False,
        memory_enabled=True,
        clear_context=True,
        ready_items=items,
        ready_budget=800,
    )
    assert "Ready memory" not in sys_clear


def test_estimate_ask_session_with_keyword() -> None:
    s = Session(
        id="x",
        created="t",
        updated="t",
        title="t",
        keyword="kw",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert s.keyword == "kw"
