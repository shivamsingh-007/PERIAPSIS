"""Tests for full orchestration flow: intake → plan → execute → validate → checkpoint → reflect → decide."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.runtime.graph import (
    build_main_graph,
    checkpoint_node,
    decide,
    execute,
    intake,
    plan,
    policy_check,
    reflect,
    should_continue,
    validation_gate,
    validation_gate_async,
    validate,
)
from packages.runtime.state import (
    Action,
    BudgetPolicy,
    RunState,
    RunStatus,
    StepResult,
    TerminalState,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_state(
    goal: str = "list all users",
    iterations: int = 0,
    tool_calls: int = 0,
    total_cost_usd: float = 0.0,
    runtime_seconds: float = 0.0,
    no_progress_rounds: int = 0,
    terminal_state: TerminalState | None = None,
    plan: list | None = None,
    steps: list | None = None,
    budget: BudgetPolicy | None = None,
    risk_tier: str = "low",
) -> RunState:
    return RunState(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        goal=goal,
        iterations=iterations,
        tool_calls=tool_calls,
        total_cost_usd=total_cost_usd,
        runtime_seconds=runtime_seconds,
        no_progress_rounds=no_progress_rounds,
        terminal_state=terminal_state,
        plan=plan or [],
        steps=steps or [],
        budget=budget or BudgetPolicy(),
        risk_tier=risk_tier,
    )


def _step_result(
    step_number: int = 1,
    success: bool = True,
    result_text: str = "ok",
    cost_usd: float = 0.001,
    tool_name: str | None = "search",
) -> StepResult:
    return StepResult(
        step_number=step_number,
        node_name="execute",
        action=Action(action_type="execute", tool_name=tool_name, input_data={}) if tool_name else None,
        output={"result": result_text, "success": success},
        cost_usd=cost_usd,
    )


# ---------------------------------------------------------------------------
# 1. intake node
# ---------------------------------------------------------------------------

class TestIntakeNode:
    def test_intake_returns_running_status(self):
        state = _make_state(goal="list users")
        result = intake(state)
        assert result["status"] == RunStatus.RUNNING

    def test_intake_increments_iterations(self):
        state = _make_state(goal="list users", iterations=3)
        result = intake(state)
        assert result["iterations"] == 4

    def test_intake_increments_current_step(self):
        state = _make_state(goal="list users")
        state.current_step = 5
        result = intake(state)
        assert result["current_step"] == 6

    def test_intake_classifies_low_risk(self):
        state = _make_state(goal="list all users")
        result = intake(state)
        assert result["risk_tier"] == "low"

    def test_intake_classifies_medium_risk(self):
        state = _make_state(goal="update the database config")
        result = intake(state)
        assert result["risk_tier"] == "medium"

    def test_intake_classifies_high_risk_delete(self):
        state = _make_state(goal="delete all records from users")
        result = intake(state)
        assert result["risk_tier"] == "high"

    def test_intake_classifies_high_risk_deploy(self):
        state = _make_state(goal="deploy to production")
        result = intake(state)
        assert result["risk_tier"] == "high"

    def test_intake_classifies_high_risk_drop(self):
        state = _make_state(goal="drop the table")
        result = intake(state)
        assert result["risk_tier"] == "high"

    def test_intake_classifies_medium_risk_change(self):
        state = _make_state(goal="change the password policy")
        result = intake(state)
        assert result["risk_tier"] == "medium"

    def test_intake_classifies_medium_risk_write(self):
        state = _make_state(goal="write a new report")
        result = intake(state)
        assert result["risk_tier"] == "medium"

    def test_intake_goal_case_insensitive(self):
        state = _make_state(goal="DELETE all DATA")
        result = intake(state)
        assert result["risk_tier"] == "high"

    def test_intake_goal_empty_string(self):
        state = _make_state(goal="")
        result = intake(state)
        assert result["risk_tier"] == "low"


# ---------------------------------------------------------------------------
# 2. policy_check node
# ---------------------------------------------------------------------------

class TestPolicyCheck:
    def test_policy_check_no_budget_exceeded(self):
        state = _make_state(goal="list users", iterations=1)
        result = policy_check(state)
        assert "terminal_state" not in result

    def test_policy_check_budget_exceeded_iterations(self):
        state = _make_state(
            goal="list users",
            iterations=12,
            budget=BudgetPolicy(max_iterations=12),
        )
        result = policy_check(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET
        assert result["status"] == RunStatus.COMPLETED

    def test_policy_check_budget_exceeded_cost(self):
        state = _make_state(
            goal="list users",
            total_cost_usd=3.0,
            budget=BudgetPolicy(max_cost_usd=2.50),
        )
        result = policy_check(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET

    def test_policy_check_budget_exceeded_tool_calls(self):
        state = _make_state(
            goal="list users",
            tool_calls=24,
            budget=BudgetPolicy(max_tool_calls=24),
        )
        result = policy_check(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET

    def test_policy_check_no_progress_exceeded(self):
        state = _make_state(
            goal="list users",
            no_progress_rounds=2,
            budget=BudgetPolicy(stop_on_no_progress_rounds=2),
        )
        result = policy_check(state)
        assert result["terminal_state"] == TerminalState.STOP_NO_PROGRESS


# ---------------------------------------------------------------------------
# 3. plan node
# ---------------------------------------------------------------------------

class TestPlanNode:
    @pytest.mark.asyncio
    async def test_plan_returns_actions(self):
        state = _make_state(goal="list all users")
        result = await plan(state)
        assert "plan" in result
        assert len(result["plan"]) == 2

    @pytest.mark.asyncio
    async def test_plan_first_action_is_research(self):
        state = _make_state(goal="find bugs")
        result = await plan(state)
        assert result["plan"][0].action_type == "research"

    @pytest.mark.asyncio
    async def test_plan_second_action_is_execute(self):
        state = _make_state(goal="find bugs")
        result = await plan(state)
        assert result["plan"][1].action_type == "execute"

    @pytest.mark.asyncio
    async def test_plan_includes_goal_in_input(self):
        state = _make_state(goal="deploy service")
        result = await plan(state)
        assert result["plan"][1].input_data["goal"] == "deploy service"


# ---------------------------------------------------------------------------
# 4. validation_gate node
# ---------------------------------------------------------------------------

class TestValidationGate:
    def test_validation_gate_empty_plan(self):
        state = _make_state()
        result = validation_gate(state)
        assert result == {}

    def test_validation_gate_allows_low_risk(self):
        action = Action(action_type="research", tool_name="search", input_data={})
        state = _make_state(goal="list users", plan=[action])
        result = validation_gate(state)
        assert result == {}

    def test_validation_gate_blocks_unallowed_tool(self):
        action = Action(action_type="execute", tool_name="dangerous_tool", input_data={})
        state = _make_state(goal="list users", plan=[action])
        result = validation_gate(state)
        assert result.get("terminal_state") == TerminalState.STOP_POLICY

    def test_validation_gate_escalates_medium_risk(self):
        action = Action(action_type="write", tool_name="ticketing", input_data={})
        state = _make_state(goal="update config", plan=[action], risk_tier="medium")
        result = validation_gate(state)
        assert result.get("terminal_state") == TerminalState.ESCALATED_TO_HUMAN

    def test_validation_gate_escalates_high_risk_review(self):
        action = Action(action_type="deploy", tool_name="internal-read", input_data={})
        state = _make_state(goal="deploy to production", plan=[action], risk_tier="high")
        result = validation_gate(state)
        assert result.get("terminal_state") == TerminalState.ESCALATED_TO_HUMAN

    def test_validation_gate_checks_cost_limit(self):
        action = Action(action_type="research", tool_name="search", input_data={})
        state = _make_state(
            goal="list users",
            plan=[action],
            total_cost_usd=15.0,
        )
        result = validation_gate(state)
        assert result.get("terminal_state") == TerminalState.STOP_POLICY


# ---------------------------------------------------------------------------
# 5. validation_gate_async node
# ---------------------------------------------------------------------------

class TestValidationGateAsync:
    @pytest.mark.asyncio
    async def test_async_gate_empty_plan(self):
        state = _make_state()
        result = await validation_gate_async(state)
        assert result == {}

    @pytest.mark.asyncio
    @patch("packages.runtime.graph.governance_event_logger")
    async def test_async_gate_logs_policy_violation(self, mock_logger):
        mock_logger.log_policy_violation = AsyncMock()
        action = Action(action_type="execute", tool_name="dangerous_tool", input_data={})
        state = _make_state(goal="list users", plan=[action])
        result = await validation_gate_async(state)
        assert result.get("terminal_state") == TerminalState.STOP_POLICY
        mock_logger.log_policy_violation.assert_called_once()

    @pytest.mark.asyncio
    @patch("packages.runtime.graph.governance_event_logger")
    async def test_async_gate_logs_approval_request(self, mock_logger):
        mock_logger.log_approval_requested = AsyncMock()
        action = Action(action_type="write", tool_name="ticketing", input_data={})
        state = _make_state(goal="update config", plan=[action], risk_tier="medium")
        result = await validation_gate_async(state)
        assert result.get("terminal_state") == TerminalState.ESCALATED_TO_HUMAN
        mock_logger.log_approval_requested.assert_called_once()


# ---------------------------------------------------------------------------
# 6. execute node
# ---------------------------------------------------------------------------

class TestExecuteNode:
    def test_execute_empty_plan_returns_fail_tooling(self):
        state = _make_state()
        result = execute(state)
        assert result["terminal_state"] == TerminalState.FAIL_TOOLING
        assert result["status"] == RunStatus.COMPLETED

    def test_execute_runs_action(self):
        action = Action(action_type="research", tool_name="search", input_data={})
        state = _make_state(goal="list users", plan=[action])
        state.current_step = 1
        result = execute(state)
        assert "steps" in result
        assert len(result["steps"]) == 1
        assert result["steps"][0].output["success"] is True

    def test_execute_increments_tool_calls(self):
        action = Action(action_type="research", tool_name="search", input_data={})
        state = _make_state(goal="list users", plan=[action], tool_calls=3)
        state.current_step = 1
        result = execute(state)
        assert result["tool_calls"] == 4

    def test_execute_adds_cost(self):
        action = Action(action_type="research", tool_name="search", input_data={})
        state = _make_state(goal="list users", plan=[action], total_cost_usd=0.01)
        state.current_step = 1
        result = execute(state)
        assert result["total_cost_usd"] == pytest.approx(0.011, abs=1e-6)

    def test_execute_step_has_latency(self):
        action = Action(action_type="research", tool_name="search", input_data={})
        state = _make_state(goal="list users", plan=[action])
        state.current_step = 1
        result = execute(state)
        assert result["steps"][0].latency_ms >= 0

    def test_execute_step_records_action_type(self):
        action = Action(action_type="deploy", tool_name="deployer", input_data={})
        state = _make_state(goal="deploy", plan=[action])
        state.current_step = 1
        result = execute(state)
        assert result["steps"][0].action.action_type == "deploy"


# ---------------------------------------------------------------------------
# 7. validate node
# ---------------------------------------------------------------------------

class TestValidateNode:
    def test_validate_no_steps_returns_fail(self):
        state = _make_state()
        result = validate(state)
        assert result["terminal_state"] == TerminalState.FAIL_INVARIANT

    def test_validate_failing_step_returns_fail(self):
        step = _step_result(success=False)
        state = _make_state(steps=[step])
        result = validate(state)
        assert result["terminal_state"] == TerminalState.FAIL_INVARIANT

    def test_validate_passing_step(self):
        step = _step_result(success=True, result_text="done")
        state = _make_state(steps=[step])
        result = validate(state)
        assert result["validation_result"]["passed"] is True
        assert result["validation_result"]["step"] == 1

    def test_validate_resets_no_progress(self):
        step = _step_result(success=True, result_text="done")
        state = _make_state(steps=[step], no_progress_rounds=2)
        result = validate(state)
        assert result["no_progress_rounds"] == 0

    def test_validate_failing_step_does_not_reset_progress(self):
        step = _step_result(success=True, result_text="")
        state = _make_state(steps=[step], no_progress_rounds=1)
        result = validate(state)
        assert "no_progress_rounds" not in result


# ---------------------------------------------------------------------------
# 8. reflect node
# ---------------------------------------------------------------------------

class TestReflectNode:
    def test_reflect_empty_steps_returns_empty(self):
        state = _make_state()
        result = reflect(state)
        assert result == {}

    def test_reflect_increments_no_progress_on_empty_result(self):
        step = _step_result(result_text="")
        state = _make_state(steps=[step], no_progress_rounds=0)
        result = reflect(state)
        assert result["no_progress_rounds"] == 1

    def test_reflect_keeps_progress_on_success(self):
        step = _step_result(result_text="done")
        state = _make_state(steps=[step], no_progress_rounds=0)
        result = reflect(state)
        assert result["no_progress_rounds"] == 0

    def test_reflect_increments_no_progress_rounds(self):
        step = _step_result(result_text="")
        state = _make_state(steps=[step], no_progress_rounds=3)
        result = reflect(state)
        assert result["no_progress_rounds"] == 4


# ---------------------------------------------------------------------------
# 9. decide node
# ---------------------------------------------------------------------------

class TestDecideNode:
    def test_decide_returns_empty_when_can_continue(self):
        state = _make_state(goal="list users", iterations=1)
        result = decide(state)
        assert "terminal_state" not in result

    def test_decide_returns_budget_exceeded(self):
        state = _make_state(
            goal="list users",
            iterations=12,
            budget=BudgetPolicy(max_iterations=12),
        )
        result = decide(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET

    def test_decide_max_iterations_returns_success(self):
        state = _make_state(
            goal="list users",
            iterations=12,
            budget=BudgetPolicy(max_iterations=11),
        )
        result = decide(state)
        assert result["terminal_state"] == TerminalState.SUCCESS
        assert result["status"] == RunStatus.COMPLETED

    def test_decide_no_progress_exceeded(self):
        state = _make_state(
            goal="list users",
            no_progress_rounds=2,
            budget=BudgetPolicy(stop_on_no_progress_rounds=2),
        )
        result = decide(state)
        assert result["terminal_state"] == TerminalState.STOP_NO_PROGRESS

    def test_decide_cost_exceeded(self):
        state = _make_state(
            goal="list users",
            total_cost_usd=5.0,
            budget=BudgetPolicy(max_cost_usd=2.50),
        )
        result = decide(state)
        assert result["terminal_state"] == TerminalState.STOP_BUDGET


# ---------------------------------------------------------------------------
# 10. should_continue helper
# ---------------------------------------------------------------------------

class TestShouldContinue:
    def test_continue_when_no_terminal(self):
        state = _make_state(goal="list users")
        assert should_continue(state) == "continue"

    def test_stop_when_terminal_set(self):
        state = _make_state(goal="list users", terminal_state=TerminalState.SUCCESS)
        assert should_continue(state) == "stop"

    def test_escalate_when_escalated(self):
        state = _make_state(goal="list users", terminal_state=TerminalState.ESCALATED_TO_HUMAN)
        assert should_continue(state) == "escalate"

    def test_stop_when_budget_exceeded(self):
        state = _make_state(goal="list users", terminal_state=TerminalState.STOP_BUDGET)
        assert should_continue(state) == "stop"


# ---------------------------------------------------------------------------
# 11. checkpoint_node
# ---------------------------------------------------------------------------

class TestCheckpointNode:
    @pytest.mark.asyncio
    @patch("packages.runtime.graph.checkpoint_store")
    async def test_checkpoint_saves_state(self, mock_store):
        mock_store.save = AsyncMock(return_value="cp_ref")
        state = _make_state(goal="list users")
        result = await checkpoint_node(state)
        assert result == {}
        mock_store.save.assert_called_once()

    @pytest.mark.asyncio
    @patch("packages.runtime.graph.checkpoint_store")
    async def test_checkpoint_passes_run_id(self, mock_store):
        mock_store.save = AsyncMock(return_value="cp_ref")
        state = _make_state(goal="list users")
        await checkpoint_node(state)
        call_kwargs = mock_store.save.call_args[1]
        assert call_kwargs["run_id"] == state.run_id


# ---------------------------------------------------------------------------
# 12. build_main_graph
# ---------------------------------------------------------------------------

class TestBuildMainGraph:
    def test_build_main_graph_returns_compiled_graph(self):
        graph = build_main_graph()
        assert graph is not None
        assert hasattr(graph, "ainvoke")

    def test_graph_has_expected_nodes(self):
        graph = build_main_graph()
        assert hasattr(graph, "get_graph")
