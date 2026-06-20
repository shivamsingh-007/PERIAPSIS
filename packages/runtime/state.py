from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TerminalState(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    ESCALATED_TO_HUMAN = "ESCALATED_TO_HUMAN"
    STOP_BUDGET = "STOP_BUDGET"
    STOP_POLICY = "STOP_POLICY"
    STOP_NO_PROGRESS = "STOP_NO_PROGRESS"
    FAIL_TOOLING = "FAIL_TOOLING"
    FAIL_INVARIANT = "FAIL_INVARIANT"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BudgetPolicy(BaseModel):
    max_iterations: int = 12
    max_tool_calls: int = 24
    max_cost_usd: float = 2.50
    max_runtime_seconds: int = 180
    max_parallel_workers: int = 4
    max_external_writes: int = 2
    stop_on_no_progress_rounds: int = 2


class Action(BaseModel):
    action_type: str
    tool_name: str | None = None
    input_data: dict = Field(default_factory=dict)
    risk_tier: RiskTier = RiskTier.LOW


class StepResult(BaseModel):
    step_number: int
    node_name: str
    action: Action | None = None
    output: dict = Field(default_factory=dict)
    validation_result: dict | None = None
    cost_tokens_in: int = 0
    cost_tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str | None = None


class RunState(BaseModel):
    """Typed state object for the main loop graph."""

    run_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    goal: str = ""
    status: RunStatus = RunStatus.PENDING
    terminal_state: TerminalState | None = None
    risk_tier: RiskTier = RiskTier.LOW

    budget: BudgetPolicy = Field(default_factory=BudgetPolicy)
    iterations: int = 0
    tool_calls: int = 0
    total_cost_usd: float = 0.0
    tokens_prompt: int = 0
    tokens_completion: int = 0
    last_output: str = ""
    runtime_seconds: float = 0.0
    no_progress_rounds: int = 0

    plan: list[Action] = Field(default_factory=list)
    current_step: int = 0
    steps: list[StepResult] = Field(default_factory=list)
    memory_context: list[dict] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def is_terminal(self) -> bool:
        return self.terminal_state is not None

    def can_continue(self) -> bool:
        if self.is_terminal():
            return False
        if self.iterations >= self.budget.max_iterations:
            return False
        if self.total_cost_usd >= self.budget.max_cost_usd:
            return False
        if self.runtime_seconds >= self.budget.max_runtime_seconds:
            return False
        if self.tool_calls >= self.budget.max_tool_calls:
            return False
        return True

    def check_budget(self) -> TerminalState | None:
        if self.iterations >= self.budget.max_iterations:
            return TerminalState.STOP_BUDGET
        if self.total_cost_usd >= self.budget.max_cost_usd:
            return TerminalState.STOP_BUDGET
        if self.runtime_seconds >= self.budget.max_runtime_seconds:
            return TerminalState.STOP_BUDGET
        if self.tool_calls >= self.budget.max_tool_calls:
            return TerminalState.STOP_BUDGET
        if self.no_progress_rounds >= self.budget.stop_on_no_progress_rounds:
            return TerminalState.STOP_NO_PROGRESS
        return None
