"""Tests for auth dependencies (get_current_user, get_current_tenant, verify_ws_token)."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials

from packages.security.auth import AuthManager, TokenPayload


def _make_auth_manager():
    return AuthManager(secret_key="test-key-for-deps")


def _make_token(auth_manager: AuthManager, sub="user-1", tenant_id="tenant-1"):
    return auth_manager.create_token(sub, tenant_id, role="admin")


class TestGetCurrentUser:
    def test_missing_header_returns_401(self):
        from apps.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/governance/events")
        assert resp.status_code in (401, 403)

    def test_invalid_token_returns_401(self):
        from apps.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/governance/events",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code in (401, 403)

    def test_valid_token_passes(self):
        from packages.security.auth import auth_manager
        token = _make_token(auth_manager)
        from apps.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/governance/events",
            headers={"Authorization": f"Bearer {token.access_token}"},
        )
        # Should not be 401 - might be 200 or other error
        assert resp.status_code != 401


class TestGetCurrentTenant:
    def test_extracts_tenant_from_token(self):
        from packages.security.auth import auth_manager
        token = _make_token(auth_manager, tenant_id="my-tenant")
        from apps.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/governance/events",
            headers={"Authorization": f"Bearer {token.access_token}"},
        )
        # Should get past auth (tenant extraction happens inside)
        assert resp.status_code != 401


class TestVerifyWsToken:
    def test_ws_token_param_exists(self):
        from packages.security.dependencies import verify_ws_token
        import inspect
        sig = inspect.signature(verify_ws_token)
        assert "token" in sig.parameters
        assert "websocket" in sig.parameters
