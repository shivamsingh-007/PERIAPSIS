from __future__ import annotations

import uuid
from enum import Enum
from typing import Callable

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from packages.logging.structured import get_logger

logger = get_logger("rbac")


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(str, Enum):
    RUN_CREATE = "run:create"
    RUN_READ = "run:read"
    RUN_UPDATE = "run:update"
    RUN_DELETE = "run:delete"
    RUN_EXECUTE = "run:execute"
    APPROVAL_CREATE = "approval:create"
    APPROVAL_APPROVE = "approval:approve"
    MEMORY_WRITE = "memory:write"
    MEMORY_READ = "memory:read"
    POLICY_UPDATE = "policy:update"
    USER_MANAGE = "user:manage"
    TENANT_MANAGE = "tenant:manage"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),
    Role.OPERATOR: {
        Permission.RUN_CREATE,
        Permission.RUN_READ,
        Permission.RUN_UPDATE,
        Permission.RUN_EXECUTE,
        Permission.APPROVAL_CREATE,
        Permission.APPROVAL_APPROVE,
        Permission.MEMORY_WRITE,
        Permission.MEMORY_READ,
    },
    Role.VIEWER: {
        Permission.RUN_READ,
        Permission.MEMORY_READ,
    },
}


class RBACMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, get_role: Callable | None = None):
        super().__init__(app)
        self.get_role = get_role or self._default_get_role

    def _default_get_role(self, request: Request) -> Role:
        role_str = request.headers.get("X-User-Role", "viewer")
        try:
            return Role(role_str)
        except ValueError:
            return Role.VIEWER

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        role = self.get_role(request)
        request.state.role = role
        request.state.permissions = ROLE_PERMISSIONS.get(role, set())

        required_permission = self._get_required_permission(request)
        if required_permission and required_permission not in request.state.permissions:
            logger.warning(f"Access denied: {role.value} lacks {required_permission.value}")
            return Response(
                content=f'{{"error": "Forbidden", "required": "{required_permission.value}"}}',
                status_code=403,
                headers={"Content-Type": "application/json"},
            )

        return await call_next(request)

    def _get_required_permission(self, request: Request) -> Permission | None:
        path = request.url.path
        method = request.method

        if "/runs" in path:
            if method == "POST":
                return Permission.RUN_CREATE
            elif method == "GET":
                return Permission.RUN_READ
            elif method in ("PUT", "PATCH"):
                return Permission.RUN_UPDATE
            elif method == "DELETE":
                return Permission.RUN_DELETE
            elif "/execute" in path:
                return Permission.RUN_EXECUTE

        if "/approvals" in path:
            if method == "POST" and "/approve" in path:
                return Permission.APPROVAL_APPROVE
            elif method == "POST":
                return Permission.APPROVAL_CREATE

        if "/memory" in path:
            if method in ("POST", "PUT", "DELETE"):
                return Permission.MEMORY_WRITE
            elif method == "GET":
                return Permission.MEMORY_READ

        return None


def require_permission(permission: Permission):
    async def check(request: Request):
        if permission not in request.state.permissions:
            raise HTTPException(status_code=403, detail=f"Permission denied: {permission.value}")
    return check
