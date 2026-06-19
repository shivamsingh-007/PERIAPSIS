from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("compliance")


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RegulatoryScope(str, Enum):
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI = "pci"
    SOC2 = "soc2"
    INTERNAL = "internal"


class DataDomain(str, Enum):
    PII = "pii"
    FINANCIAL = "financial"
    HEALTH = "health"
    INTERNAL = "internal"
    PUBLIC = "public"


class AssetType(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    MODEL = "model"
    SWARM = "swarm"
    DATASET = "dataset"


class AssetEntry(BaseModel):
    asset_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    asset_type: AssetType
    owner: str
    team: str
    risk_tier: RiskTier
    data_domains: list[DataDomain] = Field(default_factory=list)
    regulatory_scopes: list[RegulatoryScope] = Field(default_factory=list)
    approved_environments: list[str] = Field(default_factory=lambda: ["dev"])
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_audit: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyGate(BaseModel):
    gate_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    phase: str
    risk_tiers: list[RiskTier] = Field(default_factory=list)
    requires_human_approval: bool = False
    requires_tests: bool = False
    requires_governance_review: bool = False
    required_regulatory: list[RegulatoryScope] = Field(default_factory=list)
    description: str = ""


class AuditEvent(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_id: str
    swarm_id: str | None = None
    action: str
    target: str
    tools_used: list[str] = Field(default_factory=list)
    data_domains_accessed: list[DataDomain] = Field(default_factory=list)
    input_hash: str | None = None
    output_hash: str | None = None
    risk_tier: RiskTier = RiskTier.LOW
    result: str = "success"
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageRecord(BaseModel):
    lineage_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_id: str
    agent_id: str
    datasets_read: list[str] = Field(default_factory=list)
    datasets_written: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    models_invoked: list[str] = Field(default_factory=list)
    parent_lineage_id: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


DEFAULT_POLICY_GATES: list[PolicyGate] = [
    PolicyGate(
        name="pre_deploy_swarm",
        phase="pre_deploy",
        risk_tiers=[RiskTier.MEDIUM, RiskTier.HIGH, RiskTier.CRITICAL],
        requires_human_approval=True,
        requires_governance_review=True,
        description="New agent swarm requires security and governance review",
    ),
    PolicyGate(
        name="pre_run_high_risk",
        phase="pre_run",
        risk_tiers=[RiskTier.HIGH, RiskTier.CRITICAL],
        requires_human_approval=True,
        description="High-risk runs require human approval",
    ),
    PolicyGate(
        name="pre_ship_contracts",
        phase="pre_ship",
        risk_tiers=[RiskTier.HIGH, RiskTier.CRITICAL],
        requires_tests=True,
        requires_governance_review=True,
        requires_human_approval=True,
        description="High-risk outputs require tests, governance review, and human sign-off",
    ),
    PolicyGate(
        name="pre_ship_default",
        phase="pre_ship",
        risk_tiers=[RiskTier.LOW, RiskTier.MEDIUM],
        requires_tests=True,
        description="Standard outputs require tests",
    ),
]


class ComplianceRegistry:
    def __init__(self):
        self._assets: dict[uuid.UUID, AssetEntry] = {}
        self._audit_log: list[AuditEvent] = []
        self._lineage: list[LineageRecord] = []
        self._gates: list[PolicyGate] = list(DEFAULT_POLICY_GATES)

    def register_asset(
        self,
        name: str,
        asset_type: AssetType,
        owner: str,
        team: str,
        risk_tier: RiskTier,
        data_domains: list[DataDomain] | None = None,
        regulatory_scopes: list[RegulatoryScope] | None = None,
        approved_environments: list[str] | None = None,
        description: str = "",
    ) -> AssetEntry:
        entry = AssetEntry(
            name=name,
            asset_type=asset_type,
            owner=owner,
            team=team,
            risk_tier=risk_tier,
            data_domains=data_domains or [],
            regulatory_scopes=regulatory_scopes or [],
            approved_environments=approved_environments or ["dev"],
            description=description,
        )
        self._assets[entry.asset_id] = entry
        logger.info(f"Registered asset: {name} ({asset_type.value})")
        return entry

    def get_asset(self, asset_id: uuid.UUID) -> AssetEntry | None:
        return self._assets.get(asset_id)

    def list_assets(self, asset_type: AssetType | None = None) -> list[AssetEntry]:
        if asset_type:
            return [a for a in self._assets.values() if a.asset_type == asset_type]
        return list(self._assets.values())

    def evaluate_gate(
        self,
        phase: str,
        risk_tier: RiskTier,
    ) -> tuple[bool, list[str]]:
        blocking_gates = [
            g for g in self._gates
            if g.phase == phase and risk_tier in g.risk_tiers
        ]

        if not blocking_gates:
            return True, []

        requirements = []
        for gate in blocking_gates:
            if gate.requires_human_approval:
                requirements.append(f"{gate.name}: requires human approval")
            if gate.requires_tests:
                requirements.append(f"{gate.name}: requires passing tests")
            if gate.requires_governance_review:
                requirements.append(f"{gate.name}: requires governance review")

        return False, requirements

    def log_audit_event(
        self,
        agent_id: str,
        action: str,
        target: str,
        swarm_id: str | None = None,
        tools_used: list[str] | None = None,
        data_domains_accessed: list[DataDomain] | None = None,
        input_content: str | None = None,
        output_content: str | None = None,
        risk_tier: RiskTier = RiskTier.LOW,
        result: str = "success",
    ) -> AuditEvent:
        input_hash = None
        output_hash = None

        if input_content:
            input_hash = hashlib.sha256(input_content.encode()).hexdigest()
        if output_content:
            output_hash = hashlib.sha256(output_content.encode()).hexdigest()

        event = AuditEvent(
            agent_id=agent_id,
            swarm_id=swarm_id,
            action=action,
            target=target,
            tools_used=tools_used or [],
            data_domains_accessed=data_domains_accessed or [],
            input_hash=input_hash,
            output_hash=output_hash,
            risk_tier=risk_tier,
            result=result,
        )

        self._audit_log.append(event)
        return event

    def get_audit_log(
        self,
        agent_id: str | None = None,
        swarm_id: str | None = None,
        risk_tier: RiskTier | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        events = self._audit_log

        if agent_id:
            events = [e for e in events if e.agent_id == agent_id]
        if swarm_id:
            events = [e for e in events if e.swarm_id == swarm_id]
        if risk_tier:
            events = [e for e in events if e.risk_tier == risk_tier]

        return events[-limit:]

    def create_lineage(
        self,
        task_id: str,
        agent_id: str,
        datasets_read: list[str] | None = None,
        datasets_written: list[str] | None = None,
        tools_called: list[str] | None = None,
        models_invoked: list[str] | None = None,
        parent_lineage_id: uuid.UUID | None = None,
    ) -> LineageRecord:
        record = LineageRecord(
            task_id=task_id,
            agent_id=agent_id,
            datasets_read=datasets_read or [],
            datasets_written=datasets_written or [],
            tools_called=tools_called or [],
            models_invoked=models_invoked or [],
            parent_lineage_id=parent_lineage_id,
        )
        self._lineage.append(record)
        return record

    def get_lineage(
        self,
        task_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[LineageRecord]:
        records = self._lineage
        if task_id:
            records = [r for r in records if r.task_id == task_id]
        if agent_id:
            records = [r for r in records if r.agent_id == agent_id]
        return records

    def generate_compliance_report(self) -> dict:
        total_assets = len(self._assets)
        total_events = len(self._audit_log)
        high_risk_events = sum(
            1 for e in self._audit_log
            if e.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL)
        )
        failed_events = sum(1 for e in self._audit_log if e.result != "success")

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_assets": total_assets,
                "total_audit_events": total_events,
                "high_risk_events": high_risk_events,
                "failed_events": failed_events,
                "compliance_score": round(
                    (1 - failed_events / max(total_events, 1)) * 100, 1
                ),
            },
            "assets_by_type": {
                t.value: len([a for a in self._assets.values() if a.asset_type == t])
                for t in AssetType
            },
            "events_by_risk": {
                r.value: len([e for e in self._audit_log if e.risk_tier == r])
                for r in RiskTier
            },
            "active_gates": len(self._gates),
        }


compliance_registry = ComplianceRegistry()
