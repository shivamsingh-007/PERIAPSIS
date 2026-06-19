from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text

from packages.schemas.database import get_session


class GovernanceEventLogger:
    async def log(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        control_domain: str,
        policy_rule: str,
        decision: str,
        reviewer: uuid.UUID | None = None,
        details: dict | None = None,
    ) -> uuid.UUID:
        event_id = uuid.uuid4()
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO governance_events
                        (event_id, run_id, tenant_id, control_domain, policy_rule,
                         decision, reviewer, details, created_at)
                    VALUES
                        (:event_id, :run_id, :tenant_id, :control_domain, :policy_rule,
                         :decision, :reviewer, :details, NOW())
                    """
                ),
                {
                    "event_id": event_id,
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "control_domain": control_domain,
                    "policy_rule": policy_rule,
                    "decision": decision,
                    "reviewer": reviewer,
                    "details": details,
                },
            )
        return event_id

    async def log_approval_requested(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        action_type: str,
        tool_name: str | None,
        risk_tier: str,
    ) -> uuid.UUID:
        return await self.log(
            run_id=run_id,
            tenant_id=tenant_id,
            control_domain="approval",
            policy_rule=f"risk_tier:{risk_tier}",
            decision="approval_requested",
            details={
                "action_type": action_type,
                "tool_name": tool_name,
                "risk_tier": risk_tier,
            },
        )

    async def log_approval_granted(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        reviewer: uuid.UUID,
        action_type: str,
    ) -> uuid.UUID:
        return await self.log(
            run_id=run_id,
            tenant_id=tenant_id,
            control_domain="approval",
            policy_rule="human_approval",
            decision="approved",
            reviewer=reviewer,
            details={"action_type": action_type},
        )

    async def log_approval_denied(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        reviewer: uuid.UUID,
        action_type: str,
        reason: str = "",
    ) -> uuid.UUID:
        return await self.log(
            run_id=run_id,
            tenant_id=tenant_id,
            control_domain="approval",
            policy_rule="human_approval",
            decision="denied",
            reviewer=reviewer,
            details={"action_type": action_type, "reason": reason},
        )

    async def log_policy_violation(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        policy_rule: str,
        details: dict | None = None,
    ) -> uuid.UUID:
        return await self.log(
            run_id=run_id,
            tenant_id=tenant_id,
            control_domain="policy_violation",
            policy_rule=policy_rule,
            decision="violated",
            details=details,
        )

    async def get_events_for_run(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM governance_events
                    WHERE run_id = :run_id AND tenant_id = :tenant_id
                    ORDER BY created_at ASC
                    """
                ),
                {"run_id": run_id, "tenant_id": tenant_id},
            )
            return [dict(row) for row in result.mappings().all()]


governance_event_logger = GovernanceEventLogger()
