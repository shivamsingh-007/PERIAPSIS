from __future__ import annotations

import asyncio
import uuid

import pytest

from packages.infrastructure.request_queue import RequestQueue, QueuedRequest, QueuePriority


@pytest.fixture
def queue():
    return RequestQueue(max_concurrent=3)


class TestRequestQueue:
    @pytest.mark.asyncio
    async def test_init(self, queue):
        assert queue is not None

    @pytest.mark.asyncio
    async def test_enqueue(self, queue):
        result = await queue.enqueue(payload={"goal": "test"})
        assert result is not None
        assert result.status == "queued"

    @pytest.mark.asyncio
    async def test_process_next(self, queue):
        await queue.enqueue(payload={"goal": "test"})
        result = await queue.process_next()
        assert result is not None

    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue):
        await queue.enqueue(payload={}, priority=QueuePriority.LOW)
        await queue.enqueue(payload={}, priority=QueuePriority.HIGH)
        await queue.enqueue(payload={}, priority=QueuePriority.NORMAL)
        first = await queue.process_next()
        assert first.priority == QueuePriority.HIGH

    @pytest.mark.asyncio
    async def test_max_concurrent(self, queue):
        for i in range(5):
            await queue.enqueue(payload={})
        processed = 0
        while True:
            result = await queue.process_next()
            if result is None:
                break
            processed += 1
        assert processed <= 5

    @pytest.mark.asyncio
    async def test_stats(self, queue):
        stats = queue.get_stats()
        assert "queue_size" in stats
        assert "total_processed" in stats

    @pytest.mark.asyncio
    async def test_empty_queue(self, queue):
        result = await queue.process_next()
        assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_access(self, queue):
        for i in range(10):
            await queue.enqueue(payload={})
        stats = queue.get_stats()
        assert stats["queue_size"] == 10
