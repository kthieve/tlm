"""Authentication session persistence (timeouts)."""

from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional


def _get_token_file() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home:
        base = Path(state_home)
    else:
        base = Path.home() / ".local" / "state"
    
    d = base / "tlm"
    d.mkdir(parents=True, exist_ok=True)
    return d / "auth_token.json"


def create_auth_token(ttl_minutes: int = 30) -> str:
    """Create a new session token valid for N minutes."""
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + (ttl_minutes * 60)
    
    f = _get_token_file()
    data = {
        "token": token,
        "expires_at": expires_at
    }
    
    f.write_text(json.dumps(data), encoding="utf-8")
    f.chmod(0o600)
    return token


def validate_auth_token() -> bool:
    """Check if the current session token is valid and not expired."""
    f = _get_token_file()
    if not f.exists():
        return False
        
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        expires_at = data.get("expires_at", 0)
        if time.time() < expires_at:
            return True
        else:
            f.unlink()  # Expired
            return False
    except (json.JSONDecodeError, KeyError, OSError):
        if f.exists():
            f.unlink()
        return False


def revoke_auth_token() -> None:
    """Revoke (delete) the session token."""
    f = _get_token_file()
    if f.exists():
        f.unlink()


def get_token_expiry() -> Optional[float]:
    """Return the expiry timestamp if a valid token exists."""
    f = _get_token_file()
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return float(data.get("expires_at", 0))
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return None
