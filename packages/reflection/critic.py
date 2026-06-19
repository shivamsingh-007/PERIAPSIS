from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session


class CriticType(str, Enum):
    STEP = "step"
    ERROR = "error"
    STRATEGY = "strategy"
    FINAL = "final"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReflectionResult(BaseModel):
    reflection_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    critic_type: CriticType
    finding: str
    severity: Severity
    confidence: float = 0.5
    recommended_action: str = ""
    promoted: bool = False


class CriticNode:
    async def step_reflect(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        step_number: int,
        action_type: str,
        output: dict,
        success: bool,
    ) -> ReflectionResult:
        if success:
            finding = f"Step {step_number} ({action_type}) completed successfully"
            severity = Severity.LOW
        else:
            finding = f"Step {step_number} ({action_type}) failed: {output.get('error', 'unknown')}"
            severity = Severity.MEDIUM

        result = ReflectionResult(
            critic_type=CriticType.STEP,
            finding=finding,
            severity=severity,
            confidence=0.8 if success else 0.6,
            recommended_action="continue" if success else "retry_with_different_approach",
        )

        await self._save_reflection(run_id, tenant_id, result, step_number)
        return result

    async def error_reflect(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        step_number: int,
        error: str,
        action_type: str,
    ) -> ReflectionResult:
        result = ReflectionResult(
            critic_type=CriticType.ERROR,
            finding=f"Error in step {step_number} ({action_type}): {error}",
            severity=Severity.HIGH,
            confidence=0.7,
            recommended_action="investigate_root_cause",
        )

        await self._save_reflection(run_id, tenant_id, result, step_number)
        return result

    async def strategy_reflect(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        iterations: int,
        max_iterations: int,
        progress: bool,
    ) -> ReflectionResult:
        progress_pct = iterations / max_iterations if max_iterations > 0 else 0

        if not progress:
            finding = f"No progress after {iterations} iterations. Strategy change recommended."
            severity = Severity.HIGH
            action = "change_strategy"
        elif progress_pct > 0.8:
            finding = f"Close to budget limit ({iterations}/{max_iterations}). Consider wrapping up."
            severity = Severity.MEDIUM
            action = "wrap_up"
        else:
            finding = f"Progressing normally ({iterations}/{max_iterations} iterations)"
            severity = Severity.LOW
            action = "continue"

        result = ReflectionResult(
            critic_type=CriticType.STRATEGY,
            finding=finding,
            severity=severity,
            confidence=0.75,
            recommended_action=action,
        )

        await self._save_reflection(run_id, tenant_id, result, None)
        return result

    async def final_reflect(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        terminal_state: str,
        total_steps: int,
        total_cost: float,
    ) -> ReflectionResult:
        if terminal_state == "SUCCESS":
            finding = f"Run completed successfully in {total_steps} steps, cost: ${total_cost:.4f}"
            severity = Severity.LOW
        elif terminal_state in ("STOP_BUDGET", "STOP_NO_PROGRESS"):
            finding = f"Run stopped: {terminal_state}. {total_steps} steps, cost: ${total_cost:.4f}"
            severity = Severity.MEDIUM
        else:
            finding = f"Run ended with {terminal_state}. {total_steps} steps, cost: ${total_cost:.4f}"
            severity = Severity.HIGH

        result = ReflectionResult(
            critic_type=CriticType.FINAL,
            finding=finding,
            severity=severity,
            confidence=0.9,
            recommended_action="log_and_archive",
        )

        await self._save_reflection(run_id, tenant_id, result, None)
        return result

    async def _save_reflection(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        result: ReflectionResult,
        step_number: int | None,
    ) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO reflections
                        (reflection_id, run_id, step_id, tenant_id, critic_type,
                         finding, severity, confidence, recommended_action, promoted, created_at)
                    VALUES
                        (:reflection_id, :run_id, :step_id, :tenant_id, :critic_type,
                         :finding, :severity, :confidence, :recommended_action, :promoted, NOW())
                    """
                ),
                {
                    "reflection_id": result.reflection_id,
                    "run_id": run_id,
                    "step_id": None,
                    "tenant_id": tenant_id,
                    "critic_type": result.critic_type.value,
                    "finding": result.finding,
                    "severity": result.severity.value,
                    "confidence": result.confidence,
                    "recommended_action": result.recommended_action,
                    "promoted": result.promoted,
                },
            )


critic_node = CriticNode()
