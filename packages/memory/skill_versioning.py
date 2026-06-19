from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("skill_versioning")


class SkillVersion(BaseModel):
    version_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    skill_name: str
    version: str
    content: dict = Field(default_factory=dict)
    hash: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "system"
    changelog: str = ""
    is_active: bool = True
    metrics: dict[str, Any] = Field(default_factory=dict)


class SkillRollback(BaseModel):
    rollback_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    skill_name: str
    from_version: str
    to_version: str
    reason: str
    rolled_back_at: datetime = Field(default_factory=datetime.utcnow)
    rolled_back_by: str = "system"


class SkillVersionManager:
    def __init__(self):
        self._versions: dict[str, list[SkillVersion]] = {}
        self._rollbacks: list[SkillRollback] = {}

    def create_version(
        self,
        skill_name: str,
        content: dict,
        changelog: str = "",
        created_by: str = "system",
    ) -> SkillVersion:
        if skill_name not in self._versions:
            self._versions[skill_name] = []

        existing = self._versions[skill_name]
        if existing:
            for v in existing:
                v.is_active = False

        version_num = len(existing) + 1
        version_str = f"v{version_num}"

        content_hash = hashlib.sha256(
            str(sorted(content.items())).encode()
        ).hexdigest()[:12]

        version = SkillVersion(
            skill_name=skill_name,
            version=version_str,
            content=content,
            hash=content_hash,
            changelog=changelog,
            created_by=created_by,
        )

        self._versions[skill_name].append(version)
        logger.info(f"Created skill version: {skill_name}:{version_str}")
        return version

    def get_active_version(self, skill_name: str) -> SkillVersion | None:
        versions = self._versions.get(skill_name, [])
        for v in reversed(versions):
            if v.is_active:
                return v
        return None

    def get_version(self, skill_name: str, version: str) -> SkillVersion | None:
        for v in self._versions.get(skill_name, []):
            if v.version == version:
                return v
        return None

    def list_versions(self, skill_name: str) -> list[SkillVersion]:
        return self._versions.get(skill_name, [])

    def rollback(
        self,
        skill_name: str,
        target_version: str,
        reason: str = "",
        rolled_back_by: str = "system",
    ) -> SkillVersion | None:
        current = self.get_active_version(skill_name)
        target = self.get_version(skill_name, target_version)

        if not target:
            logger.error(f"Target version {target_version} not found for {skill_name}")
            return None

        if current:
            current.is_active = False

        target.is_active = True

        rollback = SkillRollback(
            skill_name=skill_name,
            from_version=current.version if current else "none",
            to_version=target_version,
            reason=reason,
            rolled_back_by=rolled_back_by,
        )
        self._rollbacks[str(rollback.rollback_id)] = rollback

        logger.info(f"Rolled back {skill_name}: {current.version if current else 'none'} -> {target_version}")
        return target

    def update_metrics(self, skill_name: str, version: str, metrics: dict) -> None:
        v = self.get_version(skill_name, version)
        if v:
            v.metrics.update(metrics)

    def get_skill_history(self, skill_name: str) -> dict:
        versions = self._versions.get(skill_name, [])
        return {
            "skill_name": skill_name,
            "total_versions": len(versions),
            "active_version": self.get_active_version(skill_name).version if self.get_active_version(skill_name) else None,
            "versions": [
                {
                    "version": v.version,
                    "hash": v.hash,
                    "created_at": v.created_at.isoformat(),
                    "is_active": v.is_active,
                    "changelog": v.changelog,
                }
                for v in versions
            ],
        }

    def list_all_skills(self) -> list[str]:
        return list(self._versions.keys())


skill_version_manager = SkillVersionManager()
