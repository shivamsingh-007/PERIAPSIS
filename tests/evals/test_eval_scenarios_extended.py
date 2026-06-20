from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from packages.harness.eval_runner import EvalResult, EvalRunner, EvalScenario
from packages.harness.scoring import (
    HarnessScorer,
    ScenarioResult,
    ScenarioScore,
    ScoreCategory,
    harness_scorer,
)


@pytest.fixture
def mock_harness_db():
    with patch("packages.harness.scoring.get_session") as mock:
        session = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=session)
        mock.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock


class TestEvalScenarioExtended:
    def test_scenario_all_fields(self):
        s = EvalScenario(
            scenario_id="s1",
            name="Full Test",
            description="Complete coverage",
            category="correctness",
            max_score=100,
            required=False,
            timeout_seconds=60,
        )
        assert s.scenario_id == "s1"
        assert s.name == "Full Test"
        assert s.description == "Complete coverage"
        assert s.category == "correctness"
        assert s.max_score == 100
        assert s.required is False
        assert s.timeout_seconds == 60

    def test_scenario_model_dump(self):
        s = EvalScenario(
            scenario_id="s1", name="t", description="d", category="c", max_score=5
        )
        d = s.model_dump()
        assert d["scenario_id"] == "s1"
        assert d["max_score"] == 5


class TestEvalResultExtended:
    def test_result_model_dump(self):
        r = EvalResult(
            scenario_id="s1",
            result=ScenarioResult.PASS,
            score=9.5,
            details={"checks": "ok"},
            duration_ms=123.4,
        )
        d = r.model_dump()
        assert d["result"] == "pass"
        assert d["score"] == 9.5
        assert d["duration_ms"] == 123.4

    def test_result_with_error(self):
        r = EvalResult(
            scenario_id="s1",
            result=ScenarioResult.FAIL,
            error="timeout",
        )
        assert r.error == "timeout"
        assert r.score == 0.0


class TestEvalRunnerScenariosExtended:
    @pytest.mark.asyncio
    async def test_run_scenario_with_kwargs(self):
        runner = EvalRunner()
        scenario = EvalScenario(
            scenario_id="s1", name="t", description="d", category="c", max_score=10
        )

        async def func(goal="default", **kwargs):
            return EvalResult(
                scenario_id="s1",
                result=ScenarioResult.PASS,
                score=10,
                details={"goal": goal},
            )

        runner.register(scenario, func)
        result = await runner.run_scenario("s1", goal="custom")
        assert result.details["goal"] == "custom"

    @pytest.mark.asyncio
    async def test_run_scenario_timeout(self):
        runner = EvalRunner()
        scenario = EvalScenario(
            scenario_id="s1",
            name="t",
            description="d",
            category="c",
            max_score=10,
            timeout_seconds=0.1,
        )

        async def slow_func(**kwargs):
            await asyncio.sleep(5)
            return EvalResult(scenario_id="s1", result=ScenarioResult.PASS, score=10)

        runner.register(scenario, slow_func)
        result = await runner.run_scenario("s1")
        assert result.result == ScenarioResult.FAIL

    @pytest.mark.asyncio
    async def test_run_all_mixed_results(self):
        runner = EvalRunner()
        scenarios = []
        for i in range(5):
            s = EvalScenario(
                scenario_id=f"s{i}",
                name=f"t{i}",
                description="d",
                category="c",
                max_score=10,
            )
            scenarios.append(s)

        for i, s in enumerate(scenarios):
            if i % 2 == 0:
                async def func(sid=s.scenario_id, **kwargs):
                    return EvalResult(scenario_id=sid, result=ScenarioResult.PASS, score=10)
            else:
                async def func(sid=s.scenario_id, **kwargs):
                    return EvalResult(scenario_id=sid, result=ScenarioResult.FAIL, score=0)
            runner.register(s, func)

        results = await runner.run_all()
        assert len(results) == 5
        summary = runner.get_summary()
        assert summary["passed"] == 3
        assert summary["failed"] == 2

    @pytest.mark.asyncio
    async def test_run_scenario_duration_tracked(self):
        runner = EvalRunner()
        scenario = EvalScenario(
            scenario_id="s1", name="t", description="d", category="c", max_score=10
        )

        async def func(**kwargs):
            await asyncio.sleep(0.05)
            return EvalResult(scenario_id="s1", result=ScenarioResult.PASS, score=10)

        runner.register(scenario, func)
        result = await runner.run_scenario("s1")
        assert result.duration_ms > 0

    def test_get_results_accumulate(self):
        runner = EvalRunner()
        for i in range(3):
            runner._results.append(
                EvalResult(scenario_id=f"s{i}", result=ScenarioResult.PASS, score=10)
            )
        results = runner.get_results()
        assert len(results) == 3

    def test_get_summary_pass_rate(self):
        runner = EvalRunner()
        runner._results = [
            EvalResult(scenario_id="s1", result=ScenarioResult.PASS, score=10),
            EvalResult(scenario_id="s2", result=ScenarioResult.PASS, score=10),
            EvalResult(scenario_id="s3", result=ScenarioResult.PASS, score=10),
        ]
        summary = runner.get_summary()
        assert summary["pass_rate"] == 1.0


