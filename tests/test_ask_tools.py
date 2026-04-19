from tlm.ask_tools import split_reply_and_execs


def test_split_extracts_argv() -> None:
    text = 'Here.\n```tlm-exec\n["uname", "-a"]\n```\nDone.'
    visible, argvs = split_reply_and_execs(text)
    assert argvs == [["uname", "-a"]]
    assert "Here" in visible and "Done" in visible
    assert "tlm-exec" not in visible


def test_split_invalid_json_keeps_block() -> None:
    text = 'X\n```tlm-exec\nnot json\n```'
    visible, argvs = split_reply_and_execs(text)
    assert argvs == []
    assert "not json" in visible
