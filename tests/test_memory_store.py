from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.memory.store import MemoryStore


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


class TestMemoryStoreWrite:
    @pytest.mark.asyncio
    async def test_write_creates_memory(self, store, tenant_id):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await store.write(
                tenant_id=tenant_id,
                scope="run",
                memory_type="lesson",
                content="Test lesson content",
            )
            assert result is not None
            assert isinstance(result, uuid.UUID)

    @pytest.mark.asyncio
    async def test_write_deduplicates_by_hash(self, store, tenant_id):
        mock_session = AsyncMock()
        existing_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = {"memory_id": existing_id, "confidence": 0.5}
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await store.write(
                tenant_id=tenant_id,
                scope="run",
                memory_type="lesson",
                content="Duplicate content",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_write_with_graph_metadata(self, store, tenant_id):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await store.write(
                tenant_id=tenant_id,
                scope="run",
                memory_type="lesson",
                content="Graph-linked content",
                graph_node_id="node_123",
                graph_concepts=["auth", "security"],
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_write_with_source_ref(self, store, tenant_id):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await store.write(
                tenant_id=tenant_id,
                scope="run",
                memory_type="lesson",
                content="Sourced content",
                source_ref={"run_id": "run_123", "step": 3},
                confidence=0.9,
            )
            assert result is not None


class TestMemoryStoreHash:
    def test_hash_content_deterministic(self, store):
        h1 = store._hash_content("test content")
        h2 = store._hash_content("test content")
        assert h1 == h2

    def test_hash_content_unique(self, store):
        h1 = store._hash_content("content A")
        h2 = store._hash_content("content B")
        assert h1 != h2

    def test_hash_content_empty(self, store):
        h = store._hash_content("")
        assert isinstance(h, str)
        assert len(h) == 64


class TestMemoryStoreGetByGraphConcept:
    @pytest.mark.asyncio
    async def test_get_by_graph_concept(self, store, tenant_id):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {"memory_id": uuid.uuid4(), "content": "auth lesson"}
        ]
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await store.get_by_graph_concept(tenant_id, "auth")
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_by_graph_concept_empty(self, store, tenant_id):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await store.get_by_graph_concept(tenant_id, "nonexistent")
            assert len(results) == 0


class TestMemoryStoreGetByGraphNode:
    @pytest.mark.asyncio
    async def test_get_by_graph_node_found(self, store, tenant_id):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = {
            "memory_id": uuid.uuid4(),
            "content": "linked content",
        }
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await store.get_by_graph_node(tenant_id, "node_123")
            assert result is not None
            assert result["content"] == "linked content"

    @pytest.mark.asyncio
    async def test_get_by_graph_node_not_found(self, store, tenant_id):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await store.get_by_graph_node(tenant_id, "nonexistent")
            assert result is None


class TestMemoryStoreDelete:
    @pytest.mark.asyncio
    async def test_delete_success(self, store, tenant_id):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await store.delete(tenant_id, uuid.uuid4())
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, store, tenant_id):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await store.delete(tenant_id, uuid.uuid4())
            assert result is False


class TestMemoryStoreExpire:
    @pytest.mark.asyncio
    async def test_expire_old(self, store, tenant_id):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute.return_value = mock_result

        with patch("packages.memory.store.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            count = await store.expire_old(tenant_id)
            assert count == 5
