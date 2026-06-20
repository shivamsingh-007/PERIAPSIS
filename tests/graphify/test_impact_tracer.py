from __future__ import annotations

import pytest

from packages.graphify.impact_tracer import (
    ImpactResult,
    ImpactTracer,
)


class TestImpactResult:
    def test_create_result(self):
        result = ImpactResult(
            node_id="n1",
            impacted_nodes=["n2", "n3"],
            risk_level="medium",
        )
        assert result.node_id == "n1"
        assert len(result.impacted_nodes) == 2
        assert result.risk_level == "medium"

    def test_result_defaults(self):
        result = ImpactResult(node_id="n1")
        assert result.impacted_nodes == []
        assert result.impacted_files == []
        assert result.upstream_count == 0
        assert result.downstream_count == 0


class TestImpactTracer:
    def test_init(self):
        tracer = ImpactTracer()
        assert tracer is not None

    def test_trace_change_impact(self):
        tracer = ImpactTracer()
        result = tracer.trace_change_impact("nonexistent_node")
        assert isinstance(result, ImpactResult)
        assert result.node_id == "nonexistent_node"

    def test_risk_assessment_low(self):
        tracer = ImpactTracer()
        risk = tracer._assess_risk(1, 0, 0)
        assert risk == "low"

    def test_risk_assessment_medium(self):
        tracer = ImpactTracer()
        risk = tracer._assess_risk(6, 0, 0)
        assert risk == "medium"

    def test_risk_assessment_high(self):
        tracer = ImpactTracer()
        risk = tracer._assess_risk(25, 0, 0)
        assert risk == "high"

    def test_get_architectural_critique(self):
        tracer = ImpactTracer()
        result = tracer.get_architectural_critique("nonexistent")
        assert "node_id" in result
        assert "neighbor_count" in result
        assert "blast_radius" in result
        assert "concerns" in result
        assert "risk_level" in result

    def test_critique_low_risk(self):
        tracer = ImpactTracer()
        result = tracer.get_architectural_critique("isolated_node")
        assert result["risk_level"] in ["low", "medium", "high"]

    def test_thresholds(self):
        assert ImpactTracer.HIGH_RISK_THRESHOLD == 20
        assert ImpactTracer.MEDIUM_RISK_THRESHOLD == 5

    def test_trace_upstream(self):
        tracer = ImpactTracer()
        result = tracer._trace_upstream("nonexistent")
        assert isinstance(result, list)

    def test_trace_downstream(self):
        tracer = ImpactTracer()
        result = tracer._trace_downstream("nonexistent")
        assert isinstance(result, list)
