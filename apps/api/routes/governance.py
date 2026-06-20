"""Governance API routes — real DB-backed endpoints for events and approvals."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from packages.schemas.database import get_session
from packages.schemas.models import GovernanceEvent, Run
from packages.security.dependencies import get_current_user, get_current_tenant
from packages.security.auth import TokenPayload

router = APIRouter(prefix="/governance", tags=["governance"])


class GovernanceEventResponse(BaseModel):
    id: str
    run_id: str
    control_domain: str
    policy_rule: str
    decision: str
    reviewer: str | None = None
    details: dict | None = None
    created_at: str


class GovernanceSummary(BaseModel):
    total: int
    approved: int
    pending: int
    denied: int
    require_approval: int


@router.get("/events", response_model=list[GovernanceEventResponse])
async def list_events(
    run_id: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant),
):
    """List governance events for the tenant, with optional filters."""
    async with get_session() as session:
        stmt = select(GovernanceEvent).where(
            GovernanceEvent.tenant_id == tenant_id
        )
        if run_id:
            stmt = stmt.where(GovernanceEvent.run_id == run_id)
        if decision:
            stmt = stmt.where(GovernanceEvent.decision == decision)
        stmt = stmt.order_by(GovernanceEvent.created_at.desc()).offset(offset).limit(limit)

        result = await session.execute(stmt)
        events = result.scalars().all()

        return [
            GovernanceEventResponse(
                id=str(e.event_id),
                run_id=str(e.run_id),
                control_domain=e.control_domain,
                policy_rule=e.policy_rule,
                decision=e.decision,
                reviewer=str(e.reviewer) if e.reviewer else None,
                details=e.details,
                created_at=e.created_at.isoformat(),
            )
            for e in events
        ]


@router.get("/summary", response_model=GovernanceSummary)
async def governance_summary(
    user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant),
):
    """Return counts of governance events by decision type."""
    async with get_session() as session:
        stmt = select(
            GovernanceEvent.decision,
            func.count(GovernanceEvent.event_id),
        ).where(
            GovernanceEvent.tenant_id == tenant_id
        ).group_by(GovernanceEvent.decision)

        result = await session.execute(stmt)
        rows = result.all()

        counts = {row[0]: row[1] for row in rows}
        total = sum(counts.values())

        return GovernanceSummary(
            total=total,
            approved=counts.get("pass", 0) + counts.get("approved", 0),
            pending=counts.get("require_approval", 0) + counts.get("pending", 0),
            denied=counts.get("deny", 0) + counts.get("denied", 0),
            require_approval=counts.get("require_approval", 0),
        )


@router.post("/approve/{event_id}")
async def approve_event(
    event_id: str,
    user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant),
):
    """Approve a pending governance event."""
    async with get_session() as session:
        result = await session.execute(
            select(GovernanceEvent).where(
                GovernanceEvent.event_id == uuid.UUID(event_id),
                GovernanceEvent.tenant_id == tenant_id,
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(404, "Governance event not found")

        if event.decision not in ("require_approval", "pending"):
            raise HTTPException(400, f"Event decision is '{event.decision}', cannot approve")

        event.decision = "approved"
        event.reviewer = uuid.UUID(user.sub) if user.sub else None
        event.details = {**(event.details or {}), "approved_by": user.sub}
        await session.commit()

        return {"status": "ok", "eventId": str(event.event_id), "newDecision": "approved"}


@router.post("/deny/{event_id}")
async def deny_event(
    event_id: str,
    reason: str = "",
    user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant),
):
    """Deny a pending governance event."""
    async with get_session() as session:
        result = await session.execute(
            select(GovernanceEvent).where(
                GovernanceEvent.event_id == uuid.UUID(event_id),
                GovernanceEvent.tenant_id == tenant_id,
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(404, "Governance event not found")

        if event.decision not in ("require_approval", "pending"):
            raise HTTPException(400, f"Event decision is '{event.decision}', cannot deny")

        event.decision = "denied"
        event.reviewer = uuid.UUID(user.sub) if user.sub else None
        event.details = {
            **(event.details or {}),
            "denied_by": user.sub,
            "reason": reason,
        }
        await session.commit()

        return {"status": "ok", "eventId": str(event.event_id), "newDecision": "denied"}
