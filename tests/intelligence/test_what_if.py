from __future__ import annotations
"""Tests for packages.intelligence.what_if - WhatIfAnalysis."""

import uuid

import pytest

from packages.intelligence.what_if import WhatIfAnalysis, WhatIfScenario


class TestWhatIfAnalysis:
    def setup_method(self):
        self.analysis = WhatIfAnalysis()

    def test_create_scenario(self):
        scenario = self.analysis.create_scenario(
            "budget test",
            original_state={"budget_limit": 1.0, "risk_tier": "low"},
            modifications={"budget_limit": 2.0},
        )
        assert scenario.name == "budget test"
        assert scenario.modified_state["budget_limit"] == 2.0
        assert scenario.original_state["budget_limit"] == 1.0

    def test_predict_budget_ratio(self):
        scenario = self.analysis.create_scenario(
            "doubles budget",
            original_state={"budget_limit": 1.0},
            modifications={"budget_limit": 2.0},
        )
        assert scenario.predicted_outcome["estimated_cost_ratio"] == 2.0

    def test_predict_risk_tier(self):
        scenario = self.analysis.create_scenario(
            "high risk",
            original_state={"risk_tier": "low"},
            modifications={"risk_tier": "high"},
        )
        assert scenario.predicted_outcome["risk_multiplier"] == 1.5

    def test_predict_goal_change(self):
        scenario = self.analysis.create_scenario(
            "new goal",
            original_state={"goal": "old"},
            modifications={"goal": "new"},
        )
        assert scenario.predicted_outcome["goal_changed"] is True
        assert scenario.predicted_outcome["estimated_additional_steps"] == 2

    def test_confidence_with_no_history(self):
        scenario = self.analysis.create_scenario(
            "test",
            original_state={"a": 1},
            modifications={"a": 2},
        )
        assert scenario.confidence == 0.3

    def test_confidence_with_history(self):
        for _ in range(10):
            self.analysis.record_run({"a": 1, "b": 2})
        scenario = self.analysis.create_scenario(
            "test",
            original_state={"a": 1},
            modifications={"a": 2},
        )
        assert scenario.confidence > 0.3

    def test_get_scenario(self):
        scenario = self.analysis.create_scenario(
            "test", {"a": 1}, {"a": 2}
        )
        found = self.analysis.get_scenario(scenario.scenario_id)
        assert found is not None
        assert found.name == "test"

    def test_get_scenario_not_found(self):
        assert self.analysis.get_scenario(uuid.uuid4()) is None

    def test_list_scenarios(self):
        self.analysis.create_scenario("s1", {"a": 1}, {"a": 2})
        self.analysis.create_scenario("s2", {"b": 1}, {"b": 3})
        scenarios = self.analysis.list_scenarios()
        assert len(scenarios) == 2

    def test_compare_scenarios(self):
        s1 = self.analysis.create_scenario("s1", {"a": 1}, {"a": 2})
        s2 = self.analysis.create_scenario("s2", {"b": 1}, {"b": 3})
        result = self.analysis.compare_scenarios([s1.scenario_id, s2.scenario_id])
        assert len(result["scenarios"]) == 2

    def test_compare_scenarios_partial(self):
        s1 = self.analysis.create_scenario("s1", {"a": 1}, {"a": 2})
        result = self.analysis.compare_scenarios([s1.scenario_id, uuid.uuid4()])
        assert len(result["scenarios"]) == 1
