from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session
from packages.logging.structured import get_logger

logger = get_logger("feature_flags")


class FlagType(str, Enum):
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_SEGMENT = "user_segment"


class FeatureFlag(BaseModel):
    flag_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    name: str
    description: str = ""
    flag_type: FlagType = FlagType.BOOLEAN
    enabled: bool = True
    percentage: float = 100.0
    user_segments: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeatureFlagManager:
    def __init__(self):
        self._cache: dict[str, FeatureFlag] = {}

    async def create_flag(
        self,
        tenant_id: uuid.UUID,
        name: str,
        description: str = "",
        flag_type: FlagType = FlagType.BOOLEAN,
        enabled: bool = True,
        percentage: float = 100.0,
        user_segments: list[str] | None = None,
        config: dict | None = None,
    ) -> FeatureFlag:
        flag = FeatureFlag(
            tenant_id=tenant_id,
            name=name,
            description=description,
            flag_type=flag_type,
            enabled=enabled,
            percentage=percentage,
            user_segments=user_segments or [],
            config=config or {},
        )

        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO feature_flags
                        (flag_id, tenant_id, name, description, flag_type, enabled,
                         percentage, user_segments, config, created_at)
                    VALUES
                        (:flag_id, :tenant_id, :name, :description, :flag_type, :enabled,
                         :percentage, :user_segments, :config, NOW())
                    """
                ),
                {
                    "flag_id": flag.flag_id,
                    "tenant_id": tenant_id,
                    "name": name,
                    "description": description,
                    "flag_type": flag_type.value,
                    "enabled": enabled,
                    "percentage": percentage,
                    "user_segments": user_segments or [],
                    "config": config or {},
                },
            )

        self._cache[f"{tenant_id}:{name}"] = flag
        logger.info(f"Feature flag created: {name}")
        return flag

    async def is_enabled(
        self,
        tenant_id: uuid.UUID,
        flag_name: str,
        user_id: str | None = None,
        user_segments: list[str] | None = None,
    ) -> bool:
        cache_key = f"{tenant_id}:{flag_name}"
        flag = self._cache.get(cache_key)

        if not flag:
            flag = await self._get_flag(tenant_id, flag_name)
            if not flag:
                return False
            self._cache[cache_key] = flag

        if not flag.enabled:
            return False

        if flag.flag_type == FlagType.BOOLEAN:
            return True

        if flag.flag_type == FlagType.PERCENTAGE:
            if user_id:
                hash_val = int(hashlib.md5(f"{flag.flag_id}:{user_id}".encode()).hexdigest(), 16)
                return (hash_val % 100) < flag.percentage
            return True

        if flag.flag_type == FlagType.USER_SEGMENT:
            if not user_segments:
                return False
            return bool(set(flag.user_segments) & set(user_segments))

        return False

    async def _get_flag(self, tenant_id: uuid.UUID, name: str) -> FeatureFlag | None:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM feature_flags
                    WHERE tenant_id = :tenant_id AND name = :name
                    """
                ),
                {"tenant_id": tenant_id, "name": name},
            )
            row = result.mappings().first()
            if row:
                data = dict(row)
                data["user_segments"] = data.get("user_segments", [])
                data["config"] = data.get("config", {})
                return FeatureFlag(**data)
            return None

    async def update_flag(
        self,
        tenant_id: uuid.UUID,
        flag_name: str,
        **kwargs,
    ) -> bool:
        updates = []
        params = {"tenant_id": tenant_id, "name": flag_name}

        for key, value in kwargs.items():
            if key in ("enabled", "percentage", "description"):
                updates.append(f"{key} = :{key}")
                params[key] = value
            elif key == "user_segments":
                updates.append("user_segments = :user_segments")
                params["user_segments"] = value

        if not updates:
            return False

        set_clause = ", ".join(updates)

        async with get_session() as session:
            result = await session.execute(
                text(f"UPDATE feature_flags SET {set_clause} WHERE tenant_id = :tenant_id AND name = :name"),
                params,
            )

        cache_key = f"{tenant_id}:{flag_name}"
        self._cache.pop(cache_key, None)

        return result.rowcount > 0

    async def delete_flag(self, tenant_id: uuid.UUID, flag_name: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                text("DELETE FROM feature_flags WHERE tenant_id = :tenant_id AND name = :name"),
                {"tenant_id": tenant_id, "name": flag_name},
            )

        cache_key = f"{tenant_id}:{flag_name}"
        self._cache.pop(cache_key, None)

        return result.rowcount > 0

    async def list_flags(self, tenant_id: uuid.UUID) -> list[FeatureFlag]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM feature_flags
                    WHERE tenant_id = :tenant_id
                    ORDER BY name
                    """
                ),
                {"tenant_id": tenant_id},
            )
            flags = []
            for row in result.mappings().all():
                data = dict(row)
                data["user_segments"] = data.get("user_segments", [])
                data["config"] = data.get("config", {})
                flags.append(FeatureFlag(**data))
            return flags


feature_flag_manager = FeatureFlagManager()
