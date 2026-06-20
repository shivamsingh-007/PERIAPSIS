from __future__ import annotations
"""Tests for packages.memory.conflict - MemoryConflictResolver (in-memory strategies)."""

import uuid

import pytest

from packages.memory.conflict import (
    ConflictResult,
    ConflictStrategy,
    MemoryConflictResolver,
)


class TestMemoryConflictResolverLogic:
    """Test conflict resolution logic without DB."""

    def setup_method(self):
        self.resolver = MemoryConflictResolver(default_strategy=ConflictStrategy.HIGHEST_CONFIDENCE)

    def test_highest_confidence_keeps_existing(self):
        existing = {"confidence": 0.8, "content": "existing"}
        result = self.resolver._resolve_highest_confidence(
            existing, uuid.uuid4(), new_confidence=0.5, new_content="new"
        )
        assert result.kept_memory_id is not None
        assert result.removed_memory_id is None

    def test_highest_confidence_replaces_existing(self):
        existing = {"confidence": 0.5, "content": "existing"}
        result = self.resolver._resolve_highest_confidence(
            existing, uuid.uuid4(), new_confidence=0.9, new_content="new"
        )
        assert result.kept_memory_id is None
        assert result.removed_memory_id is not None

    def test_most_recent_replaces(self):
        existing = {"confidence": 0.8, "content": "old"}
        result = self.resolver._resolve_most_recent(
            existing, uuid.uuid4(), new_content="new", new_confidence=0.9
        )
        assert result.strategy_used == ConflictStrategy.MOST_RECENT
        assert result.removed_memory_id is not None

    def test_keep_both_no_removal(self):
        result = ConflictResult(strategy_used=ConflictStrategy.KEEP_BOTH)
        assert result.needs_human_review is False

    def test_human_decides(self):
        result = ConflictResult(
            strategy_used=ConflictStrategy.HUMAN_DECIDES,
            needs_human_review=True,
        )
        assert result.needs_human_review is True

    def test_default_strategy(self):
        assert self.resolver.default_strategy == ConflictStrategy.HIGHEST_CONFIDENCE

    def test_conflict_strategy_enum(self):
        assert len(list(ConflictStrategy)) == 5
