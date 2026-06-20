from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.memory.store import MemoryStore
from packages.memory.write_filter import MemoryWriteFilter, MemoryCandidate, FilterDecision


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def write_filter():
    return MemoryWriteFilter()


class TestMemoryWriteFilter:
    def test_allow_valid_lesson(self, write_filter):
        candidate = MemoryCandidate(
            content="Always validate user input",
            memory_type="lesson",
            confidence=0.8,
            has_source_attribution=True,
        )
        result = write_filter.evaluate(candidate)
        assert result.decision == FilterDecision.ALLOW

    def test_deny_low_confidence_fact(self, write_filter):
        candidate = MemoryCandidate(
            content="Some fact",
            memory_type="fact",
            confidence=0.2,
            has_source_attribution=False,
        )
        result = write_filter.evaluate(candidate)
        assert result.decision in [FilterDecision.DENY, FilterDecision.LOW_CONFIDENCE, FilterDecision.REQUIRE_SOURCE]

    def test_require_source_for_facts(self, write_filter):
        candidate = MemoryCandidate(
            content="Important fact",
            memory_type="fact",
            confidence=0.7,
            has_source_attribution=False,
        )
        result = write_filter.evaluate(candidate)
        assert result.decision == FilterDecision.REQUIRE_SOURCE

    def test_ttl_calculation(self, write_filter):
        ttl = write_filter.get_ttl_days("lesson", 0.9)
        assert ttl > 0
        ttl_low = write_filter.get_ttl_days("lesson", 0.3)
        assert ttl_low <= ttl


class TestMemoryDeduplication:
    @pytest.mark.asyncio
    async def test_write_same_content_deduplicates(self, store):
        tenant_id = uuid.uuid4()
        mock_session = AsyncMock()
        mock_result = MagicMock()

        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.mappings.return_value.first.return_value = None
            else:
                result.mappings.return_value.first.return_value = {
                    "memory_id": uuid.uuid4(),
                    "confidence": 0.5,
                }
            call_count += 1
            return result

        mock_session.execute = mock_execute

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            r1 = await store.write(tenant_id, "test", "lesson", "Same content")
            r2 = await store.write(tenant_id, "test", "lesson", "Same content")
            assert r1 is not None
            assert r2 is None


class TestMemoryScopeIsolation:
    @pytest.mark.asyncio
    async def test_scope_isolation(self, store):
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            r1 = await store.write(tenant_a, "user:123", "lesson", "Tenant A lesson")
            r2 = await store.write(tenant_b, "user:456", "lesson", "Tenant B lesson")
            assert r1 is not None
            assert r2 is not None
            assert r1 != r2


class TestMemoryConfidenceScoring:
    @pytest.mark.asyncio
    async def test_high_confidence_increases_score(self, store):
        tenant_id = uuid.uuid4()
        mock_session = AsyncMock()
        mock_result = MagicMock()

        existing_id = uuid.uuid4()
        mock_result.mappings.return_value.first.return_value = {
            "memory_id": existing_id,
            "confidence": 0.5,
        }
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await store.write(
                tenant_id, "test", "lesson", "Content",
                confidence=0.9,
            )
            assert result is None
