from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from sqlalchemy import text

from packages.schemas.database import get_session
from packages.logging.structured import get_logger

logger = get_logger("rls")


class RowLevelSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, get_tenant_id: Callable | None = None):
        super().__init__(app)
        self.get_tenant_id = get_tenant_id or self._default_get_tenant

    def _default_get_tenant(self, request: Request) -> str | None:
        return request.headers.get("X-Tenant-ID")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tenant_id = self.get_tenant_id(request)

        if tenant_id:
            request.state.tenant_id = uuid.UUID(tenant_id) if tenant_id else None
            await self._set_rls_context(tenant_id)

        response = await call_next(request)
        return response

    async def _set_rls_context(self, tenant_id: str):
        try:
            async with get_session() as session:
                await session.execute(
                    text("SET app.current_tenant = :tenant_id"),
                    {"tenant_id": tenant_id},
                )
        except Exception as e:
            logger.warning(f"Failed to set RLS context: {e}")


class TenantIsolator:
    def __init__(self):
        self._policies: dict[str, dict] = {}

    def add_policy(self, table: str, policy: dict):
        self._policies[table] = policy

    async def check_access(
        self,
        tenant_id: uuid.UUID,
        resource_tenant_id: uuid.UUID,
        operation: str = "read",
    ) -> bool:
        if tenant_id == resource_tenant_id:
            return True

        return False

    async def filter_query(
        self,
        tenant_id: uuid.UUID,
        base_query: str,
        table_alias: str = "",
    ) -> tuple[str, dict]:
        prefix = f"{table_alias}." if table_alias else ""
        filtered_query = f"{base_query} WHERE {prefix}tenant_id = :tenant_id"
        return filtered_query, {"tenant_id": str(tenant_id)}


tenant_isolator = TenantIsolator()


async def get_current_tenant(
    request: Request,
) -> uuid.UUID:
    """FastAPI dependency that extracts tenant_id from request state.

    Used by fleet.py and resilience.py for backwards compat.
    Falls back to X-Tenant-ID header if middleware hasn't set state.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        header_val = request.headers.get("X-Tenant-ID")
        if header_val:
            tenant_id = uuid.UUID(header_val)
    if tenant_id is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Missing tenant_id")
    return tenant_id
