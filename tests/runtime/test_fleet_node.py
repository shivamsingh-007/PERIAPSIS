from __future__ import annotations

import uuid

import pytest

from packages.runtime.fleet_node import (
    _select_swarm,
    fleet_reflect,
)


@pytest.fixture
def base_state():
    return {
        "goal": "Refactor authentication module",
        "risk_tier": "low",
        "budget_limit": 5.0,
        "tenant_id": str(uuid.uuid4()),
        "steps": [],
        "total_cost": 0.0,
        "total_steps": 0,
        "consecutive_errors": 0,
    }


class TestSelectSwarm:
    def test_security_keyword(self):
        result = _select_swarm("Fix security vulnerability", "low")
        assert "security" in result.lower() or result == "security-swarm"

    def test_research_keyword(self):
        result = _select_swarm("Research the best approach", "low")
        assert "research" in result.lower() or result == "research-swarm"

    def test_governance_keyword(self):
        result = _select_swarm("Check compliance requirements", "low")
        assert "governance" in result.lower() or result == "governance-swarm"

    def test_default_keyword(self):
        result = _select_swarm("Write code for the feature", "low")
        assert result is not None

    def test_empty_goal(self):
        result = _select_swarm("", "low")
        assert result is not None


class TestFleetReflect:
    @pytest.mark.asyncio
    async def test_no_steps(self, base_state):
        result = await fleet_reflect(base_state)
        assert result == base_state

    @pytest.mark.asyncio
    async def test_successful_step(self, base_state):
        base_state["steps"] = [
            {"success": True, "action_type": "fleet_worker", "detail": "worker-1"}
        ]
        result = await fleet_reflect(base_state)
        assert result["consecutive_errors"] == 0

    @pytest.mark.asyncio
    async def test_failed_step_increments_errors(self, base_state):
        base_state["steps"] = [
            {"success": False, "action_type": "fleet_worker", "detail": "worker-1"}
        ]
        result = await fleet_reflect(base_state)
        assert result["consecutive_errors"] == 1

    @pytest.mark.asyncio
    async def test_multiple_failures_triggers_compact(self, base_state):
        base_state["consecutive_errors"] = 3
        base_state["steps"] = [
            {"success": False, "action_type": "fleet_worker", "detail": "w"}
        ]
        result = await fleet_reflect(base_state)
        assert result["consecutive_errors"] == 4
        assert result["should_compact"] is True
