from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session
from packages.logging.structured import get_logger

logger = get_logger("scheduler")


class ScheduleType(str, Enum):
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"


class ScheduleConfig(BaseModel):
    schedule_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    name: str
    schedule_type: ScheduleType
    interval_seconds: int | None = None
    cron_expression: str | None = None
    run_config: dict = Field(default_factory=dict)
    active: bool = True
    next_run: datetime | None = None
    last_run: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RunScheduler:
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._callbacks: dict[str, Callable] = {}

    def register_callback(self, name: str, callback: Callable):
        self._callbacks[name] = callback

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _scheduler_loop(self):
        while self._running:
            try:
                await self._check_and_run_due_schedules()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(30)

    async def _check_and_run_due_schedules(self):
        now = datetime.utcnow()
        schedules = await self._get_due_schedules(now)

        for schedule in schedules:
            try:
                await self._execute_schedule(schedule)
                await self._update_next_run(schedule)
            except Exception as e:
                logger.error(f"Schedule execution failed: {schedule['name']}: {e}")

    async def _get_due_schedules(self, now: datetime) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM run_schedules
                    WHERE active = true
                      AND (next_run IS NULL OR next_run <= :now)
                    """
                ),
                {"now": now},
            )
            return [dict(row) for row in result.mappings().all()]

    async def _execute_schedule(self, schedule: dict):
        logger.info(f"Executing schedule: {schedule['name']}")
        run_config = json.loads(schedule.get("run_config", "{}"))

        callback = self._callbacks.get("create_run")
        if callback:
            await callback(
                tenant_id=uuid.UUID(schedule["tenant_id"]),
                **run_config,
            )

        await self._update_last_run(schedule)

    async def _update_next_run(self, schedule: dict):
        schedule_type = schedule.get("schedule_type")
        interval = schedule.get("interval_seconds")

        if schedule_type == "interval" and interval:
            next_run = datetime.utcnow() + timedelta(seconds=interval)
        elif schedule_type == "cron" and schedule.get("cron_expression"):
            next_run = self._calculate_next_cron(schedule["cron_expression"])
        else:
            next_run = None

        async with get_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE run_schedules
                    SET next_run = :next_run
                    WHERE schedule_id = :schedule_id
                    """
                ),
                {"schedule_id": schedule["schedule_id"], "next_run": next_run},
            )

    async def _update_last_run(self, schedule: dict):
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE run_schedules
                    SET last_run = NOW()
                    WHERE schedule_id = :schedule_id
                    """
                ),
                {"schedule_id": schedule["schedule_id"]},
            )

    def _calculate_next_cron(self, cron_expr: str) -> datetime:
        return datetime.utcnow() + timedelta(hours=1)

    async def create_schedule(
        self,
        tenant_id: uuid.UUID,
        name: str,
        schedule_type: ScheduleType,
        run_config: dict,
        interval_seconds: int | None = None,
        cron_expression: str | None = None,
    ) -> ScheduleConfig:
        config = ScheduleConfig(
            tenant_id=tenant_id,
            name=name,
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            cron_expression=cron_expression,
            run_config=run_config,
        )

        if schedule_type == ScheduleType.INTERVAL and interval_seconds:
            config.next_run = datetime.utcnow() + timedelta(seconds=interval_seconds)

        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO run_schedules
                        (schedule_id, tenant_id, name, schedule_type, interval_seconds,
                         cron_expression, run_config, active, next_run, created_at)
                    VALUES
                        (:schedule_id, :tenant_id, :name, :schedule_type, :interval_seconds,
                         :cron_expression, :run_config, :active, :next_run, NOW())
                    """
                ),
                {
                    "schedule_id": config.schedule_id,
                    "tenant_id": tenant_id,
                    "name": name,
                    "schedule_type": schedule_type.value,
                    "interval_seconds": interval_seconds,
                    "cron_expression": cron_expression,
                    "run_config": json.dumps(run_config),
                    "active": True,
                    "next_run": config.next_run,
                },
            )

        logger.info(f"Schedule created: {config.name}")
        return config

    async def list_schedules(self, tenant_id: uuid.UUID) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM run_schedules
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at DESC
                    """
                ),
                {"tenant_id": tenant_id},
            )
            return [dict(row) for row in result.mappings().all()]

    async def delete_schedule(self, schedule_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    DELETE FROM run_schedules
                    WHERE schedule_id = :schedule_id AND tenant_id = :tenant_id
                    """
                ),
                {"schedule_id": schedule_id, "tenant_id": tenant_id},
            )
            return result.rowcount > 0


run_scheduler = RunScheduler()
