"""Password and recovery key management for Tier 0/1 access."""

from __future__ import annotations

import hashlib
import secrets
import base64
from typing import Optional


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Hash password using PBKDF2-SHA256. Returns 'salt:hash'."""
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{base64.b64encode(salt).decode()}:{base64.b64encode(dk).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored 'salt:hash' string."""
    try:
        salt_b64, hash_b64 = stored_hash.split(":", 1)
        salt = base64.b64decode(salt_b64)
        # re-hash and compare
        new_hash = hash_password(password, salt=salt)
        return secrets.compare_digest(new_hash, stored_hash)
    except (ValueError, TypeError):
        return False


def generate_recovery_key() -> str:
    """Generate a high-entropy 24-character recovery key."""
    return secrets.token_urlsafe(18)  # ~144 bits of entropy


def hash_recovery_key(key: str) -> str:
    """Simply SHA-256 the recovery key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_recovery_key(key: str, stored_sha256: str) -> bool:
    """Verify recovery key against stored SHA-256 hash."""
    return secrets.compare_digest(hashlib.sha256(key.encode()).hexdigest(), stored_sha256)
