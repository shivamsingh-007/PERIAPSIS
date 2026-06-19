from __future__ import annotations

import time
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("health")


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DependencyHealth(BaseModel):
    name: str
    status: HealthStatus
    latency_ms: float = 0.0
    error: str | None = None
    last_checked: datetime = Field(default_factory=datetime.utcnow)


class HealthChecker:
    def __init__(self):
        self._dependencies: dict[str, callable] = {}
        self._results: dict[str, DependencyHealth] = {}

    def register_dependency(self, name: str, check_fn: callable) -> None:
        self._dependencies[name] = check_fn

    async def check_all(self) -> dict:
        results = {}
        overall_status = HealthStatus.HEALTHY

        for name, check_fn in self._dependencies.items():
            start = time.time()
            try:
                await check_fn()
                latency = (time.time() - start) * 1000
                health = DependencyHealth(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                )
            except Exception as e:
                latency = (time.time() - start) * 1000
                health = DependencyHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=latency,
                    error=str(e),
                )
                overall_status = HealthStatus.UNHEALTHY

            self._results[name] = health
            results[name] = health.model_dump()

        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": results,
        }

    def get_status(self) -> dict:
        return {
            "dependencies": {
                name: h.model_dump()
                for name, h in self._results.items()
            }
        }


health_checker = HealthChecker()
