from __future__ import annotations
"""Tests for packages.governance.policy - PolicyEngine, RiskTierConfig, PolicyDecision."""

import pytest

from packages.governance.policy import (
    PolicyDecision,
    PolicyEngine,
    RiskTier,
    RiskTierConfig,
    ToolPolicy,
)


class TestPolicyDecision:
    def test_all_variants(self):
        assert len(list(PolicyDecision)) == 4

    def test_allow_value(self):
        assert PolicyDecision.ALLOW.value == "allow"

    def test_deny_value(self):
        assert PolicyDecision.DENY.value == "deny"


class TestRiskTierConfig:
    def test_defaults(self):
        config = RiskTierConfig()
        assert config.human_approval_required is False
        assert config.secondary_review_required is False
        assert config.max_cost_usd == 10.0

    def test_custom(self):
        config = RiskTierConfig(human_approval_required=True, max_cost_usd=5.0)
        assert config.human_approval_required is True


class TestPolicyEngine:
    def setup_method(self):
        self.engine = PolicyEngine()

    def test_low_tier_allows_search(self):
        decision = self.engine.evaluate_action(
            action_type="research",
            tool_name="search",
            risk_tier="low",
        )
        assert decision == PolicyDecision.ALLOW

    def test_medium_tier_requires_approval(self):
        decision = self.engine.evaluate_action(
            action_type="research",
            tool_name="search",
            risk_tier="medium",
        )
        assert decision == PolicyDecision.REQUIRE_APPROVAL

    def test_high_tier_requires_secondary_review(self):
        decision = self.engine.evaluate_action(
            action_type="research",
            tool_name="internal-read",
            risk_tier="high",
        )
        assert decision == PolicyDecision.REQUIRE_SECONDARY_REVIEW

    def test_unknown_tool_denied(self):
        decision = self.engine.evaluate_action(
            action_type="research",
            tool_name="unknown-tool",
            risk_tier="low",
        )
        assert decision == PolicyDecision.DENY

    def test_cost_exceeded_denied(self):
        decision = self.engine.evaluate_action(
            action_type="research",
            tool_name="search",
            risk_tier="low",
            current_cost=10.0,
        )
        assert decision == PolicyDecision.DENY

    def test_iterations_exceeded_denied(self):
        decision = self.engine.evaluate_action(
            action_type="research",
            tool_name="search",
            risk_tier="low",
            current_iterations=20,
        )
        assert decision == PolicyDecision.DENY

    def test_get_tier_config_low(self):
        config = self.engine.get_tier_config("low")
        assert config.human_approval_required is False

    def test_get_tier_config_medium(self):
        config = self.engine.get_tier_config("medium")
        assert config.human_approval_required is True

    def test_get_tier_config_high(self):
        config = self.engine.get_tier_config("high")
        assert config.secondary_review_required is True

    def test_get_tier_config_unknown_defaults_to_low(self):
        config = self.engine.get_tier_config("unknown")
        assert config.human_approval_required is False

    def test_register_tool(self):
        policy = ToolPolicy(
            name="dangerous-tool",
            allowed_tiers=[RiskTier.LOW],
            requires_approval_tiers=[RiskTier.MEDIUM, RiskTier.HIGH],
        )
        self.engine.register_tool(policy)
        assert "dangerous-tool" in self.engine._tool_policies

    def test_tool_policy_blocks_high_tier(self):
        # "search" is in low tier's allowed_connectors, but NOT in high tier's
        # So even with a registered tool policy, the tier check blocks it first
        decision = self.engine.evaluate_action(
            action_type="execute",
            tool_name="search",
            risk_tier="high",
        )
        assert decision == PolicyDecision.DENY

    def test_tool_policy_allows_low_tier_with_allowed_connector(self):
        # "search" is in low tier's allowed_connectors; registering a tool policy
        # should still ALLOW for low tier
        policy = ToolPolicy(
            name="search",
            allowed_tiers=[RiskTier.LOW],
            requires_approval_tiers=[RiskTier.MEDIUM],
        )
        self.engine.register_tool(policy)
        decision = self.engine.evaluate_action(
            action_type="execute",
            tool_name="search",
            risk_tier="low",
        )
        assert decision == PolicyDecision.ALLOW

    def test_tool_policy_approval_for_medium_with_allowed_connector(self):
        # "search" is in medium tier's allowed_connectors
        policy = ToolPolicy(
            name="search",
            allowed_tiers=[RiskTier.LOW, RiskTier.MEDIUM],
            requires_approval_tiers=[RiskTier.MEDIUM],
        )
        self.engine.register_tool(policy)
        decision = self.engine.evaluate_action(
            action_type="execute",
            tool_name="search",
            risk_tier="medium",
        )
        assert decision == PolicyDecision.REQUIRE_APPROVAL

    def test_should_escalate_approval(self):
        assert self.engine.should_escalate(PolicyDecision.REQUIRE_APPROVAL) is True

    def test_should_escalate_secondary_review(self):
        assert self.engine.should_escalate(PolicyDecision.REQUIRE_SECONDARY_REVIEW) is True

    def test_should_escalate_allow(self):
        assert self.engine.should_escalate(PolicyDecision.ALLOW) is False

    def test_should_escalate_deny(self):
        assert self.engine.should_escalate(PolicyDecision.DENY) is False

    def test_is_denied_true(self):
        assert self.engine.is_denied(PolicyDecision.DENY) is True

    def test_is_denied_false(self):
        assert self.engine.is_denied(PolicyDecision.ALLOW) is False

    def test_no_tool_name_allows(self):
        decision = self.engine.evaluate_action(
            action_type="research",
            tool_name=None,
            risk_tier="low",
        )
        assert decision == PolicyDecision.ALLOW
