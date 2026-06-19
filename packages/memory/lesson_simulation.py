from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("lesson_simulation")


class SimulationResult(BaseModel):
    simulation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    lesson_id: str
    scenario_id: str
    passed: bool
    actual_outcome: str
    expected_outcome: str
    improvement: float = 0.0
    execution_time_ms: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EvalScenario(BaseModel):
    scenario_id: str
    name: str
    description: str
    input_data: dict = Field(default_factory=dict)
    expected_output: str = ""
    expected_behavior: list[str] = Field(default_factory=list)
    risk_tier: str = "low"


DEFAULT_SCENARIOS: list[EvalScenario] = [
    EvalScenario(
        scenario_id="basic_task",
        name="Basic Task Completion",
        description="Simple task that should complete without errors",
        expected_behavior=["completes_within_budget", "no_errors"],
    ),
    EvalScenario(
        scenario_id="error_recovery",
        name="Error Recovery",
        description="Task that encounters and recovers from errors",
        expected_behavior=["recovers_from_error", "maintains_progress"],
    ),
    EvalScenario(
        scenario_id="budget_constraint",
        name="Budget Constraint",
        description="Task that must complete within strict budget",
        expected_behavior=["stays_within_budget", "completes_task"],
    ),
    EvalScenario(
        scenario_id="multi_step",
        name="Multi-Step Planning",
        description="Complex task requiring planning and execution",
        expected_behavior=["creates_plan", "follows_plan", "validates_output"],
    ),
]


class LessonSimulator:
    def __init__(self):
        self._scenarios: dict[str, EvalScenario] = {
            s.scenario_id: s for s in DEFAULT_SCENARIOS
        }
        self._results: list[SimulationResult] = []

    def register_scenario(self, scenario: EvalScenario) -> None:
        self._scenarios[scenario.scenario_id] = scenario

    async def simulate_lesson(
        self,
        lesson_id: str,
        lesson_content: dict,
        scenario_id: str | None = None,
    ) -> SimulationResult:
        scenarios = (
            [self._scenarios[scenario_id]]
            if scenario_id and scenario_id in self._scenarios
            else list(self._scenarios.values())
        )

        if not scenarios:
            raise ValueError("No scenarios available for simulation")

        scenario = scenarios[0]
        start_time = datetime.utcnow()

        passed = await self._evaluate_lesson_against_scenario(lesson_content, scenario)

        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        result = SimulationResult(
            lesson_id=lesson_id,
            scenario_id=scenario.scenario_id,
            passed=passed,
            actual_outcome="passed" if passed else "failed",
            expected_outcome=scenario.expected_behavior[0] if scenario.expected_behavior else "completes",
            improvement=1.0 if passed else 0.0,
            execution_time_ms=execution_time,
        )

        self._results.append(result)
        return result

    async def simulate_all(
        self,
        lesson_id: str,
        lesson_content: dict,
    ) -> list[SimulationResult]:
        results = []
        for scenario_id in self._scenarios:
            result = await self.simulate_lesson(lesson_id, lesson_content, scenario_id)
            results.append(result)
        return results

    async def _evaluate_lesson_against_scenario(
        self,
        lesson_content: dict,
        scenario: EvalScenario,
    ) -> bool:
        lesson_type = lesson_content.get("category", "")
        behaviors = scenario.expected_behavior

        if "error_prevention" in lesson_type:
            return "recovers_from_error" in behaviors or "no_errors" in behaviors
        elif "best_practice" in lesson_type:
            return "completes_within_budget" in behaviors or "follows_plan" in behaviors
        elif "pattern_recognition" in lesson_type:
            return True

        return True

    def get_results(self, lesson_id: str | None = None) -> list[SimulationResult]:
        if lesson_id:
            return [r for r in self._results if r.lesson_id == lesson_id]
        return list(self._results)

    def get_pass_rate(self, lesson_id: str | None = None) -> float:
        results = self.get_results(lesson_id)
        if not results:
            return 0.0
        passed = sum(1 for r in results if r.passed)
        return passed / len(results)

    def list_scenarios(self) -> list[EvalScenario]:
        return list(self._scenarios.values())

    def get_summary(self) -> dict:
        results = self._results
        return {
            "total_simulations": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "pass_rate": self.get_pass_rate(),
            "scenarios": len(self._scenarios),
        }


lesson_simulator = LessonSimulator()
