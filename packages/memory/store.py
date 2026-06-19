from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text

from packages.schemas.database import get_session


class MemoryStore:
    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    async def write(
        self,
        tenant_id: uuid.UUID,
        scope: str,
        memory_type: str,
        content: str,
        source_ref: dict | None = None,
        confidence: float = 0.5,
        ttl_days: int = 365,
        scope_ref: uuid.UUID | None = None,
    ) -> uuid.UUID | None:
        content_hash = self._hash_content(content)

        existing = await self._get_by_hash(tenant_id, content_hash)
        if existing:
            await self._update_confidence(existing["memory_id"], confidence)
            return None

        memory_id = uuid.uuid4()
        expires_at = datetime.utcnow() + timedelta(days=ttl_days)

        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO memory_items
                        (memory_id, tenant_id, scope, scope_ref, memory_type, content,
                         content_hash, source_ref, confidence, ttl_days, expires_at, created_at)
                    VALUES
                        (:memory_id, :tenant_id, :scope, :scope_ref, :memory_type, :content,
                         :content_hash, :source_ref, :confidence, :ttl_days, :expires_at, NOW())
                    """
                ),
                {
                    "memory_id": memory_id,
                    "tenant_id": tenant_id,
                    "scope": scope,
                    "scope_ref": scope_ref,
                    "memory_type": memory_type,
                    "content": content,
                    "content_hash": content_hash,
                    "source_ref": source_ref,
                    "confidence": confidence,
                    "ttl_days": ttl_days,
                    "expires_at": expires_at,
                },
            )
        return memory_id

    async def retrieve(
        self,
        tenant_id: uuid.UUID,
        scope: str | None = None,
        memory_type: str | None = None,
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> list[dict]:
        conditions = ["tenant_id = :tenant_id", "expires_at > NOW()", "confidence >= :min_confidence"]
        params: dict = {"tenant_id": tenant_id, "min_confidence": min_confidence, "limit": limit}

        if scope:
            conditions.append("scope = :scope")
            params["scope"] = scope
        if memory_type:
            conditions.append("memory_type = :memory_type")
            params["memory_type"] = memory_type

        where = " AND ".join(conditions)

        async with get_session() as session:
            result = await session.execute(
                text(
                    f"""
                    SELECT * FROM memory_items
                    WHERE {where}
                    ORDER BY confidence DESC, created_at DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
            return [dict(row) for row in result.mappings().all()]

    async def retrieve_by_context(
        self,
        tenant_id: uuid.UUID,
        context_keywords: list[str],
        limit: int = 5,
    ) -> list[dict]:
        if not context_keywords:
            return []

        like_conditions = ["content ILIKE :kw_0"]
        params: dict = {"tenant_id": tenant_id, "limit": limit}

        for i, kw in enumerate(context_keywords[:5]):
            like_conditions.append(f"content ILIKE :kw_{i}")
            params[f"kw_{i}"] = f"%{kw}%"

        where = f"tenant_id = :tenant_id AND expires_at > NOW() AND ({' OR '.join(like_conditions)})"

        async with get_session() as session:
            result = await session.execute(
                text(
                    f"""
                    SELECT * FROM memory_items
                    WHERE {where}
                    ORDER BY confidence DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
            return [dict(row) for row in result.mappings().all()]

    async def _get_by_hash(self, tenant_id: uuid.UUID, content_hash: str) -> dict | None:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM memory_items
                    WHERE tenant_id = :tenant_id AND content_hash = :content_hash
                    """
                ),
                {"tenant_id": tenant_id, "content_hash": content_hash},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    async def _update_confidence(self, memory_id: uuid.UUID, new_confidence: float) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE memory_items
                    SET confidence = GREATEST(confidence, :confidence)
                    WHERE memory_id = :memory_id
                    """
                ),
                {"memory_id": memory_id, "confidence": new_confidence},
            )

    async def deduplicate(self, tenant_id: uuid.UUID) -> int:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    DELETE FROM memory_items
                    WHERE memory_id NOT IN (
                        SELECT MIN(memory_id)
                        FROM memory_items
                        WHERE tenant_id = :tenant_id
                        GROUP BY content_hash
                    ) AND tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": tenant_id},
            )
            return result.rowcount

    async def expire_old(self, tenant_id: uuid.UUID) -> int:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    DELETE FROM memory_items
                    WHERE tenant_id = :tenant_id AND expires_at <= NOW()
                    """
                ),
                {"tenant_id": tenant_id},
            )
            return result.rowcount

    async def delete(self, tenant_id: uuid.UUID, memory_id: uuid.UUID) -> bool:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    DELETE FROM memory_items
                    WHERE memory_id = :memory_id AND tenant_id = :tenant_id
                    """
                ),
                {"memory_id": memory_id, "tenant_id": tenant_id},
            )
            return result.rowcount > 0


memory_store = MemoryStore()
