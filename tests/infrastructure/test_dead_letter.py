from __future__ import annotations
"""Tests for packages.infrastructure.dead_letter - DeadLetterQueue."""

import uuid

import pytest

from packages.infrastructure.dead_letter import DeadLetterMessage, DeadLetterQueue


class TestDeadLetterQueue:
    def setup_method(self):
        self.queue = DeadLetterQueue()

    def test_add_message(self):
        msg = self.queue.add("my_queue", {"key": "value"}, "timeout error")
        assert msg.original_queue == "my_queue"
        assert msg.payload == {"key": "value"}
        assert msg.error == "timeout error"
        assert msg.acknowledged is False

    def test_acknowledge(self):
        msg = self.queue.add("q", {}, "error")
        result = self.queue.acknowledge(msg.message_id, "admin")
        assert result is True
        assert msg.acknowledged is True
        assert msg.acknowledged_by == "admin"

    def test_acknowledge_nonexistent(self):
        result = self.queue.acknowledge(uuid.uuid4())
        assert result is False

    def test_requeue(self):
        msg = self.queue.add("q", {"data": 1}, "error")
        payload = self.queue.requeue(msg.message_id)
        assert payload == {"data": 1}

    def test_requeue_acknowledged(self):
        msg = self.queue.add("q", {}, "error")
        self.queue.acknowledge(msg.message_id)
        payload = self.queue.requeue(msg.message_id)
        assert payload is None

    def test_requeue_nonexistent(self):
        payload = self.queue.requeue(uuid.uuid4())
        assert payload is None

    def test_get_unacknowledged(self):
        self.queue.add("q", {}, "e1")
        self.queue.add("q", {}, "e2")
        msg3 = self.queue.add("q", {}, "e3")
        self.queue.acknowledge(msg3.message_id)
        unack = self.queue.get_unacknowledged()
        assert len(unack) == 2

    def test_get_stats(self):
        self.queue.add("q", {}, "e1")
        msg2 = self.queue.add("q", {}, "e2")
        self.queue.acknowledge(msg2.message_id)
        stats = self.queue.get_stats()
        assert stats["total"] == 2
        assert stats["unacknowledged"] == 1
        assert stats["acknowledged"] == 1

    def test_stats_empty(self):
        stats = self.queue.get_stats()
        assert stats["total"] == 0
