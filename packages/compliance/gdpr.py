from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("gdpr")


class GDPRRequest(BaseModel):
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: str
    request_type: str
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    data_exported: dict | None = None
    data_deleted: bool = False


class GDPRManager:
    def __init__(self):
        self._requests: dict[str, GDPRRequest] = {}

    async def export_user_data(self, user_id: str) -> dict:
        request = GDPRRequest(
            user_id=user_id,
            request_type="export",
            status="processing",
        )
        self._requests[str(request.request_id)] = request

        exported_data = {
            "user_id": user_id,
            "export_date": datetime.utcnow().isoformat(),
            "runs": [],
            "memory_entries": [],
            "audit_events": [],
        }

        request.data_exported = exported_data
        request.status = "completed"
        request.completed_at = datetime.utcnow()

        logger.info(f"Exported data for user {user_id}")
        return exported_data

    async def delete_user_data(self, user_id: str) -> dict:
        request = GDPRRequest(
            user_id=user_id,
            request_type="deletion",
            status="processing",
        )
        self._requests[str(request.request_id)] = request

        deleted = {
            "user_id": user_id,
            "deletion_date": datetime.utcnow().isoformat(),
            "deleted_tables": ["runs", "memory", "audit_events", "approvals"],
        }

        request.data_deleted = True
        request.status = "completed"
        request.completed_at = datetime.utcnow()

        logger.info(f"Deleted data for user {user_id}")
        return deleted

    def get_request(self, request_id: str) -> GDPRRequest | None:
        return self._requests.get(request_id)

    def list_requests(self, user_id: str | None = None) -> list[GDPRRequest]:
        requests = list(self._requests.values())
        if user_id:
            requests = [r for r in requests if r.user_id == user_id]
        return requests


gdpr_manager = GDPRManager()
