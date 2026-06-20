"""FastAPI dependencies for authentication and tenant extraction."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from packages.security.auth import AuthManager, TokenPayload, auth_manager

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    auth: AuthManager = Depends(lambda: auth_manager),
) -> TokenPayload:
    """Extract and verify the current user from the Authorization header.

    Raises 401 if token is missing, expired, or invalid.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    payload = auth.verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


async def get_current_tenant(
    user: TokenPayload = Depends(get_current_user),
) -> str:
    """Extract tenant_id from the authenticated user."""
    return user.tenant_id


async def get_current_tenant_from_header(
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    user: TokenPayload = Depends(get_current_user),
) -> str:
    """Extract tenant_id from X-Tenant-ID header, falling back to user's tenant.

    Validates that the header tenant matches the user's token tenant.
    """
    tenant_id = x_tenant_id or user.tenant_id
    if tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Tenant ID mismatch between header and token",
        )
    return tenant_id


async def get_current_tenant_from_query(
    tenant_id: str | None = Query(None),
    user: TokenPayload = Depends(get_current_user),
) -> str:
    """Extract tenant_id from query parameter, falling back to user's tenant."""
    return tenant_id or user.tenant_id


async def verify_ws_token(
    websocket: WebSocket,
    token: str | None = Query(None),
    auth: AuthManager = Depends(lambda: auth_manager),
) -> TokenPayload:
    """Verify JWT token from WebSocket query parameter.

    Closes the WebSocket with 1008 (Policy Violation) if token is invalid.
    """
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        raise HTTPException(status_code=401, detail="Missing token in WebSocket query")

    payload = auth.verify_token(token)
    if payload is None:
        await websocket.close(code=1008, reason="Invalid token")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload
