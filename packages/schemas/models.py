from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.schemas.database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class Run(Base):
    __tablename__ = "runs"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    terminal_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    budget_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    governance_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    steps: Mapped[list[RunStep]] = relationship(back_populates="run", cascade="all, delete-orphan")
    reflections: Mapped[list[Reflection]] = relationship(back_populates="run", cascade="all, delete-orphan")
    governance_events: Mapped[list[GovernanceEvent]] = relationship(back_populates="run", cascade="all, delete-orphan")
    harness_scores: Mapped[list[HarnessScore]] = relationship(back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("tenant_id", "run_id", name="uq_runs_tenant_run"),)


class RunStep(Base):
    __tablename__ = "run_steps"

    step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_state_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_state_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    action_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    validation_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost_tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checkpoint_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    run: Mapped[Run] = relationship(back_populates="steps")

    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "step_number", name="uq_run_steps_tenant_run_step"),
        UniqueConstraint("tenant_id", "run_id", "node_name", "step_number", name="uq_run_steps_tenant_run_node_step"),
    )


class MemoryItem(Base):
    __tablename__ = "memory_items"

    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)  # VECTOR(1536) via pgvector
    source_ref: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.5)
    ttl_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "content_hash", name="uq_memory_items_tenant_hash"),)


class Skill(Base):
    __tablename__ = "skills"

    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(50), nullable=False)
    owner: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "name", "version", name="uq_skills_tenant_name_version"),)


class Reflection(Base):
    __tablename__ = "reflections"

    reflection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=False, index=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("run_steps.step_id"), nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    critic_type: Mapped[str] = mapped_column(String(50), nullable=False)
    finding: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    promoted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    run: Mapped[Run] = relationship(back_populates="reflections")


class HarnessScore(Base):
    __tablename__ = "harness_scores"

    score_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    threshold: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    pass_fail: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    run: Mapped[Run] = relationship(back_populates="harness_scores")


class GovernanceEvent(Base):
    __tablename__ = "governance_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    control_domain: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_rule: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewer: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    run: Mapped[Run] = relationship(back_populates="governance_events")


class FleetJob(Base):
    __tablename__ = "fleet_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    worker_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    workspace_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    budget_slice: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
