from __future__ import annotations

import uuid
from pydantic import BaseModel
from fastapi import APIRouter, Query

from packages.memory.store import memory_store
from packages.memory.write_filter import (
    MemoryCandidate,
    MemoryType,
    memory_write_filter,
)
from packages.memory.promotion import lesson_promoter, PromotionTarget

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryWriteRequest(BaseModel):
    tenant_id: uuid.UUID
    scope: str = "run"
    scope_ref: uuid.UUID | None = None
    memory_type: str = "fact"
    content: str
    source_ref: dict | None = None
    confidence: float = 0.5
    has_source_attribution: bool = False


class MemoryWriteResponse(BaseModel):
    status: str
    memory_id: uuid.UUID | None = None
    filter_decision: str
    filter_reason: str


class MemoryRetrieveRequest(BaseModel):
    tenant_id: uuid.UUID
    scope: str | None = None
    memory_type: str | None = None
    limit: int = 10
    min_confidence: float = 0.0


class LessonPromotionRequest(BaseModel):
    tenant_id: uuid.UUID
    content: str
    promotion_target: str = "requires_human"
    confidence: float = 0.5
    supporting_evidence: list[str] = []


class LessonPromotionResponse(BaseModel):
    status: str
    promotion_id: uuid.UUID
    message: str


class PromotionActionRequest(BaseModel):
    promotion_id: uuid.UUID
    tenant_id: uuid.UUID
    reviewer: uuid.UUID
    reason: str = ""


@router.post("/memories", response_model=MemoryWriteResponse)
async def write_memory(request: MemoryWriteRequest):
    candidate = MemoryCandidate(
        content=request.content,
        memory_type=MemoryType(request.memory_type),
        source_ref=request.source_ref,
        confidence=request.confidence,
        scope=request.scope,
        has_source_attribution=request.has_source_attribution,
    )

    result = memory_write_filter.evaluate(candidate)

    if result.decision.value == "deny":
        return MemoryWriteResponse(
            status="denied",
            memory_id=None,
            filter_decision=result.decision.value,
            filter_reason=result.reason,
        )

    ttl_days = memory_write_filter.get_ttl_days(
        MemoryType(request.memory_type), result.adjusted_confidence
    )

    memory_id = await memory_store.write(
        tenant_id=request.tenant_id,
        scope=request.scope,
        memory_type=request.memory_type,
        content=request.content,
        source_ref=request.source_ref,
        confidence=result.adjusted_confidence,
        ttl_days=ttl_days,
        scope_ref=request.scope_ref,
    )

    return MemoryWriteResponse(
        status="created" if memory_id else "updated",
        memory_id=memory_id,
        filter_decision=result.decision.value,
        filter_reason=result.reason,
    )


@router.post("/memories/search")
async def search_memories(request: MemoryRetrieveRequest):
    results = await memory_store.retrieve(
        tenant_id=request.tenant_id,
        scope=request.scope,
        memory_type=request.memory_type,
        limit=request.limit,
        min_confidence=request.min_confidence,
    )
    return {"memories": results, "count": len(results)}


@router.post("/memories/deduplicate")
async def deduplicate_memories(tenant_id: uuid.UUID):
    removed = await memory_store.deduplicate(tenant_id)
    return {"removed": removed}


@router.post("/memories/expire")
async def expire_old_memories(tenant_id: uuid.UUID):
    removed = await memory_store.expire_old(tenant_id)
    return {"removed": removed}


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: uuid.UUID, tenant_id: uuid.UUID):
    deleted = await memory_store.delete(tenant_id, memory_id)
    return {"deleted": deleted}


@router.post("/reflections/step")
async def step_reflection(
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    step_number: int,
    action_type: str,
    output: dict,
    success: bool,
):
    from packages.reflection.critic import critic_node

    result = await critic_node.step_reflect(
        run_id=run_id,
        tenant_id=tenant_id,
        step_number=step_number,
        action_type=action_type,
        output=output,
        success=success,
    )
    return result.model_dump()


@router.post("/reflections/error")
async def error_reflection(
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    step_number: int,
    error: str,
    action_type: str,
):
    from packages.reflection.critic import critic_node

    result = await critic_node.error_reflect(
        run_id=run_id,
        tenant_id=tenant_id,
        step_number=step_number,
        error=error,
        action_type=action_type,
    )
    return result.model_dump()


@router.post("/reflections/strategy")
async def strategy_reflection(
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    iterations: int,
    max_iterations: int,
    progress: bool,
):
    from packages.reflection.critic import critic_node

    result = await critic_node.strategy_reflect(
        run_id=run_id,
        tenant_id=tenant_id,
        iterations=iterations,
        max_iterations=max_iterations,
        progress=progress,
    )
    return result.model_dump()


@router.post("/reflections/final")
async def final_reflection(
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    terminal_state: str,
    total_steps: int,
    total_cost: float,
):
    from packages.reflection.critic import critic_node

    result = await critic_node.final_reflect(
        run_id=run_id,
        tenant_id=tenant_id,
        terminal_state=terminal_state,
        total_steps=total_steps,
        total_cost=total_cost,
    )
    return result.model_dump()


@router.post("/lessons/promote", response_model=LessonPromotionResponse)
async def promote_lesson(request: LessonPromotionRequest):
    from packages.memory.promotion import LessonCandidate

    candidate = LessonCandidate(
        content=request.content,
        promotion_target=PromotionTarget(request.promotion_target),
        confidence=request.confidence,
        supporting_evidence=request.supporting_evidence,
    )

    result = await lesson_promoter.submit_for_promotion(
        tenant_id=request.tenant_id,
        candidate=candidate,
    )

    return LessonPromotionResponse(
        status="pending",
        promotion_id=result.promotion_id,
        message="Lesson submitted for human review",
    )


@router.post("/lessons/approve")
async def approve_lesson(request: PromotionActionRequest):
    approved = await lesson_promoter.approve_promotion(
        promotion_id=request.promotion_id,
        tenant_id=request.tenant_id,
        reviewer=request.reviewer,
    )
    return {"approved": approved}


@router.post("/lessons/reject")
async def reject_lesson(request: PromotionActionRequest):
    rejected = await lesson_promoter.reject_promotion(
        promotion_id=request.promotion_id,
        tenant_id=request.tenant_id,
        reviewer=request.reviewer,
        reason=request.reason,
    )
    return {"rejected": rejected}


@router.get("/lessons/pending")
async def get_pending_lessons(tenant_id: uuid.UUID):
    pending = await lesson_promoter.get_pending_promotions(tenant_id)
    return {"pending": pending, "count": len(pending)}
