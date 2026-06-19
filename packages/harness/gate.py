from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session
from packages.harness.scoring import ScenarioResult, RunScore


class GateDecision(str, Enum):
    PASS = "pass"
    BLOCK = "block"
    WARN = "warn"


class GateBlock(BaseModel):
    block_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    decision: GateDecision
    reason: str
    failed_scenarios: list[str] = Field(default_factory=list)
    overall_score: float = 0.0
    blocked_at: datetime = Field(default_factory=datetime.utcnow)


class ShipGate:
    def __init__(self, blocking_enabled: bool = True):
        self.blocking_enabled = blocking_enabled

    async def evaluate(self, run_score: RunScore) -> GateBlock:
        failed_required = []
        warnings = []

        for sr in run_score.scenario_scores:
            if sr.result == ScenarioResult.FAIL:
                failed_required.append(sr.scenario_name)
            elif sr.result == ScenarioResult.WARN:
                warnings.append(sr.scenario_name)

        if failed_required and self.blocking_enabled:
            decision = GateDecision.BLOCK
            reason = f"Required scenarios failed: {', '.join(failed_required)}"
        elif warnings:
            decision = GateDecision.WARN
            reason = f"Warnings: {', '.join(warnings)}"
        else:
            decision = GateDecision.PASS
            reason = "All scenarios passed"

        block = GateBlock(
            run_id=run_score.run_id,
            tenant_id=run_score.tenant_id,
            decision=decision,
            reason=reason,
            failed_scenarios=failed_required,
            overall_score=run_score.overall_score,
        )

        await self._persist_block(block)
        return block

    async def _persist_block(self, block: GateBlock) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO governance_events
                        (event_id, run_id, tenant_id, control_domain, policy_rule,
                         decision, details, created_at)
                    VALUES
                        (:event_id, :run_id, :tenant_id, :control_domain, :policy_rule,
                         :decision, :details, NOW())
                    """
                ),
                {
                    "event_id": block.block_id,
                    "run_id": block.run_id,
                    "tenant_id": block.tenant_id,
                    "control_domain": "ship_gate",
                    "policy_rule": "harness_scoring",
                    "decision": block.decision.value,
                    "details": {
                        "reason": block.reason,
                        "failed_scenarios": block.failed_scenarios,
                        "overall_score": block.overall_score,
                    },
                },
            )

    async def check_if_blocked(self, run_id: uuid.UUID) -> bool:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT decision FROM governance_events
                    WHERE run_id = :run_id AND control_domain = 'ship_gate'
                    ORDER BY created_at DESC LIMIT 1
                    """
                ),
                {"run_id": run_id},
            )
            row = result.mappings().first()
            return row["decision"] == "block" if row else False

    async def get_gate_history(
        self,
        tenant_id: uuid.UUID,
        limit: int = 50,
    ) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM governance_events
                    WHERE tenant_id = :tenant_id AND control_domain = 'ship_gate'
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"tenant_id": tenant_id, "limit": limit},
            )
            return [dict(row) for row in result.mappings().all()]


ship_gate = ShipGate()
