from __future__ import annotations
"""Tests for packages.tenant.isolation - TenantIsolation."""

import uuid

import pytest

from packages.tenant.isolation import TenantConfig, TenantIsolation, TenantWorkspace


class TestTenantIsolation:
    def setup_method(self):
        self.isolation = TenantIsolation()

    def test_create_tenant(self):
        tenant = self.isolation.create_tenant("Acme Corp", plan="pro", budget_limit=500.0)
        assert tenant.name == "Acme Corp"
        assert tenant.plan == "pro"
        assert tenant.budget_limit == 500.0

    def test_get_tenant(self):
        tenant = self.isolation.create_tenant("Acme")
        found = self.isolation.get_tenant(tenant.tenant_id)
        assert found is not None
        assert found.name == "Acme"

    def test_get_tenant_not_found(self):
        assert self.isolation.get_tenant(uuid.uuid4()) is None

    def test_workspace_created_with_tenant(self):
        tenant = self.isolation.create_tenant("Acme")
        ws = self.isolation.get_workspace(tenant.tenant_id)
        assert ws is not None
        assert ws.tenant_id == tenant.tenant_id

    def test_check_budget_within(self):
        tenant = self.isolation.create_tenant("Acme", budget_limit=100.0)
        assert self.isolation.check_budget(tenant.tenant_id, 50.0) is True

    def test_check_budget_exceeded(self):
        tenant = self.isolation.create_tenant("Acme", budget_limit=100.0)
        assert self.isolation.check_budget(tenant.tenant_id, 101.0) is False

    def test_check_budget_unknown_tenant(self):
        assert self.isolation.check_budget(uuid.uuid4(), 10.0) is False

    def test_record_usage(self):
        tenant = self.isolation.create_tenant("Acme", budget_limit=100.0)
        self.isolation.record_usage(tenant.tenant_id, 30.0)
        self.isolation.record_usage(tenant.tenant_id, 20.0)
        found = self.isolation.get_tenant(tenant.tenant_id)
        assert found.budget_used == 50.0

    def test_check_agent_limit_within(self):
        tenant = self.isolation.create_tenant("Acme", max_agents=5)
        assert self.isolation.check_agent_limit(tenant.tenant_id, 3) is True

    def test_check_agent_limit_exceeded(self):
        tenant = self.isolation.create_tenant("Acme", max_agents=5)
        assert self.isolation.check_agent_limit(tenant.tenant_id, 5) is False

    def test_check_agent_limit_unknown(self):
        assert self.isolation.check_agent_limit(uuid.uuid4(), 1) is False

    def test_list_tenants(self):
        self.isolation.create_tenant("A")
        self.isolation.create_tenant("B")
        tenants = self.isolation.list_tenants()
        assert len(tenants) == 2

    def test_get_usage_analytics(self):
        tenant = self.isolation.create_tenant("Acme", budget_limit=200.0, max_agents=5)
        self.isolation.record_usage(tenant.tenant_id, 80.0)
        analytics = self.isolation.get_usage_analytics(tenant.tenant_id)
        assert analytics["name"] == "Acme"
        assert analytics["budget_limit"] == 200.0
        assert analytics["budget_used"] == 80.0
        assert analytics["budget_remaining"] == 120.0
        assert analytics["budget_utilization"] == 40.0

    def test_get_usage_analytics_unknown(self):
        assert self.isolation.get_usage_analytics(uuid.uuid4()) == {}
