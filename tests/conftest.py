from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.runtime.state import (
    Action,
    BudgetPolicy,
    RiskTier,
    RunState,
    RunStatus,
    StepResult,
    TerminalState,
)


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def run_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def test_goal() -> str:
    return "Test goal: refactor authentication module"


@pytest.fixture
def low_risk_goal() -> str:
    return "Read the configuration file"


@pytest.fixture
def high_risk_goal() -> str:
    return "Delete production database"


@pytest.fixture
def budget_policy() -> BudgetPolicy:
    return BudgetPolicy()


@pytest.fixture
def test_run_state(tenant_id, run_id, test_goal, budget_policy) -> RunState:
    return RunState(
        run_id=run_id,
        tenant_id=tenant_id,
        goal=test_goal,
        budget=budget_policy,
    )


@pytest.fixture
def running_state(test_run_state) -> RunState:
    state = test_run_state.model_copy()
    state.status = RunStatus.RUNNING
    state.iterations = 1
    return state


@pytest.fixture
def completed_state(test_run_state) -> RunState:
    state = test_run_state.model_copy()
    state.status = RunStatus.COMPLETED
    state.terminal_state = TerminalState.SUCCESS
    return state


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None
    mock_result.mappings.return_value.all.return_value = []
    mock_result.rowcount = 0
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def mock_engine():
    engine = AsyncMock()
    conn = AsyncMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=conn)
    engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)
    return engine


@pytest.fixture
def mock_get_session(mock_db_session):
    with patch("packages.schemas.database.get_session") as mock:
        mock.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock


@pytest.fixture
def sample_step_result() -> StepResult:
    return StepResult(
        step_number=1,
        node_name="execute",
        action=Action(action_type="execute", tool_name="default", input_data={"goal": "test"}),
        output={"result": "done", "success": True},
        latency_ms=100,
        cost_tokens_in=50,
        cost_tokens_out=25,
        cost_usd=0.001,
    )


@pytest.fixture
def sample_governance_event():
    return {
        "event_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "control_domain": "budget",
        "policy_rule": "max_iterations",
        "decision": "DENY",
        "reviewer": "system",
        "details": {},
    }
