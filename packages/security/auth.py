from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("auth")


class TokenPayload(BaseModel):
    sub: str
    tenant_id: str
    role: str
    permissions: list[str] = Field(default_factory=list)
    exp: float
    iat: float
    jti: str = Field(default_factory=lambda: str(uuid.uuid4()))


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    refresh_token: str | None = None


class OIDCConfig(BaseModel):
    issuer: str
    client_id: str
    client_secret: str
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    jwks_uri: str = ""


class AuthManager:
    def __init__(self, secret_key: str | None = None, auth_repo=None):
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.auth_repo = auth_repo
        # In-memory fallback (used when no repo provided)
        self._tokens: dict[str, TokenPayload] = {}
        self._refresh_tokens: dict[str, str] = {}
        self._revoked_tokens: set[str] = set()
        self._oidc_configs: dict[str, OIDCConfig] = {}

    async def create_token_async(
        self,
        subject: str,
        tenant_id: str,
        role: str = "viewer",
        permissions: list[str] | None = None,
        expires_in: int = 3600,
    ) -> AuthToken:
        """Create token with optional DB persistence."""
        jti = str(uuid.uuid4())
        token_str = self._encode_token_pjwt(subject, tenant_id, role, permissions or [], expires_in, jti=jti)
        now = time.time()

        if self.auth_repo:
            try:
                await self.auth_repo.create_token(
                    token_id=jti,
                    tenant_id=tenant_id,
                    user_id=subject,
                    token_data=token_str,
                    expires_at=datetime.fromtimestamp(now + expires_in, tz=timezone.utc),
                )
            except Exception as e:
                logger.warning(f"Failed to persist token to DB: {e}")

        self._tokens[jti] = TokenPayload(
            sub=subject,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions or [],
            exp=now + expires_in,
            iat=now,
            jti=jti,
        )

        refresh_token = secrets.token_urlsafe(64)
        self._refresh_tokens[refresh_token] = jti

        return AuthToken(
            access_token=token_str,
            expires_in=expires_in,
            refresh_token=refresh_token,
        )

    def create_token(
        self,
        subject: str,
        tenant_id: str,
        role: str = "viewer",
        permissions: list[str] | None = None,
        expires_in: int = 3600,
    ) -> AuthToken:
        """Sync token creation (in-memory only)."""
        jti = str(uuid.uuid4())
        token_str = self._encode_token_pjwt(subject, tenant_id, role, permissions or [], expires_in, jti=jti)
        now = time.time()

        self._tokens[jti] = TokenPayload(
            sub=subject,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions or [],
            exp=now + expires_in,
            iat=now,
            jti=jti,
        )

        refresh_token = secrets.token_urlsafe(64)
        self._refresh_tokens[refresh_token] = jti

        return AuthToken(
            access_token=token_str,
            expires_in=expires_in,
            refresh_token=refresh_token,
        )

    async def verify_token_async(self, token: str) -> TokenPayload | None:
        """Verify token with optional DB lookup for revocation."""
        try:
            payload_dict = self._decode_token_pjwt(token)
            jti = payload_dict.get("jti", "")

            if self.auth_repo:
                try:
                    record = await self.auth_repo.get_token(jti)
                    if record and record.is_revoked:
                        return None
                except Exception:
                    pass

            if jti in self._revoked_tokens:
                return None

            return TokenPayload(**payload_dict)
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            return None

    def verify_token(self, token: str) -> TokenPayload | None:
        """Sync token verification (in-memory only)."""
        try:
            payload_dict = self._decode_token_pjwt(token)
            jti = payload_dict.get("jti", "")
            if jti in self._revoked_tokens:
                return None
            return TokenPayload(**payload_dict)
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            return None

    async def revoke_token_async(self, token: str) -> bool:
        """Revoke token with optional DB persistence."""
        payload = self.verify_token(token)
        if payload:
            self._revoked_tokens.add(payload.jti)
            if self.auth_repo:
                try:
                    await self.auth_repo.revoke_token(payload.jti)
                except Exception as e:
                    logger.warning(f"Failed to revoke token in DB: {e}")
            return True
        return False

    def revoke_token(self, token: str) -> bool:
        """Sync token revocation (in-memory only)."""
        payload = self.verify_token(token)
        if payload:
            self._revoked_tokens.add(payload.jti)
            return True
        return False

    def refresh_access_token(self, refresh_token: str) -> AuthToken | None:
        jti = self._refresh_tokens.get(refresh_token)
        if not jti:
            return None

        old_payload = self._tokens.get(jti)
        if not old_payload:
            return None

        self._revoked_tokens.add(jti)
        del self._refresh_tokens[refresh_token]

        return self.create_token(
            subject=old_payload.sub,
            tenant_id=old_payload.tenant_id,
            role=old_payload.role,
            permissions=old_payload.permissions,
        )

    def configure_oidc(self, provider: str, config: OIDCConfig) -> None:
        self._oidc_configs[provider] = config
        logger.info(f"Configured OIDC provider: {provider}")

    def get_oidc_config(self, provider: str) -> OIDCConfig | None:
        return self._oidc_configs.get(provider)

    def check_permission(self, payload: TokenPayload, permission: str) -> bool:
        if payload.role == "admin":
            return True
        return permission in payload.permissions

    def _encode_token_pjwt(
        self,
        subject: str,
        tenant_id: str,
        role: str,
        permissions: list[str],
        expires_in: int,
        jti: str | None = None,
    ) -> str:
        """Encode token using PyJWT (standard)."""
        from packages.security.jwt_utils import create_access_token
        return create_access_token(
            subject=subject,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions,
            expires_delta=timedelta(seconds=expires_in),
            jti=jti,
            secret_key=self.secret_key,
        )

    def _decode_token_pjwt(self, token: str) -> dict[str, Any]:
        """Decode token using PyJWT (standard)."""
        from packages.security.jwt_utils import decode_access_token
        return decode_access_token(token, secret_key=self.secret_key)


def _extract_jti(token_str: str) -> str:
    """Extract jti from an encoded JWT without verifying (for in-memory lookup).

    PyJWT produces 3-part tokens: header.payload.signature
    """
    import base64
    import json

    try:
        parts = token_str.split(".")
        if len(parts) < 2:
            return ""
        # For 3-part JWTs (PyJWT), payload is at index 1
        payload_b64 = parts[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload_data = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload_data.get("jti", "")
    except Exception:
        return ""


auth_manager = AuthManager()
