from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("request_queue")


class QueuePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class QueuedRequest(BaseModel):
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    payload: dict = Field(default_factory=dict)
    priority: QueuePriority = QueuePriority.NORMAL
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: str = "queued"
    result: Any = None
    error: str | None = None
    retries: int = 0
    max_retries: int = 3


class RequestQueue:
    def __init__(self, max_concurrent: int = 10, max_queue_size: int = 1000):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._active: int = 0
        self._processed: list[QueuedRequest] = []
        self._handlers: dict[str, Callable[..., Coroutine]] = {}
        self._counter: int = 0

    def register_handler(self, name: str, handler: Callable[..., Coroutine]) -> None:
        self._handlers[name] = handler

    async def enqueue(
        self,
        payload: dict,
        priority: QueuePriority = QueuePriority.NORMAL,
        handler_name: str | None = None,
    ) -> QueuedRequest:
        request = QueuedRequest(payload=payload, priority=priority)

        priority_value = {
            QueuePriority.CRITICAL: 0,
            QueuePriority.HIGH: 1,
            QueuePriority.NORMAL: 2,
            QueuePriority.LOW: 3,
        }.get(priority, 2)

        self._counter += 1
        await self._queue.put((priority_value, self._counter, request))
        logger.info(f"Enqueued request {request.request_id} with priority {priority.value}")
        return request

    async def process_next(self) -> QueuedRequest | None:
        if self._active >= self.max_concurrent:
            return None

        try:
            priority_value, _counter, request = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

        self._active += 1
        request.started_at = datetime.utcnow()
        request.status = "processing"

        try:
            handler = self._handlers.get("default")
            if handler:
                request.result = await handler(request.payload)
            request.status = "completed"
        except Exception as e:
            request.error = str(e)
            request.status = "failed"

            if request.retries < request.max_retries:
                request.retries += 1
                await self._queue.put((priority_value, self._counter, request))
                request.status = "retrying"
        finally:
            request.completed_at = datetime.utcnow()
            self._active -= 1
            self._processed.append(request)

        return request

    async def process_all(self) -> int:
        processed = 0
        while not self._queue.empty():
            result = await self.process_next()
            if result:
                processed += 1
        return processed

    def get_queue_size(self) -> int:
        return self._queue.qsize()

    def get_stats(self) -> dict:
        return {
            "queue_size": self._queue.qsize(),
            "active": self._active,
            "max_concurrent": self.max_concurrent,
            "total_processed": len(self._processed),
            "successful": sum(1 for r in self._processed if r.status == "completed"),
            "failed": sum(1 for r in self._processed if r.status == "failed"),
        }


request_queue = RequestQueue()
