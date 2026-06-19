from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session


class PromotionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROMOTED = "promoted"


class PromotionTarget(str, Enum):
    SKILL = "skill"
    PROMPT = "prompt"
    RULE = "rule"
    DATASET = "dataset"
    REQUIRES_HUMAN = "requires_human"


class LessonCandidate(BaseModel):
    content: str
    source_reflection_id: uuid.UUID | None = None
    promotion_target: PromotionTarget = PromotionTarget.REQUIRES_HUMAN
    confidence: float = 0.5
    supporting_evidence: list[str] = Field(default_factory=list)


class PromotionRequest(BaseModel):
    promotion_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    lesson: str
    status: PromotionStatus = PromotionStatus.PENDING
    promotion_target: PromotionTarget
    reviewer: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LessonPromoter:
    async def submit_for_promotion(
        self,
        tenant_id: uuid.UUID,
        candidate: LessonCandidate,
    ) -> PromotionRequest:
        request = PromotionRequest(
            tenant_id=tenant_id,
            lesson=candidate.content,
            promotion_target=candidate.promotion_target,
        )

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
                    "event_id": request.promotion_id,
                    "run_id": uuid.uuid4(),
                    "tenant_id": tenant_id,
                    "control_domain": "lesson_promotion",
                    "policy_rule": "self_learning_promotion",
                    "decision": "pending",
                    "details": {
                        "lesson": candidate.content,
                        "target": candidate.promotion_target.value,
                        "confidence": candidate.confidence,
                        "evidence": candidate.supporting_evidence,
                    },
                },
            )
        return request

    async def approve_promotion(
        self,
        promotion_id: uuid.UUID,
        tenant_id: uuid.UUID,
        reviewer: uuid.UUID,
    ) -> bool:
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE governance_events
                    SET decision = 'approved', reviewer = :reviewer, details = details || '{"status": "approved"}'
                    WHERE event_id = :event_id AND tenant_id = :tenant_id
                      AND control_domain = 'lesson_promotion'
                    """
                ),
                {
                    "event_id": promotion_id,
                    "tenant_id": tenant_id,
                    "reviewer": reviewer,
                },
            )
        return True

    async def reject_promotion(
        self,
        promotion_id: uuid.UUID,
        tenant_id: uuid.UUID,
        reviewer: uuid.UUID,
        reason: str = "",
    ) -> bool:
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE governance_events
                    SET decision = 'rejected', reviewer = :reviewer,
                        details = details || '{"status": "rejected", "reason": :reason}'
                    WHERE event_id = :event_id AND tenant_id = :tenant_id
                      AND control_domain = 'lesson_promotion'
                    """
                ),
                {
                    "event_id": promotion_id,
                    "tenant_id": tenant_id,
                    "reviewer": reviewer,
                    "reason": reason,
                },
            )
        return True

    async def get_pending_promotions(
        self,
        tenant_id: uuid.UUID,
    ) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM governance_events
                    WHERE tenant_id = :tenant_id
                      AND control_domain = 'lesson_promotion'
                      AND decision = 'pending'
                    ORDER BY created_at ASC
                    """
                ),
                {"tenant_id": tenant_id},
            )
            return [dict(row) for row in result.mappings().all()]


lesson_promoter = LessonPromoter()
