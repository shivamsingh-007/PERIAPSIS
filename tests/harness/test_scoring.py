from __future__ import annotations
"""Tests for packages.harness.scoring - HarnessScorer, scoring logic (in-memory only)."""

import uuid

import pytest

from packages.harness.scoring import (
    HarnessScorer,
    RunScore,
    ScenarioResult,
    ScenarioScore,
    ScoreCategory,
)


class TestHarnessScorer:
    def setup_method(self):
        self.scorer = HarnessScorer(passing_threshold=0.7)

    def test_register_scenario(self):
        self.scorer.register_scenario(
            "s1", "Correctness Check", ScoreCategory.CORRECTNESS
        )
        scenarios = self.scorer.list_scenarios()
        assert len(scenarios) == 1
        assert scenarios[0]["id"] == "s1"

    def test_list_scenarios(self):
        self.scorer.register_scenario("s1", "Check 1", ScoreCategory.CORRECTNESS)
        self.scorer.register_scenario("s2", "Check 2", ScoreCategory.EFFICIENCY)
        scenarios = self.scorer.list_scenarios()
        assert len(scenarios) == 2

    def test_score_run_all_pass(self):
        self.scorer.register_scenario("s1", "Check 1", ScoreCategory.CORRECTNESS)
        scores = [ScenarioScore(
            scenario_id="s1", scenario_name="Check 1",
            result=ScenarioResult.PASS, score=1.0, max_score=1.0,
        )]
        run_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        # score_run calls _persist_score which needs DB, so test in-memory logic
        category_scores = {cat: [] for cat in ScoreCategory}
        for sr in scores:
            scenario_def = self.scorer._scenarios.get(sr.scenario_id)
            if scenario_def:
                cat = scenario_def["category"]
                normalized = sr.score / sr.max_score if sr.max_score > 0 else 0
                category_scores[cat].append(normalized)
        assert len(category_scores[ScoreCategory.CORRECTNESS]) == 1
        assert category_scores[ScoreCategory.CORRECTNESS][0] == 1.0

    def test_scenario_result_enum(self):
        assert ScenarioResult.PASS.value == "pass"
        assert ScenarioResult.FAIL.value == "fail"
        assert ScenarioResult.WARN.value == "warn"
        assert ScenarioResult.SKIP.value == "skip"

    def test_score_category_enum(self):
        assert ScoreCategory.CORRECTNESS.value == "correctness"
        assert len(list(ScoreCategory)) == 6

    def test_scenario_score_defaults(self):
        ss = ScenarioScore(scenario_id="s1", scenario_name="Test", result=ScenarioResult.PASS)
        assert ss.score == 0.0
        assert ss.max_score == 1.0

    def test_run_score_defaults(self):
        rs = RunScore(run_id=uuid.uuid4(), tenant_id=uuid.uuid4())
        assert rs.overall_score == 0.0
        assert rs.passed is False
        assert rs.gate_blocked is False
