from __future__ import annotations
"""Tests for packages.runtime.graph - Graph nodes and routing logic."""

import uuid

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
from packages.runtime.graph import (
    decide,
    execute,
    intake,
    policy_check,
    reflect,
    should_continue,
    validate,
    validation_gate,
)


def _make_state(**kwargs) -> RunState:
    defaults = {
        "run_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "goal": "test goal",
        "budget": BudgetPolicy(),
    }
    defaults.update(kwargs)
    return RunState(**defaults)


class TestIntake:
    def test_sets_running_status(self):
        state = _make_state()
        result = intake(state)
        assert result["status"] == RunStatus.RUNNING

    def test_increments_iterations(self):
        state = _make_state(iterations=0)
        result = intake(state)
        assert result["iterations"] == 1

    def test_increments_current_step(self):
        state = _make_state(current_step=0)
        result = intake(state)
        assert result["current_step"] == 1

    def test_low_risk_default(self):
        state = _make_state(goal="read the docs")
        result = intake(state)
        assert result["risk_tier"] == "low"

    def test_high_risk_delete(self):
        state = _make_state(goal="delete all records")
        result = intake(state)
        assert result["risk_tier"] == "high"

    def test_high_risk_deploy(self):
        state = _make_state(goal="deploy to production")
        result = intake(state)
        assert result["risk_tier"] == "high"

    def test_high_risk_remove(self):
        state = _make_state(goal="remove old files")
        result = intake(state)
        assert result["risk_tier"] == "high"

    def test_high_risk_drop(self):
        state = _make_state(goal="drop the table")
        result = intake(state)
        assert result["risk_tier"] == "high"

    def test_medium_risk_update(self):
        state = _make_state(goal="update the config")
        result = intake(state)
        assert result["risk_tier"] == "medium"

    def test_medium_risk_modify(self):
        state = _make_state(goal="modify the schema")
        result = intake(state)
        assert result["risk_tier"] == "medium"

    def test_medium_risk_write(self):
        state = _make_state(goal="write a report")
        result = intake(state)
        assert result["risk_tier"] == "medium"

    def test_medium_risk_change(self):
        state = _make_state(goal="change the setting")
        result = intake(state)
        assert result["risk_tier"] == "medium"

    def test_case_insensitive(self):
        state = _make_state(goal="DELETE everything")
        result = intake(state)
        assert result["risk_tier"] == "high"


class TestPolicyCheck:
    def test_no_budget_violation(self):
        state = _make_state(iterations=1, total_cost_usd=0.1)
        result = policy_check(state)
        assert result == {}

    def test_budget_violation_iterations(self):
        state = _make_state(
            iterations=12,
            budget=BudgetPolicy(max_iterations=12),
        )
        result = policy_check(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET
        assert result["status"] == RunStatus.COMPLETED

    def test_budget_violation_cost(self):
        state = _make_state(
            total_cost_usd=2.51,
            budget=BudgetPolicy(max_cost_usd=2.50),
        )
        result = policy_check(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET


class TestExecute:
    def test_execute_with_plan(self):
        state = _make_state(
            current_step=1,
            plan=[Action(action_type="research", tool_name="search")],
        )
        result = execute(state)
        assert len(result["steps"]) == 1
        assert result["steps"][0].node_name == "execute"
        assert result["tool_calls"] == 1
        assert result["total_cost_usd"] > 0

    def test_execute_empty_plan(self):
        state = _make_state(plan=[])
        result = execute(state)
        assert result["terminal_state"] == TerminalState.FAIL_TOOLING
        assert result["status"] == RunStatus.COMPLETED

    def test_execute_step_number(self):
        state = _make_state(
            current_step=3,
            plan=[Action(action_type="execute", tool_name="default")],
        )
        result = execute(state)
        assert result["steps"][0].step_number == 3


class TestValidate:
    def test_validate_success(self):
        state = _make_state(
            steps=[StepResult(step_number=1, node_name="execute", output={"success": True, "result": "done"})]
        )
        result = validate(state)
        assert result["validation_result"]["passed"] is True
        assert result["no_progress_rounds"] == 0

    def test_validate_no_steps(self):
        state = _make_state(steps=[])
        result = validate(state)
        assert result["terminal_state"] == TerminalState.FAIL_INVARIANT
        assert result["status"] == RunStatus.COMPLETED

    def test_validate_failed_step(self):
        state = _make_state(
            steps=[StepResult(step_number=1, node_name="execute", output={"success": False})]
        )
        result = validate(state)
        assert result["terminal_state"] == TerminalState.FAIL_INVARIANT


class TestReflect:
    def test_reflect_with_steps(self):
        state = _make_state(
            steps=[StepResult(step_number=1, node_name="execute", output={"result": "done"})],
            no_progress_rounds=0,
        )
        result = reflect(state)
        assert "no_progress_rounds" in result

    def test_reflect_no_steps(self):
        state = _make_state(steps=[])
        result = reflect(state)
        assert result == {}

    def test_reflect_empty_result_increments(self):
        state = _make_state(
            steps=[StepResult(step_number=1, node_name="execute", output={"result": ""})],
            no_progress_rounds=0,
        )
        result = reflect(state)
        assert result["no_progress_rounds"] == 1


class TestDecide:
    def test_decide_no_violation(self):
        state = _make_state(iterations=1)
        result = decide(state)
        assert result == {}

    def test_decide_budget_violation(self):
        state = _make_state(
            iterations=12,
            budget=BudgetPolicy(max_iterations=12),
        )
        result = decide(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET

    def test_decide_max_iterations_reached(self):
        state = _make_state(
            iterations=12,
            budget=BudgetPolicy(max_iterations=12),
        )
        result = decide(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET


class TestShouldContinue:
    def test_continue_when_not_terminal(self):
        state = _make_state()
        assert should_continue(state) == "continue"

    def test_stop_when_terminal(self):
        state = _make_state(terminal_state=TerminalState.SUCCESS)
        assert should_continue(state) == "stop"

    def test_stop_when_failed(self):
        state = _make_state(terminal_state=TerminalState.FAIL_TOOLING)
        assert should_continue(state) == "stop"

    def test_escalate_when_escalated(self):
        state = _make_state(terminal_state=TerminalState.ESCALATED_TO_HUMAN)
        result = should_continue(state)
        assert result == "escalate"

    def test_stop_when_budget_exceeded(self):
        state = _make_state(terminal_state=TerminalState.STOP_BUDGET)
        assert should_continue(state) == "stop"

    def test_stop_when_policy(self):
        state = _make_state(terminal_state=TerminalState.STOP_POLICY)
        assert should_continue(state) == "stop"
