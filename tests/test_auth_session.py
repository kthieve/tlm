import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tlm.safety.auth_session import (
    create_auth_token,
    get_token_expiry,
    revoke_auth_token,
    validate_auth_token,
)


@pytest.fixture
def temp_token_file(tmp_path, monkeypatch):
    f = tmp_path / "auth_token.json"
    monkeypatch.setattr("tlm.safety.auth_session._get_token_file", lambda: f)
    return f


def test_create_and_validate(temp_token_file):
    token = create_auth_token(ttl_minutes=10)
    assert token is not None
    assert temp_token_file.exists()
    
    assert validate_auth_token() is True
    assert get_token_expiry() > time.time()


def test_expiry(temp_token_file):
    create_auth_token(ttl_minutes=10)
    
    # Mock time to be 11 minutes in the future
    with patch("time.time", return_value=time.time() + 660):
        assert validate_auth_token() is False
        assert not temp_token_file.exists()


def test_revoke(temp_token_file):
    create_auth_token(ttl_minutes=10)
    revoke_auth_token()
    assert not temp_token_file.exists()
    assert validate_auth_token() is False
