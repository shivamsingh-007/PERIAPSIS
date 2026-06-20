from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.scoring import (
    HarnessScorer,
    RunScore,
    ScenarioResult,
    ScenarioScore,
    ScoreCategory,
    harness_scorer,
)


class TestScoreCategory:
    def test_all_variants(self):
        assert len(list(ScoreCategory)) == 6

    def test_values(self):
        assert ScoreCategory.CORRECTNESS.value == "correctness"
        assert ScoreCategory.OVERALL.value == "overall"


class TestScenarioResult:
    def test_all_variants(self):
        assert len(list(ScenarioResult)) == 4

    def test_values(self):
        assert ScenarioResult.PASS.value == "pass"
        assert ScenarioResult.FAIL.value == "fail"


class TestScenarioScore:
    def test_create_score(self):
        score = ScenarioScore(
            scenario_id="s1",
            scenario_name="test",
            result=ScenarioResult.PASS,
            score=9.0,
            max_score=10.0,
        )
        assert score.score == 9.0
        assert score.result == ScenarioResult.PASS

    def test_score_defaults(self):
        score = ScenarioScore(
            scenario_id="s1",
            scenario_name="test",
            result=ScenarioResult.PASS,
            score=10,
            max_score=10,
        )
        assert score.details == {}
        assert score.duration_ms == 0


class TestHarnessScorer:
    def test_init(self):
        scorer = HarnessScorer()
        assert scorer is not None

    def test_register_scenario(self):
        scorer = HarnessScorer()
        scorer.register_scenario(
            scenario_id="s1",
            name="test",
            category=ScoreCategory.CORRECTNESS,
            max_score=10,
            required=True,
        )
        scenarios = scorer.list_scenarios()
        assert len(scenarios) == 1

    def test_list_scenarios_empty(self):
        scorer = HarnessScorer()
        scenarios = scorer.list_scenarios()
        assert scenarios == []

    async def test_get_score(self):
        scorer = HarnessScorer()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result
        with patch("packages.harness.scoring.get_session") as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await scorer.get_score(uuid.uuid4())
        assert result is None
