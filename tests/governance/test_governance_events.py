"""Tests for GovernanceEventLogger: log_event, query_events, audit trail."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.governance.events import GovernanceEventLogger, governance_event_logger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def logger():
    return GovernanceEventLogger()


@pytest.fixture
def run_id():
    return uuid.uuid4()


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def reviewer_id():
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# 1. log - core method
# ---------------------------------------------------------------------------

class TestLogEvent:
    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_log_returns_uuid(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await logger.log(
            run_id=run_id,
            tenant_id=tenant_id,
            control_domain="test_domain",
            policy_rule="test_rule",
            decision="allow",
        )
        assert isinstance(result, uuid.UUID)

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_log_executes_insert(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.log(
            run_id=run_id,
            tenant_id=tenant_id,
            control_domain="approval",
            policy_rule="human_approval",
            decision="approved",
        )
        mock_ctx.execute.assert_called_once()

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_log_passes_details(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        details = {"key": "value"}
        await logger.log(
            run_id=run_id,
            tenant_id=tenant_id,
            control_domain="policy",
            policy_rule="rule1",
            decision="deny",
            details=details,
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["details"] == details

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_log_passes_reviewer(self, mock_session, logger, run_id, tenant_id, reviewer_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.log(
            run_id=run_id,
            tenant_id=tenant_id,
            control_domain="approval",
            policy_rule="human_approval",
            decision="approved",
            reviewer=reviewer_id,
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["reviewer"] == reviewer_id


# ---------------------------------------------------------------------------
# 2. log_approval_requested
# ---------------------------------------------------------------------------

class TestLogApprovalRequested:
    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_returns_uuid(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await logger.log_approval_requested(
            run_id=run_id,
            tenant_id=tenant_id,
            action_type="deploy",
            tool_name="deployer",
            risk_tier="high",
        )
        assert isinstance(result, uuid.UUID)

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_sets_correct_control_domain(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.log_approval_requested(
            run_id=run_id,
            tenant_id=tenant_id,
            action_type="write",
            tool_name="ticketing",
            risk_tier="medium",
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["control_domain"] == "approval"
        assert params["decision"] == "approval_requested"

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_includes_action_type_in_details(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.log_approval_requested(
            run_id=run_id,
            tenant_id=tenant_id,
            action_type="execute",
            tool_name="default",
            risk_tier="low",
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["details"]["action_type"] == "execute"


# ---------------------------------------------------------------------------
# 3. log_approval_granted
# ---------------------------------------------------------------------------

class TestLogApprovalGranted:
    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_returns_uuid(self, mock_session, logger, run_id, tenant_id, reviewer_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await logger.log_approval_granted(
            run_id=run_id,
            tenant_id=tenant_id,
            reviewer=reviewer_id,
            action_type="deploy",
        )
        assert isinstance(result, uuid.UUID)

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_sets_approved_decision(self, mock_session, logger, run_id, tenant_id, reviewer_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.log_approval_granted(
            run_id=run_id,
            tenant_id=tenant_id,
            reviewer=reviewer_id,
            action_type="write",
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["decision"] == "approved"

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_sets_human_approval_rule(self, mock_session, logger, run_id, tenant_id, reviewer_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.log_approval_granted(
            run_id=run_id,
            tenant_id=tenant_id,
            reviewer=reviewer_id,
            action_type="execute",
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["policy_rule"] == "human_approval"


# ---------------------------------------------------------------------------
# 4. log_approval_denied
# ---------------------------------------------------------------------------

class TestLogApprovalDenied:
    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_returns_uuid(self, mock_session, logger, run_id, tenant_id, reviewer_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await logger.log_approval_denied(
            run_id=run_id,
            tenant_id=tenant_id,
            reviewer=reviewer_id,
            action_type="deploy",
            reason="too risky",
        )
        assert isinstance(result, uuid.UUID)

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_sets_denied_decision(self, mock_session, logger, run_id, tenant_id, reviewer_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.log_approval_denied(
            run_id=run_id,
            tenant_id=tenant_id,
            reviewer=reviewer_id,
            action_type="write",
            reason="not allowed",
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["decision"] == "denied"

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_includes_reason_in_details(self, mock_session, logger, run_id, tenant_id, reviewer_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.log_approval_denied(
            run_id=run_id,
            tenant_id=tenant_id,
            reviewer=reviewer_id,
            action_type="deploy",
            reason="security concern",
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["details"]["reason"] == "security concern"


# ---------------------------------------------------------------------------
# 5. log_policy_violation
# ---------------------------------------------------------------------------

class TestLogPolicyViolation:
    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_returns_uuid(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await logger.log_policy_violation(
            run_id=run_id,
            tenant_id=tenant_id,
            policy_rule="rate_limit_exceeded",
        )
        assert isinstance(result, uuid.UUID)

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_sets_violated_decision(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.log_policy_violation(
            run_id=run_id,
            tenant_id=tenant_id,
            policy_rule="max_iterations",
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["decision"] == "violated"

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_sets_policy_violation_domain(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.log_policy_violation(
            run_id=run_id,
            tenant_id=tenant_id,
            policy_rule="cost_limit",
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["control_domain"] == "policy_violation"

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_includes_details(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        details = {"action_type": "deploy", "tool_name": "dangerous"}
        await logger.log_policy_violation(
            run_id=run_id,
            tenant_id=tenant_id,
            policy_rule="tool_denied",
            details=details,
        )
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["details"] == details


# ---------------------------------------------------------------------------
# 6. get_events_for_run
# ---------------------------------------------------------------------------

class TestGetEventsForRun:
    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_returns_empty_when_no_events(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await logger.get_events_for_run(run_id, tenant_id)
        assert result == []

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_returns_events_list(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_row = {"event_id": uuid.uuid4(), "decision": "approved"}
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [mock_row]
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await logger.get_events_for_run(run_id, tenant_id)
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("packages.governance.events.get_session")
    async def test_passes_correct_params(self, mock_session, logger, run_id, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await logger.get_events_for_run(run_id, tenant_id)
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["run_id"] == run_id
        assert params["tenant_id"] == tenant_id


# ---------------------------------------------------------------------------
# 7. singleton instance
# ---------------------------------------------------------------------------

class TestGovernanceEventLoggerSingleton:
    def test_singleton_is_instance(self):
        assert isinstance(governance_event_logger, GovernanceEventLogger)
