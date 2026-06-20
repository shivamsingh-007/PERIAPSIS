from __future__ import annotations

import pytest

from packages.governance.policy import (
    PolicyDecision,
    PolicyEngine,
    RiskTierConfig,
    ToolPolicy,
    RiskTier,
)


@pytest.fixture
def engine():
    return PolicyEngine()


class TestPolicyEngine:
    def test_init(self, engine):
        assert engine is not None

    def test_register_tool(self, engine):
        policy = ToolPolicy(
            name="write_file",
            allowed_tiers=[RiskTier.LOW, RiskTier.MEDIUM],
            requires_approval_tiers=[RiskTier.HIGH],
        )
        engine.register_tool(policy)
        assert "write_file" in engine._tool_policies

    def test_evaluate_action_low_risk(self, engine):
        decision = engine.evaluate_action(
            action_type="read",
            tool_name="search",
            risk_tier="low",
        )
        assert decision in [PolicyDecision.ALLOW, PolicyDecision.REQUIRE_APPROVAL]

    def test_evaluate_action_high_risk(self, engine):
        decision = engine.evaluate_action(
            action_type="delete",
            tool_name="write_file",
            risk_tier="high",
        )
        assert decision in [PolicyDecision.DENY, PolicyDecision.REQUIRE_APPROVAL, PolicyDecision.REQUIRE_SECONDARY_REVIEW]

    def test_should_escalate(self, engine):
        assert engine.should_escalate(PolicyDecision.REQUIRE_APPROVAL) is True
        assert engine.should_escalate(PolicyDecision.REQUIRE_SECONDARY_REVIEW) is True
        assert engine.should_escalate(PolicyDecision.ALLOW) is False

    def test_is_denied(self, engine):
        assert engine.is_denied(PolicyDecision.DENY) is True
        assert engine.is_denied(PolicyDecision.ALLOW) is False

    def test_get_tier_config(self, engine):
        config = engine.get_tier_config("low")
        assert isinstance(config, RiskTierConfig)
        assert config.human_approval_required is False

    def test_budget_enforcement(self, engine):
        decision = engine.evaluate_action(
            action_type="execute",
            tool_name="default",
            risk_tier="low",
            current_cost=2.50,
            current_iterations=12,
        )
        assert decision in [PolicyDecision.DENY, PolicyDecision.REQUIRE_APPROVAL]
