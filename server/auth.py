"""Password hashing and signed session tokens (stdlib only, no external deps)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

PBKDF2_ITERATIONS = 200_000
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 days


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def hash_password(password: str) -> str:
    """Return `pbkdf2$<iterations>$<salt_b64>$<hash_b64>` for storage in env/config."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2${PBKDF2_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification of `password` against a `hash_password` string."""
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), _unb64(salt_b64), int(iterations)
        )
        return hmac.compare_digest(expected, _unb64(hash_b64))
    except (ValueError, TypeError):
        return False


def create_session_token(username: str, secret: str) -> str:
    """Return `<payload_b64>.<hmac_hex>`; the token expires after SESSION_TTL_SECONDS."""
    payload = json.dumps(
        {"u": username, "exp": int(time.time()) + SESSION_TTL_SECONDS},
        separators=(",", ":"),
    )
    raw = _b64(payload.encode())
    signature = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{signature}"


def verify_session_token(token: str, secret: str) -> str | None:
    """Return the username if the token is valid and not expired, else None."""
    try:
        raw, signature = token.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        data = json.loads(_unb64(raw))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("exp", 0) < time.time():
        return None
    username = data.get("u")
    return username if isinstance(username, str) else None
