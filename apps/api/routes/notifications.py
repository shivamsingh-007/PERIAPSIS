"""Notifications API routes — subscriptions and job management."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from packages.schemas.database import get_session
from packages.schemas.models import NotificationSubscription, NotificationJob
from packages.security.dependencies import get_current_user, get_current_tenant
from packages.security.auth import TokenPayload

router = APIRouter(prefix="/notifications", tags=["notifications"])


class SubscriptionCreate(BaseModel):
    run_id: str | None = None
    channel: str  # "email" | "slack"
    target: str


class SubscriptionResponse(BaseModel):
    id: str
    run_id: str | None
    channel: str
    target: str
    is_active: bool
    created_at: str


class JobResponse(BaseModel):
    id: str
    subscription_id: str
    status: str
    error_message: str | None = None
    created_at: str
    sent_at: str | None = None


@router.post("/subscribe", response_model=SubscriptionResponse)
async def create_subscription(
    payload: SubscriptionCreate,
    user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant),
):
    """Create a notification subscription for a run or tenant-wide."""
    if payload.channel not in ("email", "slack"):
        raise HTTPException(400, "Channel must be 'email' or 'slack'")

    async with get_session() as session:
        sub = NotificationSubscription(
            tenant_id=tenant_id,
            run_id=payload.run_id,
            channel=payload.channel,
            target=payload.target,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(sub)
        await session.commit()
        await session.refresh(sub)

        return SubscriptionResponse(
            id=str(sub.id),
            run_id=sub.run_id,
            channel=sub.channel,
            target=sub.target,
            is_active=sub.is_active,
            created_at=sub.created_at.isoformat(),
        )


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant),
):
    """List all active subscriptions for the tenant."""
    async with get_session() as session:
        stmt = (
            select(NotificationSubscription)
            .where(
                NotificationSubscription.tenant_id == tenant_id,
                NotificationSubscription.is_active == True,
            )
            .order_by(NotificationSubscription.created_at.desc())
        )
        result = await session.execute(stmt)
        subs = result.scalars().all()

        return [
            SubscriptionResponse(
                id=str(s.id),
                run_id=s.run_id,
                channel=s.channel,
                target=s.target,
                is_active=s.is_active,
                created_at=s.created_at.isoformat(),
            )
            for s in subs
        ]


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant),
):
    """Soft-delete a notification subscription."""
    async with get_session() as session:
        result = await session.execute(
            select(NotificationSubscription).where(
                NotificationSubscription.id == uuid.UUID(subscription_id),
                NotificationSubscription.tenant_id == tenant_id,
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise HTTPException(404, "Subscription not found")

        sub.is_active = False
        await session.commit()
        return {"status": "ok"}


@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant),
):
    """List notification jobs for the tenant."""
    async with get_session() as session:
        stmt = select(NotificationJob).where(NotificationJob.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(NotificationJob.status == status)
        stmt = stmt.order_by(NotificationJob.created_at.desc()).limit(limit)

        result = await session.execute(stmt)
        jobs = result.scalars().all()

        return [
            JobResponse(
                id=str(j.id),
                subscription_id=str(j.subscription_id),
                status=j.status,
                error_message=j.error_message,
                created_at=j.created_at.isoformat(),
                sent_at=j.sent_at.isoformat() if j.sent_at else None,
            )
            for j in jobs
        ]
