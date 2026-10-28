"""Password hashing and signed session tokens (standard library only).

Passwords: scrypt with a random salt, compared in constant time.
Tokens: ``<user_id>.<expires_unix>.<hmac-sha256>`` signed with ``SESSION_SECRET``.
The token carries no personal data; the user is looked up on every request.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}

_secret: bytes | None = None


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    candidate = hashlib.scrypt(password.encode(), salt=_unb64(salt), **_SCRYPT)
    return hmac.compare_digest(candidate, _unb64(digest))


def _signing_key() -> bytes:
    global _secret
    if settings.session_secret:
        return settings.session_secret.encode()
    if _secret is None:
        logger.warning(
            "SESSION_SECRET is not set; using a random one. Restarting logs everyone out."
        )
        _secret = secrets.token_bytes(32)
    return _secret


def _sign(payload: str) -> str:
    return _b64(hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest())


def issue_token(user_id: int, now: float | None = None) -> str:
    expires = int((now or time.time()) + settings.session_hours * 3600)
    payload = f"{user_id}.{expires}"
    return f"{payload}.{_sign(payload)}"


def read_token(token: str, now: float | None = None) -> int | None:
    """The user id of a valid, unexpired token; ``None`` otherwise."""
    try:
        user_id, expires, signature = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(f"{user_id}.{expires}")):
        return None
    if not (user_id.isdigit() and expires.isdigit()):
        return None
    if int(expires) < (now or time.time()):
        return None
    return int(user_id)
