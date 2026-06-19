from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session
from packages.logging.structured import get_logger

logger = get_logger("cost_prediction")


class CostPrediction(BaseModel):
    predicted_cost: float
    confidence: float
    breakdown: dict[str, float] = Field(default_factory=dict)
    based_on_runs: int = 0
    factors: list[str] = Field(default_factory=list)


class CostPredictor:
    def __init__(self):
        self._base_costs = {
            "llm_call": 0.002,
            "tool_execution": 0.001,
            "memory_write": 0.0005,
            "validation": 0.0003,
            "reflection": 0.0002,
        }

    async def predict(
        self,
        tenant_id: uuid.UUID,
        goal: str,
        estimated_steps: int = 5,
        risk_tier: str = "low",
        **kwargs,
    ) -> CostPrediction:
        historical_stats = await self._get_historical_stats(tenant_id)

        base_cost = self._calculate_base_cost(estimated_steps, risk_tier)

        if historical_stats:
            avg_cost = historical_stats.get("avg_cost", 0)
            avg_steps = historical_stats.get("avg_steps", 5)
            if avg_steps > 0:
                cost_per_step = avg_cost / avg_steps
                base_cost = cost_per_step * estimated_steps

        breakdown = self._calculate_breakdown(estimated_steps, risk_tier)
        total = sum(breakdown.values())

        confidence = min(0.9, 0.5 + (historical_stats.get("run_count", 0) / 100))

        factors = []
        if risk_tier == "high":
            factors.append("High risk tier increases cost by 20%")
            total *= 1.2
        if estimated_steps > 10:
            factors.append(f"Complex task with {estimated_steps} estimated steps")

        return CostPrediction(
            predicted_cost=round(total, 4),
            confidence=round(confidence, 2),
            breakdown=breakdown,
            based_on_runs=historical_stats.get("run_count", 0),
            factors=factors,
        )

    def _calculate_base_cost(self, steps: int, risk_tier: str) -> float:
        cost = steps * self._base_costs["llm_call"] * 3
        cost += steps * self._base_costs["tool_execution"]
        cost += steps * self._base_costs["validation"]
        cost += steps * self._base_costs["reflection"]
        return cost

    def _calculate_breakdown(self, steps: int, risk_tier: str) -> dict[str, float]:
        return {
            "llm_calls": steps * 3 * self._base_costs["llm_call"],
            "tool_executions": steps * self._base_costs["tool_execution"],
            "memory_writes": steps * self._base_costs["memory_write"],
            "validations": steps * self._base_costs["validation"],
            "reflections": steps * self._base_costs["reflection"],
        }

    async def _get_historical_stats(self, tenant_id: uuid.UUID) -> dict:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) as run_count,
                        AVG(total_cost) as avg_cost,
                        AVG(total_steps) as avg_steps,
                        MAX(total_cost) as max_cost,
                        MIN(total_cost) as min_cost
                    FROM runs
                    WHERE tenant_id = :tenant_id AND state = 'SUCCESS'
                    """
                ),
                {"tenant_id": tenant_id},
            )
            row = result.mappings().first()
            if row:
                data = dict(row)
                if data.get("run_count", 0) > 0:
                    return data
            return {}

    async def update_model(
        self,
        tenant_id: uuid.UUID,
        actual_cost: float,
        predicted_cost: float,
        steps: int,
    ):
        logger.info(
            f"Cost prediction feedback: predicted={predicted_cost}, actual={actual_cost}, steps={steps}"
        )


cost_predictor = CostPredictor()