class TestHarnessScorerExtended:
    @pytest.mark.asyncio
    async def test_score_run_multiple_categories(self, mock_harness_db):
        scorer = HarnessScorer(passing_threshold=0.5)
        scorer.register_scenario("s1", "S1", ScoreCategory.CORRECTNESS)
        scorer.register_scenario("s2", "S2", ScoreCategory.EFFICIENCY)
        scorer.register_scenario("s3", "S3", ScoreCategory.SAFETY)

        results = [
            ScenarioScore(
                scenario_id="s1", scenario_name="S1",
                result=ScenarioResult.PASS, score=0.9, max_score=1.0,
            ),
            ScenarioScore(
                scenario_id="s2", scenario_name="S2",
                result=ScenarioResult.PASS, score=0.8, max_score=1.0,
            ),
            ScenarioScore(
                scenario_id="s3", scenario_name="S3",
                result=ScenarioResult.PASS, score=0.7, max_score=1.0,
            ),
        ]

        score = await scorer.score_run(uuid.uuid4(), uuid.uuid4(), results)
        assert score.passed is True
        assert len(score.category_scores) == 3

    @pytest.mark.asyncio
    async def test_gate_blocked_on_required_fail(self, mock_harness_db):
        scorer = HarnessScorer(passing_threshold=0.5)
        scorer.register_scenario("s1", "S1", ScoreCategory.CORRECTNESS, required=True)

        results = [
            ScenarioScore(
                scenario_id="s1", scenario_name="S1",
                result=ScenarioResult.FAIL, score=0.0, max_score=1.0,
            ),
        ]

        score = await scorer.score_run(uuid.uuid4(), uuid.uuid4(), results)
        assert score.gate_blocked is True
        assert score.passed is False

    @pytest.mark.asyncio
    async def test_overall_score_calculation(self, mock_harness_db):
        scorer = HarnessScorer(passing_threshold=0.0)
        scorer.register_scenario("s1", "S1", ScoreCategory.CORRECTNESS)
        scorer.register_scenario("s2", "S2", ScoreCategory.CORRECTNESS)

        results = [
            ScenarioScore(
                scenario_id="s1", scenario_name="S1",
                result=ScenarioResult.PASS, score=1.0, max_score=1.0,
            ),
            ScenarioScore(
                scenario_id="s2", scenario_name="S2",
                result=ScenarioResult.PASS, score=0.6, max_score=1.0,
            ),
        ]

        score = await scorer.score_run(uuid.uuid4(), uuid.uuid4(), results)
        assert score.overall_score == pytest.approx(0.8, abs=0.01)

    @pytest.mark.asyncio
    async def test_unregistered_scenario_ignored(self, mock_harness_db):
        scorer = HarnessScorer(passing_threshold=0.5)

        results = [
            ScenarioScore(
                scenario_id="unknown", scenario_name="Unknown",
                result=ScenarioResult.PASS, score=1.0, max_score=1.0,
            ),
        ]

        score = await scorer.score_run(uuid.uuid4(), uuid.uuid4(), results)
        assert score.overall_score == 0.0
        assert score.passed is False

    @pytest.mark.asyncio
    async def test_warn_does_not_block_gate(self, mock_harness_db):
        scorer = HarnessScorer(passing_threshold=0.0)
        scorer.register_scenario("s1", "S1", ScoreCategory.CORRECTNESS, required=True)

        results = [
            ScenarioScore(
                scenario_id="s1", scenario_name="S1",
                result=ScenarioResult.WARN, score=0.5, max_score=1.0,
            ),
        ]

        score = await scorer.score_run(uuid.uuid4(), uuid.uuid4(), results)
        assert score.gate_blocked is False

    def test_list_scenarios_empty(self):
        scorer = HarnessScorer()
        assert scorer.list_scenarios() == []

    def test_list_scenarios_populated(self):
        scorer = HarnessScorer()
        scorer.register_scenario("s1", "S1", ScoreCategory.CORRECTNESS, max_score=10)
        scenarios = scorer.list_scenarios()
        assert len(scenarios) == 1
        assert scenarios[0]["id"] == "s1"
        assert scenarios[0]["max_score"] == 10
