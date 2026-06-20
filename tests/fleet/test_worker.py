from __future__ import annotations

import uuid

import pytest

from packages.fleet.worker import (
    JobResult,
    JobSpec,
    WorkerAgent,
    WorkerPool,
    WorkerState,
)


@pytest.fixture
def pool():
    return WorkerPool()


@pytest.fixture
def sample_job():
    return JobSpec(
        job_id=uuid.uuid4(),
        goal="test goal",
        risk_tier="low",
        budget_slice=1.0,
    )


class TestWorkerState:
    def test_all_variants(self):
        assert len(list(WorkerState)) == 6

    def test_values(self):
        assert WorkerState.IDLE.value == "idle"
        assert WorkerState.RUNNING.value == "running"
        assert WorkerState.COMPLETED.value == "completed"
        assert WorkerState.FAILED.value == "failed"


class TestJobSpec:
    def test_create_job(self):
        spec = JobSpec(
            job_id=uuid.uuid4(),
            goal="test",
            risk_tier="low",
            budget_slice=1.0,
        )
        assert spec.goal == "test"
        assert spec.timeout_seconds == 300

    def test_job_defaults(self):
        spec = JobSpec(
            job_id=uuid.uuid4(),
            goal="test",
            risk_tier="low",
            budget_slice=1.0,
        )
        assert spec.input_data == {}
        assert spec.required_roles == []
        assert spec.metadata == {}


class TestJobResult:
    def test_create_result(self):
        result = JobResult(
            job_id=uuid.uuid4(),
            worker_id="worker-1",
            status="completed",
            output={"result": "done"},
        )
        assert result.status == "completed"
        assert result.output == {"result": "done"}

    def test_result_defaults(self):
        result = JobResult(
            job_id=uuid.uuid4(),
            worker_id="w1",
            status="completed",
        )
        assert result.error is None
        assert result.cost == 0.0
        assert result.artifacts == []


class TestWorkerPool:
    def test_get_metrics_empty(self, pool):
        metrics = pool.get_metrics()
        assert "total_workers" in metrics
        assert metrics["total_workers"] == 0

    def test_list_workers_empty(self, pool):
        workers = pool.list_workers()
        assert workers == []

    def test_get_worker_not_found(self, pool):
        result = pool.get_worker(uuid.uuid4())
        assert result is None

    def test_get_result_not_found(self, pool):
        result = pool.get_result(uuid.uuid4())
        assert result is None
