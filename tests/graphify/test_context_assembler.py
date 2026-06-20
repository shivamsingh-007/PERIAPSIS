from __future__ import annotations

import pytest

from packages.graphify.context_assembler import (
    AssembledContext,
    ContextAssembler,
    ContextChunk,
)


class TestContextChunk:
    def test_create_chunk(self):
        chunk = ContextChunk(
            source="concept:auth",
            content="Authentication module",
            relevance=0.9,
        )
        assert chunk.source == "concept:auth"
        assert chunk.relevance == 0.9

    def test_chunk_defaults(self):
        chunk = ContextChunk(source="s", content="c")
        assert chunk.relevance == 0.0
        assert chunk.node_type == ""
        assert chunk.metadata == {}


class TestAssembledContext:
    def test_create_context(self):
        ctx = AssembledContext(
            goal="test goal",
            chunks=[],
            total_tokens_estimate=100,
        )
        assert ctx.goal == "test goal"
        assert ctx.total_tokens_estimate == 100

    def test_context_defaults(self):
        ctx = AssembledContext(goal="test")
        assert ctx.chunks == []
        assert ctx.sources_consulted == []
        assert ctx.graph_queries == 0


class TestContextAssembler:
    def test_init(self):
        assembler = ContextAssembler()
        assert assembler is not None
        assert assembler.max_tokens == 8000

    def test_custom_max_tokens(self):
        assembler = ContextAssembler(max_tokens=4000)
        assert assembler.max_tokens == 4000

    def test_chars_per_token(self):
        assert ContextAssembler.CHARS_PER_TOKEN == 4

    @pytest.mark.asyncio
    async def test_assemble_for_planning(self):
        assembler = ContextAssembler()
        result = await assembler.assemble_for_planning("refactor authentication")
        assert isinstance(result, AssembledContext)
        assert result.goal == "refactor authentication"

    @pytest.mark.asyncio
    async def test_assemble_for_editing(self):
        assembler = ContextAssembler()
        result = await assembler.assemble_for_editing("src/auth.py")
        assert isinstance(result, AssembledContext)
        assert "src/auth.py" in result.goal

    @pytest.mark.asyncio
    async def test_assemble_for_reflection(self):
        assembler = ContextAssembler()
        result = await assembler.assemble_for_reflection("test_auth.py")
        assert isinstance(result, AssembledContext)
        assert "test_auth.py" in result.goal

    def test_truncate_to_budget(self):
        assembler = ContextAssembler(max_tokens=100)
        chunks = [
            ContextChunk(source="a", content="x" * 500, relevance=0.9),
            ContextChunk(source="b", content="y" * 500, relevance=0.8),
            ContextChunk(source="c", content="z" * 500, relevance=0.7),
        ]
        result = assembler._truncate_to_budget(chunks)
        total_chars = sum(len(c.content) for c in result)
        assert total_chars <= 100 * 4

    def test_truncate_preserves_high_relevance(self):
        assembler = ContextAssembler(max_tokens=50)
        chunks = [
            ContextChunk(source="a", content="x" * 100, relevance=0.5),
            ContextChunk(source="b", content="y" * 100, relevance=0.9),
        ]
        result = assembler._truncate_to_budget(chunks)
        assert len(result) >= 1
        assert result[0].relevance >= 0.5

    def test_get_stats(self):
        assembler = ContextAssembler()
        stats = assembler.get_stats()
        assert "max_tokens" in stats
        assert "chars_per_token" in stats
        assert stats["max_tokens"] == 8000
