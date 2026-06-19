from __future__ import annotations

import uuid
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from packages.resilience.circuit_breaker import circuit_breaker_registry, CircuitBreakerConfig
from packages.harness.cost_prediction import cost_predictor, CostPrediction
from packages.runtime.replay import run_replayer, ReplayConfig, ReplayResult
from packages.security.rls import get_current_tenant

router = APIRouter(prefix="/api/v1/resilience", tags=["resilience"])


class CircuitBreakerStatusResponse(BaseModel):
    breakers: list[dict]


@router.get("/circuit-breakers", response_model=CircuitBreakerStatusResponse)
async def get_circuit_breakers(tenant_id: uuid.UUID = Depends(get_current_tenant)):
    breakers = circuit_breaker_registry.get_all()
    return CircuitBreakerStatusResponse(breakers=breakers)


class CircuitBreakerResetRequest(BaseModel):
    service_name: str


@router.post("/circuit-breakers/reset")
async def reset_circuit_breaker(
    req: CircuitBreakerResetRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant),
):
    breaker = circuit_breaker_registry.get_or_create(req.service_name)
    breaker.reset()
    return {"status": "reset", "service": req.service_name}


class CostPredictionRequest(BaseModel):
    goal: str
    estimated_steps: int = 5
    risk_tier: str = "low"


@router.post("/cost-predict", response_model=CostPrediction)
async def predict_cost(
    req: CostPredictionRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant),
):
    prediction = await cost_predictor.predict(
        tenant_id=tenant_id,
        goal=req.goal,
        estimated_steps=req.estimated_steps,
        risk_tier=req.risk_tier,
    )
    return prediction


class ReplayRequest(BaseModel):
    original_run_id: uuid.UUID
    modified_state: dict | None = None
    skip_steps: list[int] = Field(default_factory=list)
    override_goal: str | None = None
    override_budget: float | None = None


@router.post("/replay", response_model=ReplayResult)
async def create_replay(
    req: ReplayRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant),
):
    config = ReplayConfig(
        original_run_id=req.original_run_id,
        modified_state=req.modified_state,
        skip_steps=req.skip_steps,
        override_goal=req.override_goal,
        override_budget=req.override_budget,
    )
    result = await run_replayer.create_replay(tenant_id=tenant_id, config=config)
    return result


@router.post("/replay/{replay_id}/execute", response_model=ReplayResult)
async def execute_replay(
    replay_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant),
):
    result = await run_replayer.execute_replay(replay_id=replay_id, tenant_id=tenant_id)
    return result


@router.get("/replays")
async def list_replays(tenant_id: uuid.UUID = Depends(get_current_tenant)):
    replays = await run_replayer.list_replays(tenant_id=tenant_id)
    return {"replays": [r.model_dump() for r in replays]}
