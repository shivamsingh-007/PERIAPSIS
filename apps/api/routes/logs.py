"""Logs API endpoint — returns recent structured log entries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from packages.security.dependencies import get_current_user, get_current_tenant
from packages.security.auth import TokenPayload

router = APIRouter(prefix="/logs", tags=["logs"])


class LogEntry(BaseModel):
    timestamp: str
    level: str
    logger: str
    message: str
    run_id: str | None = None
    tenant_id: str | None = None


@router.get("", response_model=list[LogEntry])
async def list_logs(
    level: str | None = Query(None),
    logger_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant),
):
    """Return recent log entries from the structured logging buffer.

    In production, this would query a logs table or external logging service.
    For now, returns entries from the in-memory log buffer.
    """
    from packages.logging.structured import get_log_buffer

    buffer = get_log_buffer(limit=limit)

    logs = []
    for entry in buffer:
        if level and entry.get("level", "").upper() != level.upper():
            continue
        if logger_name and entry.get("logger") != logger_name:
            continue
        logs.append(LogEntry(
            timestamp=entry.get("timestamp", ""),
            level=entry.get("level", "INFO"),
            logger=entry.get("logger", "unknown"),
            message=entry.get("message", ""),
            run_id=entry.get("run_id"),
            tenant_id=entry.get("tenant_id"),
        ))

    return logs[:limit]
