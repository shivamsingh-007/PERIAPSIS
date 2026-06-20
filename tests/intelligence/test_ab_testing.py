from __future__ import annotations
"""Tests for packages.intelligence.ab_testing - ABTestManager."""

import pytest

from packages.intelligence.ab_testing import ABTestManager, Experiment, Variant


class TestABTestManager:
    def setup_method(self):
        self.manager = ABTestManager()

    def test_create_experiment(self):
        exp = self.manager.create_experiment(
            "test_exp",
            [{"variant_id": "a", "name": "Control", "weight": 1.0},
             {"variant_id": "b", "name": "Variant", "weight": 1.0}],
            description="Test experiment",
        )
        assert exp.name == "test_exp"
        assert len(exp.variants) == 2
        assert exp.is_active is True

    def test_assign_variant(self):
        self.manager.create_experiment(
            "exp1",
            [{"variant_id": "a", "name": "A", "weight": 1.0},
             {"variant_id": "b", "name": "B", "weight": 1.0}],
        )
        variant = self.manager.assign_variant("exp1", "user1")
        assert variant is not None
        assert variant.variant_id in ("a", "b")

    def test_assign_variant_nonexistent(self):
        assert self.manager.assign_variant("nonexistent", "user1") is None

    def test_assign_variant_inactive(self):
        exp = self.manager.create_experiment(
            "exp1",
            [{"variant_id": "a", "name": "A", "weight": 1.0}],
        )
        exp.is_active = False
        assert self.manager.assign_variant("exp1", "user1") is None

    def test_record_outcome(self):
        self.manager.create_experiment(
            "exp1",
            [{"variant_id": "a", "name": "A", "weight": 1.0}],
        )
        self.manager.record_outcome("exp1", "a", 0.8)
        self.manager.record_outcome("exp1", "a", 0.9)
        results = self.manager.get_results("exp1")
        assert results["variants"]["a"]["count"] == 2

    def test_record_outcome_nonexistent(self):
        # Should not raise
        self.manager.record_outcome("nonexistent", "a", 0.8)

    def test_get_results(self):
        self.manager.create_experiment(
            "exp1",
            [{"variant_id": "a", "name": "A", "weight": 1.0},
             {"variant_id": "b", "name": "B", "weight": 1.0}],
        )
        self.manager.record_outcome("exp1", "a", 0.8)
        self.manager.record_outcome("exp1", "a", 0.9)
        self.manager.record_outcome("exp1", "b", 0.6)
        results = self.manager.get_results("exp1")
        assert results["experiment"] == "exp1"
        assert results["variants"]["a"]["mean"] == pytest.approx(0.85)
        assert results["variants"]["b"]["mean"] == pytest.approx(0.6)

    def test_get_results_nonexistent(self):
        assert self.manager.get_results("nonexistent") == {}

    def test_get_winning_variant(self):
        self.manager.create_experiment(
            "exp1",
            [{"variant_id": "a", "name": "A", "weight": 1.0},
             {"variant_id": "b", "name": "B", "weight": 1.0}],
        )
        self.manager.record_outcome("exp1", "a", 0.9)
        self.manager.record_outcome("exp1", "b", 0.5)
        winner = self.manager.get_winning_variant("exp1")
        assert winner == "a"

    def test_get_winning_variant_nonexistent(self):
        assert self.manager.get_winning_variant("nonexistent") is None

    def test_list_experiments(self):
        self.manager.create_experiment("exp1", [{"variant_id": "a", "name": "A"}])
        self.manager.create_experiment("exp2", [{"variant_id": "b", "name": "B"}])
        exps = self.manager.list_experiments()
        assert len(exps) == 2

    def test_weighted_assignment(self):
        self.manager.create_experiment(
            "exp1",
            [{"variant_id": "a", "name": "A", "weight": 99.0},
             {"variant_id": "b", "name": "B", "weight": 1.0}],
        )
        # With 99:1 weight, 'a' should be assigned most of the time
        counts = {"a": 0, "b": 0}
        for _ in range(100):
            v = self.manager.assign_variant("exp1", f"user{_}")
            counts[v.variant_id] += 1
        assert counts["a"] > counts["b"]
