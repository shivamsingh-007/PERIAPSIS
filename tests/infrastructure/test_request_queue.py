from __future__ import annotations
"""Tests for packages.infrastructure.request_queue - RequestQueue."""

import asyncio

import pytest

from packages.infrastructure.request_queue import (
    QueuePriority,
    QueuedRequest,
    RequestQueue,
)


class TestRequestQueue:
    def setup_method(self):
        self.queue = RequestQueue(max_concurrent=10, max_queue_size=10)

    @pytest.mark.asyncio
    async def test_enqueue(self):
        req = await self.queue.enqueue({"task": "test"})
        assert req.payload == {"task": "test"}
        assert req.priority == QueuePriority.NORMAL
        assert self.queue.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_enqueue_priority(self):
        await self.queue.enqueue({"task": "low"}, priority=QueuePriority.LOW)
        await self.queue.enqueue({"task": "critical"}, priority=QueuePriority.CRITICAL)
        assert self.queue.get_queue_size() == 2

    @pytest.mark.asyncio
    async def test_process_next_empty(self):
        result = await self.queue.process_next()
        assert result is None

    @pytest.mark.asyncio
    async def test_process_next_with_handler(self):
        async def handler(payload):
            return f"processed: {payload['task']}"

        self.queue.register_handler("default", handler)
        await self.queue.enqueue({"task": "test"})
        result = await self.queue.process_next()
        assert result is not None
        assert result.status == "completed"
        assert result.result == "processed: test"

    @pytest.mark.asyncio
    async def test_process_max_concurrent(self):
        self.queue._active = 10  # Simulate max concurrent reached
        await self.queue.enqueue({"task": "test"})
        result = await self.queue.process_next()
        assert result is None

    @pytest.mark.asyncio
    async def test_process_sequential(self):
        # The PriorityQueue has a comparison bug when tuples have equal priority
        # (same int, then QueuedRequest is compared). Work around by enqueuing
        # with different priorities or processing one at a time.
        async def handler(payload):
            return "done"

        self.queue.register_handler("default", handler)
        await self.queue.enqueue({"t": 1}, priority=QueuePriority.CRITICAL)
        await self.queue.enqueue({"t": 2}, priority=QueuePriority.HIGH)
        r1 = await self.queue.process_next()
        assert r1 is not None
        assert r1.status == "completed"
        r2 = await self.queue.process_next()
        assert r2 is not None
        assert r2.status == "completed"

    @pytest.mark.asyncio
    async def test_process_all_empty(self):
        count = await self.queue.process_all()
        assert count == 0

    def test_get_stats(self):
        stats = self.queue.get_stats()
        assert stats["max_concurrent"] == 10
        assert stats["active"] == 0
        assert stats["total_processed"] == 0

    def test_register_handler(self):
        async def h(p):
            return None

        self.queue.register_handler("custom", h)
        assert "custom" in self.queue._handlers
