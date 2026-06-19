from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

from packages.harness.scoring import ScenarioResult, ScenarioScore, harness_scorer


class EvalScenario(BaseModel):
    scenario_id: str
    name: str
    description: str = ""
    category: str = "general"
    max_score: float = 1.0
    required: bool = True
    timeout_seconds: float = 30.0


class EvalResult(BaseModel):
    scenario_id: str
    result: ScenarioResult
    score: float = 0.0
    details: dict = Field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


ScenarioFunc = Callable[..., Coroutine[Any, Any, EvalResult]]


class EvalRunner:
    def __init__(self):
        self._scenarios: dict[str, tuple[EvalScenario, ScenarioFunc]] = {}
        self._results: list[EvalResult] = []

    def register(
        self,
        scenario: EvalScenario,
        func: ScenarioFunc,
    ):
        self._scenarios[scenario.scenario_id] = (scenario, func)
        harness_scorer.register_scenario(
            scenario_id=scenario.scenario_id,
            name=scenario.name,
            category=harness_scorer._scenarios.get(scenario.scenario_id, {}).get("category", "general"),
            max_score=scenario.max_score,
            required=scenario.required,
        )

    async def run_scenario(
        self,
        scenario_id: str,
        **kwargs,
    ) -> EvalResult:
        if scenario_id not in self._scenarios:
            return EvalResult(
                scenario_id=scenario_id,
                result=ScenarioResult.SKIP,
                error=f"Scenario {scenario_id} not found",
            )

        scenario, func = self._scenarios[scenario_id]
        start = time.time()

        try:
            import asyncio
            result = await asyncio.wait_for(
                func(**kwargs),
                timeout=scenario.timeout_seconds,
            )
            duration = (time.time() - start) * 1000
            result.duration_ms = duration
            self._results.append(result)
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = EvalResult(
                scenario_id=scenario_id,
                result=ScenarioResult.FAIL,
                error=str(e),
                duration_ms=duration,
            )
            self._results.append(result)
            return result

    async def run_all(self, **kwargs) -> list[EvalResult]:
        results = []
        for scenario_id in self._scenarios:
            result = await self.run_scenario(scenario_id, **kwargs)
            results.append(result)
        return results

    def get_results(self) -> list[EvalResult]:
        return self._results

    def get_summary(self) -> dict:
        total = len(self._results)
        passed = sum(1 for r in self._results if r.result == ScenarioResult.PASS)
        failed = sum(1 for r in self._results if r.result == ScenarioResult.FAIL)
        warned = sum(1 for r in self._results if r.result == ScenarioResult.WARN)
        skipped = sum(1 for r in self._results if r.result == ScenarioResult.SKIP)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "warned": warned,
            "skipped": skipped,
            "pass_rate": passed / total if total > 0 else 0.0,
        }


eval_runner = EvalRunner()
