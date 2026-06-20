from __future__ import annotations
"""Tests for packages.runtime.state - RunState, enums, budget logic."""

import uuid
from datetime import datetime

import pytest

from packages.runtime.state import (
    Action,
    BudgetPolicy,
    RiskTier,
    RunState,
    RunStatus,
    StepResult,
    TerminalState,
)


class TestTerminalState:
    def test_all_variants_exist(self):
        variants = list(TerminalState)
        assert len(variants) == 8

    def test_success_value(self):
        assert TerminalState.SUCCESS.value == "SUCCESS"

    def test_string_representation(self):
        assert str(TerminalState.STOP_BUDGET) == "TerminalState.STOP_BUDGET"

    def test_enum_from_value(self):
        assert TerminalState("FAIL_TOOLING") == TerminalState.FAIL_TOOLING

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            TerminalState("INVALID")


class TestRunStatus:
    def test_all_variants(self):
        assert len(list(RunStatus)) == 5

    def test_pending_value(self):
        assert RunStatus.PENDING.value == "pending"

    def test_enum_from_string(self):
        assert RunStatus("running") == RunStatus.RUNNING


class TestRiskTier:
    def test_all_variants(self):
        assert len(list(RiskTier)) == 3

    def test_low_value(self):
        assert RiskTier.LOW.value == "low"

    def test_from_string(self):
        assert RiskTier("high") == RiskTier.HIGH


class TestBudgetPolicy:
    def test_defaults(self):
        bp = BudgetPolicy()
        assert bp.max_iterations == 12
        assert bp.max_tool_calls == 24
        assert bp.max_cost_usd == 2.50
        assert bp.max_runtime_seconds == 180
        assert bp.max_parallel_workers == 4
        assert bp.max_external_writes == 2
        assert bp.stop_on_no_progress_rounds == 2

    def test_custom_values(self):
        bp = BudgetPolicy(max_iterations=5, max_cost_usd=1.0)
        assert bp.max_iterations == 5
        assert bp.max_cost_usd == 1.0

    def test_serialization(self):
        bp = BudgetPolicy(max_iterations=10)
        data = bp.model_dump()
        assert data["max_iterations"] == 10
        bp2 = BudgetPolicy(**data)
        assert bp2.max_iterations == 10


class TestAction:
    def test_defaults(self):
        a = Action(action_type="research")
        assert a.action_type == "research"
        assert a.tool_name is None
        assert a.input_data == {}
        assert a.risk_tier == RiskTier.LOW

    def test_full_action(self):
        a = Action(
            action_type="execute",
            tool_name="search",
            input_data={"query": "test"},
            risk_tier=RiskTier.HIGH,
        )
        assert a.tool_name == "search"
        assert a.risk_tier == RiskTier.HIGH


class TestStepResult:
    def test_defaults(self):
        s = StepResult(step_number=1, node_name="intake")
        assert s.step_number == 1
        assert s.node_name == "intake"
        assert s.cost_usd == 0.0
        assert s.error is None

    def test_with_output(self):
        s = StepResult(
            step_number=2,
            node_name="execute",
            output={"result": "done", "success": True},
            cost_tokens_in=500,
            cost_tokens_out=200,
            cost_usd=0.01,
            latency_ms=150,
        )
        assert s.output["success"] is True
        assert s.cost_tokens_in == 500


class TestRunState:
    def test_default_state(self):
        state = RunState()
        assert state.status == RunStatus.PENDING
        assert state.terminal_state is None
        assert state.risk_tier == RiskTier.LOW
        assert state.iterations == 0
        assert state.total_cost_usd == 0.0
        assert state.plan == []
        assert state.steps == []

    def test_is_terminal_false(self):
        state = RunState()
        assert state.is_terminal() is False

    def test_is_terminal_true(self):
        state = RunState(terminal_state=TerminalState.SUCCESS)
        assert state.is_terminal() is True

    def test_can_continue_default(self):
        state = RunState()
        assert state.can_continue() is True

    def test_can_continue_terminal(self):
        state = RunState(terminal_state=TerminalState.FAIL_TOOLING)
        assert state.can_continue() is False

    def test_can_continue_budget_iterations(self):
        state = RunState(iterations=12, budget=BudgetPolicy(max_iterations=12))
        assert state.can_continue() is False

    def test_can_continue_budget_cost(self):
        state = RunState(total_cost_usd=2.50, budget=BudgetPolicy(max_cost_usd=2.50))
        assert state.can_continue() is False

    def test_can_continue_budget_runtime(self):
        state = RunState(runtime_seconds=180, budget=BudgetPolicy(max_runtime_seconds=180))
        assert state.can_continue() is False

    def test_can_continue_budget_tool_calls(self):
        state = RunState(tool_calls=24, budget=BudgetPolicy(max_tool_calls=24))
        assert state.can_continue() is False

    def test_can_continue_within_budget(self):
        state = RunState(
            iterations=5,
            total_cost_usd=1.0,
            runtime_seconds=60,
            tool_calls=10,
            budget=BudgetPolicy(max_iterations=12, max_cost_usd=2.50),
        )
        assert state.can_continue() is True

    def test_check_budget_no_violation(self):
        state = RunState()
        assert state.check_budget() is None

    def test_check_budget_iterations_exceeded(self):
        state = RunState(iterations=12, budget=BudgetPolicy(max_iterations=12))
        assert state.check_budget() == TerminalState.STOP_BUDGET

    def test_check_budget_cost_exceeded(self):
        state = RunState(total_cost_usd=2.51, budget=BudgetPolicy(max_cost_usd=2.50))
        assert state.check_budget() == TerminalState.STOP_BUDGET

    def test_check_budget_runtime_exceeded(self):
        state = RunState(runtime_seconds=181, budget=BudgetPolicy(max_runtime_seconds=180))
        assert state.check_budget() == TerminalState.STOP_BUDGET

    def test_check_budget_tool_calls_exceeded(self):
        state = RunState(tool_calls=25, budget=BudgetPolicy(max_tool_calls=24))
        assert state.check_budget() == TerminalState.STOP_BUDGET

    def test_check_budget_no_progress(self):
        state = RunState(
            no_progress_rounds=2,
            budget=BudgetPolicy(stop_on_no_progress_rounds=2),
        )
        assert state.check_budget() == TerminalState.STOP_NO_PROGRESS

    def test_check_budget_no_progress_below_threshold(self):
        state = RunState(
            no_progress_rounds=1,
            budget=BudgetPolicy(stop_on_no_progress_rounds=2),
        )
        assert state.check_budget() is None

    def test_unique_ids(self):
        s1 = RunState()
        s2 = RunState()
        assert s1.run_id != s2.run_id
        assert s1.tenant_id != s2.tenant_id

    def test_model_dump(self):
        state = RunState(goal="test goal")
        data = state.model_dump()
        assert data["goal"] == "test goal"
        assert "status" in data
        assert "budget" in data
