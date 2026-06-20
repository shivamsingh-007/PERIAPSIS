from __future__ import annotations

import uuid

import pytest

from packages.fleet.compliance import (
    AssetEntry,
    AssetType,
    AuditEvent,
    ComplianceRegistry,
    DataDomain,
    LineageRecord,
    PolicyGate,
    RegulatoryScope,
    RiskTier,
    DEFAULT_POLICY_GATES,
)


@pytest.fixture
def registry():
    return ComplianceRegistry()


class TestRiskTier:
    def test_all_variants(self):
        assert len(list(RiskTier)) == 4

    def test_values(self):
        assert RiskTier.LOW.value == "low"
        assert RiskTier.CRITICAL.value == "critical"


class TestRegulatoryScope:
    def test_all_variants(self):
        assert len(list(RegulatoryScope)) >= 5


class TestDataDomain:
    def test_all_variants(self):
        assert len(list(DataDomain)) >= 5


class TestAssetType:
    def test_all_variants(self):
        assert len(list(AssetType)) >= 5


class TestAssetEntry:
    def test_create_asset(self):
        asset = AssetEntry(
            asset_id=uuid.uuid4(),
            name="test-agent",
            asset_type=AssetType.AGENT,
            owner="team-a",
            team="team-a",
            risk_tier=RiskTier.LOW,
        )
        assert asset.name == "test-agent"
        assert asset.asset_type == AssetType.AGENT


class TestPolicyGate:
    def test_default_gates(self):
        assert len(DEFAULT_POLICY_GATES) == 4
        names = [g.name for g in DEFAULT_POLICY_GATES]
        assert "pre_deploy_swarm" in names
        assert "pre_run_high_risk" in names

    def test_gate_phases(self):
        phases = set(g.phase for g in DEFAULT_POLICY_GATES)
        assert "pre_deploy" in phases
        assert "pre_run" in phases
        assert "pre_ship" in phases


class TestComplianceRegistry:
    def test_register_asset(self, registry):
        asset = registry.register_asset(
            name="test-agent",
            asset_type=AssetType.AGENT,
            owner="team-a",
            team="team-a",
            risk_tier=RiskTier.LOW,
        )
        assert asset.name == "test-agent"
        assert asset.asset_id is not None

    def test_get_asset(self, registry):
        asset = registry.register_asset(
            name="test-agent",
            asset_type=AssetType.AGENT,
            owner="team-a",
            team="team-a",
            risk_tier=RiskTier.LOW,
        )
        retrieved = registry.get_asset(asset.asset_id)
        assert retrieved is not None
        assert retrieved.name == "test-agent"

    def test_get_asset_not_found(self, registry):
        result = registry.get_asset(uuid.uuid4())
        assert result is None

    def test_list_assets(self, registry):
        registry.register_asset(name="agent-1", asset_type=AssetType.AGENT, owner="a", team="a", risk_tier=RiskTier.LOW)
        registry.register_asset(name="tool-1", asset_type=AssetType.TOOL, owner="b", team="b", risk_tier=RiskTier.MEDIUM)
        agents = registry.list_assets(AssetType.AGENT)
        assert len(agents) == 1

    def test_evaluate_gate_pass(self, registry):
        passed, issues = registry.evaluate_gate("pre_run", RiskTier.LOW)
        assert isinstance(passed, bool)
        assert isinstance(issues, list)

    def test_evaluate_gate_high_risk(self, registry):
        passed, issues = registry.evaluate_gate("pre_run", RiskTier.HIGH)
        assert isinstance(passed, bool)

    def test_log_audit_event(self, registry):
        event = registry.log_audit_event(
            agent_id="agent-1",
            action="execute",
            target="file.py",
            risk_tier=RiskTier.LOW,
            result="success",
        )
        assert event.event_id is not None
        assert event.action == "execute"

    def test_get_audit_log(self, registry):
        registry.log_audit_event(
            agent_id="agent-1",
            action="read",
            target="file.py",
            risk_tier=RiskTier.LOW,
            result="success",
        )
        log = registry.get_audit_log()
        assert len(log) >= 1

    def test_create_lineage(self, registry):
        lineage = registry.create_lineage(
            task_id="task-1",
            agent_id="agent-1",
            datasets_read=["data-1"],
            datasets_written=["out-1"],
        )
        assert lineage.lineage_id is not None
        assert lineage.task_id == "task-1"

    def test_get_lineage(self, registry):
        registry.create_lineage(
            task_id="task-1",
            agent_id="agent-1",
            datasets_read=["data-1"],
            datasets_written=[],
        )
        records = registry.get_lineage(task_id="task-1")
        assert len(records) >= 1

    def test_generate_compliance_report(self, registry):
        registry.register_asset(name="a", asset_type=AssetType.AGENT, owner="o", team="o", risk_tier=RiskTier.LOW)
        registry.log_audit_event(agent_id="a", action="test", target="t", risk_tier=RiskTier.LOW, result="ok")
        report = registry.generate_compliance_report()
        assert "summary" in report
        assert "total_assets" in report["summary"]
        assert "total_audit_events" in report["summary"]
        assert report["summary"]["total_assets"] >= 1

    def test_default_policy_gates_loaded(self, registry):
        assert len(DEFAULT_POLICY_GATES) == 4

    def test_multiple_audits(self, registry):
        for i in range(5):
            registry.log_audit_event(
                agent_id=f"agent-{i}",
                action="test",
                target=f"target-{i}",
                risk_tier=RiskTier.LOW,
                result="ok",
            )
        log = registry.get_audit_log()
        assert len(log) >= 5

    def test_lineage_chain(self, registry):
        l1 = registry.create_lineage(task_id="t1", agent_id="a1", datasets_read=[], datasets_written=["d1"])
        l2 = registry.create_lineage(task_id="t2", agent_id="a2", datasets_read=["d1"], datasets_written=["d2"], parent_lineage_id=l1.lineage_id)
        assert l2.parent_lineage_id == l1.lineage_id
