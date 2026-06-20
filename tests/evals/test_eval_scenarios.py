from __future__ import annotations

import pytest

from packages.harness.eval_runner import (
    EvalResult,
    EvalRunner,
    EvalScenario,
)
from packages.harness.scoring import ScenarioResult


@pytest.fixture
def runner():
    return EvalRunner()


class TestEvalScenario:
    def test_create_scenario(self):
        scenario = EvalScenario(
            scenario_id="test-1",
            name="Basic QA",
            description="Simple question answering",
            category="correctness",
            max_score=10,
            required=True,
        )
        assert scenario.name == "Basic QA"
        assert scenario.required is True

    def test_scenario_defaults(self):
        scenario = EvalScenario(
            scenario_id="s1",
            name="test",
            description="d",
            category="c",
            max_score=10,
        )
        assert scenario.required is True
        assert scenario.timeout_seconds == 30


class TestEvalResult:
    def test_create_result(self):
        result = EvalResult(
            scenario_id="s1",
            result=ScenarioResult.PASS,
            score=9.0,
            details={"checks": "All checks passed"},
        )
        assert result.result == ScenarioResult.PASS
        assert result.score == 9.0

    def test_result_defaults(self):
        result = EvalResult(
            scenario_id="s1",
            result=ScenarioResult.PASS,
            score=10,
        )
        assert result.error is None
        assert result.duration_ms == 0.0


class TestEvalRunner:
    def test_init(self, runner):
        assert runner is not None

    async def test_register_scenario(self, runner):
        scenario = EvalScenario(
            scenario_id="s1",
            name="test",
            description="d",
            category="c",
            max_score=10,
        )
        async def dummy():
            return EvalResult(scenario_id="s1", result=ScenarioResult.PASS, score=10)
        runner.register(scenario, dummy)
        assert "s1" in runner._scenarios

    def test_get_results_empty(self, runner):
        results = runner.get_results()
        assert results == []

    def test_get_summary_empty(self, runner):
        summary = runner.get_summary()
        assert "total" in summary
        assert summary["total"] == 0
