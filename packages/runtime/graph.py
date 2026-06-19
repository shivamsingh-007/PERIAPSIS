from __future__ import annotations

import time
import uuid
from typing import Literal

from langgraph.graph import END, StateGraph

from packages.governance.events import governance_event_logger
from packages.governance.policy import PolicyDecision, policy_engine
from packages.runtime.checkpoint import checkpoint_store
from packages.runtime.state import (
    Action,
    RunState,
    RunStatus,
    StepResult,
    TerminalState,
)


def intake(state: RunState) -> dict:
    """Parse goal, classify risk, initialize run state."""
    risk_tier = "low"
    goal_lower = state.goal.lower()
    if any(w in goal_lower for w in ["delete", "remove", "drop", "deploy", "production"]):
        risk_tier = "high"
    elif any(w in goal_lower for w in ["update", "modify", "change", "write"]):
        risk_tier = "medium"

    return {
        "status": RunStatus.RUNNING,
        "risk_tier": risk_tier,
        "iterations": state.iterations + 1,
        "current_step": state.current_step + 1,
    }


def policy_check(state: RunState) -> dict:
    """Evaluate governance policies, check budget."""
    budget_check = state.check_budget()
    if budget_check:
        return {"terminal_state": budget_check, "status": RunStatus.COMPLETED}
    return {}


def plan(state: RunState) -> dict:
    """Generate action plan based on goal."""
    actions = [
        Action(action_type="research", tool_name="search", input_data={"query": state.goal}),
        Action(action_type="execute", tool_name="default", input_data={"goal": state.goal}),
    ]
    return {"plan": actions}


def validation_gate(state: RunState) -> dict:
    """Check action eligibility against governance policies before execution."""
    if not state.plan:
        return {}

    action = state.plan[0]
    decision = policy_engine.evaluate_action(
        action_type=action.action_type,
        tool_name=action.tool_name,
        risk_tier=state.risk_tier.value if hasattr(state.risk_tier, 'value') else state.risk_tier,
        current_cost=state.total_cost_usd,
        current_iterations=state.iterations,
    )

    if policy_engine.is_denied(decision):
        return {
            "terminal_state": TerminalState.STOP_POLICY,
            "status": RunStatus.COMPLETED,
        }

    if policy_engine.should_escalate(decision):
        return {
            "terminal_state": TerminalState.ESCALATED_TO_HUMAN,
            "status": RunStatus.PAUSED,
        }

    return {}


async def validation_gate_async(state: RunState) -> dict:
    """Async validation gate that also logs governance events."""
    if not state.plan:
        return {}

    action = state.plan[0]
    decision = policy_engine.evaluate_action(
        action_type=action.action_type,
        tool_name=action.tool_name,
        risk_tier=state.risk_tier.value if hasattr(state.risk_tier, 'value') else state.risk_tier,
        current_cost=state.total_cost_usd,
        current_iterations=state.iterations,
    )

    if policy_engine.is_denied(decision):
        await governance_event_logger.log_policy_violation(
            run_id=state.run_id,
            tenant_id=state.tenant_id,
            policy_rule=f"action_denied:{action.action_type}",
            details={
                "tool_name": action.tool_name,
                "risk_tier": state.risk_tier.value if hasattr(state.risk_tier, 'value') else state.risk_tier,
                "decision": decision.value,
            },
        )
        return {
            "terminal_state": TerminalState.STOP_POLICY,
            "status": RunStatus.COMPLETED,
        }

    if policy_engine.should_escalate(decision):
        await governance_event_logger.log_approval_requested(
            run_id=state.run_id,
            tenant_id=state.tenant_id,
            action_type=action.action_type,
            tool_name=action.tool_name,
            risk_tier=state.risk_tier.value if hasattr(state.risk_tier, 'value') else state.risk_tier,
        )
        return {
            "terminal_state": TerminalState.ESCALATED_TO_HUMAN,
            "status": RunStatus.PAUSED,
        }

    return {}


