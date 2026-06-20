from __future__ import annotations
"""Tests for packages.security.auth - AuthManager token lifecycle."""

import time
import uuid

import pytest

from packages.security.auth import (
    AuthManager,
    AuthToken,
    OIDCConfig,
    TokenPayload,
)


class TestTokenPayload:
    def test_defaults(self):
        payload = TokenPayload(sub="user1", tenant_id="t1", role="viewer", exp=1.0, iat=0.0)
        assert payload.sub == "user1"
        assert payload.role == "viewer"
        assert payload.jti  # UUID generated

    def test_unique_jti(self):
        p1 = TokenPayload(sub="u1", tenant_id="t1", role="viewer", exp=1.0, iat=0.0)
        p2 = TokenPayload(sub="u1", tenant_id="t1", role="viewer", exp=1.0, iat=0.0)
        assert p1.jti != p2.jti


class TestAuthToken:
    def test_defaults(self):
        token = AuthToken(access_token="abc")
        assert token.token_type == "bearer"
        assert token.expires_in == 3600
        assert token.refresh_token is None


class TestAuthManager:
    def setup_method(self):
        self.manager = AuthManager(secret_key="test-secret-key-for-testing-only!")

    def test_create_token(self):
        token = self.manager.create_token("user1", "tenant1")
        assert token.access_token
        assert token.refresh_token
        assert token.token_type == "bearer"
        assert token.expires_in == 3600

    def test_verify_token_valid(self):
        token = self.manager.create_token("user1", "tenant1")
        payload = self.manager.verify_token(token.access_token)
        assert payload is not None
        assert payload.sub == "user1"
        assert payload.tenant_id == "tenant1"

    def test_verify_token_invalid(self):
        payload = self.manager.verify_token("invalid.token.string")
        assert payload is None

    def test_verify_token_revoked(self):
        token = self.manager.create_token("user1", "tenant1")
        self.manager.revoke_token(token.access_token)
        payload = self.manager.verify_token(token.access_token)
        assert payload is None

    def test_revoke_token_returns_true(self):
        token = self.manager.create_token("user1", "tenant1")
        assert self.manager.revoke_token(token.access_token) is True

    def test_revoke_invalid_token_returns_false(self):
        assert self.manager.revoke_token("invalid") is False

    def test_refresh_token(self):
        token = self.manager.create_token("user1", "tenant1", role="admin")
        new_token = self.manager.refresh_access_token(token.refresh_token)
        assert new_token is not None
        assert new_token.access_token != token.access_token
        # Old token should be revoked
        old_payload = self.manager.verify_token(token.access_token)
        assert old_payload is None

    def test_refresh_invalid_token(self):
        result = self.manager.refresh_access_token("invalid-refresh")
        assert result is None

    def test_token_expiry(self):
        token = self.manager.create_token("user1", "tenant1", expires_in=-1)
        payload = self.manager.verify_token(token.access_token)
        assert payload is None

    def test_create_token_custom_permissions(self):
        token = self.manager.create_token(
            "user1", "tenant1", permissions=["run:read", "run:create"]
        )
        payload = self.manager.verify_token(token.access_token)
        assert "run:read" in payload.permissions
        assert "run:create" in payload.permissions

    def test_check_permission_admin(self):
        payload = TokenPayload(sub="u1", tenant_id="t1", role="admin", exp=99999999, iat=0)
        assert self.manager.check_permission(payload, "run:create") is True

    def test_check_permission_viewer(self):
        payload = TokenPayload(
            sub="u1", tenant_id="t1", role="viewer",
            permissions=["run:read"], exp=99999999, iat=0,
        )
        assert self.manager.check_permission(payload, "run:read") is True
        assert self.manager.check_permission(payload, "run:create") is False

    def test_check_permission_operator(self):
        payload = TokenPayload(
            sub="u1", tenant_id="t1", role="operator",
            permissions=["run:read", "run:create"], exp=99999999, iat=0,
        )
        assert self.manager.check_permission(payload, "run:create") is True

    def test_oidc_config(self):
        config = OIDCConfig(
            issuer="https://example.com",
            client_id="id1",
            client_secret="secret1",
        )
        self.manager.configure_oidc("github", config)
        loaded = self.manager.get_oidc_config("github")
        assert loaded is not None
        assert loaded.issuer == "https://example.com"

    def test_oidc_config_not_found(self):
        assert self.manager.get_oidc_config("nonexistent") is None

    def test_different_secret_keys_incompatible(self):
        m1 = AuthManager(secret_key="key1")
        m2 = AuthManager(secret_key="key2")
        token = m1.create_token("user1", "tenant1")
        payload = m2.verify_token(token.access_token)
        assert payload is None
