from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.websocket.manager import (
    ConnectionManager,
    RunStatusBroadcaster,
    WSMessage,
    ws_manager,
)


class TestConnectionManagerRealtime:
    def setup_method(self):
        self.manager = ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_and_broadcast(self):
        ws = AsyncMock()
        cid = await self.manager.connect(ws, "client-1")
        await self.manager.broadcast("event1", {"key": "val"})
        ws.send_json.assert_called_once()
        call_data = ws.send_json.call_args[0][0]
        assert call_data["event"] == "event1"

    @pytest.mark.asyncio
    async def test_topic_isolation(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await self.manager.connect(ws1, "c1")
        await self.manager.connect(ws2, "c2")
        self.manager.subscribe("c1", "tenant:A")
        self.manager.subscribe("c2", "tenant:B")
        await self.manager.broadcast("update", {"x": 1}, topic="tenant:A")
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_subscribe_before_connect(self):
        self.manager.subscribe("ghost", "topic1")
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        self.manager.subscribe("c1", "topic1")
        await self.manager.broadcast("test", {}, topic="topic1")
        ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_records_history(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        await self.manager.broadcast("event1", {"data": 1})
        history = self.manager.get_history()
        assert len(history) == 1
        assert history[0]["event"] == "event1"

    @pytest.mark.asyncio
    async def test_history_limit_enforced(self):
        self.manager._max_history = 3
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        for i in range(5):
            await self.manager.broadcast(f"event{i}", {"i": i})
        history = self.manager.get_history()
        assert len(history) == 3
        assert history[0]["event"] == "event2"

    @pytest.mark.asyncio
    async def test_send_to_client(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        await self.manager.send_to("c1", "update", {"step": 1})
        ws.send_json.assert_called_once()
        data = ws.send_json.call_args[0][0]
        assert data["event"] == "update"
        assert data["data"]["step"] == 1

    @pytest.mark.asyncio
    async def test_disconnect_cleans_everything(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        self.manager.subscribe("c1", "t1")
        self.manager.subscribe("c1", "t2")
        self.manager.disconnect("c1")
        assert "c1" not in self.manager._connections
        subs = self.manager.get_subscriptions()
        assert "c1" not in subs.get("t1", [])
        assert "c1" not in subs.get("t2", [])

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_topic(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        await self.manager.connect(ws1, "c1")
        await self.manager.connect(ws2, "c2")
        await self.manager.connect(ws3, "c3")
        self.manager.subscribe("c1", "run:123")
        self.manager.subscribe("c2", "run:123")
        self.manager.subscribe("c3", "run:456")
        await self.manager.broadcast("step", {"n": 1}, topic="run:123")
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()
        ws3.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_topic_fallback(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        await self.manager.broadcast("test", {}, topic="nonexistent")
        ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_connections(self):
        ws = AsyncMock()
        ws.url = "ws://test"
        await self.manager.connect(ws, "c1")
        conns = self.manager.get_connections()
        assert "c1" in conns

    @pytest.mark.asyncio
    async def test_get_subscriptions(self):
        self.manager.subscribe("c1", "t1")
        self.manager.subscribe("c1", "t2")
        subs = self.manager.get_subscriptions()
        assert len(subs) == 2
        assert "c1" in subs["t1"]
        assert "c1" in subs["t2"]

    @pytest.mark.asyncio
    async def test_broadcast_concurrent(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        tasks = [self.manager.broadcast(f"e{i}", {"i": i}) for i in range(10)]
        await asyncio.gather(*tasks)
        assert ws.send_json.call_count == 10


class TestRunStatusBroadcasterRealtime:
    def setup_method(self):
        self.manager = ConnectionManager()
        self.broadcaster = RunStatusBroadcaster()

    @pytest.mark.asyncio
    async def test_run_lifecycle_events(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        self.manager.subscribe("c1", "tenant:t1")

        with patch("packages.websocket.manager.ws_manager", self.manager):
            await self.broadcaster.on_run_created("run-1", "t1", "Deploy")
            await self.broadcaster.on_run_updated("run-1", "t1", "RUNNING")
            await self.broadcaster.on_step_completed("run-1", "t1", 1, True)
            await self.broadcaster.on_run_completed("run-1", "t1", "SUCCESS", 0.5)

        assert ws.send_json.call_count == 4
        events = [call[0][0]["event"] for call in ws.send_json.call_args_list]
        assert events == ["run.created", "run.updated", "step.completed", "run.completed"]

    @pytest.mark.asyncio
    async def test_approval_flow(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        self.manager.subscribe("c1", "tenant:t1")

        with patch("packages.websocket.manager.ws_manager", self.manager):
            await self.broadcaster.on_approval_needed("run-1", "t1", "appr-1")

        call_data = ws.send_json.call_args[0][0]
        assert call_data["event"] == "approval.needed"
        assert call_data["data"]["approval_id"] == "appr-1"

    @pytest.mark.asyncio
    async def test_step_failure_event(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        self.manager.subscribe("c1", "run:run-1")

        with patch("packages.websocket.manager.ws_manager", self.manager):
            await self.broadcaster.on_step_completed("run-1", "t1", 3, False)

        call_data = ws.send_json.call_args[0][0]
        assert call_data["data"]["success"] is False
        assert call_data["data"]["step"] == 3
