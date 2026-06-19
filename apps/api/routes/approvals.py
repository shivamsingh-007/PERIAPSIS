from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.governance.events import governance_event_logger
from packages.schemas.database import get_session

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalRequest(BaseModel):
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    action_type: str
    tool_name: str | None = None
    risk_tier: str
    requested_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalResponse(BaseModel):
    event_id: uuid.UUID
    run_id: uuid.UUID
    status: str
    action_type: str
    risk_tier: str
    created_at: datetime


class ApproveRequest(BaseModel):
    reviewer: uuid.UUID
    reason: str = ""


class PendingApproval(BaseModel):
    event_id: uuid.UUID
    run_id: uuid.UUID
    action_type: str
    tool_name: str | None
    risk_tier: str
    created_at: datetime


@router.get("/pending", response_model=list[PendingApproval])
async def list_pending_approvals(tenant_id: uuid.UUID):
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT ge.*, r.goal
                FROM governance_events ge
                JOIN runs r ON r.run_id = ge.run_id
                WHERE ge.tenant_id = :tenant_id
                  AND ge.control_domain = 'approval'
                  AND ge.decision = 'approval_requested'
                  AND ge.event_id NOT IN (
                      SELECT ge2.event_id
                      FROM governance_events ge2
                      WHERE ge2.control_domain = 'approval'
                        AND ge2.decision IN ('approved', 'denied')
                        AND ge2.run_id = ge.run_id
                  )
                ORDER BY ge.created_at ASC
                """
            ),
            {"tenant_id": tenant_id},
        )
        rows = result.mappings().all()

    return [
        PendingApproval(
            event_id=r["event_id"],
            run_id=r["run_id"],
            action_type=r["details"].get("action_type", "") if r["details"] else "",
            tool_name=r["details"].get("tool_name") if r["details"] else None,
            risk_tier=r["details"].get("risk_tier", "") if r["details"] else "",
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.post("/{event_id}/approve", response_model=ApprovalResponse)
async def approve_action(event_id: uuid.UUID, tenant_id: uuid.UUID, req: ApproveRequest):
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT * FROM governance_events WHERE event_id = :event_id AND tenant_id = :tenant_id"
            ),
            {"event_id": event_id, "tenant_id": tenant_id},
        )
        event = result.mappings().first()
        if not event:
            raise HTTPException(status_code=404, detail="Approval request not found")

        if event["decision"] not in ("approval_requested",):
            raise HTTPException(status_code=400, detail="Event is not a pending approval")

    await governance_event_logger.log_approval_granted(
        run_id=event["run_id"],
        tenant_id=tenant_id,
        reviewer=req.reviewer,
        action_type=event["details"].get("action_type", "") if event["details"] else "",
    )

    async with get_session() as session:
        await session.execute(
            text(
                """
                UPDATE runs SET status = 'running', updated_at = NOW()
                WHERE run_id = :run_id AND tenant_id = :tenant_id AND status = 'paused'
                """
            ),
            {"run_id": event["run_id"], "tenant_id": tenant_id},
        )

    return ApprovalResponse(
        event_id=event_id,
        run_id=event["run_id"],
        status="approved",
        action_type=event["details"].get("action_type", "") if event["details"] else "",
        risk_tier=event["details"].get("risk_tier", "") if event["details"] else "",
        created_at=datetime.utcnow(),
    )


@router.post("/{event_id}/deny", response_model=ApprovalResponse)
async def deny_action(event_id: uuid.UUID, tenant_id: uuid.UUID, req: ApproveRequest):
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT * FROM governance_events WHERE event_id = :event_id AND tenant_id = :tenant_id"
            ),
            {"event_id": event_id, "tenant_id": tenant_id},
        )
        event = result.mappings().first()
        if not event:
            raise HTTPException(status_code=404, detail="Approval request not found")

        if event["decision"] not in ("approval_requested",):
            raise HTTPException(status_code=400, detail="Event is not a pending approval")

    await governance_event_logger.log_approval_denied(
        run_id=event["run_id"],
        tenant_id=tenant_id,
        reviewer=req.reviewer,
        action_type=event["details"].get("action_type", "") if event["details"] else "",
        reason=req.reason,
    )

    async with get_session() as session:
        await session.execute(
            text(
                """
                UPDATE runs SET status = 'completed', terminal_state = 'STOP_POLICY', updated_at = NOW()
                WHERE run_id = :run_id AND tenant_id = :tenant_id AND status = 'paused'
                """
            ),
            {"run_id": event["run_id"], "tenant_id": tenant_id},
        )

    return ApprovalResponse(
        event_id=event_id,
        run_id=event["run_id"],
        status="denied",
        action_type=event["details"].get("action_type", "") if event["details"] else "",
        risk_tier=event["details"].get("risk_tier", "") if event["details"] else "",
        created_at=datetime.utcnow(),
    )


@router.get("/events/{run_id}")
async def get_governance_events(run_id: uuid.UUID, tenant_id: uuid.UUID):
    events = await governance_event_logger.get_events_for_run(run_id, tenant_id)
    return {"events": events}
