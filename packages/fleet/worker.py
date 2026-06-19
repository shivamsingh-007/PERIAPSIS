from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger
from packages.fleet.swarm import AgentDefinition, AgentRole, SwarmInstance

logger = get_logger("worker")


class WorkerState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class JobSpec(BaseModel):
    job_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    goal: str
    risk_tier: str = "low"
    budget_slice: float = 1.0
    workspace_ref: str | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    required_roles: list[AgentRole] = Field(default_factory=list)
    timeout_seconds: int = 300
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobResult(BaseModel):
    job_id: uuid.UUID
    worker_id: str
    status: WorkerState
    output: Any = None
    error: str | None = None
    cost: float = 0.0
    steps_taken: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    artifacts: list[dict] = Field(default_factory=list)


class WorkerAgent:
    def __init__(
        self,
        worker_id: str,
        agent_def: AgentDefinition,
        ruflo_client: Any,
    ):
        self.worker_id = worker_id
        self.agent_def = agent_def
        self.ruflo_client = ruflo_client
        self.state = WorkerState.IDLE
        self.current_job: JobSpec | None = None

    async def execute(self, job: JobSpec) -> JobResult:
        self.state = WorkerState.RUNNING
        self.current_job = job
        started_at = datetime.utcnow()

        result = JobResult(
            job_id=job.job_id,
            worker_id=self.worker_id,
            status=WorkerState.RUNNING,
            started_at=started_at,
        )

        try:
            task_prompt = self._build_task_prompt(job)

            ruflo_result = await self.ruflo_client.agent_spawn(
                role=self.agent_def.role.value,
                task=task_prompt,
            )

            output = ruflo_result.get("output", ruflo_result)
            result.output = output
            result.status = WorkerState.COMPLETED
            result.steps_taken = ruflo_result.get("steps", 1)
            result.cost = ruflo_result.get("cost", 0.0)

            await self.ruflo_client.memory_store(
                key=f"worker:{self.worker_id}:last_result",
                value=str(output)[:1000],
                namespace="worker_results",
            )

        except Exception as e:
            result.status = WorkerState.FAILED
            result.error = str(e)
            logger.error(f"Worker {self.worker_id} failed: {e}")

        finally:
            result.completed_at = datetime.utcnow()
            self.state = WorkerState.IDLE
            self.current_job = None

        return result

    def _build_task_prompt(self, job: JobSpec) -> str:
        parts = [
            f"Role: {self.agent_def.role.value}",
            f"Goal: {job.goal}",
            f"Risk Tier: {job.risk_tier}",
            f"Budget: ${job.budget_slice:.2f}",
        ]

        if job.input_data:
            parts.append(f"Input: {job.input_data}")

        if self.agent_def.system_prompt:
            parts.append(f"\nInstructions: {self.agent_def.system_prompt}")

        return "\n".join(parts)


class WorkerPool:
    def __init__(self):
        self._workers: dict[str, WorkerAgent] = {}
        self._job_queue: asyncio.Queue[JobSpec] = asyncio.Queue()
        self._results: dict[uuid.UUID, JobResult] = {}

    async def create_worker(
        self,
        agent_def: AgentDefinition,
        ruflo_client: Any,
    ) -> WorkerAgent:
        worker_id = f"{agent_def.role.value}-{uuid.uuid4().hex[:8]}"
        worker = WorkerAgent(worker_id, agent_def, ruflo_client)
        self._workers[worker_id] = worker
        logger.info(f"Created worker: {worker_id}")
        return worker

    async def submit_job(
        self,
        job: JobSpec,
        swarm: SwarmInstance,
        ruflo_client: Any,
    ) -> JobResult:
        available_workers = [
            w for w in self._workers.values()
            if w.state == WorkerState.IDLE
        ]

        if not available_workers:
            for agent_def in swarm.config.agents:
                if not job.required_roles or agent_def.role in job.required_roles:
                    worker = await self.create_worker(agent_def, ruflo_client)
                    available_workers.append(worker)

        if not available_workers:
            return JobResult(
                job_id=job.job_id,
                worker_id="none",
                status=WorkerState.FAILED,
                error="No available workers",
            )

        worker = available_workers[0]
        result = await worker.execute(job)
        self._results[job.job_id] = result
        return result

    async def submit_parallel(
        self,
        jobs: list[JobSpec],
        swarm: SwarmInstance,
        ruflo_client: Any,
    ) -> list[JobResult]:
        tasks = [
            self.submit_job(job, swarm, ruflo_client)
            for job in jobs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(JobResult(
                    job_id=jobs[i].job_id,
                    worker_id="parallel",
                    status=WorkerState.FAILED,
                    error=str(result),
                ))
            else:
                final_results.append(result)

        return final_results

    def get_result(self, job_id: uuid.UUID) -> JobResult | None:
        return self._results.get(job_id)

    def get_worker(self, worker_id: str) -> WorkerAgent | None:
        return self._workers.get(worker_id)

    def list_workers(self) -> list[dict]:
        return [
            {
                "worker_id": w.worker_id,
                "role": w.agent_def.role.value,
                "state": w.state.value,
                "current_job": w.current_job.job_id if w.current_job else None,
            }
            for w in self._workers.values()
        ]

    def get_metrics(self) -> dict:
        total = len(self._workers)
        idle = sum(1 for w in self._workers.values() if w.state == WorkerState.IDLE)
        running = sum(1 for w in self._workers.values() if w.state == WorkerState.RUNNING)

        return {
            "total_workers": total,
            "idle": idle,
            "running": running,
            "total_jobs_completed": len(self._results),
            "successful_jobs": sum(
                1 for r in self._results.values()
                if r.status == WorkerState.COMPLETED
            ),
            "failed_jobs": sum(
                1 for r in self._results.values()
                if r.status == WorkerState.FAILED
            ),
        }


worker_pool = WorkerPool()
