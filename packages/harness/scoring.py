from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session


class ScoreCategory(str, Enum):
    CORRECTNESS = "correctness"
    EFFICIENCY = "efficiency"
    GOVERNANCE = "governance"
    COST = "cost"
    SAFETY = "safety"
    OVERALL = "overall"


class ScenarioResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


class ScenarioScore(BaseModel):
    scenario_id: str
    scenario_name: str
    result: ScenarioResult
    score: float = 0.0
    max_score: float = 1.0
    details: dict = Field(default_factory=dict)
    duration_ms: float = 0.0


class RunScore(BaseModel):
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    scenario_scores: list[ScenarioScore] = Field(default_factory=list)
    category_scores: dict[ScoreCategory, float] = Field(default_factory=dict)
    overall_score: float = 0.0
    passed: bool = False
    gate_blocked: bool = False
    scored_at: datetime = Field(default_factory=datetime.utcnow)


class HarnessScorer:
    def __init__(self, passing_threshold: float = 0.7):
        self.passing_threshold = passing_threshold
        self._scenarios: dict[str, dict] = {}

    def register_scenario(
        self,
        scenario_id: str,
        name: str,
        category: ScoreCategory,
        max_score: float = 1.0,
        required: bool = True,
    ):
        self._scenarios[scenario_id] = {
            "name": name,
            "category": category,
            "max_score": max_score,
            "required": required,
        }

    async def score_run(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scenario_results: list[ScenarioScore],
    ) -> RunScore:
        category_scores: dict[ScoreCategory, list[float]] = {cat: [] for cat in ScoreCategory}

        for sr in scenario_results:
            scenario_def = self._scenarios.get(sr.scenario_id)
            if scenario_def:
                cat = scenario_def["category"]
                normalized = sr.score / sr.max_score if sr.max_score > 0 else 0
                category_scores[cat].append(normalized)

        avg_scores = {}
        for cat, scores in category_scores.items():
            if scores:
                avg_scores[cat] = sum(scores) / len(scores)

        overall_scores = [v for v in avg_scores.values() if v > 0]
        overall = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0

        passed = overall >= self.passing_threshold

        gate_blocked = False
        for sr in scenario_results:
            if sr.result == ScenarioResult.FAIL:
                scenario_def = self._scenarios.get(sr.scenario_id, {})
                if scenario_def.get("required", True):
                    gate_blocked = True
                    break

        run_score = RunScore(
            run_id=run_id,
            tenant_id=tenant_id,
            scenario_scores=scenario_results,
            category_scores=avg_scores,
            overall_score=overall,
            passed=passed,
            gate_blocked=gate_blocked,
        )

        await self._persist_score(run_score)
        return run_score

    async def _persist_score(self, score: RunScore) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO harness_scores
                        (score_id, run_id, tenant_id, scenario_results,
                         category_scores, overall_score, passed, gate_blocked, scored_at)
                    VALUES
                        (:score_id, :run_id, :tenant_id, :scenario_results,
                         :category_scores, :overall_score, :passed, :gate_blocked, :scored_at)
                    """
                ),
                {
                    "score_id": uuid.uuid4(),
                    "run_id": score.run_id,
                    "tenant_id": score.tenant_id,
                    "scenario_results": [s.model_dump() for s in score.scenario_scores],
                    "category_scores": {k.value: v for k, v in score.category_scores.items()},
                    "overall_score": score.overall_score,
                    "passed": score.passed,
                    "gate_blocked": score.gate_blocked,
                    "scored_at": score.scored_at,
                },
            )

    async def get_score(self, run_id: uuid.UUID) -> RunScore | None:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM harness_scores WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id},
            )
            row = result.mappings().first()
            if row:
                data = dict(row)
                return RunScore(
                    run_id=data["run_id"],
                    tenant_id=data["tenant_id"],
                    category_scores={
                        ScoreCategory(k): v
                        for k, v in (data.get("category_scores") or {}).items()
                    },
                    overall_score=data.get("overall_score", 0),
                    passed=data.get("passed", False),
                    gate_blocked=data.get("gate_blocked", False),
                )
            return None

    def list_scenarios(self) -> list[dict]:
        return [
            {"id": sid, **defn}
            for sid, defn in self._scenarios.items()
        ]


harness_scorer = HarnessScorer()
