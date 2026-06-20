from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.eval_runner import EvalResult, EvalRunner, EvalScenario
from packages.harness.scoring import (
    HarnessScorer,
    RunScore,
    ScenarioResult,
    ScenarioScore,
    harness_scorer,
)


@pytest.fixture
def runner():
    return EvalRunner()


@pytest.fixture
def scorer():
    return HarnessScorer()


@pytest.fixture
def mock_harness_db():
    with patch("packages.harness.scoring.get_session") as mock:
        session = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=session)
        mock.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock


class TestHarnessScorer:
    def test_init(self, scorer):
        assert scorer.passing_threshold == 0.7
        assert scorer._scenarios == {}

    def test_init_custom_threshold(self):
        s = HarnessScorer(passing_threshold=0.9)
        assert s.passing_threshold == 0.9

    def test_register_scenario(self, scorer):
        from packages.harness.scoring import ScoreCategory
        scorer.register_scenario(
            scenario_id="s1",
            name="Test",
            category=ScoreCategory.CORRECTNESS,
            max_score=1.0,
            required=True,
        )
        assert "s1" in scorer._scenarios
        assert scorer._scenarios["s1"]["name"] == "Test"

    def test_list_scenarios(self, scorer):
        from packages.harness.scoring import ScoreCategory
        scorer.register_scenario("s1", "S1", ScoreCategory.CORRECTNESS)
        scorer.register_scenario("s2", "S2", ScoreCategory.EFFICIENCY)
        scenarios = scorer.list_scenarios()
        assert len(scenarios) == 2

    @pytest.mark.asyncio
    async def test_score_run_pass(self, scorer, mock_harness_db):
        run_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        from packages.harness.scoring import ScoreCategory
        scorer.register_scenario("s1", "S1", ScoreCategory.CORRECTNESS)
        scenario_results = [
            ScenarioScore(
                scenario_id="s1",
                scenario_name="S1",
                result=ScenarioResult.PASS,
                score=0.9,
                max_score=1.0,
            ),
        ]
        score = await scorer.score_run(run_id, tenant_id, scenario_results)
        assert isinstance(score, RunScore)
        assert score.passed is True
        assert score.overall_score >= 0.7
        assert score.gate_blocked is False

    @pytest.mark.asyncio
    async def test_score_run_fail(self, scorer, mock_harness_db):
        run_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        from packages.harness.scoring import ScoreCategory
        scorer.register_scenario("s1", "S1", ScoreCategory.CORRECTNESS, required=True)
        scenario_results = [
            ScenarioScore(
                scenario_id="s1",
                scenario_name="S1",
                result=ScenarioResult.FAIL,
                score=0.0,
                max_score=1.0,
            ),
        ]
        score = await scorer.score_run(run_id, tenant_id, scenario_results)
        assert score.passed is False
        assert score.gate_blocked is True

    @pytest.mark.asyncio
    async def test_score_run_gate_blocked_optional(self, scorer, mock_harness_db):
        run_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        from packages.harness.scoring import ScoreCategory
        scorer.register_scenario("s1", "S1", ScoreCategory.CORRECTNESS, required=False)
        scenario_results = [
            ScenarioScore(
                scenario_id="s1",
                scenario_name="S1",
                result=ScenarioResult.FAIL,
                score=0.0,
                max_score=1.0,
            ),
        ]
        score = await scorer.score_run(run_id, tenant_id, scenario_results)
        assert score.gate_blocked is False

    @pytest.mark.asyncio
    async def test_score_run_empty(self, scorer, mock_harness_db):
        run_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        score = await scorer.score_run(run_id, tenant_id, [])
        assert score.overall_score == 0.0
        assert score.passed is False


