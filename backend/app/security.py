"""Password hashing and signed access tokens.

Standard library and already-locked packages only, so the dependency lock does
not change:

* passwords - PBKDF2-HMAC-SHA256 (``hashlib``), stored as
  ``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``;
* tokens    - ``itsdangerous`` timed signatures carrying the user id and role.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
_TOKEN_SALT = "access-token"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return a salted PBKDF2 hash of ``password`` in the storage format."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Check ``password`` against a stored hash in constant time."""
    try:
        scheme, iterations, salt_b64, digest_b64 = stored_hash.split("$")
    except ValueError:
        return False
    if scheme != PASSWORD_SCHEME:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        base64.b64decode(salt_b64),
        int(iterations),
    )
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt=_TOKEN_SALT)


def create_access_token(user_id: int, role: str) -> str:
    """Return a signed token identifying the user."""
    return _serializer().dumps({"sub": user_id, "role": role})


def read_access_token(token: str) -> dict[str, Any] | None:
    """Return the token payload, or ``None`` if it is forged or expired."""
    try:
        payload = _serializer().loads(token, max_age=get_settings().access_token_ttl_seconds)
    except (BadSignature, SignatureExpired):
        return None
    return payload if isinstance(payload, dict) and "sub" in payload else None
