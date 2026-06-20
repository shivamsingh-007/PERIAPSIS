from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.runtime.executor import ToolExecutionResult
from packages.runtime.state import (
    Action,
    BudgetPolicy,
    RunState,
    RunStatus,
    StepResult,
    TerminalState,
)
from packages.runtime.graph import (
    intake,
    plan,
    execute,
    validate,
    reflect,
    decide,
    should_continue,
    build_main_graph,
)


class MockExecutor:
    """Mock executor for lifecycle tests."""

    def __init__(self, output: str = "Mock output", cost_usd: float = 0.001):
        self.output = output
        self.cost_usd = cost_usd

    async def execute(self, state: RunState) -> ToolExecutionResult:
        return ToolExecutionResult(
            output=self.output,
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=self.cost_usd,
        )


def _make_state(goal="test goal", tenant_id=None):
    return RunState(
        run_id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        goal=goal,
        budget=BudgetPolicy(max_iterations=5, max_cost_usd=1.0),
    )


class TestIntakeNode:
    def test_low_risk_goal(self):
        state = _make_state("read the config file")
        result = intake(state)
        assert result["status"] == RunStatus.RUNNING
        assert result["risk_tier"] == "low"

    def test_high_risk_goal(self):
        state = _make_state("delete production database")
        result = intake(state)
        assert result["risk_tier"] == "high"

    def test_medium_risk_goal(self):
        state = _make_state("update the user profile")
        result = intake(state)
        assert result["risk_tier"] == "medium"

    def test_increments_iterations(self):
        state = _make_state()
        state.iterations = 3
        result = intake(state)
        assert result["iterations"] == 4


class TestPlanNode:
    @pytest.mark.asyncio
    async def test_plan_generates_actions(self):
        state = _make_state()
        result = await plan(state)
        assert "plan" in result
        assert len(result["plan"]) == 2
        assert result["plan"][0].action_type == "research"

    @pytest.mark.asyncio
    async def test_plan_includes_goal(self):
        state = _make_state("refactor auth")
        result = await plan(state)
        assert result["plan"][1].input_data["goal"] == "refactor auth"


class TestExecuteNode:
    @pytest.mark.asyncio
    async def test_execute_runs_action(self):
        state = _make_state()
        state.plan = [
            Action(action_type="execute", tool_name="default", input_data={"goal": "test"})
        ]
        result = await execute(state, executor=MockExecutor())
        assert "steps" in result
        assert len(result["steps"]) == 1
        assert result["steps"][0].output.get("success") is True

    @pytest.mark.asyncio
    async def test_execute_no_plan_fails(self):
        state = _make_state()
        state.plan = []
        result = await execute(state)
        assert result["terminal_state"] == TerminalState.FAIL_TOOLING

    @pytest.mark.asyncio
    async def test_execute_increments_cost(self):
        state = _make_state()
        state.plan = [
            Action(action_type="execute", tool_name="default", input_data={})
        ]
        result = await execute(state, executor=MockExecutor(cost_usd=0.005))
        assert result["total_cost_usd"] == 0.005


class TestValidateNode:
    def test_validate_success(self):
        state = _make_state()
        state.steps = [
            StepResult(
                step_number=1,
                node_name="execute",
                output={"success": True, "result": "done"},
                latency_ms=100,
                cost_tokens_in=50,
                cost_tokens_out=25,
                cost_usd=0.001,
            )
        ]
        result = validate(state)
        assert result["validation_result"]["passed"] is True
        assert result["no_progress_rounds"] == 0

    def test_validate_no_steps_fails(self):
        state = _make_state()
        state.steps = []
        result = validate(state)
        assert result["terminal_state"] == TerminalState.FAIL_INVARIANT

    def test_validate_failed_step(self):
        state = _make_state()
        state.steps = [
            StepResult(
                step_number=1,
                node_name="execute",
                output={"success": False},
                latency_ms=100,
                cost_tokens_in=50,
                cost_tokens_out=25,
                cost_usd=0.001,
            )
        ]
        result = validate(state)
        assert result["terminal_state"] == TerminalState.FAIL_INVARIANT


class TestReflectNode:
    def test_reflect_no_steps(self):
        state = _make_state()
        state.steps = []
        result = reflect(state)
        assert result == {}

    def test_reflect_with_progress(self):
        state = _make_state()
        state.steps = [
            StepResult(
                step_number=1,
                node_name="execute",
                output={"result": "something", "success": True},
                latency_ms=100,
                cost_tokens_in=50,
                cost_tokens_out=25,
                cost_usd=0.001,
            )
        ]
        result = reflect(state)
        assert result["no_progress_rounds"] == 0

    def test_reflect_no_progress(self):
        state = _make_state()
        state.no_progress_rounds = 1
        state.steps = [
            StepResult(
                step_number=1,
                node_name="execute",
                output={"result": "", "success": True},
                latency_ms=100,
                cost_tokens_in=50,
                cost_tokens_out=25,
                cost_usd=0.001,
            )
        ]
        result = reflect(state)
        assert result["no_progress_rounds"] == 2


class TestDecideNode:
    def test_decide_continues(self):
        state = _make_state()
        state.iterations = 1
        result = decide(state)
        assert result == {}

    def test_decide_max_iterations(self):
        state = _make_state()
        state.iterations = 5
        state.budget = BudgetPolicy(max_iterations=5)
        result = decide(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET

    def test_decide_budget_exceeded(self):
        state = _make_state()
        state.total_cost_usd = 2.0
        state.budget = BudgetPolicy(max_cost_usd=1.0)
        result = decide(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET


class TestShouldContinue:
    def test_continue(self):
        state = _make_state()
        assert should_continue(state) == "continue"

    def test_stop_terminal(self):
        state = _make_state()
        state.terminal_state = TerminalState.SUCCESS
        state.status = RunStatus.COMPLETED
        assert should_continue(state) == "stop"

    def test_escalate(self):
        state = _make_state()
        state.terminal_state = TerminalState.ESCALATED_TO_HUMAN
        state.status = RunStatus.PAUSED
        assert should_continue(state) == "escalate"


class TestBuildMainGraph:
    def test_graph_builds(self):
        graph = build_main_graph()
        assert graph is not None