class TestEvalRunnerExtended:
    def test_init(self, runner):
        assert runner._scenarios == {}
        assert runner._results == []

    def test_register(self, runner):
        scenario = EvalScenario(
            scenario_id="s1", name="test", description="d", category="c", max_score=10
        )
        async def func(**kwargs):
            return EvalResult(scenario_id="s1", result=ScenarioResult.PASS, score=10)

        runner.register(scenario, func)
        assert "s1" in runner._scenarios
        assert runner._scenarios["s1"][0] is scenario

    @pytest.mark.asyncio
    async def test_run_scenario(self, runner):
        scenario = EvalScenario(
            scenario_id="s1", name="test", description="d", category="c", max_score=10
        )
        async def func(**kwargs):
            return EvalResult(scenario_id="s1", result=ScenarioResult.PASS, score=10)

        runner.register(scenario, func)
        result = await runner.run_scenario("s1")
        assert result.result == ScenarioResult.PASS
        assert result.score == 10
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_run_scenario_not_found(self, runner):
        result = await runner.run_scenario("nonexistent")
        assert result.result == ScenarioResult.SKIP
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_run_scenario_exception(self, runner):
        scenario = EvalScenario(
            scenario_id="s1", name="test", description="d", category="c", max_score=10
        )
        async def failing_func(**kwargs):
            raise RuntimeError("boom")

        runner.register(scenario, failing_func)
        result = await runner.run_scenario("s1")
        assert result.result == ScenarioResult.FAIL
        assert "boom" in result.error

    @pytest.mark.asyncio
    async def test_run_all(self, runner):
        for i in range(3):
            scenario = EvalScenario(
                scenario_id=f"s{i}", name=f"t{i}", description="d", category="c", max_score=10
            )

            async def func(sid=f"s{i}", **kwargs):
                return EvalResult(scenario_id=sid, result=ScenarioResult.PASS, score=10)

            runner.register(scenario, func)

        results = await runner.run_all()
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_run_all_with_failure(self, runner):
        scenario1 = EvalScenario(
            scenario_id="s1", name="pass", description="d", category="c", max_score=10
        )
        scenario2 = EvalScenario(
            scenario_id="s2", name="fail", description="d", category="c", max_score=10
        )

        async def pass_func(**kwargs):
            return EvalResult(scenario_id="s1", result=ScenarioResult.PASS, score=10)

        async def fail_func(**kwargs):
            raise ValueError("fail")

        runner.register(scenario1, pass_func)
        runner.register(scenario2, fail_func)
        results = await runner.run_all()
        assert len(results) == 2
        passed = [r for r in results if r.result == ScenarioResult.PASS]
        failed = [r for r in results if r.result == ScenarioResult.FAIL]
        assert len(passed) == 1
        assert len(failed) == 1

    def test_get_results(self, runner):
        r1 = EvalResult(scenario_id="s1", result=ScenarioResult.PASS, score=10)
        r2 = EvalResult(scenario_id="s2", result=ScenarioResult.FAIL, score=0)
        runner._results = [r1, r2]
        results = runner.get_results()
        assert len(results) == 2

    def test_get_summary(self, runner):
        runner._results = [
            EvalResult(scenario_id="s1", result=ScenarioResult.PASS, score=10),
            EvalResult(scenario_id="s2", result=ScenarioResult.PASS, score=10),
            EvalResult(scenario_id="s3", result=ScenarioResult.FAIL, score=0),
            EvalResult(scenario_id="s4", result=ScenarioResult.WARN, score=5),
            EvalResult(scenario_id="s5", result=ScenarioResult.SKIP, score=0),
        ]
        summary = runner.get_summary()
        assert summary["total"] == 5
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["warned"] == 1
        assert summary["skipped"] == 1
        assert summary["pass_rate"] == 0.4

    def test_get_summary_empty(self, runner):
        summary = runner.get_summary()
        assert summary["total"] == 0
        assert summary["pass_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_run_scenario_stores_result(self, runner):
        scenario = EvalScenario(
            scenario_id="s1", name="test", description="d", category="c", max_score=10
        )

        async def func(**kwargs):
            return EvalResult(scenario_id="s1", result=ScenarioResult.PASS, score=10)

        runner.register(scenario, func)
        await runner.run_scenario("s1")
        assert len(runner._results) == 1
