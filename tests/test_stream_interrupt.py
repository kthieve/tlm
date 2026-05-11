import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from tlm.providers.openai_compat import OpenAICompatProvider


@pytest.fixture
def provider():
    return OpenAICompatProvider(
        id="test",
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        model="test-model",
    )


def test_stream_interrupt(provider):
    # Mock httpx.Client and the stream response
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    # Simulate a stream that raises KeyboardInterrupt mid-way
    def mock_iter_lines():
        yield b'data: {"choices": [{"delta": {"content": "hello"}}]}'
        raise KeyboardInterrupt()

    mock_response.iter_lines.side_effect = mock_iter_lines
    
    # Setup the mock context managers
    mock_client = MagicMock()
    # client.stream(...) returns a context manager whose __enter__ returns mock_response
    mock_client.stream.return_value.__enter__.return_value = mock_response
    
    # httpx.Client(...) returns a context manager whose __enter__ returns mock_client
    mock_client_factory = MagicMock()
    mock_client_factory.__enter__.return_value = mock_client
    
    with patch("httpx.Client", return_value=mock_client_factory):
        chunks = list(provider.stream("hello"))
        assert chunks == ["hello"]


def test_stream_timeout(provider):
    mock_client = MagicMock()
    mock_client.stream.side_effect = httpx.ReadTimeout("timeout")
    
    mock_client_factory = MagicMock()
    mock_client_factory.__enter__.return_value = mock_client

    with patch("httpx.Client", return_value=mock_client_factory):
        with pytest.raises(httpx.ReadTimeout):
            list(provider.stream("hello"))
