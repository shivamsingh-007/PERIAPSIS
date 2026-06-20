"""Tests for MemoryConsolidator: consolidate, dedup, merge."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.memory.consolidation import MemoryConsolidator, memory_consolidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def consolidator():
    return MemoryConsolidator()


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


def _make_memory(
    content: str = "test content",
    memory_type: str = "observation",
    memory_id: uuid.UUID | None = None,
    confidence: float = 0.8,
) -> dict:
    return {
        "memory_id": memory_id or uuid.uuid4(),
        "content": content,
        "memory_type": memory_type,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# 1. _generate_summary
# ---------------------------------------------------------------------------

class TestGenerateSummary:
    def test_generate_summary_empty_memories(self, consolidator):
        result = consolidator._generate_summary([], "observation")
        assert "Consolidated" in result
        assert "observation" in result
        assert "empty" in result

    def test_generate_summary_single_content(self, consolidator):
        memories = [_make_memory(content="hello world")]
        result = consolidator._generate_summary(memories, "observation")
        assert result == "Recurring observation: hello world"

    def test_generate_summary_same_contents(self, consolidator):
        memories = [
            _make_memory(content="same content"),
            _make_memory(content="same content"),
            _make_memory(content="same content"),
        ]
        result = consolidator._generate_summary(memories, "observation")
        assert result == "Recurring observation: same content"

    def test_generate_summary_multiple_unique(self, consolidator):
        memories = [
            _make_memory(content="content A"),
            _make_memory(content="content B"),
            _make_memory(content="content C"),
        ]
        result = consolidator._generate_summary(memories, "observation")
        assert "Consolidated 3 observation memories:" in result
        assert "content A" in result
        assert "content B" in result

    def test_generate_summary_truncates_at_10(self, consolidator):
        memories = [_make_memory(content=f"content {i}") for i in range(15)]
        result = consolidator._generate_summary(memories, "observation")
        assert "... and 5 more" in result

    def test_generate_summary_empty_content_filtered(self, consolidator):
        memories = [
            _make_memory(content=""),
            _make_memory(content=None),
            _make_memory(content="valid"),
        ]
        result = consolidator._generate_summary(memories, "observation")
        assert "valid" in result

    def test_generate_summary_all_empty_content(self, consolidator):
        memories = [
            _make_memory(content=""),
            _make_memory(content=None),
        ]
        result = consolidator._generate_summary(memories, "observation")
        assert "empty" in result

    def test_generate_summary_exactly_10_items(self, consolidator):
        memories = [_make_memory(content=f"item {i}") for i in range(10)]
        result = consolidator._generate_summary(memories, "observation")
        assert "Consolidated 10" in result
        assert "more" not in result

    def test_generate_summary_11_items_shows_more(self, consolidator):
        memories = [_make_memory(content=f"item {i}") for i in range(11)]
        result = consolidator._generate_summary(memories, "observation")
        assert "... and 1 more" in result

    def test_generate_summary_different_memory_types(self, consolidator):
        memories = [_make_memory(content="test")]
        result = consolidator._generate_summary(memories, "lesson")
        assert "Recurring lesson: test" in result


# ---------------------------------------------------------------------------
# 2. consolidate_old_memories
# ---------------------------------------------------------------------------

class TestConsolidateOldMemories:
    @pytest.mark.asyncio
    @patch("packages.memory.consolidation.get_session")
    @patch("packages.memory.consolidation.memory_store")
    async def test_consolidate_returns_stats(self, mock_store, mock_session, consolidator, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await consolidator.consolidate_old_memories(tenant_id)
        assert "consolidated" in result
        assert "summaries_created" in result
        assert "groups_processed" in result

    @pytest.mark.asyncio
    @patch("packages.memory.consolidation.get_session")
    @patch("packages.memory.consolidation.memory_store")
    async def test_consolidate_no_groups_returns_zeros(self, mock_store, mock_session, consolidator, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await consolidator.consolidate_old_memories(tenant_id)
        assert result["consolidated"] == 0
        assert result["summaries_created"] == 0
        assert result["groups_processed"] == 0

    @pytest.mark.asyncio
    @patch("packages.memory.consolidation.get_session")
    @patch("packages.memory.consolidation.memory_store")
    async def test_consolidate_with_groups(self, mock_store, mock_session, consolidator, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {"memory_type": "observation", "count": 5, "oldest": "2024-01-01"},
        ]
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx

        memories = [_make_memory(content=f"obs {i}") for i in range(5)]
        mock_store.retrieve = AsyncMock(return_value=memories)
        mock_store.write = AsyncMock(return_value=uuid.uuid4())
        mock_store.delete = AsyncMock(return_value=True)

        result = await consolidator.consolidate_old_memories(tenant_id, min_group_size=3)
        assert result["groups_processed"] == 1
        assert result["consolidated"] == 5
        assert result["summaries_created"] == 1

    @pytest.mark.asyncio
    @patch("packages.memory.consolidation.get_session")
    @patch("packages.memory.consolidation.memory_store")
    async def test_consolidate_skips_small_groups(self, mock_store, mock_session, consolidator, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {"memory_type": "observation", "count": 5, "oldest": "2024-01-01"},
        ]
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx

        mock_store.retrieve = AsyncMock(return_value=[_make_memory()])  # only 1, below min_group_size=3
        result = await consolidator.consolidate_old_memories(tenant_id, min_group_size=3)
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    @patch("packages.memory.consolidation.get_session")
    @patch("packages.memory.consolidation.memory_store")
    async def test_consolidate_deletes_source_memories(self, mock_store, mock_session, consolidator, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {"memory_type": "observation", "count": 3, "oldest": "2024-01-01"},
        ]
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx

        memories = [_make_memory(content=f"obs {i}") for i in range(3)]
        mock_store.retrieve = AsyncMock(return_value=memories)
        mock_store.write = AsyncMock(return_value=uuid.uuid4())
        mock_store.delete = AsyncMock(return_value=True)

        await consolidator.consolidate_old_memories(tenant_id, min_group_size=3)
        assert mock_store.delete.call_count == 3

    @pytest.mark.asyncio
    @patch("packages.memory.consolidation.get_session")
    @patch("packages.memory.consolidation.memory_store")
    async def test_consolidate_computes_avg_confidence(self, mock_store, mock_session, consolidator, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {"memory_type": "observation", "count": 3, "oldest": "2024-01-01"},
        ]
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx

        memories = [
            _make_memory(content="a", confidence=0.9),
            _make_memory(content="b", confidence=0.7),
            _make_memory(content="c", confidence=0.5),
        ]
        mock_store.retrieve = AsyncMock(return_value=memories)
        mock_store.write = AsyncMock(return_value=uuid.uuid4())
        mock_store.delete = AsyncMock(return_value=True)

        await consolidator.consolidate_old_memories(tenant_id, min_group_size=3)
        call_kwargs = mock_store.write.call_args[1]
        expected_confidence = (0.9 + 0.7 + 0.5) / 3 * 0.9
        assert call_kwargs["confidence"] == pytest.approx(expected_confidence, abs=1e-6)

    @pytest.mark.asyncio
    @patch("packages.memory.consolidation.get_session")
    @patch("packages.memory.consolidation.memory_store")
    async def test_consolidate_sets_ttl_365(self, mock_store, mock_session, consolidator, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {"memory_type": "observation", "count": 3, "oldest": "2024-01-01"},
        ]
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx

        memories = [_make_memory(content=f"obs {i}") for i in range(3)]
        mock_store.retrieve = AsyncMock(return_value=memories)
        mock_store.write = AsyncMock(return_value=uuid.uuid4())
        mock_store.delete = AsyncMock(return_value=True)

        await consolidator.consolidate_old_memories(tenant_id, min_group_size=3)
        call_kwargs = mock_store.write.call_args[1]
        assert call_kwargs["ttl_days"] == 365


# ---------------------------------------------------------------------------
# 3. get_consolidation_stats
# ---------------------------------------------------------------------------

class TestGetConsolidationStats:
    @pytest.mark.asyncio
    @patch("packages.memory.consolidation.get_session")
    async def test_returns_stats_dict(self, mock_session, consolidator, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_row = {
            "total_memories": 100,
            "summaries": 5,
            "old_memories": 30,
            "memory_types": 8,
        }
        mock_result.mappings.return_value.first.return_value = mock_row
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await consolidator.get_consolidation_stats(tenant_id)
        assert result["total_memories"] == 100
        assert result["summaries"] == 5

    @pytest.mark.asyncio
    @patch("packages.memory.consolidation.get_session")
    async def test_returns_empty_when_no_data(self, mock_session, consolidator, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        result = await consolidator.get_consolidation_stats(tenant_id)
        assert result == {}

    @pytest.mark.asyncio
    @patch("packages.memory.consolidation.get_session")
    async def test_passes_tenant_id(self, mock_session, consolidator, tenant_id):
        mock_ctx = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = {}
        mock_ctx.execute.return_value = mock_result
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        await consolidator.get_consolidation_stats(tenant_id)
        call_args = mock_ctx.execute.call_args
        params = call_args[0][1]
        assert params["tenant_id"] == tenant_id


# ---------------------------------------------------------------------------
# 4. singleton instance
# ---------------------------------------------------------------------------

class TestMemoryConsolidatorSingleton:
    def test_singleton_is_instance(self):
        assert isinstance(memory_consolidator, MemoryConsolidator)
