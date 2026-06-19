from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger
from packages.fleet.ruflo_client import RufloClient
from packages.fleet.swarm import SwarmManager, SwarmInstance, SwarmState, swarm_manager
from packages.fleet.worker import WorkerPool, JobSpec, JobResult, WorkerState, worker_pool
from packages.fleet.workspace import WorkspaceIsolator, workspace_isolator
from packages.fleet.iam import AgentIdentity, AgentRole, agent_iam
from packages.fleet.security_gateway import SecurityGateway, ThreatLevel, security_gateway
from packages.fleet.compliance import (
    ComplianceRegistry, RiskTier, DataDomain, AssetType,
    compliance_registry,
)

logger = get_logger("fleet_coordinator")


class FleetJobState(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    CHECKING = "checking"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class FleetJob(BaseModel):
    job_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    goal: str
    risk_tier: RiskTier = RiskTier.LOW
    budget_limit: float = 10.0
    workspace_ref: str | None = None
    swarm_name: str = "code-swarm"
    state: FleetJobState = FleetJobState.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    sub_jobs: list[JobResult] = Field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FleetStatus(BaseModel):
    active_swarms: int = 0
    active_workers: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    total_cost: float = 0.0


class FleetCoordinator:
    def __init__(self):
        self._jobs: dict[uuid.UUID, FleetJob] = {}
        self._ruflo_client: RufloClient | None = None

    @property
    def ruflo(self) -> RufloClient:
        if not self._ruflo_client:
            self._ruflo_client = RufloClient()
        return self._ruflo_client

    async def submit_job(
        self,
        goal: str,
        risk_tier: RiskTier = RiskTier.LOW,
        budget_limit: float = 10.0,
        swarm_name: str = "code-swarm",
        workspace_ref: str | None = None,
        require_approval: bool = False,
    ) -> FleetJob:
        compliance_check, requirements = compliance_registry.evaluate_gate(
            phase="pre_run",
            risk_tier=risk_tier,
        )

        if not compliance_check:
            return FleetJob(
                goal=goal,
                risk_tier=risk_tier,
                budget_limit=budget_limit,
                swarm_name=swarm_name,
                workspace_ref=workspace_ref,
                state=FleetJobState.BLOCKED,
                error=f"Compliance gate blocked: {requirements}",
            )

        job = FleetJob(
            goal=goal,
            risk_tier=risk_tier,
            budget_limit=budget_limit,
            swarm_name=swarm_name,
            workspace_ref=workspace_ref,
        )

        self._jobs[job.job_id] = job

        compliance_registry.log_audit_event(
            agent_id="fleet_coordinator",
            action="job_submitted",
            target=str(job.job_id),
            risk_tier=risk_tier,
            input_content=goal,
        )

        logger.info(f"Fleet job submitted: {job.job_id} ({swarm_name})")
        return job

    async def execute_job(self, job_id: uuid.UUID) -> FleetJob:
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.state = FleetJobState.PLANNING
        job.started_at = datetime.utcnow()

        try:
            swarm_config = swarm_manager.get_config(job.swarm_name)
            if not swarm_config:
                raise ValueError(f"Swarm config '{job.swarm_name}' not found")

            agent_identities = []
            for agent_def in swarm_config.agents:
                identity = agent_iam.create_identity(
                    name=f"{job.swarm_name}-{agent_def.role.value}",
                    role=AgentRole(agent_def.role.value),
                    allowed_tools=agent_def.tools,
                    allowed_environments=agent_def.allowed_environments,
                )
                agent_identities.append(identity)

            security_check = security_gateway.check_request(
                agent_id=str(job.job_id),
                content=job.goal,
            )

            if not security_check.passed:
                job.state = FleetJobState.BLOCKED
                job.error = security_check.blocked_reason
                return job

            job.state = FleetJobState.EXECUTING

            swarm_instance = await swarm_manager.create_swarm(
                config_name=job.swarm_name,
                budget_limit=job.budget_limit,
            )

            try:
                swarm_instance = await swarm_manager.initialize_swarm(
                    swarm_instance.swarm_id,
                    self.ruflo,
                )
            except Exception as e:
                logger.warning(f"Ruflo init failed, using local swarm: {e}")

            sub_jobs = []
            for agent_def in swarm_config.agents:
                sub_job = JobSpec(
                    goal=job.goal,
                    risk_tier=job.risk_tier.value,
                    budget_slice=job.budget_limit / len(swarm_config.agents),
                    workspace_ref=job.workspace_ref,
                )

                worker = await worker_pool.create_worker(agent_def, self.ruflo)
                result = await worker.execute(sub_job)
                sub_jobs.append(result)

            job.sub_jobs = sub_jobs

            successful = sum(
                1 for r in sub_jobs if r.status == WorkerState.COMPLETED
            )
            total = len(sub_jobs)

            if successful == total:
                job.state = FleetJobState.COMPLETED
            elif successful > 0:
                job.state = FleetJobState.COMPLETED
                job.metadata["partial_success"] = True
            else:
                job.state = FleetJobState.FAILED
                job.error = "All sub-jobs failed"

        except Exception as e:
            job.state = FleetJobState.FAILED
            job.error = str(e)
            logger.error(f"Fleet job {job_id} failed: {e}")

        finally:
            job.completed_at = datetime.utcnow()

            compliance_registry.log_audit_event(
                agent_id="fleet_coordinator",
                action="job_completed",
                target=str(job.job_id),
                risk_tier=job.risk_tier,
                output_content=str(job.state.value),
                result="success" if job.state == FleetJobState.COMPLETED else "failure",
            )

        return job

    async def execute_job_async(self, job_id: uuid.UUID) -> None:
        asyncio.create_task(self.execute_job(job_id))

    def get_job(self, job_id: uuid.UUID) -> FleetJob | None:
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        state: FleetJobState | None = None,
        limit: int = 50,
    ) -> list[FleetJob]:
        jobs = list(self._jobs.values())
        if state:
            jobs = [j for j in jobs if j.state == state]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)[:limit]

    def get_status(self) -> FleetStatus:
        jobs = list(self._jobs.values())
        workers = worker_pool.get_metrics()

        return FleetStatus(
            active_swarms=len(swarm_manager.list_active_swarms()),
            active_workers=workers.get("running", 0),
            pending_jobs=sum(1 for j in jobs if j.state == FleetJobState.PENDING),
            running_jobs=sum(1 for j in jobs if j.state in (
                FleetJobState.PLANNING, FleetJobState.EXECUTING,
                FleetJobState.CHECKING, FleetJobState.MERGING,
            )),
            completed_jobs=sum(1 for j in jobs if j.state == FleetJobState.COMPLETED),
            failed_jobs=sum(1 for j in jobs if j.state == FleetJobState.FAILED),
            total_cost=sum(
                sum(r.cost for r in j.sub_jobs)
                for j in jobs
            ),
        )

    async def cancel_job(self, job_id: uuid.UUID) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False

        if job.state in (FleetJobState.COMPLETED, FleetJobState.FAILED):
            return False

        job.state = FleetJobState.FAILED
        job.error = "Cancelled by user"
        job.completed_at = datetime.utcnow()
        return True


fleet_coordinator = FleetCoordinator()
