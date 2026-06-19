from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("data_retention")


class RetentionPolicy(BaseModel):
    policy_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    data_type: str
    retention_days: int
    archive_after_days: int | None = None
    delete_after_days: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True


class DataRetentionPolicy:
    def __init__(self):
        self._policies: dict[str, RetentionPolicy] = {}
        self._default_retention = 365

    def create_policy(
        self,
        name: str,
        data_type: str,
        retention_days: int,
        archive_after_days: int | None = None,
        delete_after_days: int | None = None,
    ) -> RetentionPolicy:
        policy = RetentionPolicy(
            name=name,
            data_type=data_type,
            retention_days=retention_days,
            archive_after_days=archive_after_days,
            delete_after_days=delete_after_days or retention_days,
        )
        self._policies[data_type] = policy
        logger.info(f"Created retention policy: {name} for {data_type}")
        return policy

    def get_policy(self, data_type: str) -> RetentionPolicy | None:
        return self._policies.get(data_type)

    def should_archive(self, data_type: str, created_at: datetime) -> bool:
        policy = self._policies.get(data_type)
        if not policy or not policy.archive_after_days:
            return False
        age_days = (datetime.utcnow() - created_at).days
        return age_days >= policy.archive_after_days

    def should_delete(self, data_type: str, created_at: datetime) -> bool:
        policy = self._policies.get(data_type)
        if not policy or not policy.delete_after_days:
            return False
        age_days = (datetime.utcnow() - created_at).days
        return age_days >= policy.delete_after_days

    def get_retention_cutoff(self, data_type: str) -> datetime | None:
        policy = self._policies.get(data_type)
        if not policy:
            return datetime.utcnow() - timedelta(days=self._default_retention)
        return datetime.utcnow() - timedelta(days=policy.retention_days)

    def list_policies(self) -> list[RetentionPolicy]:
        return list(self._policies.values())


data_retention_policy = DataRetentionPolicy()
