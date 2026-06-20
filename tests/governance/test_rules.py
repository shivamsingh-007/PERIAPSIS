from __future__ import annotations
"""Tests for packages.governance.rules - RulesEngine, Rule checks."""

import uuid

import pytest

from packages.governance.rules import (
    RuleResult,
    RuleSeverity,
    RuleType,
    RulesEngine,
    rules_engine,
)


class TestRulesEngineInit:
    def test_default_rules_registered(self):
        engine = RulesEngine()
        assert len(engine._rules) == 3

    def test_has_factual_evidence_rule(self):
        engine = RulesEngine()
        assert "factual_evidence_required" in engine._rules

    def test_has_trace_emission_rule(self):
        engine = RulesEngine()
        assert "run_emits_traces" in engine._rules

    def test_has_terminal_state_rule(self):
        engine = RulesEngine()
        assert "terminal_state_has_reason" in engine._rules


class TestRulesEngineRegistration:
    def test_get_rule(self):
        rule = rules_engine.get_rule("factual_evidence_required")
        assert rule is not None
        assert rule.rule_type == RuleType.FACTUAL_EVIDENCE

    def test_get_nonexistent_rule(self):
        rule = rules_engine.get_rule("nonexistent")
        assert rule is None

    def test_list_rules_no_filter(self):
        rules = rules_engine.list_rules()
        assert len(rules) == 3

    def test_list_rules_by_type(self):
        rules = rules_engine.list_rules(rule_type=RuleType.FACTUAL_EVIDENCE)
        assert len(rules) == 1
        assert rules[0].rule_id == "factual_evidence_required"

    def test_unregister_rule(self):
        engine = RulesEngine()
        result = engine.unregister_rule("factual_evidence_required")
        assert result is True
        assert "factual_evidence_required" not in engine._rules

    def test_unregister_nonexistent(self):
        engine = RulesEngine()
        result = engine.unregister_rule("nonexistent")
        assert result is False


class TestCheckFactualEvidence:
    @pytest.mark.asyncio
    async def test_high_confidence_no_source_fails(self):
        result = await rules_engine.check_factual_evidence(
            content="The sky is blue", has_source=False, confidence=0.8
        )
        assert result.passed is False
        assert result.rule_type == RuleType.FACTUAL_EVIDENCE

    @pytest.mark.asyncio
    async def test_high_confidence_with_source_passes(self):
        result = await rules_engine.check_factual_evidence(
            content="The sky is blue", has_source=True, confidence=0.8
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_low_confidence_passes(self):
        result = await rules_engine.check_factual_evidence(
            content="Maybe it's blue", has_source=False, confidence=0.5
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_boundary_confidence(self):
        result = await rules_engine.check_factual_evidence(
            content="test", has_source=False, confidence=0.71
        )
        assert result.passed is False


class TestCheckTraceEmission:
    @pytest.mark.asyncio
    async def test_has_traces_passes(self):
        result = await rules_engine.check_trace_emission(
            run_id=uuid.uuid4(), has_traces=True
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_no_traces_fails(self):
        result = await rules_engine.check_trace_emission(
            run_id=uuid.uuid4(), has_traces=False
        )
        assert result.passed is False
        assert result.severity == RuleSeverity.INFO


class TestCheckTerminalStateReason:
    @pytest.mark.asyncio
    async def test_terminal_state_no_reason_fails(self):
        result = await rules_engine.check_terminal_state_reason(
            state="SUCCESS", reason=None
        )
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_terminal_state_with_reason_passes(self):
        result = await rules_engine.check_terminal_state_reason(
            state="SUCCESS", reason="Task completed"
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_non_terminal_state_passes(self):
        result = await rules_engine.check_terminal_state_reason(
            state="running", reason=None
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_all_terminal_states_checked(self):
        terminal_states = {
            "SUCCESS", "PARTIAL_SUCCESS", "ESCALATED_TO_HUMAN",
            "STOP_BUDGET", "STOP_POLICY", "STOP_NO_PROGRESS",
            "FAIL_TOOLING", "FAIL_INVARIANT",
        }
        for state in terminal_states:
            result = await rules_engine.check_terminal_state_reason(state, None)
            assert result.passed is False, f"State {state} should fail without reason"


class TestEvaluateAll:
    @pytest.mark.asyncio
    async def test_evaluate_factual_only(self):
        results = await rules_engine.evaluate_all({
            "content": "fact",
            "has_source": False,
            "confidence": 0.8,
        })
        assert len(results) == 1
        assert results[0].rule_type == RuleType.FACTUAL_EVIDENCE

    @pytest.mark.asyncio
    async def test_evaluate_trace_only(self):
        results = await rules_engine.evaluate_all({
            "run_id": uuid.uuid4(),
            "has_traces": True,
        })
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_evaluate_all_three(self):
        results = await rules_engine.evaluate_all({
            "content": "fact",
            "has_source": True,
            "confidence": 0.8,
            "run_id": uuid.uuid4(),
            "has_traces": True,
            "state": "SUCCESS",
            "reason": "done",
        })
        assert len(results) == 3
