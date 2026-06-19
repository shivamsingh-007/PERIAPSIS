from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from packages.graphify.knowledge_graph import KnowledgeGraph, knowledge_graph
from packages.logging.structured import get_logger

logger = get_logger("context_assembler")


class ContextChunk(BaseModel):
    source: str
    content: str
    relevance: float = 0.0
    node_type: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssembledContext(BaseModel):
    goal: str
    chunks: list[ContextChunk] = Field(default_factory=list)
    total_tokens_estimate: int = 0
    sources_consulted: list[str] = Field(default_factory=list)
    graph_queries: int = 0


class ContextAssembler:
    CHARS_PER_TOKEN = 4

    def __init__(self, graph: KnowledgeGraph | None = None, max_tokens: int = 8000):
        self._graph = graph or knowledge_graph
        self.max_tokens = max_tokens
        self._query_count = 0

    async def assemble_for_planning(self, goal: str) -> AssembledContext:
        self._query_count = 0
        chunks = []

        concept_results = await self._graph.query(f"what modules relate to: {goal}")
        self._query_count += 1
        for node in concept_results.nodes:
            chunks.append(ContextChunk(
                source=f"concept:{node.label}",
                content=f"Module: {node.label} (type: {node.type})",
                relevance=0.8,
                node_type=node.type,
            ))

        files = self._graph.files_for_concept(goal)
        for f in files[:10]:
            chunks.append(ContextChunk(
                source=f"file:{f}",
                content=f"Relevant file: {f}",
                relevance=0.7,
                node_type="file",
            ))

        tests = self._graph.tests_for_symbol(goal)
        for t in tests[:5]:
            chunks.append(ContextChunk(
                source=f"test:{t}",
                content=f"Related test: {t}",
                relevance=0.6,
                node_type="test",
            ))

        docs = self._graph.docs_for_concept(goal)
        for d in docs[:5]:
            chunks.append(ContextChunk(
                source=f"doc:{d}",
                content=f"Related doc: {d}",
                relevance=0.5,
                node_type="doc",
            ))

        chunks = self._truncate_to_budget(chunks)

        return AssembledContext(
            goal=goal,
            chunks=chunks,
            total_tokens_estimate=sum(len(c.content) for c in chunks) // self.CHARS_PER_TOKEN,
            sources_consulted=list(set(c.source.split(":")[0] for c in chunks)),
            graph_queries=self._query_count,
        )

    async def assemble_for_editing(self, file_path: str) -> AssembledContext:
        self._query_count = 0
        chunks = []

        neighbors = self._graph.get_neighbors(file_path, depth=1)
        for n in neighbors:
            chunks.append(ContextChunk(
                source=f"neighbor:{n.label}",
                content=f"Related: {n.label} (type: {n.type})",
                relevance=0.9,
                node_type=n.type,
            ))
            self._query_count += 1

        node = self._graph.get_node(file_path)
        if node:
            chunks.append(ContextChunk(
                source=f"self:{file_path}",
                content=f"Current file: {node.label}",
                relevance=1.0,
                node_type=node.type,
            ))

        chunks = self._truncate_to_budget(chunks)

        return AssembledContext(
            goal=f"Edit {file_path}",
            chunks=chunks,
            total_tokens_estimate=sum(len(c.content) for c in chunks) // self.CHARS_PER_TOKEN,
            sources_consulted=["graph_neighbors", "graph_node"],
            graph_queries=self._query_count,
        )

    async def assemble_for_reflection(self, failing_test: str) -> AssembledContext:
        self._query_count = 0
        chunks = []

        path_result = await self._graph.find_path(failing_test, "")
        self._query_count += 1

        if path_result.found:
            for step in path_result.path:
                chunks.append(ContextChunk(
                    source=f"path:{step}",
                    content=f"Path step: {step}",
                    relevance=0.7,
                    node_type="path",
                ))

        neighbors = self._graph.get_neighbors(failing_test, depth=2)
        for n in neighbors:
            chunks.append(ContextChunk(
                source=f"impact:{n.label}",
                content=f"Impacted: {n.label} (type: {n.type})",
                relevance=0.6,
                node_type=n.type,
            ))
            self._query_count += 1

        chunks = self._truncate_to_budget(chunks)

        return AssembledContext(
            goal=f"Reflect on failure: {failing_test}",
            chunks=chunks,
            total_tokens_estimate=sum(len(c.content) for c in chunks) // self.CHARS_PER_TOKEN,
            sources_consulted=["graph_path", "graph_neighbors"],
            graph_queries=self._query_count,
        )

    def _truncate_to_budget(self, chunks: list[ContextChunk]) -> list[ContextChunk]:
        total = 0
        result = []
        for chunk in sorted(chunks, key=lambda c: c.relevance, reverse=True):
            chunk_tokens = len(chunk.content) // self.CHARS_PER_TOKEN
            if total + chunk_tokens > self.max_tokens:
                break
            result.append(chunk)
            total += chunk_tokens
        return result

    def get_stats(self) -> dict:
        return {
            "max_tokens": self.max_tokens,
            "chars_per_token": self.CHARS_PER_TOKEN,
            "last_query_count": self._query_count,
        }


context_assembler = ContextAssembler()
