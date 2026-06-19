from __future__ import annotations

import uuid
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from packages.fleet.coordinator import fleet_coordinator, FleetJobState
from packages.fleet.swarm import swarm_manager, SwarmConfig, SwarmTopology, AgentDefinition, AgentRole
from packages.fleet.worker import worker_pool
from packages.fleet.workspace import workspace_isolator
from packages.fleet.iam import agent_iam, AgentRole as IAMRole
from packages.fleet.security_gateway import security_gateway
from packages.fleet.compliance import compliance_registry, RiskTier, AssetType, DataDomain, RegulatoryScope
from packages.security.rls import get_current_tenant

router = APIRouter(prefix="/api/v1/fleet", tags=["fleet"])


class SubmitJobRequest(BaseModel):
    goal: str
    risk_tier: str = "low"
    budget_limit: float = 10.0
    swarm_name: str = "code-swarm"
    workspace_ref: str | None = None


@router.post("/jobs")
async def submit_job(req: SubmitJobRequest, tenant_id: uuid.UUID = Depends(get_current_tenant)):
    risk = RiskTier(req.risk_tier) if req.risk_tier in RiskTier.__members__.values() else RiskTier.LOW
    job = await fleet_coordinator.submit_job(
        goal=req.goal,
        risk_tier=risk,
        budget_limit=req.budget_limit,
        swarm_name=req.swarm_name,
        workspace_ref=req.workspace_ref,
    )
    return {"job_id": str(job.job_id), "state": job.state.value}


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, tenant_id: uuid.UUID = Depends(get_current_tenant)):
    job = fleet_coordinator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump()


@router.get("/jobs")
async def list_jobs(
    state: str | None = None,
    limit: int = 50,
    tenant_id: uuid.UUID = Depends(get_current_tenant),
):
    fleet_state = FleetJobState(state) if state and state in FleetJobState.__members__.values() else None
    jobs = fleet_coordinator.list_jobs(state=fleet_state, limit=limit)
    return {"jobs": [j.model_dump() for j in jobs]}


@router.post("/jobs/{job_id}/execute")
async def execute_job(job_id: uuid.UUID, tenant_id: uuid.UUID = Depends(get_current_tenant)):
    job = await fleet_coordinator.execute_job(job_id)
    return job.model_dump()


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: uuid.UUID, tenant_id: uuid.UUID = Depends(get_current_tenant)):
    cancelled = await fleet_coordinator.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Cannot cancel job")
    return {"status": "cancelled"}


@router.get("/status")
async def get_fleet_status(tenant_id: uuid.UUID = Depends(get_current_tenant)):
    return fleet_coordinator.get_status().model_dump()


@router.get("/swarms")
async def list_swarm_configs(tenant_id: uuid.UUID = Depends(get_current_tenant)):
    configs = swarm_manager.list_configs()
    return {"swarms": [c.model_dump() for c in configs]}


class CreateSwarmRequest(BaseModel):
    name: str
    topology: str = "hierarchical"
    agents: list[dict] = Field(default_factory=list)
    budget_limit: float = 10.0


@router.post("/swarms")
async def create_swarm_config(req: CreateSwarmRequest, tenant_id: uuid.UUID = Depends(get_current_tenant)):
    agents = [AgentDefinition(**a) for a in req.agents]
    config = SwarmConfig(
        name=req.name,
        topology=SwarmTopology(req.topology),
        agents=agents,
        budget_limit=req.budget_limit,
    )
    swarm_manager.register_config(config)
    return {"status": "registered", "name": req.name}


@router.get("/workers")
async def list_workers(tenant_id: uuid.UUID = Depends(get_current_tenant)):
    return {"workers": worker_pool.list_workers(), "metrics": worker_pool.get_metrics()}


@router.get("/worktrees")
async def list_worktrees(tenant_id: uuid.UUID = Depends(get_current_tenant)):
    return {"worktrees": workspace_isolator.list_worktrees()}


@router.get("/identity")
async def list_identities(tenant_id: uuid.UUID = Depends(get_current_tenant)):
    return {"identities": agent_iam.list_identities()}


@router.get("/security/rate-status/{agent_id}")
async def get_rate_status(agent_id: str, tenant_id: uuid.UUID = Depends(get_current_tenant)):
    return security_gateway.get_rate_status(agent_id)


@router.get("/compliance/report")
async def get_compliance_report(tenant_id: uuid.UUID = Depends(get_current_tenant)):
    return compliance_registry.generate_compliance_report()


@router.get("/compliance/audit-log")
async def get_audit_log(
    agent_id: str | None = None,
    limit: int = 100,
    tenant_id: uuid.UUID = Depends(get_current_tenant),
):
    events = compliance_registry.get_audit_log(agent_id=agent_id, limit=limit)
    return {"events": [e.model_dump() for e in events]}
