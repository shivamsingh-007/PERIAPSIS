from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session


class ConflictStrategy(str, Enum):
    HIGHEST_CONFIDENCE = "highest_confidence"
    MOST_RECENT = "most_recent"
    HUMAN_DECIDES = "human_decides"
    KEEP_BOTH = "keep_both"
    MERGE = "merge"


class ConflictResult(BaseModel):
    strategy_used: ConflictStrategy
    kept_memory_id: uuid.UUID | None = None
    removed_memory_id: uuid.UUID | None = None
    merged_content: str | None = None
    needs_human_review: bool = False


class MemoryConflictResolver:
    def __init__(self, default_strategy: ConflictStrategy = ConflictStrategy.HIGHEST_CONFIDENCE):
        self.default_strategy = default_strategy

    async def resolve(
        self,
        tenant_id: uuid.UUID,
        existing_memory_id: uuid.UUID,
        new_content: str,
        new_confidence: float,
        strategy: ConflictStrategy | None = None,
    ) -> ConflictResult:
        strategy = strategy or self.default_strategy

        existing = await self._get_memory(tenant_id, existing_memory_id)
        if not existing:
            return ConflictResult(
                strategy_used=strategy,
                kept_memory_id=None,
            )

        if strategy == ConflictStrategy.HIGHEST_CONFIDENCE:
            return self._resolve_highest_confidence(existing, existing_memory_id, new_confidence, new_content)
        elif strategy == ConflictStrategy.MOST_RECENT:
            return self._resolve_most_recent(existing, existing_memory_id, new_content, new_confidence)
        elif strategy == ConflictStrategy.KEEP_BOTH:
            return ConflictResult(strategy_used=strategy, needs_human_review=False)
        elif strategy == ConflictStrategy.MERGE:
            return await self._resolve_merge(existing, existing_memory_id, new_content, new_confidence)
        elif strategy == ConflictStrategy.HUMAN_DECIDES:
            return ConflictResult(
                strategy_used=strategy,
                needs_human_review=True,
                kept_memory_id=existing_memory_id,
            )

        return ConflictResult(strategy_used=strategy)

    def _resolve_highest_confidence(
        self,
        existing: dict,
        existing_id: uuid.UUID,
        new_confidence: float,
        new_content: str,
    ) -> ConflictResult:
        existing_confidence = existing.get("confidence", 0.5)

        if new_confidence > existing_confidence:
            return ConflictResult(
                strategy_used=ConflictStrategy.HIGHEST_CONFIDENCE,
                kept_memory_id=None,
                removed_memory_id=existing_id,
            )
        else:
            return ConflictResult(
                strategy_used=ConflictStrategy.HIGHEST_CONFIDENCE,
                kept_memory_id=existing_id,
            )

    def _resolve_most_recent(
        self,
        existing: dict,
        existing_id: uuid.UUID,
        new_content: str,
        new_confidence: float,
    ) -> ConflictResult:
        return ConflictResult(
            strategy_used=ConflictStrategy.MOST_RECENT,
            kept_memory_id=None,
            removed_memory_id=existing_id,
        )

    async def _resolve_merge(
        self,
        existing: dict,
        existing_id: uuid.UUID,
        new_content: str,
        new_confidence: float,
    ) -> ConflictResult:
        existing_content = existing.get("content", "")
        merged = f"[Existing] {existing_content}\n[New] {new_content}"

        avg_confidence = (existing.get("confidence", 0.5) + new_confidence) / 2

        return ConflictResult(
            strategy_used=ConflictStrategy.MERGE,
            merged_content=merged,
            removed_memory_id=existing_id,
        )

    async def _get_memory(self, tenant_id: uuid.UUID, memory_id: uuid.UUID) -> dict | None:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM memory_items
                    WHERE memory_id = :memory_id AND tenant_id = :tenant_id
                    """
                ),
                {"memory_id": memory_id, "tenant_id": tenant_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None


conflict_resolver = MemoryConflictResolver()
