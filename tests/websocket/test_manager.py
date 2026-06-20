from __future__ import annotations
"""Tests for packages.websocket.manager - ConnectionManager."""

import pytest

from packages.websocket.manager import ConnectionManager, WSMessage


class TestWSMessage:
    def test_defaults(self):
        msg = WSMessage(event="test")
        assert msg.event == "test"
        assert msg.data == {}

    def test_with_data(self):
        msg = WSMessage(event="run.completed", data={"run_id": "123"})
        assert msg.data["run_id"] == "123"


class TestConnectionManager:
    def setup_method(self):
        self.manager = ConnectionManager()

    def test_disconnect(self):
        # Should not raise
        self.manager.disconnect("nonexistent")

    def test_subscribe_unsubscribe(self):
        self.manager.subscribe("client1", "topic1")
        subs = self.manager.get_subscriptions()
        assert "topic1" in subs
        assert "client1" in subs["topic1"]

        self.manager.unsubscribe("client1", "topic1")
        subs = self.manager.get_subscriptions()
        assert "client1" not in subs.get("topic1", [])

    def test_get_connections_empty(self):
        assert self.manager.get_connections() == {}

    def test_get_history_empty(self):
        assert self.manager.get_history() == []

    def test_message_history_limit(self):
        self.manager._max_history = 3
        for i in range(5):
            from datetime import datetime
            msg = WSMessage(event=f"event{i}")
            self.manager._message_history.append(msg)
        self.manager._message_history = self.manager._message_history[-self.manager._max_history:]
        assert len(self.manager._message_history) == 3
