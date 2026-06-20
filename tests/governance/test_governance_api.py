"""Tests for governance API routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


def _make_user_payload():
    from packages.security.auth import TokenPayload
    return TokenPayload(
        sub="user-1",
        tenant_id="tenant-1",
        role="admin",
        permissions=["governance:read", "governance:write"],
        exp=9999999999.0,
        iat=1000000000.0,
    )


class TestGovernanceRoutes:
    def test_governance_router_exists(self):
        from apps.api.routes.governance import router
        assert router.prefix == "/governance"
        assert "governance" in router.tags

    def test_approve_requires_event_id(self):
        from apps.api.routes.governance import approve_event
        import inspect
        sig = inspect.signature(approve_event)
        assert "event_id" in sig.parameters

    def test_deny_requires_event_id_and_reason(self):
        from apps.api.routes.governance import deny_event
        import inspect
        sig = inspect.signature(deny_event)
        assert "event_id" in sig.parameters
        assert "reason" in sig.parameters

    def test_governance_summary_model(self):
        from apps.api.routes.governance import GovernanceSummary
        s = GovernanceSummary(total=10, approved=5, pending=3, denied=2, require_approval=3)
        assert s.total == 10
        assert s.approved == 5

    def test_event_response_model(self):
        from apps.api.routes.governance import GovernanceEventResponse
        e = GovernanceEventResponse(
            id="evt-1",
            run_id="run-1",
            control_domain="policy_check",
            policy_rule="risk_tier",
            decision="pass",
            created_at="2026-01-01T00:00:00",
        )
        assert e.decision == "pass"


class TestGovernanceEndpoints:
    @pytest.mark.asyncio
    async def test_list_events_empty(self):
        from httpx import AsyncClient, ASGITransport
        from apps.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/governance/events")
            # Without auth, should get 403 or 401
            assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_summary_empty(self):
        from httpx import AsyncClient, ASGITransport
        from apps.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/governance/summary")
            assert resp.status_code in (401, 403)
