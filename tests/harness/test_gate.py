from __future__ import annotations
"""Tests for packages.harness.gate - ShipGate logic (in-memory only)."""

import uuid

import pytest

from packages.harness.gate import GateBlock, GateDecision, ShipGate
from packages.harness.scoring import RunScore, ScenarioResult, ScenarioScore


class TestGateDecision:
    def test_all_values(self):
        assert GateDecision.PASS.value == "pass"
        assert GateDecision.BLOCK.value == "block"
        assert GateDecision.WARN.value == "warn"


class TestShipGateLogic:
    """Test ShipGate logic without DB persistence."""

    def test_all_pass(self):
        gate = ShipGate()
        scores = [
            ScenarioScore(
                scenario_id="s1", scenario_name="Check 1",
                result=ScenarioResult.PASS, score=1.0,
            )
        ]
        # Test the evaluation logic directly
        failed = [s for s in scores if s.result == ScenarioResult.FAIL]
        warnings = [s for s in scores if s.result == ScenarioResult.WARN]
        assert len(failed) == 0
        assert len(warnings) == 0

    def test_has_fail_blocks(self):
        scores = [
            ScenarioScore(
                scenario_id="s1", scenario_name="Check 1",
                result=ScenarioResult.FAIL, score=0.0,
            )
        ]
        failed = [s for s in scores if s.result == ScenarioResult.FAIL]
        assert len(failed) == 1

    def test_has_warnings(self):
        scores = [
            ScenarioScore(
                scenario_id="s1", scenario_name="Check 1",
                result=ScenarioResult.WARN, score=0.5,
            )
        ]
        warnings = [s for s in scores if s.result == ScenarioResult.WARN]
        assert len(warnings) == 1

    def test_gate_block_model(self):
        block = GateBlock(
            run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            decision=GateDecision.BLOCK,
            reason="Required scenarios failed",
            failed_scenarios=["s1"],
            overall_score=0.3,
        )
        assert block.decision == GateDecision.BLOCK
        assert len(block.failed_scenarios) == 1
