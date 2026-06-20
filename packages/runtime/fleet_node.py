from __future__ import annotations

from typing import Any

from packages.runtime.state import RunState, Action, StepResult, TerminalState
from packages.fleet.coordinator import FleetCoordinator, FleetJob, FleetJobState, fleet_coordinator
from packages.fleet.swarm import swarm_manager
from packages.fleet.compliance import RiskTier
from packages.graphify.graph_router import graph_router
from packages.logging.structured import get_logger

logger = get_logger("fleet_node")


def _get_state_field(state: Any, field: str, default: Any = None) -> Any:
    """Safely get a field from either a RunState Pydantic model or a dict."""
    if isinstance(state, RunState):
        return getattr(state, field, default)
    if isinstance(state, dict):
        return state.get(field, default)
    return getattr(state, field, default)


def _get_steps(state: Any) -> list:
    """Get steps from state, handling both RunState and dict."""
    if isinstance(state, RunState):
        return list(state.steps)
    if isinstance(state, dict):
        return list(state.get("steps", []))
    return []


def _get_goal(state: Any) -> str:
    return _get_state_field(state, "goal", "")


def _get_risk_tier_str(state: Any) -> str:
    val = _get_state_field(state, "risk_tier", "low")
    if hasattr(val, "value"):
        return val.value
    return str(val)


async def fleet_dispatch(state: Any) -> dict:
    """Dispatch work to fleet. Accepts RunState or dict for backwards compatibility."""
    goal = _get_goal(state)
    risk_tier_str = _get_risk_tier_str(state)

    budget = _get_state_field(state, "budget", None)
    budget_limit = budget.max_cost_usd if budget and hasattr(budget, "max_cost_usd") else 10.0

    risk_tier = RiskTier(risk_tier_str) if risk_tier_str in RiskTier.__members__.values() else RiskTier.LOW

    swarm_name = _select_swarm(goal, risk_tier)

    job = await fleet_coordinator.submit_job(
        goal=goal,
        risk_tier=risk_tier,
        budget_limit=budget_limit,
        swarm_name=swarm_name,
    )

    if job.state == FleetJobState.BLOCKED:
        return {
            "terminal_state": TerminalState.ESCALATED_TO_HUMAN,
            "status": "paused",
        }

    completed_job = await fleet_coordinator.execute_job(job.job_id)

    total_cost = sum(r.cost for r in completed_job.sub_jobs)
    outputs = [r.output for r in completed_job.sub_jobs if r.output]

    if completed_job.state == FleetJobState.COMPLETED:
        return {
            "last_output": outputs[-1] if outputs else "",
            "total_cost_usd": _get_state_field(state, "total_cost_usd", 0) + total_cost,
        }
    else:
        return {
            "terminal_state": TerminalState.FAIL_TOOLING,
            "status": "completed",
            "total_cost_usd": _get_state_field(state, "total_cost_usd", 0) + total_cost,
        }


def _select_swarm(goal: str, risk_tier: RiskTier) -> str:
    decision = graph_router.route_task(goal)

    swarm_map = {
        "security": "security-swarm",
        "governance": "governance-swarm",
        "fleet": "research-swarm",
        "testing": "code-swarm",
    }

    if decision.confidence > 0.3:
        mapped = swarm_map.get(decision.target_agent)
        if mapped:
            logger.info(f"Graph router selected swarm: {mapped} (confidence: {decision.confidence})")
            return mapped

    goal_lower = goal.lower()
    if any(word in goal_lower for word in ["security", "vulnerability", "audit", "scan"]):
        return "security-swarm"
    elif any(word in goal_lower for word in ["research", "investigate", "analyze", "find"]):
        return "research-swarm"
    elif any(word in goal_lower for word in ["compliance", "policy", "governance", "regulation"]):
        return "governance-swarm"
    else:
        return "code-swarm"


async def fleet_reflect(state: Any) -> dict:
    """Reflect on fleet execution results."""
    steps = _get_steps(state)
    if not steps:
        return {}

    last_step = steps[-1]
    if isinstance(last_step, dict):
        success = last_step.get("success", False)
    elif hasattr(last_step, "output"):
        success = last_step.output.get("success", False) if isinstance(last_step.output, dict) else False
    else:
        success = False

    if not success:
        consecutive_errors = _get_state_field(state, "consecutive_errors", 0) + 1
        return {
            "consecutive_errors": consecutive_errors,
            "should_compact": consecutive_errors >= 3,
        }

    return {"consecutive_errors": 0}
