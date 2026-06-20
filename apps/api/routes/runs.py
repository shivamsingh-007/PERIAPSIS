from __future__ import annotations

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.schemas.database import get_session
from packages.schemas.models import Run
from packages.runtime.service import run_service
from packages.runtime.state import BudgetPolicy, RunStatus, TerminalState

router = APIRouter(prefix="/runs", tags=["runs"])

ALLOWED_UPDATE_FIELDS = {"status", "terminal_state"}


class CreateRunRequest(BaseModel):
    goal: str
    tenant_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    risk_tier: str = "low"
    budget: BudgetPolicy = Field(default_factory=BudgetPolicy)


class RunResponse(BaseModel):
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    goal: str
    status: str
    terminal_state: str | None
    risk_tier: str
    created_at: datetime
    updated_at: datetime


class RunListResponse(BaseModel):
    runs: list[RunResponse]
    total: int


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(req: CreateRunRequest):
    run_id = uuid.uuid4()
    async with get_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO runs (run_id, tenant_id, goal, status, risk_tier, created_at, updated_at)
                VALUES (:run_id, :tenant_id, :goal, 'pending', :risk_tier, NOW(), NOW())
                """
            ),
            {
                "run_id": run_id,
                "tenant_id": req.tenant_id,
                "goal": req.goal,
                "risk_tier": req.risk_tier,
            },
        )
    return RunResponse(
        run_id=run_id,
        tenant_id=req.tenant_id,
        goal=req.goal,
        status="pending",
        terminal_state=None,
        risk_tier=req.risk_tier,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: uuid.UUID, tenant_id: uuid.UUID):
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT * FROM runs WHERE run_id = :run_id AND tenant_id = :tenant_id"
            ),
            {"run_id": run_id, "tenant_id": tenant_id},
        )
        row = result.mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        return RunResponse(
            run_id=row["run_id"],
            tenant_id=row["tenant_id"],
            goal=row["goal"],
            status=row["status"],
            terminal_state=row["terminal_state"],
            risk_tier=row["risk_tier"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@router.get("", response_model=RunListResponse)
async def list_runs(
    tenant_id: uuid.UUID,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    async with get_session() as session:
        where = "WHERE tenant_id = :tenant_id"
        params: dict = {"tenant_id": tenant_id, "limit": limit, "offset": offset}

        if status:
            where += " AND status = :status"
            params["status"] = status

        count_result = await session.execute(
            text(f"SELECT COUNT(*) as cnt FROM runs {where}"),
            params,
        )
        total = count_result.scalar()

        result = await session.execute(
            text(f"SELECT * FROM runs {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            params,
        )
        rows = result.mappings().all()

    return RunListResponse(
        runs=[
            RunResponse(
                run_id=r["run_id"],
                tenant_id=r["tenant_id"],
                goal=r["goal"],
                status=r["status"],
                terminal_state=r["terminal_state"],
                risk_tier=r["risk_tier"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ],
        total=total,
    )


@router.patch("/{run_id}", response_model=RunResponse)
async def update_run(
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    status: str | None = None,
    terminal_state: str | None = None,
):
    updates: dict[str, str] = {}
    if status:
        if status not in ALLOWED_UPDATE_FIELDS:
            raise HTTPException(status_code=400, detail=f"Invalid field: {status}")
        updates["status"] = status
    if terminal_state:
        if terminal_state not in ALLOWED_UPDATE_FIELDS:
            raise HTTPException(status_code=400, detail=f"Invalid field: {terminal_state}")
        updates["terminal_state"] = terminal_state

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    async with get_session() as session:
        stmt = (
            update(Run)
            .where(Run.run_id == run_id, Run.tenant_id == tenant_id)
            .values(**updates)
        )
        await session.execute(stmt)

        result = await session.execute(
            text(
                "SELECT * FROM runs WHERE run_id = :run_id AND tenant_id = :tenant_id"
            ),
            {"run_id": run_id, "tenant_id": tenant_id},
        )
        row = result.mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")

    return RunResponse(
        run_id=row["run_id"],
        tenant_id=row["tenant_id"],
        goal=row["goal"],
        status=row["status"],
        terminal_state=row["terminal_state"],
        risk_tier=row["risk_tier"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ExecuteRunRequest(BaseModel):
    goal: str
    tenant_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    budget: BudgetPolicy = Field(default_factory=BudgetPolicy)


class ExecuteRunResponse(BaseModel):
    run_id: str
    status: str
    terminal_state: str | None = None
    runtime_seconds: float | None = None
    error: str | None = None


@router.post("/execute", response_model=ExecuteRunResponse)
async def execute_run(req: ExecuteRunRequest):
    run_id = uuid.uuid4()

    async with get_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO runs (run_id, tenant_id, goal, status, risk_tier, created_at, updated_at)
                VALUES (:run_id, :tenant_id, :goal, 'pending', 'low', NOW(), NOW())
                """
            ),
            {"run_id": run_id, "tenant_id": req.tenant_id, "goal": req.goal},
        )

    result = await run_service.execute_run(
        run_id=run_id,
        tenant_id=req.tenant_id,
        goal=req.goal,
        budget=req.budget,
    )

    return ExecuteRunResponse(**result)


class MetricsSummary(BaseModel):
    total_runs: int = 0
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0
    cost_today_usd: float = 0.0
    status_distribution: list[dict] = []
    cost_by_day: list[dict] = []


@router.get("/metrics/summary", response_model=MetricsSummary)
async def metrics_summary(tenant_id: uuid.UUID | None = None):
    """Return aggregated run metrics for the dashboard."""
    async with get_session() as session:
        where = ""
        params: dict = {}
        if tenant_id:
            where = "WHERE tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id

        # Total runs
        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM runs {where}"), params
        )
        total_runs = count_result.scalar() or 0

        # Status distribution
        status_result = await session.execute(
            text(f"SELECT status, COUNT(*) as cnt FROM runs {where} GROUP BY status"), params
        )
        status_rows = status_result.all()
        status_distribution = [{"name": r[0], "value": r[1]} for r in status_rows]

        # Success rate
        completed = sum(r[1] for r in status_rows if r[0] in ("completed", "success"))
        success_rate = completed / total_runs if total_runs > 0 else 0.0

        # Cost from run_steps
        cost_result = await session.execute(
            text("SELECT SUM(cost_usd) FROM run_steps"), {}
        )
        total_cost = cost_result.scalar() or 0.0

        # Cost by day (last 7 days)
        cost_day_result = await session.execute(
            text(
                """
                SELECT TO_CHAR(created_at, 'Dy') as day, COALESCE(SUM(cost_usd), 0)
                FROM run_steps
                WHERE created_at >= NOW() - INTERVAL '7 days'
                GROUP BY day, DATE(created_at)
                ORDER BY DATE(created_at)
                """
            ),
            {},
        )
        cost_by_day = [{"name": r[0], "value": float(r[1])} for r in cost_day_result.all()]

        # Average latency
        lat_result = await session.execute(
            text("SELECT AVG(latency_ms) FROM run_steps WHERE latency_ms IS NOT NULL"), {}
        )
        avg_latency = float(lat_result.scalar() or 0)

        return MetricsSummary(
            total_runs=total_runs,
            avg_latency_ms=avg_latency,
            success_rate=success_rate,
            cost_today_usd=float(total_cost),
            status_distribution=status_distribution,
            cost_by_day=cost_by_day,
        )
