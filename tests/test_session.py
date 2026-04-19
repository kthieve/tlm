from tlm.session import (
    Session,
    append_user,
    estimate_messages_tokens,
    new_session,
    trim_session_to_budget,
)


def test_trim_session_drops_from_front() -> None:
    s = new_session()
    for i in range(20):
        append_user(s, "x" * 200)
    trim_session_to_budget(s, max_tokens=50)
    assert len(s.messages) < 20


def test_estimate_tokens_positive() -> None:
    s = Session(
        id="1",
        created="t",
        updated="t",
        title="t",
        messages=[{"role": "user", "content": "hello"}],
    )
    assert estimate_messages_tokens(s.messages) >= 1
