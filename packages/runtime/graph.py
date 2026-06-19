from __future__ import annotations

from typing import Annotated, Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from packages.runtime.state import RunState, RunStatus, TerminalState


def intake(state: RunState) -> dict:
    """Parse goal, classify risk, initialize run state."""
    return {
        "status": RunStatus.RUNNING,
        "iterations": state.iterations + 1,
    }


def policy_check(state: RunState) -> dict:
    """Evaluate governance policies, check budget."""
    budget_check = state.check_budget()
    if budget_check:
        return {"terminal_state": budget_check, "status": RunStatus.COMPLETED}
    return {}


def plan(state: RunState) -> dict:
    """LLM generates action plan."""
    return {}


def execute(state: RunState) -> dict:
    """Run tool or subagent."""
    return {}


def validate(state: RunState) -> dict:
    """Check output against invariants."""
    return {}


def checkpoint(state: RunState) -> dict:
    """Persist state to Postgres."""
    return {}


def reflect(state: RunState) -> dict:
    """Generate step reflection."""
    return {}


def decide(state: RunState) -> dict:
    """Determine next state."""
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
    graph.add_node("execute", execute)
    graph.add_node("validate", validate)
    graph.add_node("checkpoint", checkpoint)
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
    graph.add_edge("plan", "execute")
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
