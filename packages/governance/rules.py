from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("rules")


class RuleType(str, Enum):
    FACTUAL_EVIDENCE = "factual_evidence"
    TRACE_EMISSION = "trace_emission"
    TERMINAL_STATE_REASON = "terminal_state_reason"
    BUDGET_ENFORCEMENT = "budget_enforcement"
    MEMORY_WRITE = "memory_write"


class RuleSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RuleResult(BaseModel):
    rule_id: str
    rule_type: RuleType
    passed: bool
    severity: RuleSeverity
    message: str
    details: dict = Field(default_factory=dict)


class Rule(BaseModel):
    rule_id: str
    rule_type: RuleType
    name: str
    description: str
    severity: RuleSeverity = RuleSeverity.WARNING
    enabled: bool = True
    check: Callable[..., Coroutine[Any, Any, RuleResult]] | None = None


class RulesEngine:
    def __init__(self):
        self._rules: dict[str, Rule] = {}
        self._register_default_rules()

    def _register_default_rules(self):
        self.register_rule(Rule(
            rule_id="factual_evidence_required",
            rule_type=RuleType.FACTUAL_EVIDENCE,
            name="Factual Claims Require Evidence",
            description="All factual claims must have source attribution",
            severity=RuleSeverity.WARNING,
        ))

        self.register_rule(Rule(
            rule_id="run_emits_traces",
            rule_type=RuleType.TRACE_EMISSION,
            name="Every Run Emits Traces",
            description="All runs must produce trace events for observability",
            severity=RuleSeverity.INFO,
        ))

        self.register_rule(Rule(
            rule_id="terminal_state_has_reason",
            rule_type=RuleType.TERMINAL_STATE_REASON,
            name="Terminal State Includes Reason",
            description="All terminal states must include a reason string",
            severity=RuleSeverity.WARNING,
        ))

    def register_rule(self, rule: Rule):
        self._rules[rule.rule_id] = rule
        logger.info(f"Rule registered: {rule.name}")

    def unregister_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def get_rule(self, rule_id: str) -> Rule | None:
        return self._rules.get(rule_id)

    def list_rules(self, rule_type: RuleType | None = None) -> list[Rule]:
        rules = list(self._rules.values())
        if rule_type:
            rules = [r for r in rules if r.rule_type == rule_type]
        return rules

    async def check_factual_evidence(
        self,
        content: str,
        has_source: bool,
        confidence: float,
    ) -> RuleResult:
        rule = self._rules.get("factual_evidence_required")
        if not rule or not rule.enabled:
            return RuleResult(
                rule_id="factual_evidence_required",
                rule_type=RuleType.FACTUAL_EVIDENCE,
                passed=True,
                severity=RuleSeverity.INFO,
                message="Rule disabled",
            )

        if confidence > 0.7 and not has_source:
            return RuleResult(
                rule_id="factual_evidence_required",
                rule_type=RuleType.FACTUAL_EVIDENCE,
                passed=False,
                severity=rule.severity,
                message=f"Factual claim with confidence {confidence} requires source attribution",
                details={"content": content[:100], "confidence": confidence},
            )

        return RuleResult(
            rule_id="factual_evidence_required",
            rule_type=RuleType.FACTUAL_EVIDENCE,
            passed=True,
            severity=RuleSeverity.INFO,
            message="Factual evidence check passed",
        )

    async def check_trace_emission(
        self,
        run_id: uuid.UUID,
        has_traces: bool,
    ) -> RuleResult:
        rule = self._rules.get("run_emits_traces")
        if not rule or not rule.enabled:
            return RuleResult(
                rule_id="run_emits_traces",
                rule_type=RuleType.TRACE_EMISSION,
                passed=True,
                severity=RuleSeverity.INFO,
                message="Rule disabled",
            )

        if not has_traces:
            return RuleResult(
                rule_id="run_emits_traces",
                rule_type=RuleType.TRACE_EMISSION,
                passed=False,
                severity=rule.severity,
                message=f"Run {run_id} has no trace events",
                details={"run_id": str(run_id)},
            )

        return RuleResult(
            rule_id="run_emits_traces",
            rule_type=RuleType.TRACE_EMISSION,
            passed=True,
            severity=RuleSeverity.INFO,
            message="Trace emission check passed",
        )

    async def check_terminal_state_reason(
        self,
        state: str,
        reason: str | None,
    ) -> RuleResult:
        terminal_states = {
            "SUCCESS", "PARTIAL_SUCCESS", "ESCALATED_TO_HUMAN",
            "STOP_BUDGET", "STOP_POLICY", "STOP_NO_PROGRESS",
            "FAIL_TOOLING", "FAIL_INVARIANT",
        }

        rule = self._rules.get("terminal_state_has_reason")
        if not rule or not rule.enabled:
            return RuleResult(
                rule_id="terminal_state_has_reason",
                rule_type=RuleType.TERMINAL_STATE_REASON,
                passed=True,
                severity=RuleSeverity.INFO,
                message="Rule disabled",
            )

        if state in terminal_states and not reason:
            return RuleResult(
                rule_id="terminal_state_has_reason",
                rule_type=RuleType.TERMINAL_STATE_REASON,
                passed=False,
                severity=rule.severity,
                message=f"Terminal state '{state}' must include a reason",
                details={"state": state},
            )

        return RuleResult(
            rule_id="terminal_state_has_reason",
            rule_type=RuleType.TERMINAL_STATE_REASON,
            passed=True,
            severity=RuleSeverity.INFO,
            message="Terminal state reason check passed",
        )

    async def evaluate_all(
        self,
        context: dict,
    ) -> list[RuleResult]:
        results = []

        if "content" in context and "has_source" in context:
            result = await self.check_factual_evidence(
                context["content"],
                context["has_source"],
                context.get("confidence", 0.5),
            )
            results.append(result)

        if "run_id" in context and "has_traces" in context:
            result = await self.check_trace_emission(
                context["run_id"],
                context["has_traces"],
            )
            results.append(result)

        if "state" in context:
            result = await self.check_terminal_state_reason(
                context["state"],
                context.get("reason"),
            )
            results.append(result)

        return results


rules_engine = RulesEngine()
