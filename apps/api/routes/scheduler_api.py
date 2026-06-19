from __future__ import annotations

import uuid
from pydantic import BaseModel
from fastapi import APIRouter

from packages.scheduler.scheduler import run_scheduler, ScheduleType

router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleCreateRequest(BaseModel):
    tenant_id: uuid.UUID
    name: str
    schedule_type: str
    run_config: dict
    interval_seconds: int | None = None
    cron_expression: str | None = None


class ScheduleResponse(BaseModel):
    status: str
    schedule_id: uuid.UUID | None = None
    message: str = ""


@router.post("/", response_model=ScheduleResponse)
async def create_schedule(request: ScheduleCreateRequest):
    config = await run_scheduler.create_schedule(
        tenant_id=request.tenant_id,
        name=request.name,
        schedule_type=ScheduleType(request.schedule_type),
        run_config=request.run_config,
        interval_seconds=request.interval_seconds,
        cron_expression=request.cron_expression,
    )
    return ScheduleResponse(
        status="created",
        schedule_id=config.schedule_id,
        message=f"Schedule '{config.name}' created",
    )


@router.get("/{tenant_id}")
async def list_schedules(tenant_id: uuid.UUID):
    schedules = await run_scheduler.list_schedules(tenant_id)
    return {"schedules": schedules, "count": len(schedules)}


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: uuid.UUID, tenant_id: uuid.UUID):
    deleted = await run_scheduler.delete_schedule(schedule_id, tenant_id)
    return {"deleted": deleted}


@router.post("/start")
async def start_scheduler():
    await run_scheduler.start()
    return {"status": "started"}


@router.post("/stop")
async def stop_scheduler():
    await run_scheduler.stop()
    return {"status": "stopped"}
