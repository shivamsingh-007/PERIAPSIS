"""Tests for WebSocket authentication."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


class TestWebSocketAuth:
    def test_ws_route_exists(self):
        from apps.api.routes.websocket import router
        assert "websocket" in router.tags

    def test_runs_ws_has_token_param(self):
        from apps.api.routes.websocket import runs_websocket
        import inspect
        sig = inspect.signature(runs_websocket)
        assert "token" in sig.parameters

    def test_legacy_ws_has_client_id(self):
        from apps.api.routes.websocket import websocket_endpoint
        import inspect
        sig = inspect.signature(websocket_endpoint)
        assert "client_id" in sig.parameters

    @patch("apps.api.routes.websocket.auth_manager")
    def test_ws_rejects_missing_token(self, mock_auth):
        from apps.api.main import app
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/runs") as ws:
                pass

    @patch("apps.api.routes.websocket.auth_manager")
    def test_ws_rejects_invalid_token(self, mock_auth):
        mock_auth.verify_token.return_value = None
        from apps.api.main import app
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/runs?token=bad-token") as ws:
                pass

    def test_ws_accepts_valid_token(self):
        from packages.security.auth import TokenPayload

        async def run():
            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.receive_json = AsyncMock(side_effect=WebSocketDisconnect)
            mock_ws.send_json = AsyncMock()
            mock_ws.close = AsyncMock()
            mock_ws.client_state = MagicMock()

            payload = TokenPayload(
                sub="user-1",
                tenant_id="tenant-1",
                role="admin",
                permissions=[],
                exp=9999999999.0,
                iat=1000000000.0,
            )
            with patch("apps.api.routes.websocket.auth_manager") as mock_auth, \
                 patch("apps.api.routes.websocket.ws_manager") as mock_wsm:
                mock_auth.verify_token.return_value = payload
                mock_wsm.connect = AsyncMock(return_value="client-1")
                mock_wsm.subscribe = MagicMock()

                from apps.api.routes.websocket import runs_websocket
                await runs_websocket(mock_ws, token="valid-token")

                mock_auth.verify_token.assert_called_once_with("valid-token")
                mock_wsm.connect.assert_awaited_once_with(mock_ws, "tenant-1:user-1")
                mock_wsm.subscribe.assert_called_once_with("tenant-1:user-1", "tenant:tenant-1")

        asyncio.run(run())

    def test_ws_closes_on_invalid_token(self):
        async def run():
            mock_ws = MagicMock()
            mock_ws.close = AsyncMock()
            mock_ws.client_state = MagicMock()

            with patch("apps.api.routes.websocket.auth_manager") as mock_auth:
                mock_auth.verify_token.return_value = None

                from apps.api.routes.websocket import runs_websocket
                await runs_websocket(mock_ws, token="bad-token")

                mock_ws.close.assert_awaited_once_with(code=1008, reason="Invalid or expired token")

        asyncio.run(run())

    def test_ws_closes_on_missing_token(self):
        async def run():
            mock_ws = MagicMock()
            mock_ws.close = AsyncMock()
            mock_ws.client_state = MagicMock()

            from apps.api.routes.websocket import runs_websocket
            await runs_websocket(mock_ws, token=None)

            mock_ws.close.assert_awaited_once_with(code=1008, reason="Missing token")

        asyncio.run(run())

    def test_handle_message_subscribe(self):
        from apps.api.routes.websocket import _handle_message
        import asyncio

        async def run():
            with patch("apps.api.routes.websocket.ws_manager") as mock_ws:
                mock_ws.send_to = AsyncMock()
                await _handle_message("client-1", "tenant-1", {"action": "subscribe", "topic": "run:123"})
                mock_ws.subscribe.assert_called_once_with("client-1", "run:123")
                mock_ws.send_to.assert_called_once()

        asyncio.run(run())

    def test_handle_message_ping(self):
        from apps.api.routes.websocket import _handle_message
        import asyncio

        async def run():
            with patch("apps.api.routes.websocket.ws_manager") as mock_ws:
                mock_ws.send_to = AsyncMock()
                await _handle_message("client-1", "tenant-1", {"action": "ping"})
                mock_ws.send_to.assert_called_once_with("client-1", "pong", {})

        asyncio.run(run())
