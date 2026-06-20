from __future__ import annotations

import uuid

import pytest

from packages.tenant.isolation import TenantConfig, TenantIsolation, TenantWorkspace


class TestTenantConfigExtended:
    def test_create_config(self):
        config = TenantConfig(name="Acme", plan="pro", budget_limit=500.0)
        assert config.name == "Acme"
        assert config.plan == "pro"
        assert config.budget_limit == 500.0

    def test_config_defaults(self):
        config = TenantConfig(name="Test")
        assert config.plan == "free"
        assert config.budget_limit == 100.0
        assert config.budget_used == 0.0
        assert config.max_agents == 5
        assert config.max_runs_per_day == 50
        assert config.allowed_environments == ["dev"]
        assert config.data_isolation is True
        assert config.is_active is True
        assert config.metadata == {}

    def test_config_with_metadata(self):
        config = TenantConfig(name="X", metadata={"region": "us-east"})
        assert config.metadata["region"] == "us-east"

    def test_config_idempotent(self):
        c1 = TenantConfig(name="A")
        c2 = TenantConfig(name="A")
        assert c1.tenant_id != c2.tenant_id


class TestTenantWorkspaceExtended:
    def test_workspace_fields(self):
        ws = TenantWorkspace(
            tenant_id=uuid.uuid4(),
            workspace_path="/ws/1",
            database_schema="tenant_abc",
            storage_bucket="bucket-abc",
        )
        assert ws.workspace_path == "/ws/1"
        assert ws.database_schema == "tenant_abc"
        assert ws.storage_bucket == "bucket-abc"


class TestTenantIsolationExtended:
    def setup_method(self):
        self.isolation = TenantIsolation()

    def test_create_tenant_defaults(self):
        tenant = self.isolation.create_tenant("Test")
        assert tenant.plan == "free"
        assert tenant.budget_limit == 100.0
        assert tenant.max_agents == 5
        assert tenant.max_runs_per_day == 50

    def test_create_tenant_custom(self):
        tenant = self.isolation.create_tenant(
            "Enterprise",
            plan="enterprise",
            budget_limit=10000.0,
            max_agents=50,
            max_runs_per_day=500,
        )
        assert tenant.plan == "enterprise"
        assert tenant.budget_limit == 10000.0
        assert tenant.max_agents == 50
        assert tenant.max_runs_per_day == 500

    def test_create_multiple_tenants(self):
        t1 = self.isolation.create_tenant("A")
        t2 = self.isolation.create_tenant("B")
        assert t1.tenant_id != t2.tenant_id
        assert len(self.isolation.list_tenants()) == 2

    def test_workspace_path_format(self):
        tenant = self.isolation.create_tenant("X")
        ws = self.isolation.get_workspace(tenant.tenant_id)
        assert ws.workspace_path.startswith("/workspaces/")

    def test_workspace_schema_format(self):
        tenant = self.isolation.create_tenant("X")
        ws = self.isolation.get_workspace(tenant.tenant_id)
        assert ws.database_schema.startswith("tenant_")

    def test_workspace_storage_format(self):
        tenant = self.isolation.create_tenant("X")
        ws = self.isolation.get_workspace(tenant.tenant_id)
        assert ws.storage_bucket.startswith("tenant-")

    def test_check_budget_exact_limit(self):
        tenant = self.isolation.create_tenant("A", budget_limit=100.0)
        assert self.isolation.check_budget(tenant.tenant_id, 100.0) is True

    def test_check_budget_one_over(self):
        tenant = self.isolation.create_tenant("A", budget_limit=100.0)
        assert self.isolation.check_budget(tenant.tenant_id, 100.01) is False

    def test_record_usage_cumulative(self):
        tenant = self.isolation.create_tenant("A", budget_limit=200.0)
        self.isolation.record_usage(tenant.tenant_id, 50.0)
        self.isolation.record_usage(tenant.tenant_id, 50.0)
        self.isolation.record_usage(tenant.tenant_id, 50.0)
        found = self.isolation.get_tenant(tenant.tenant_id)
        assert found.budget_used == 150.0

    def test_check_agent_limit_exact(self):
        tenant = self.isolation.create_tenant("A", max_agents=3)
        assert self.isolation.check_agent_limit(tenant.tenant_id, 2) is True

    def test_check_agent_limit_at_limit(self):
        tenant = self.isolation.create_tenant("A", max_agents=3)
        assert self.isolation.check_agent_limit(tenant.tenant_id, 3) is False

    def test_list_tenants_active_only(self):
        t1 = self.isolation.create_tenant("A")
        t2 = self.isolation.create_tenant("B")
        t2.is_active = False
        active = self.isolation.list_tenants(active_only=True)
        assert len(active) == 1
        assert active[0].tenant_id == t1.tenant_id

    def test_list_tenants_all(self):
        t1 = self.isolation.create_tenant("A")
        t2 = self.isolation.create_tenant("B")
        t2.is_active = False
        all_tenants = self.isolation.list_tenants(active_only=False)
        assert len(all_tenants) == 2

    def test_get_usage_analytics_utilization(self):
        tenant = self.isolation.create_tenant("A", budget_limit=200.0)
        self.isolation.record_usage(tenant.tenant_id, 100.0)
        analytics = self.isolation.get_usage_analytics(tenant.tenant_id)
        assert analytics["budget_utilization"] == 50.0

    def test_get_usage_analytics_zero_budget(self):
        tenant = self.isolation.create_tenant("A", budget_limit=0.0)
        analytics = self.isolation.get_usage_analytics(tenant.tenant_id)
        assert analytics["budget_utilization"] == 0.0

    def test_get_usage_analytics_keys(self):
        tenant = self.isolation.create_tenant("A")
        analytics = self.isolation.get_usage_analytics(tenant.tenant_id)
        expected_keys = {
            "tenant_id", "name", "plan", "budget_limit", "budget_used",
            "budget_remaining", "budget_utilization", "max_agents", "max_runs_per_day",
        }
        assert set(analytics.keys()) == expected_keys

    def test_budget_remaining(self):
        tenant = self.isolation.create_tenant("A", budget_limit=500.0)
        self.isolation.record_usage(tenant.tenant_id, 200.0)
        analytics = self.isolation.get_usage_analytics(tenant.tenant_id)
        assert analytics["budget_remaining"] == 300.0
