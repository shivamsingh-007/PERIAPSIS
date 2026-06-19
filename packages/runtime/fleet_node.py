from __future__ import annotations

from typing import Any

from packages.runtime.state import RunState, Action, StepResult, TerminalState
from packages.fleet.coordinator import FleetCoordinator, FleetJob, FleetJobState, fleet_coordinator
from packages.fleet.swarm import swarm_manager
from packages.fleet.compliance import RiskTier
from packages.logging.structured import get_logger

logger = get_logger("fleet_node")


async def fleet_dispatch(state: RunState) -> RunState:
    goal = state.get("goal", "")
    risk_tier_str = state.get("risk_tier", "low")
    budget_limit = state.get("budget_limit", 10.0)

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
            **state,
            "terminal": TerminalState.ESCALATED_TO_HUMAN,
            "terminal_reason": f"Fleet blocked: {job.error}",
            "steps": state.get("steps", []) + [
                StepResult(
                    action=Action(type="fleet_dispatch", detail=f"Blocked: {job.error}"),
                    observation=f"Compliance gate blocked fleet job: {job.error}",
                    success=False,
                ).model_dump()
            ],
        }

    completed_job = await fleet_coordinator.execute_job(job.job_id)

    steps = state.get("steps", [])
    for sub_result in completed_job.sub_jobs:
        steps.append(
            StepResult(
                action=Action(
                    type="fleet_worker",
                    detail=f"Worker {sub_result.worker_id}",
                ),
                observation=str(sub_result.output)[:500] if sub_result.output else sub_result.error,
                success=sub_result.status.value == "completed",
            ).model_dump()
        )

    total_cost = sum(r.cost for r in completed_job.sub_jobs)
    outputs = [r.output for r in completed_job.sub_jobs if r.output]

    if completed_job.state == FleetJobState.COMPLETED:
        return {
            **state,
            "final_output": outputs[-1] if outputs else None,
            "total_cost": state.get("total_cost", 0) + total_cost,
            "total_steps": state.get("total_steps", 0) + len(completed_job.sub_jobs),
            "steps": steps,
        }
    else:
        return {
            **state,
            "terminal": TerminalState.FAIL_TOOLING,
            "terminal_reason": f"Fleet job failed: {completed_job.error}",
            "total_cost": state.get("total_cost", 0) + total_cost,
            "total_steps": state.get("total_steps", 0) + len(completed_job.sub_jobs),
            "steps": steps,
        }


def _select_swarm(goal: str, risk_tier: RiskTier) -> str:
    goal_lower = goal.lower()

    if any(word in goal_lower for word in ["security", "vulnerability", "audit", "scan"]):
        return "security-swarm"
    elif any(word in goal_lower for word in ["research", "investigate", "analyze", "find"]):
        return "research-swarm"
    elif any(word in goal_lower for word in ["compliance", "policy", "governance", "regulation"]):
        return "governance-swarm"
    else:
        return "code-swarm"


async def fleet_reflect(state: RunState) -> RunState:
    steps = state.get("steps", [])
    if not steps:
        return state

    last_step = steps[-1]
    success = last_step.get("success", False)

    if not success:
        return {
            **state,
            "consecutive_errors": state.get("consecutive_errors", 0) + 1,
            "should_compact": state.get("consecutive_errors", 0) >= 3,
        }

    return {
        **state,
        "consecutive_errors": 0,
    }