def execute(state: RunState) -> dict:
    """Run the current action from the plan."""
    if not state.plan:
        return {"terminal_state": TerminalState.FAIL_TOOLING, "status": RunStatus.COMPLETED}

    step_number = state.current_step
    action = state.plan[0] if state.plan else None

    start = time.time()
    output = {"result": f"Executed: {action.action_type if action else 'none'}", "success": True}
    latency_ms = int((time.time() - start) * 1000)

    step = StepResult(
        step_number=step_number,
        node_name="execute",
        action=action,
        output=output,
        latency_ms=latency_ms,
        cost_tokens_in=100,
        cost_tokens_out=50,
        cost_usd=0.001,
    )

    return {
        "steps": state.steps + [step],
        "tool_calls": state.tool_calls + 1,
        "total_cost_usd": state.total_cost_usd + step.cost_usd,
    }


def validate(state: RunState) -> dict:
    """Check output against invariants."""
    if not state.steps:
        return {"terminal_state": TerminalState.FAIL_INVARIANT, "status": RunStatus.COMPLETED}

    last_step = state.steps[-1]
    if not last_step.output.get("success", False):
        return {"terminal_state": TerminalState.FAIL_INVARIANT, "status": RunStatus.COMPLETED}

    return {
        "validation_result": {"passed": True, "step": last_step.step_number},
        "no_progress_rounds": 0,
    }


async def checkpoint_node(state: RunState) -> dict:
    """Persist state to Postgres."""
    await checkpoint_store.save(
        run_id=state.run_id,
        tenant_id=state.tenant_id,
        state=state.model_dump(mode="json"),
    )
    return {}


def reflect(state: RunState) -> dict:
    """Generate step reflection."""
    if not state.steps:
        return {}

    last_step = state.steps[-1]
    return {
        "no_progress_rounds": state.no_progress_rounds + 1
        if last_step.output.get("result", "") == ""
        else state.no_progress_rounds
    }


def decide(state: RunState) -> dict:
    """Determine next state."""
    budget_check = state.check_budget()
    if budget_check:
        return {"terminal_state": budget_check, "status": RunStatus.COMPLETED}

    if state.iterations >= state.budget.max_iterations:
        return {"terminal_state": TerminalState.SUCCESS, "status": RunStatus.COMPLETED}

    return {}


def should_continue(state: RunState) -> Literal["continue", "escalate", "stop"]:
    if state.is_terminal():
        return "stop"
    if state.terminal_state == TerminalState.ESCALATED_TO_HUMAN:
        return "escalate"
    return "continue"


def build_main_graph() -> StateGraph:
    graph = StateGraph(RunState)

    graph.add_node("intake", intake)
    graph.add_node("policy_check", policy_check)
    graph.add_node("plan", plan)
    graph.add_node("validation_gate", validation_gate)
    graph.add_node("execute", execute)
    graph.add_node("validate", validate)
    graph.add_node("checkpoint", checkpoint_node)
    graph.add_node("reflect", reflect)
    graph.add_node("decide", decide)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "policy_check")
    graph.add_conditional_edges(
        "policy_check",
        should_continue,
        {
            "continue": "plan",
            "escalate": END,
            "stop": END,
        },
    )
    graph.add_edge("plan", "validation_gate")
    graph.add_conditional_edges(
        "validation_gate",
        should_continue,
        {
            "continue": "execute",
            "escalate": END,
            "stop": END,
        },
    )
    graph.add_edge("execute", "validate")
    graph.add_edge("validate", "checkpoint")
    graph.add_edge("checkpoint", "reflect")
    graph.add_edge("reflect", "decide")
    graph.add_conditional_edges(
        "decide",
        should_continue,
        {
            "continue": "intake",
            "escalate": END,
            "stop": END,
        },
    )

    return graph.compile()
