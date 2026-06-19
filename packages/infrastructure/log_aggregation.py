from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("log_aggregation")


class AggregatedLog(BaseModel):
    log_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source: str
    level: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    fields: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None


class LogAggregator:
    def __init__(self):
        self._logs: list[AggregatedLog] = []
        self._buffer: list[AggregatedLog] = []
        self._flush_interval = 100

    def ingest(
        self,
        source: str,
        level: str,
        message: str,
        fields: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> AggregatedLog:
        log = AggregatedLog(
            source=source,
            level=level,
            message=message,
            fields=fields or {},
            trace_id=trace_id,
        )
        self._buffer.append(log)

        if len(self._buffer) >= self._flush_interval:
            self.flush()

        return log

    def flush(self) -> int:
        count = len(self._buffer)
        self._logs.extend(self._buffer)
        self._buffer.clear()
        return count

    def query(
        self,
        source: str | None = None,
        level: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AggregatedLog]:
        self.flush()

        results = self._logs

        if source:
            results = [l for l in results if l.source == source]
        if level:
            results = [l for l in results if l.level == level]
        if start_time:
            results = [l for l in results if l.timestamp >= start_time]
        if end_time:
            results = [l for l in results if l.timestamp <= end_time]

        return results[-limit:]

    def get_stats(self) -> dict:
        self.flush()
        return {
            "total_logs": len(self._logs),
            "buffer_size": len(self._buffer),
            "sources": list(set(l.source for l in self._logs)),
        }


log_aggregator = LogAggregator()
