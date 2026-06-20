"""Tests for notifications API routes."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from contextlib import asynccontextmanager


@asynccontextmanager
async def _mock_session():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.flush = AsyncMock()
    yield mock_session



@pytest.mark.asyncio
@patch("packages.middleware.idempotency.get_session", _mock_session)
@patch("apps.api.routes.notifications.get_session", _mock_session)
async def test_subscribe_with_auth():
    from packages.security.auth import auth_manager
    token = auth_manager.create_token("user-1", "tenant-1", role="admin")
    from httpx import AsyncClient, ASGITransport
    from apps.api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/notifications/subscribe",
            json={"channel": "email", "target": "test@example.com"},
            headers={"Authorization": f"Bearer {token.access_token}"},
        )
        assert resp.status_code in (200, 201)


@pytest.mark.asyncio
@patch("packages.middleware.idempotency.get_session", _mock_session)
@patch("apps.api.routes.notifications.get_session", _mock_session)
async def test_list_subscriptions_with_auth():
    from packages.security.auth import auth_manager
    token = auth_manager.create_token("user-1", "tenant-1", role="admin")
    from httpx import AsyncClient, ASGITransport
    from apps.api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/notifications/subscriptions",
            headers={"Authorization": f"Bearer {token.access_token}"},
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
@patch("packages.middleware.idempotency.get_session", _mock_session)
@patch("apps.api.routes.notifications.get_session", _mock_session)
async def test_subscribe_without_auth_rejected():
    from httpx import AsyncClient, ASGITransport
    from apps.api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/notifications/subscribe",
            json={"channel": "email", "target": "test@example.com"},
        )
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
@patch("packages.middleware.idempotency.get_session", _mock_session)
@patch("apps.api.routes.notifications.get_session", _mock_session)
async def test_list_subscriptions_without_auth_rejected():
    from httpx import AsyncClient, ASGITransport
    from apps.api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/notifications/subscriptions")
        assert resp.status_code in (401, 403)
