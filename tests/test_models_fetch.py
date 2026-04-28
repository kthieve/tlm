"""Tests for OpenAI-compatible /v1/models listing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tlm.providers.openai_compat import fetch_remote_model_ids
from tlm.providers.registry import list_remote_model_ids
from tlm.settings import UserSettings


def test_fetch_remote_model_ids_parses_and_sorts() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"id": "b"}, {"id": "a"}]}
    mock_resp.raise_for_status = MagicMock()
    with patch("httpx.Client") as m:
        inst = m.return_value.__enter__.return_value
        inst.get.return_value = mock_resp
        out = fetch_remote_model_ids(
            provider_id="deepseek", base_url="https://api.example/v1", api_key="k", timeout=5.0
        )
    assert out == ["a", "b"]
    inst.get.assert_called_once()
    u = inst.get.call_args[0][0]
    assert u.endswith("/models")


def test_list_remote_model_ids_requires_key() -> None:
    s = UserSettings()
    s.api_keys = {}
    with pytest.raises(ValueError, match="No API key"):
        list_remote_model_ids("deepseek", settings=s)
