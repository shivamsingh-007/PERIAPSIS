from __future__ import annotations

import uuid

import pytest

from packages.governance.rules import (
    RuleResult,
    RuleSeverity,
    RuleType,
    RulesEngine,
    Rule,
    rules_engine,
)


class TestRulesEngine:
    def test_init(self):
        engine = RulesEngine()
        assert engine is not None

    def test_default_rules_registered(self):
        engine = RulesEngine()
        rules = engine.list_rules()
        assert len(rules) >= 3

    async def test_check_factual_evidence_pass(self):
        engine = RulesEngine()
        result = await engine.check_factual_evidence(
            content="The sky is blue",
            has_source=True,
            confidence=0.9,
        )
        assert isinstance(result, RuleResult)
        assert result.passed is True

    async def test_check_factual_evidence_fail_no_source(self):
        engine = RulesEngine()
        result = await engine.check_factual_evidence(
            content="The sky is blue",
            has_source=False,
            confidence=0.9,
        )
        assert result.passed is False

    async def test_check_trace_emission(self):
        engine = RulesEngine()
        result = await engine.check_trace_emission(
            run_id=uuid.uuid4(),
            has_traces=True,
        )
        assert result.passed is True

    async def test_check_terminal_state_reason(self):
        engine = RulesEngine()
        result = await engine.check_terminal_state_reason(
            state="SUCCESS",
            reason="All steps completed",
        )
        assert result.passed is True

    def test_register_custom_rule(self):
        engine = RulesEngine()
        custom = Rule(
            rule_id="custom-1",
            rule_type=RuleType.BUDGET_ENFORCEMENT,
            name="custom rule",
            description="test",
            severity=RuleSeverity.WARNING,
            enabled=True,
        )
        engine.register_rule(custom)
        assert engine.get_rule("custom-1") is not None

    def test_unregister_rule(self):
        engine = RulesEngine()
        custom = Rule(
            rule_id="to-remove",
            rule_type=RuleType.BUDGET_ENFORCEMENT,
            name="remove me",
            description="test",
            severity=RuleSeverity.INFO,
            enabled=True,
        )
        engine.register_rule(custom)
        engine.unregister_rule("to-remove")
        assert engine.get_rule("to-remove") is None

    async def test_evaluate_all(self):
        engine = RulesEngine()
        results = await engine.evaluate_all({
            "content": "test",
            "has_source": True,
            "confidence": 0.8,
            "run_id": uuid.uuid4(),
            "has_traces": True,
            "state": "SUCCESS",
            "reason": "done",
        })
        assert isinstance(results, list)
        assert len(results) >= 3

    def test_list_rules_by_type(self):
        engine = RulesEngine()
        rules = engine.list_rules(rule_type=RuleType.FACTUAL_EVIDENCE)
        assert isinstance(rules, list)
