from __future__ import annotations

import uuid
from pydantic import BaseModel
from fastapi import APIRouter

from packages.harness.scoring import harness_scorer, ScenarioScore, ScenarioResult
from packages.harness.metrics import metrics_collector
from packages.harness.gate import ship_gate

router = APIRouter(prefix="/harness", tags=["harness"])


class ScoreRunRequest(BaseModel):
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    scenario_results: list[dict]


class MetricsQueryRequest(BaseModel):
    metric_name: str
    tenant_id: uuid.UUID | None = None
    since: str | None = None
    limit: int = 100


@router.post("/score")
async def score_run(request: ScoreRunRequest):
    scenario_scores = [
        ScenarioScore(
            scenario_id=s["scenario_id"],
            scenario_name=s.get("scenario_name", ""),
            result=ScenarioResult(s.get("result", "pass")),
            score=s.get("score", 1.0),
            max_score=s.get("max_score", 1.0),
            details=s.get("details", {}),
        )
        for s in request.scenario_results
    ]

    run_score = await harness_scorer.score_run(
        run_id=request.run_id,
        tenant_id=request.tenant_id,
        scenario_results=scenario_scores,
    )

    gate_block = await ship_gate.evaluate(run_score)

    return {
        "score": {
            "overall": run_score.overall_score,
            "passed": run_score.passed,
            "categories": {k.value: v for k, v in run_score.category_scores.items()},
        },
        "gate": {
            "decision": gate_block.decision.value,
            "reason": gate_block.reason,
            "blocked": gate_block.decision.value == "block",
        },
    }


@router.get("/scenarios")
async def list_scenarios():
    return {"scenarios": harness_scorer.list_scenarios()}


@router.get("/score/{run_id}")
async def get_run_score(run_id: uuid.UUID):
    score = await harness_scorer.get_score(run_id)
    if not score:
        return {"error": "Score not found"}
    return {
        "overall": score.overall_score,
        "passed": score.passed,
        "gate_blocked": score.gate_blocked,
        "categories": {k.value: v for k, v in score.category_scores.items()},
    }


@router.post("/metrics/query")
async def query_metrics(request: MetricsQueryRequest):
    from datetime import datetime
    since = datetime.fromisoformat(request.since) if request.since else None

    results = await metrics_collector.query_metric(
        metric_name=request.metric_name,
        tenant_id=request.tenant_id,
        since=since,
        limit=request.limit,
    )
    return {"metrics": results, "count": len(results)}


@router.post("/metrics/aggregate")
async def aggregate_metrics(request: MetricsQueryRequest):
    from datetime import datetime
    since = datetime.fromisoformat(request.since) if request.since else None

    result = await metrics_collector.aggregate_metric(
        metric_name=request.metric_name,
        tenant_id=request.tenant_id,
        since=since,
    )
    return {"aggregation": result}


@router.get("/gate/history/{tenant_id}")
async def get_gate_history(tenant_id: uuid.UUID, limit: int = 50):
    history = await ship_gate.get_gate_history(tenant_id, limit)
    return {"history": history, "count": len(history)}


@router.get("/gate/blocked/{run_id}")
async def check_gate_blocked(run_id: uuid.UUID):
    blocked = await ship_gate.check_if_blocked(run_id)
    return {"blocked": blocked}


@router.post("/eval/run-all")
async def run_all_evals():
    from packages.harness.eval_runner import eval_runner
    results = await eval_runner.run_all()
    summary = eval_runner.get_summary()
    return {
        "results": [r.model_dump() for r in results],
        "summary": summary,
    }


@router.get("/eval/results")
async def get_eval_results():
    from packages.harness.eval_runner import eval_runner
    results = eval_runner.get_results()
    summary = eval_runner.get_summary()
    return {
        "results": [r.model_dump() for r in results],
        "summary": summary,
    }
