from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("dead_letter")


class DeadLetterMessage(BaseModel):
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    original_queue: str
    payload: dict = Field(default_factory=dict)
    error: str
    retry_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeadLetterQueue:
    def __init__(self):
        self._messages: dict[uuid.UUID, DeadLetterMessage] = {}

    def add(
        self,
        original_queue: str,
        payload: dict,
        error: str,
        retry_count: int = 0,
    ) -> DeadLetterMessage:
        msg = DeadLetterMessage(
            original_queue=original_queue,
            payload=payload,
            error=error,
            retry_count=retry_count,
        )
        self._messages[msg.message_id] = msg
        logger.warning(f"Dead letter: {msg.message_id} from {original_queue}: {error}")
        return msg

    def acknowledge(self, message_id: uuid.UUID, acknowledged_by: str = "system") -> bool:
        msg = self._messages.get(message_id)
        if msg:
            msg.acknowledged = True
            msg.acknowledged_by = acknowledged_by
            return True
        return False

    def requeue(self, message_id: uuid.UUID) -> dict | None:
        msg = self._messages.get(message_id)
        if msg and not msg.acknowledged:
            return msg.payload
        return None

    def get_unacknowledged(self) -> list[DeadLetterMessage]:
        return [m for m in self._messages.values() if not m.acknowledged]

    def get_stats(self) -> dict:
        messages = list(self._messages.values())
        return {
            "total": len(messages),
            "unacknowledged": sum(1 for m in messages if not m.acknowledged),
            "acknowledged": sum(1 for m in messages if m.acknowledged),
        }


dead_letter_queue = DeadLetterQueue()
