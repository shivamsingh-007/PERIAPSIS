from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_SECONDARY_REVIEW = "require_secondary_review"


class ToolPolicy(BaseModel):
    name: str
    allowed_tiers: list[RiskTier] = Field(default_factory=lambda: [RiskTier.LOW])
    requires_approval_tiers: list[RiskTier] = Field(default_factory=lambda: [RiskTier.MEDIUM, RiskTier.HIGH])


class RiskTierConfig(BaseModel):
    human_approval_required: bool = False
    secondary_review_required: bool = False
    allowed_connectors: list[str] = Field(default_factory=list)
    max_cost_usd: float = 10.0
    max_iterations: int = 20


class PolicyEngine:
    def __init__(self):
        self._tier_configs: dict[str, RiskTierConfig] = {
            "low": RiskTierConfig(
                human_approval_required=False,
                allowed_connectors=["search", "docs", "internal-read"],
            ),
            "medium": RiskTierConfig(
                human_approval_required=True,
                allowed_connectors=["search", "docs", "internal-read", "ticketing"],
                max_cost_usd=5.0,
                max_iterations=15,
            ),
            "high": RiskTierConfig(
                human_approval_required=True,
                secondary_review_required=True,
                allowed_connectors=["internal-read"],
                max_cost_usd=2.50,
                max_iterations=10,
            ),
        }
        self._tool_policies: dict[str, ToolPolicy] = {}

    def register_tool(self, policy: ToolPolicy) -> None:
        self._tool_policies[policy.name] = policy

    def get_tier_config(self, tier: str) -> RiskTierConfig:
        return self._tier_configs.get(tier, self._tier_configs["low"])

    def evaluate_action(
        self,
        action_type: str,
        tool_name: str | None,
        risk_tier: str,
        current_cost: float = 0.0,
        current_iterations: int = 0,
    ) -> PolicyDecision:
        tier_config = self.get_tier_config(risk_tier)

        if current_cost >= tier_config.max_cost_usd:
            return PolicyDecision.DENY

        if current_iterations >= tier_config.max_iterations:
            return PolicyDecision.DENY

        if tool_name and tool_name not in tier_config.allowed_connectors:
            return PolicyDecision.DENY

        if tool_name and tool_name in self._tool_policies:
            tool_policy = self._tool_policies[tool_name]
            tier_enum = RiskTier(risk_tier)
            if tier_enum not in tool_policy.allowed_tiers:
                return PolicyDecision.DENY
            if tier_enum in tool_policy.requires_approval_tiers:
                return PolicyDecision.REQUIRE_APPROVAL

        if tier_config.secondary_review_required:
            return PolicyDecision.REQUIRE_SECONDARY_REVIEW

        if tier_config.human_approval_required:
            return PolicyDecision.REQUIRE_APPROVAL

        return PolicyDecision.ALLOW

    def should_escalate(self, decision: PolicyDecision) -> bool:
        return decision in (
            PolicyDecision.REQUIRE_APPROVAL,
            PolicyDecision.REQUIRE_SECONDARY_REVIEW,
        )

    def is_denied(self, decision: PolicyDecision) -> bool:
        return decision == PolicyDecision.DENY


policy_engine = PolicyEngine()
