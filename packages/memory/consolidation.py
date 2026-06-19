from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import text

from packages.schemas.database import get_session
from packages.memory.store import memory_store


class MemoryConsolidator:
    async def consolidate_old_memories(
        self,
        tenant_id: uuid.UUID,
        older_than_days: int = 30,
        min_group_size: int = 3,
    ) -> dict:
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT memory_type, COUNT(*) as count, MIN(created_at) as oldest
                    FROM memory_items
                    WHERE tenant_id = :tenant_id
                      AND created_at < :cutoff
                      AND memory_type NOT IN ('summary', 'constraint')
                    GROUP BY memory_type
                    HAVING COUNT(*) >= :min_group
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "cutoff": cutoff_date,
                    "min_group": min_group_size,
                },
            )
            groups = [dict(row) for row in result.mappings().all()]

        consolidated = 0
        summaries_created = 0

        for group in groups:
            memories = await memory_store.retrieve(
                tenant_id=tenant_id,
                memory_type=group["memory_type"],
                limit=50,
            )

            if len(memories) < min_group_size:
                continue

            summary_content = self._generate_summary(memories, group["memory_type"])

            avg_confidence = sum(m.get("confidence", 0.5) for m in memories) / len(memories)

            summary_id = await memory_store.write(
                tenant_id=tenant_id,
                scope="consolidated",
                memory_type="summary",
                content=summary_content,
                source_ref={
                    "consolidated_from": [str(m.get("memory_id")) for m in memories],
                    "original_type": group["memory_type"],
                    "count": len(memories),
                },
                confidence=avg_confidence * 0.9,
                ttl_days=365,
            )

            if summary_id:
                summaries_created += 1
                for mem in memories:
                    await memory_store.delete(tenant_id, mem["memory_id"])
                    consolidated += 1

        return {
            "consolidated": consolidated,
            "summaries_created": summaries_created,
            "groups_processed": len(groups),
        }

    def _generate_summary(self, memories: list[dict], memory_type: str) -> str:
        contents = [m.get("content", "") for m in memories if m.get("content")]

        if not contents:
            return f"Consolidated {memory_type} memories (empty)"

        unique_contents = list(set(contents))

        if len(unique_contents) == 1:
            return f"Recurring {memory_type}: {unique_contents[0]}"

        summary_parts = [
            f"Consolidated {len(memories)} {memory_type} memories:",
            *unique_contents[:10],
        ]
        if len(unique_contents) > 10:
            summary_parts.append(f"... and {len(unique_contents) - 10} more")

        return "\n".join(summary_parts)

    async def get_consolidation_stats(self, tenant_id: uuid.UUID) -> dict:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) as total_memories,
                        COUNT(CASE WHEN memory_type = 'summary' THEN 1 END) as summaries,
                        COUNT(CASE WHEN created_at < NOW() - INTERVAL '30 days' THEN 1 END) as old_memories,
                        COUNT(DISTINCT memory_type) as memory_types
                    FROM memory_items
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": tenant_id},
            )
            row = result.mappings().first()
            return dict(row) if row else {}


memory_consolidator = MemoryConsolidator()
