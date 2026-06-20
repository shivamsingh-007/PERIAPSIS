from __future__ import annotations
"""Tests for packages.runtime.graph - Graph nodes and routing logic."""

import uuid

import pytest

from packages.runtime.executor import ToolExecutionResult
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


class MockExecutor:
    """Mock executor that returns controlled results for testing."""

    def __init__(
        self,
        output: str = "Mock LLM response",
        prompt_tokens: int = 100,
        completion_tokens: int = 50,
        cost_usd: float = 0.001,
        error: str | None = None,
    ):
        self.output = output
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.cost_usd = cost_usd
        self.error = error

    async def execute(self, state: RunState) -> ToolExecutionResult:
        return ToolExecutionResult(
            output=self.output,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            cost_usd=self.cost_usd,
            error=self.error,
        )


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
    @pytest.mark.asyncio
    async def test_execute_with_plan(self):
        state = _make_state(
            current_step=1,
            plan=[Action(action_type="research", tool_name="search")],
        )
        executor = MockExecutor(output="Research findings", cost_usd=0.002)
        result = await execute(state, executor=executor)
        assert len(result["steps"]) == 1
        assert result["steps"][0].node_name == "execute"
        assert result["tool_calls"] == 1
        assert result["total_cost_usd"] == 0.002
        assert result["last_output"] == "Research findings"

    @pytest.mark.asyncio
    async def test_execute_empty_plan(self):
        state = _make_state(plan=[])
        result = await execute(state)
        assert result["terminal_state"] == TerminalState.FAIL_TOOLING
        assert result["status"] == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_step_number(self):
        state = _make_state(
            current_step=3,
            plan=[Action(action_type="execute", tool_name="default")],
        )
        result = await execute(state, executor=MockExecutor())
        assert result["steps"][0].step_number == 3

    @pytest.mark.asyncio
    async def test_execute_updates_tokens(self):
        state = _make_state(
            plan=[Action(action_type="research", tool_name="search")],
            tokens_prompt=10,
            tokens_completion=5,
        )
        executor = MockExecutor(prompt_tokens=200, completion_tokens=80)
        result = await execute(state, executor=executor)
        assert result["tokens_prompt"] == 210
        assert result["tokens_completion"] == 85

    @pytest.mark.asyncio
    async def test_execute_accumulates_cost(self):
        state = _make_state(
            plan=[Action(action_type="research", tool_name="search")],
            total_cost_usd=0.01,
        )
        executor = MockExecutor(cost_usd=0.005)
        result = await execute(state, executor=executor)
        assert result["total_cost_usd"] == pytest.approx(0.015)

    @pytest.mark.asyncio
    async def test_execute_executor_error(self):
        state = _make_state(
            plan=[Action(action_type="research", tool_name="search")],
        )
        executor = MockExecutor(error="API timeout")
        result = await execute(state, executor=executor)
        assert result["terminal_state"] == TerminalState.FAIL_TOOLING
        assert result["status"] == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_sets_last_output(self):
        state = _make_state(
            plan=[Action(action_type="research", tool_name="search")],
        )
        executor = MockExecutor(output="Detailed analysis result")
        result = await execute(state, executor=executor)
        assert result["last_output"] == "Detailed analysis result"

    @pytest.mark.asyncio
    async def test_execute_preserves_existing_steps(self):
        existing_step = StepResult(
            step_number=1, node_name="plan", output={"result": "planned"}
        )
        state = _make_state(
            current_step=2,
            plan=[Action(action_type="research", tool_name="search")],
            steps=[existing_step],
        )
        result = await execute(state, executor=MockExecutor())
        assert len(result["steps"]) == 2
        assert result["steps"][0].node_name == "plan"
        assert result["steps"][1].node_name == "execute"


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
