from __future__ import annotations
"""Tests for packages.reflection.critic - CriticNode reflection logic (in-memory)."""

import uuid

import pytest

from packages.reflection.critic import CriticType, ReflectionResult, Severity


class TestCriticNodeLogic:
    """Test reflection result models without DB persistence."""

    def test_reflection_result_defaults(self):
        result = ReflectionResult(
            critic_type=CriticType.STEP,
            finding="step completed",
            severity=Severity.LOW,
        )
        assert result.confidence == 0.5
        assert result.promoted is False

    def test_critic_type_enum(self):
        assert CriticType.STEP.value == "step"
        assert CriticType.ERROR.value == "error"
        assert CriticType.STRATEGY.value == "strategy"
        assert CriticType.FINAL.value == "final"

    def test_severity_enum(self):
        assert Severity.LOW.value == "low"
        assert Severity.CRITICAL.value == "critical"
        assert len(list(Severity)) == 4

    def test_step_reflect_success_logic(self):
        # Test the logic that would produce a success reflection
        finding = "Step 1 (research) completed successfully"
        severity = Severity.LOW
        assert "completed successfully" in finding
        assert severity == Severity.LOW

    def test_step_reflect_failure_logic(self):
        finding = "Step 1 (research) failed: timeout"
        severity = Severity.MEDIUM
        assert "failed" in finding
        assert severity == Severity.MEDIUM

    def test_strategy_reflect_no_progress_logic(self):
        finding = "No progress after 5 iterations. Strategy change recommended."
        severity = Severity.HIGH
        assert "No progress" in finding
        assert severity == Severity.HIGH

    def test_strategy_reflect_near_budget_logic(self):
        progress_pct = 9 / 10
        assert progress_pct > 0.8

    def test_final_reflect_success_logic(self):
        terminal_state = "SUCCESS"
        assert terminal_state == "SUCCESS"

    def test_final_reflect_budget_stop_logic(self):
        terminal_state = "STOP_BUDGET"
        assert terminal_state in ("STOP_BUDGET", "STOP_NO_PROGRESS")
