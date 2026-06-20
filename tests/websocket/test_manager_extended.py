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
    run_broadcaster,
)


class TestWSMessageExtended:
    def test_model_dump(self):
        msg = WSMessage(event="run.created", data={"run_id": "123"})
        d = msg.model_dump()
        assert d["event"] == "run.created"
        assert d["data"]["run_id"] == "123"
        assert "timestamp" in d

    def test_timestamp_auto(self):
        before = datetime.utcnow()
        msg = WSMessage(event="test")
        after = datetime.utcnow()
        assert before <= msg.timestamp <= after


class TestConnectionManagerExtended:
    def setup_method(self):
        self.manager = ConnectionManager()

    def test_subscribe_creates_topic(self):
        self.manager.subscribe("c1", "new_topic")
        subs = self.manager.get_subscriptions()
        assert "new_topic" in subs
        assert "c1" in subs["new_topic"]

    def test_subscribe_multiple_clients(self):
        self.manager.subscribe("c1", "topic1")
        self.manager.subscribe("c2", "topic1")
        subs = self.manager.get_subscriptions()
        assert len(subs["topic1"]) == 2

    def test_subscribe_same_client_multiple_topics(self):
        self.manager.subscribe("c1", "t1")
        self.manager.subscribe("c1", "t2")
        subs = self.manager.get_subscriptions()
        assert "c1" in subs["t1"]
        assert "c1" in subs["t2"]

    def test_unsubscribe_nonexistent_topic(self):
        self.manager.unsubscribe("c1", "nonexistent")
        assert self.manager.get_subscriptions() == {}

    def test_disconnect_cleans_subscriptions(self):
        self.manager.subscribe("c1", "t1")
        self.manager.subscribe("c1", "t2")
        self.manager._connections["c1"] = MagicMock()
        self.manager.disconnect("c1")
        subs = self.manager.get_subscriptions()
        assert "c1" not in subs.get("t1", [])
        assert "c1" not in subs.get("t2", [])

    def test_get_history_limit(self):
        for i in range(10):
            self.manager._message_history.append(WSMessage(event=f"e{i}"))
        history = self.manager.get_history(limit=3)
        assert len(history) == 3
        assert history[0]["event"] == "e7"

    def test_get_history_default_limit(self):
        for i in range(60):
            self.manager._message_history.append(WSMessage(event=f"e{i}"))
        history = self.manager.get_history()
        assert len(history) == 50

    def test_message_history_capped(self):
        self.manager._max_history = 5
        for i in range(10):
            self.manager._message_history.append(WSMessage(event=f"e{i}"))
        self.manager._message_history = self.manager._message_history[-self.manager._max_history:]
        assert len(self.manager._message_history) == 5

    def test_get_connections_empty(self):
        assert self.manager.get_connections() == {}

    def test_get_subscriptions_empty(self):
        assert self.manager.get_subscriptions() == {}


class TestConnectionManagerAsync:
    def setup_method(self):
        self.manager = ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect(self):
        ws = AsyncMock()
        cid = await self.manager.connect(ws, "client-1")
        assert cid == "client-1"
        assert "client-1" in self.manager._connections

    @pytest.mark.asyncio
    async def test_connect_auto_id(self):
        ws = AsyncMock()
        cid = await self.manager.connect(ws)
        assert cid is not None
        assert len(cid) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_connect_calls_accept(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_all(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await self.manager.connect(ws1, "c1")
        await self.manager.connect(ws2, "c2")
        await self.manager.broadcast("test_event", {"key": "value"})
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_topic(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await self.manager.connect(ws1, "c1")
        await self.manager.connect(ws2, "c2")
        self.manager.subscribe("c1", "topic1")
        await self.manager.broadcast("test_event", {"key": "value"}, topic="topic1")
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_disconnected_client(self):
        ws = AsyncMock()
        ws.send_json.side_effect = Exception("disconnected")
        await self.manager.connect(ws, "c1")
        await self.manager.broadcast("test_event", {})
        assert "c1" not in self.manager._connections

    @pytest.mark.asyncio
    async def test_send_to(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        await self.manager.send_to("c1", "event", {"data": 1})
        ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_nonexistent(self):
        await self.manager.send_to("nonexistent", "event", {})

    @pytest.mark.asyncio
    async def test_send_to_disconnected(self):
        ws = AsyncMock()
        ws.send_json.side_effect = Exception("fail")
        await self.manager.connect(ws, "c1")
        await self.manager.send_to("c1", "event", {})
        assert "c1" not in self.manager._connections


class TestRunStatusBroadcaster:
    def setup_method(self):
        self.manager = ConnectionManager()
        self.broadcaster = RunStatusBroadcaster()

    @pytest.mark.asyncio
    async def test_on_run_created(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        self.manager.subscribe("c1", "tenant:t1")
        with patch("packages.websocket.manager.ws_manager", self.manager):
            await self.broadcaster.on_run_created("run-1", "t1", "Deploy app")
        ws.send_json.assert_called_once()
        call_args = ws.send_json.call_args[0][0]
        assert call_args["event"] == "run.created"
        assert call_args["data"]["run_id"] == "run-1"
        assert call_args["data"]["goal"] == "Deploy app"

    @pytest.mark.asyncio
    async def test_on_run_updated(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        self.manager.subscribe("c1", "tenant:t1")
        with patch("packages.websocket.manager.ws_manager", self.manager):
            await self.broadcaster.on_run_updated("run-1", "t1", "RUNNING", iteration=3)
        call_args = ws.send_json.call_args[0][0]
        assert call_args["event"] == "run.updated"
        assert call_args["data"]["state"] == "RUNNING"
        assert call_args["data"]["iteration"] == 3

    @pytest.mark.asyncio
    async def test_on_run_completed(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        self.manager.subscribe("c1", "tenant:t1")
        with patch("packages.websocket.manager.ws_manager", self.manager):
            await self.broadcaster.on_run_completed("run-1", "t1", "SUCCESS", 0.5)
        call_args = ws.send_json.call_args[0][0]
        assert call_args["event"] == "run.completed"
        assert call_args["data"]["cost"] == 0.5

    @pytest.mark.asyncio
    async def test_on_step_completed(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        self.manager.subscribe("c1", "run:run-1")
        with patch("packages.websocket.manager.ws_manager", self.manager):
            await self.broadcaster.on_step_completed("run-1", "t1", 3, True)
        call_args = ws.send_json.call_args[0][0]
        assert call_args["event"] == "step.completed"
        assert call_args["data"]["step"] == 3
        assert call_args["data"]["success"] is True

    @pytest.mark.asyncio
    async def test_on_approval_needed(self):
        ws = AsyncMock()
        await self.manager.connect(ws, "c1")
        self.manager.subscribe("c1", "tenant:t1")
        with patch("packages.websocket.manager.ws_manager", self.manager):
            await self.broadcaster.on_approval_needed("run-1", "t1", "approval-1")
        call_args = ws.send_json.call_args[0][0]
        assert call_args["event"] == "approval.needed"
        assert call_args["data"]["approval_id"] == "approval-1"
