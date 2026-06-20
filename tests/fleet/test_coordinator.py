from __future__ import annotations

import uuid

import pytest

from packages.fleet.coordinator import (
    FleetCoordinator,
    FleetJob,
    FleetJobState,
    FleetStatus,
)


@pytest.fixture
def coordinator():
    return FleetCoordinator()


class TestFleetJobState:
    def test_all_variants(self):
        assert len(list(FleetJobState)) == 8

    def test_values(self):
        assert FleetJobState.PENDING.value == "pending"
        assert FleetJobState.COMPLETED.value == "completed"
        assert FleetJobState.FAILED.value == "failed"
        assert FleetJobState.BLOCKED.value == "blocked"


class TestFleetJob:
    def test_create_job(self):
        job = FleetJob(
            job_id=uuid.uuid4(),
            goal="test goal",
            risk_tier="low",
            budget_limit=5.0,
        )
        assert job.goal == "test goal"
        assert job.state == FleetJobState.PENDING

    def test_job_defaults(self):
        job = FleetJob(
            job_id=uuid.uuid4(),
            goal="test",
            risk_tier="low",
            budget_limit=10.0,
        )
        assert job.sub_jobs == []
        assert job.metadata == {}


class TestFleetStatus:
    def test_create_status(self):
        status = FleetStatus(
            active_swarms=0,
            active_workers=0,
            pending_jobs=0,
            running_jobs=0,
            completed_jobs=0,
            failed_jobs=0,
            total_cost=0.0,
        )
        assert status.total_cost == 0.0


class TestFleetCoordinator:
    @pytest.mark.asyncio
    async def test_submit_job(self, coordinator):
        job = await coordinator.submit_job(
            goal="test goal",
            risk_tier="low",
            budget_limit=5.0,
        )
        assert job is not None
        assert job.goal == "test goal"
        assert job.state == FleetJobState.PENDING

    @pytest.mark.asyncio
    async def test_get_job(self, coordinator):
        job = await coordinator.submit_job(
            goal="test",
            risk_tier="low",
            budget_limit=5.0,
        )
        retrieved = coordinator.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, coordinator):
        result = coordinator.get_job(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_jobs(self, coordinator):
        await coordinator.submit_job(goal="g1", risk_tier="low", budget_limit=5.0)
        await coordinator.submit_job(goal="g2", risk_tier="medium", budget_limit=10.0)
        jobs = coordinator.list_jobs()
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_by_state(self, coordinator):
        await coordinator.submit_job(goal="g1", risk_tier="low", budget_limit=5.0)
        jobs = coordinator.list_jobs(state=FleetJobState.PENDING)
        assert len(jobs) == 1

    @pytest.mark.asyncio
    async def test_get_status(self, coordinator):
        await coordinator.submit_job(goal="g1", risk_tier="low", budget_limit=5.0)
        status = coordinator.get_status()
        assert isinstance(status, FleetStatus)
        assert status.pending_jobs >= 1

    @pytest.mark.asyncio
    async def test_cancel_job(self, coordinator):
        job = await coordinator.submit_job(goal="g1", risk_tier="low", budget_limit=5.0)
        result = await coordinator.cancel_job(job.job_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, coordinator):
        result = await coordinator.cancel_job(uuid.uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_multiple_jobs(self, coordinator):
        for i in range(5):
            await coordinator.submit_job(goal=f"goal-{i}", risk_tier="low", budget_limit=5.0)
        jobs = coordinator.list_jobs()
        assert len(jobs) == 5

    @pytest.mark.asyncio
    async def test_job_with_swarm(self, coordinator):
        job = await coordinator.submit_job(
            goal="test",
            risk_tier="low",
            budget_limit=5.0,
            swarm_name="code-swarm",
        )
        assert job.swarm_name == "code-swarm"
