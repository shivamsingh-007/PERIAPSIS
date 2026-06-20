from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.scheduler.scheduler import (
    RunScheduler,
    ScheduleConfig,
    ScheduleType,
    run_scheduler,
)


@pytest.fixture
def scheduler():
    return RunScheduler()


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


class TestScheduleConfig:
    def test_create_config(self, tenant_id):
        config = ScheduleConfig(
            tenant_id=tenant_id,
            name="daily-report",
            schedule_type=ScheduleType.ONCE,
        )
        assert config.name == "daily-report"
        assert config.tenant_id == tenant_id
        assert config.active is True
        assert config.schedule_id is not None

    def test_defaults(self, tenant_id):
        config = ScheduleConfig(
            tenant_id=tenant_id,
            name="test",
            schedule_type=ScheduleType.INTERVAL,
        )
        assert config.interval_seconds is None
        assert config.cron_expression is None
        assert config.run_config == {}
        assert config.next_run is None
        assert config.last_run is None

    def test_interval_config(self, tenant_id):
        config = ScheduleConfig(
            tenant_id=tenant_id,
            name="interval",
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=60,
        )
        assert config.interval_seconds == 60

    def test_cron_config(self, tenant_id):
        config = ScheduleConfig(
            tenant_id=tenant_id,
            name="cron",
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * *",
        )
        assert config.cron_expression == "0 9 * * *"


class TestScheduleType:
    def test_values(self):
        assert ScheduleType.ONCE.value == "once"
        assert ScheduleType.INTERVAL.value == "interval"
        assert ScheduleType.CRON.value == "cron"


class TestRunScheduler:
    def test_init(self, scheduler):
        assert scheduler._running is False
        assert scheduler._task is None
        assert scheduler._callbacks == {}

    def test_register_callback(self, scheduler):
        async def my_callback(**kwargs):
            pass
        scheduler.register_callback("create_run", my_callback)
        assert "create_run" in scheduler._callbacks
        assert scheduler._callbacks["create_run"] is my_callback

    def test_register_multiple_callbacks(self, scheduler):
        async def cb1(**kwargs):
            pass
        async def cb2(**kwargs):
            pass
        scheduler.register_callback("cb1", cb1)
        scheduler.register_callback("cb2", cb2)
        assert len(scheduler._callbacks) == 2

    def test_calculate_next_cron(self, scheduler):
        before = datetime.utcnow()
        result = scheduler._calculate_next_cron("0 9 * * *")
        after = datetime.utcnow()
        assert isinstance(result, datetime)
        assert result > before
        assert result <= after + timedelta(hours=1, seconds=5)

    @pytest.mark.asyncio
    async def test_start_sets_running(self, scheduler):
        with patch.object(scheduler, "_scheduler_loop", new_callable=AsyncMock):
            await scheduler.start()
            assert scheduler._running is True
            assert scheduler._task is not None
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, scheduler):
        with patch.object(scheduler, "_scheduler_loop", new_callable=AsyncMock):
            await scheduler.start()
            task1 = scheduler._task
            await scheduler.start()
            assert scheduler._task is task1
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop(self, scheduler):
        with patch.object(scheduler, "_scheduler_loop", new_callable=AsyncMock):
            await scheduler.start()
            assert scheduler._running is True
            await scheduler.stop()
            assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_stop_without_start(self, scheduler):
        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_create_schedule_once(self, scheduler, tenant_id):
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            session.execute = AsyncMock()
            config = await scheduler.create_schedule(
                tenant_id=tenant_id,
                name="once-task",
                schedule_type=ScheduleType.ONCE,
                run_config={"goal": "test"},
            )
            assert config.name == "once-task"
            assert config.schedule_type == ScheduleType.ONCE
            assert config.next_run is None

    @pytest.mark.asyncio
    async def test_create_schedule_interval(self, scheduler, tenant_id):
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            session.execute = AsyncMock()
            config = await scheduler.create_schedule(
                tenant_id=tenant_id,
                name="interval-task",
                schedule_type=ScheduleType.INTERVAL,
                interval_seconds=120,
                run_config={"goal": "poll"},
            )
            assert config.interval_seconds == 120
            assert config.next_run is not None

    @pytest.mark.asyncio
    async def test_create_schedule_cron(self, scheduler, tenant_id):
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            session.execute = AsyncMock()
            config = await scheduler.create_schedule(
                tenant_id=tenant_id,
                name="cron-task",
                schedule_type=ScheduleType.CRON,
                cron_expression="0 * * * *",
                run_config={"goal": "hourly"},
            )
            assert config.cron_expression == "0 * * * *"

    @pytest.mark.asyncio
    async def test_list_schedules(self, scheduler, tenant_id):
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.mappings.return_value.all.return_value = [
                {"name": "s1", "tenant_id": str(tenant_id)},
            ]
            session.execute = AsyncMock(return_value=mock_result)
            schedules = await scheduler.list_schedules(tenant_id)
            assert len(schedules) == 1
            assert schedules[0]["name"] == "s1"

    @pytest.mark.asyncio
    async def test_delete_schedule(self, scheduler, tenant_id):
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.rowcount = 1
            session.execute = AsyncMock(return_value=mock_result)
            result = await scheduler.delete_schedule(uuid.uuid4(), tenant_id)
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_schedule_not_found(self, scheduler, tenant_id):
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.rowcount = 0
            session.execute = AsyncMock(return_value=mock_result)
            result = await scheduler.delete_schedule(uuid.uuid4(), tenant_id)
            assert result is False

    @pytest.mark.asyncio
    async def test_execute_schedule(self, scheduler, tenant_id):
        callback = AsyncMock()
        scheduler.register_callback("create_run", callback)
        schedule = {
            "schedule_id": uuid.uuid4(),
            "name": "test",
            "tenant_id": str(tenant_id),
            "run_config": json.dumps({"goal": "do something"}),
        }
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            session.execute = AsyncMock()
            await scheduler._execute_schedule(schedule)
            callback.assert_called_once_with(tenant_id=tenant_id, goal="do something")

    @pytest.mark.asyncio
    async def test_execute_schedule_no_callback(self, scheduler, tenant_id):
        schedule = {
            "schedule_id": uuid.uuid4(),
            "name": "test",
            "tenant_id": str(tenant_id),
            "run_config": json.dumps({"goal": "do something"}),
        }
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            session.execute = AsyncMock()
            await scheduler._execute_schedule(schedule)

    @pytest.mark.asyncio
    async def test_update_next_run_interval(self, scheduler):
        schedule = {
            "schedule_id": uuid.uuid4(),
            "schedule_type": "interval",
            "interval_seconds": 60,
        }
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            session.execute = AsyncMock()
            await scheduler._update_next_run(schedule)
            session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_update_next_run_cron(self, scheduler):
        schedule = {
            "schedule_id": uuid.uuid4(),
            "schedule_type": "cron",
            "cron_expression": "0 9 * * *",
        }
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            session.execute = AsyncMock()
            await scheduler._update_next_run(schedule)
            session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_update_next_run_once(self, scheduler):
        schedule = {
            "schedule_id": uuid.uuid4(),
            "schedule_type": "once",
        }
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            session.execute = AsyncMock()
            await scheduler._update_next_run(schedule)
            session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_update_last_run(self, scheduler):
        schedule = {"schedule_id": uuid.uuid4()}
        with patch("packages.scheduler.scheduler.get_session") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            session.execute = AsyncMock()
            await scheduler._update_last_run(schedule)
            session.execute.assert_called()
