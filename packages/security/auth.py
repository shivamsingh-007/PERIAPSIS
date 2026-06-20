from __future__ import annotations

import hashlib
import hmac
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
        now = time.time()
        payload = TokenPayload(
            sub=subject,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions or [],
            exp=now + expires_in,
            iat=now,
        )

        token = self._encode_token(payload)

        if self.auth_repo:
            try:
                await self.auth_repo.create_token(
                    token_id=payload.jti,
                    tenant_id=tenant_id,
                    user_id=subject,
                    token_data=token,
                    expires_at=datetime.fromtimestamp(payload.exp, tz=timezone.utc),
                )
            except Exception as e:
                logger.warning(f"Failed to persist token to DB: {e}")

        self._tokens[payload.jti] = payload

        refresh_token = secrets.token_urlsafe(64)
        self._refresh_tokens[refresh_token] = payload.jti

        return AuthToken(
            access_token=token,
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
        now = time.time()
        payload = TokenPayload(
            sub=subject,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions or [],
            exp=now + expires_in,
            iat=now,
        )

        token = self._encode_token(payload)
        self._tokens[payload.jti] = payload

        refresh_token = secrets.token_urlsafe(64)
        self._refresh_tokens[refresh_token] = payload.jti

        return AuthToken(
            access_token=token,
            expires_in=expires_in,
            refresh_token=refresh_token,
        )

    async def verify_token_async(self, token: str) -> TokenPayload | None:
        """Verify token with optional DB lookup for revocation."""
        try:
            payload = self._decode_token(token)

            if self.auth_repo:
                try:
                    record = await self.auth_repo.get_token(payload.jti)
                    if record and record.is_revoked:
                        return None
                except Exception:
                    pass

            if payload.jti in self._revoked_tokens:
                return None
            if payload.exp < time.time():
                return None
            return payload
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            return None

    def verify_token(self, token: str) -> TokenPayload | None:
        """Sync token verification (in-memory only)."""
        try:
            payload = self._decode_token(token)
            if payload.jti in self._revoked_tokens:
                return None
            if payload.exp < time.time():
                return None
            return payload
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

    def _encode_token(self, payload: TokenPayload) -> str:
        import json
        import base64

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        ).decode().rstrip("=")

        body = base64.urlsafe_b64encode(
            payload.model_dump_json().encode()
        ).decode().rstrip("=")

        signature = hmac.new(
            self.secret_key.encode(),
            f"{header}.{body}".encode(),
            hashlib.sha256,
        ).hexdigest()

        return f"{header}.{body}.{signature}"

    def _decode_token(self, token: str) -> TokenPayload:
        import json
        import base64

        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header, body, signature = parts

        expected_sig = hmac.new(
            self.secret_key.encode(),
            f"{header}.{body}".encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            raise ValueError("Invalid signature")

        padded_body = body + "=" * (4 - len(body) % 4)
        payload_data = json.loads(base64.urlsafe_b64decode(padded_body))

        return TokenPayload(**payload_data)


auth_manager = AuthManager()
