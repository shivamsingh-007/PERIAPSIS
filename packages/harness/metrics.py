from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class MetricPoint(BaseModel):
    metric_name: str
    metric_type: MetricType
    value: float
    labels: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MetricsCollector:
    def __init__(self):
        self._buffer: list[MetricPoint] = []
        self._flush_threshold = 100

    async def record(self, point: MetricPoint):
        self._buffer.append(point)
        if len(self._buffer) >= self._flush_threshold:
            await self.flush()

    async def record_run_success(self, tenant_id: uuid.UUID, run_id: uuid.UUID, success: bool):
        await self.record(MetricPoint(
            metric_name="run_success_rate",
            metric_type=MetricType.GAUGE,
            value=1.0 if success else 0.0,
            labels={"tenant_id": str(tenant_id), "run_id": str(run_id)},
        ))

    async def record_cost(self, tenant_id: uuid.UUID, run_id: uuid.UUID, cost: float):
        await self.record(MetricPoint(
            metric_name="cost_per_run",
            metric_type=MetricType.HISTOGRAM,
            value=cost,
            labels={"tenant_id": str(tenant_id), "run_id": str(run_id)},
        ))

    async def record_tool_error(self, tenant_id: uuid.UUID, tool_name: str, error: str):
        await self.record(MetricPoint(
            metric_name="tool_error_rate",
            metric_type=MetricType.COUNTER,
            value=1.0,
            labels={"tenant_id": str(tenant_id), "tool": tool_name, "error": error},
        ))

    async def record_no_progress_stop(self, tenant_id: uuid.UUID, run_id: uuid.UUID):
        await self.record(MetricPoint(
            metric_name="no_progress_stop_rate",
            metric_type=MetricType.COUNTER,
            value=1.0,
            labels={"tenant_id": str(tenant_id), "run_id": str(run_id)},
        ))

    async def record_human_escalation(self, tenant_id: uuid.UUID, run_id: uuid.UUID):
        await self.record(MetricPoint(
            metric_name="human_escalation_rate",
            metric_type=MetricType.COUNTER,
            value=1.0,
            labels={"tenant_id": str(tenant_id), "run_id": str(run_id)},
        ))

    async def record_orchestration_overhead(self, tenant_id: uuid.UUID, run_id: uuid.UUID, overhead_ms: float):
        await self.record(MetricPoint(
            metric_name="p95_orchestration_overhead",
            metric_type=MetricType.HISTOGRAM,
            value=overhead_ms,
            labels={"tenant_id": str(tenant_id), "run_id": str(run_id)},
        ))

    async def flush(self):
        if not self._buffer:
            return

        points = self._buffer[:]
        self._buffer.clear()

        async with get_session() as session:
            for point in points:
                await session.execute(
                    text(
                        """
                        INSERT INTO metrics_store
                            (metric_id, metric_name, metric_type, value, labels, recorded_at)
                        VALUES
                            (:metric_id, :metric_name, :metric_type, :value, :labels, :recorded_at)
                        """
                    ),
                    {
                        "metric_id": uuid.uuid4(),
                        "metric_name": point.metric_name,
                        "metric_type": point.metric_type.value,
                        "value": point.value,
                        "labels": point.labels,
                        "recorded_at": point.timestamp,
                    },
                )

    async def query_metric(
        self,
        metric_name: str,
        tenant_id: uuid.UUID | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        conditions = ["metric_name = :metric_name"]
        params: dict = {"metric_name": metric_name, "limit": limit}

        if tenant_id:
            conditions.append("labels->>'tenant_id' = :tenant_id")
            params["tenant_id"] = str(tenant_id)

        if since:
            conditions.append("recorded_at >= :since")
            params["since"] = since

        where = " AND ".join(conditions)

        async with get_session() as session:
            result = await session.execute(
                text(
                    f"""
                    SELECT * FROM metrics_store
                    WHERE {where}
                    ORDER BY recorded_at DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
            return [dict(row) for row in result.mappings().all()]

    async def aggregate_metric(
        self,
        metric_name: str,
        tenant_id: uuid.UUID,
        since: datetime | None = None,
    ) -> dict:
        conditions = ["metric_name = :metric_name", "labels->>'tenant_id' = :tenant_id"]
        params: dict = {"metric_name": metric_name, "tenant_id": str(tenant_id)}

        if since:
            conditions.append("recorded_at >= :since")
            params["since"] = since

        where = " AND ".join(conditions)

        async with get_session() as session:
            result = await session.execute(
                text(
                    f"""
                    SELECT
                        COUNT(*) as count,
                        AVG(value) as avg_value,
                        MIN(value) as min_value,
                        MAX(value) as max_value,
                        SUM(value) as sum_value
                    FROM metrics_store
                    WHERE {where}
                    """
                ),
                params,
            )
            row = result.mappings().first()
            return dict(row) if row else {}


metrics_collector = MetricsCollector()
