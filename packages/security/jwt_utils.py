"""JWT utilities using PyJWT (standard library) instead of custom HMAC."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from packages.logging.structured import get_logger

logger = get_logger("jwt_utils")

JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
JWT_EXPIRATION_MINUTES = int(os.environ.get("JWT_EXPIRATION_MINUTES", "60"))


def create_access_token(
    subject: str,
    tenant_id: str,
    role: str = "viewer",
    permissions: list[str] | None = None,
    expires_delta: timedelta | None = None,
    jti: str | None = None,
    secret_key: str | None = None,
) -> str:
    """Create a signed JWT access token."""
    key = secret_key or JWT_SECRET_KEY
    if not key or key == "change-me-in-production":
        logger.warning("Using default SECRET_KEY — change in production!")

    if expires_delta is None:
        expires_delta = timedelta(minutes=JWT_EXPIRATION_MINUTES)

    now = datetime.now(timezone.utc)
    to_encode: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "permissions": permissions or [],
        "iat": now,
        "exp": now + expires_delta,
    }
    if jti:
        to_encode["jti"] = jti
    return jwt.encode(to_encode, key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret_key: str | None = None) -> dict[str, Any]:
    """Decode and verify a JWT access token.

    Raises jwt.ExpiredSignatureError if token is expired.
    Raises jwt.InvalidTokenError if token is invalid.
    """
    key = secret_key or JWT_SECRET_KEY
    return jwt.decode(token, key, algorithms=[JWT_ALGORITHM])
