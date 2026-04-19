"""Harvest JSON parsing."""

from tlm.harvest import _extract_json_array


def test_extract_json_array_plain() -> None:
    assert _extract_json_array('["a", "b"]') == ["a", "b"]


def test_extract_json_array_fenced() -> None:
    s = "```json\n[\"x\"]\n```"
    assert _extract_json_array(s) == ["x"]
