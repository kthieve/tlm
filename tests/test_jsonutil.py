from tlm.jsonutil import extract_json_object


def test_extract_raw_json() -> None:
    d = extract_json_object('{"a": 1}')
    assert d["a"] == 1


def test_extract_fenced() -> None:
    d = extract_json_object("```json\n{\"b\": 2}\n```")
    assert d["b"] == 2
