from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session
from packages.runtime.service import run_service
from packages.runtime.state import BudgetPolicy, RunStatus, TerminalState

router = APIRouter(prefix="/runs", tags=["runs"])


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
    async with get_session() as session:
        updates = []
        params: dict = {"run_id": run_id, "tenant_id": tenant_id}

        if status:
            updates.append("status = :status")
            params["status"] = status
        if terminal_state:
            updates.append("terminal_state = :terminal_state")
            params["terminal_state"] = terminal_state

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates.append("updated_at = NOW()")

        result = await session.execute(
            text(
                f"UPDATE runs SET {', '.join(updates)} WHERE run_id = :run_id AND tenant_id = :tenant_id RETURNING *"
            ),
            params,
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
