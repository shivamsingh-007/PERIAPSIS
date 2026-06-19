from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("tenant_isolation")


class TenantConfig(BaseModel):
    tenant_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    plan: str = "free"
    budget_limit: float = 100.0
    budget_used: float = 0.0
    max_agents: int = 5
    max_runs_per_day: int = 50
    allowed_environments: list[str] = Field(default_factory=lambda: ["dev"])
    data_isolation: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class TenantWorkspace(BaseModel):
    workspace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    workspace_path: str
    database_schema: str
    storage_bucket: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TenantIsolation:
    def __init__(self):
        self._tenants: dict[uuid.UUID, TenantConfig] = {}
        self._workspaces: dict[uuid.UUID, TenantWorkspace] = {}

    def create_tenant(
        self,
        name: str,
        plan: str = "free",
        budget_limit: float = 100.0,
        max_agents: int = 5,
        max_runs_per_day: int = 50,
    ) -> TenantConfig:
        tenant = TenantConfig(
            name=name,
            plan=plan,
            budget_limit=budget_limit,
            max_agents=max_agents,
            max_runs_per_day=max_runs_per_day,
        )
        self._tenants[tenant.tenant_id] = tenant

        workspace = TenantWorkspace(
            tenant_id=tenant.tenant_id,
            workspace_path=f"/workspaces/{tenant.tenant_id}",
            database_schema=f"tenant_{str(tenant.tenant_id)[:8]}",
            storage_bucket=f"tenant-{str(tenant.tenant_id)[:8]}",
        )
        self._workspaces[workspace.workspace_id] = workspace

        logger.info(f"Created tenant: {name} ({tenant.tenant_id})")
        return tenant

    def get_tenant(self, tenant_id: uuid.UUID) -> TenantConfig | None:
        return self._tenants.get(tenant_id)

    def get_workspace(self, tenant_id: uuid.UUID) -> TenantWorkspace | None:
        for ws in self._workspaces.values():
            if ws.tenant_id == tenant_id:
                return ws
        return None

    def check_budget(self, tenant_id: uuid.UUID, cost: float) -> bool:
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        return (tenant.budget_used + cost) <= tenant.budget_limit

    def record_usage(self, tenant_id: uuid.UUID, cost: float) -> None:
        tenant = self._tenants.get(tenant_id)
        if tenant:
            tenant.budget_used += cost

    def check_agent_limit(self, tenant_id: uuid.UUID, current_agents: int) -> bool:
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        return current_agents < tenant.max_agents

    def list_tenants(self, active_only: bool = True) -> list[TenantConfig]:
        tenants = list(self._tenants.values())
        if active_only:
            tenants = [t for t in tenants if t.is_active]
        return tenants

    def get_usage_analytics(self, tenant_id: uuid.UUID) -> dict:
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return {}

        return {
            "tenant_id": str(tenant_id),
            "name": tenant.name,
            "plan": tenant.plan,
            "budget_limit": tenant.budget_limit,
            "budget_used": tenant.budget_used,
            "budget_remaining": tenant.budget_limit - tenant.budget_used,
            "budget_utilization": round(
                tenant.budget_used / max(tenant.budget_limit, 1) * 100, 1
            ),
            "max_agents": tenant.max_agents,
            "max_runs_per_day": tenant.max_runs_per_day,
        }


tenant_isolation = TenantIsolation()
