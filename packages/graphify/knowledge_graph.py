from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.graphify.client import GraphifyClient, GraphNode, GraphEdge, graphify_client
from packages.logging.structured import get_logger

logger = get_logger("knowledge_graph")


class GraphSnapshot(BaseModel):
    snapshot_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    node_count: int = 0
    edge_count: int = 0
    hash: str = ""


class ConceptLink(BaseModel):
    concept: str
    node_id: str
    relevance: float = 0.0
    context: str = ""


class KnowledgeGraph:
    def __init__(self, client: GraphifyClient | None = None):
        self._client = client or graphify_client
        self._snapshots: list[GraphSnapshot] = []
        self._concept_cache: dict[str, list[GraphNode]] = {}
        self._link_store: dict[str, list[ConceptLink]] = {}

    async def build(self, target_dir: str = ".", force: bool = False) -> GraphSnapshot:
        result = await self._client.build_graph(target_dir=target_dir, force=force)

        stats = self._client.get_stats()
        snapshot = GraphSnapshot(
            node_count=stats["total_nodes"],
            edge_count=stats["total_edges"],
        )
        self._snapshots.append(snapshot)

        logger.info(f"Built knowledge graph: {snapshot.node_count} nodes, {snapshot.edge_count} edges")
        return snapshot

    async def update(self, target_dir: str = ".") -> GraphSnapshot:
        await self._client.update_graph(target_dir=target_dir)

        stats = self._client.get_stats()
        snapshot = GraphSnapshot(
            node_count=stats["total_nodes"],
            edge_count=stats["total_edges"],
        )
        self._snapshots.append(snapshot)

        logger.info(f"Updated knowledge graph: {snapshot.node_count} nodes")
        return snapshot

    async def query(self, question: str, budget: int | None = None):
        return await self._client.query(question, budget=budget)

    async def find_path(self, source: str, target: str):
        return await self._client.find_path(source, target)

    async def explain(self, concept: str) -> dict:
        return await self._client.explain(concept)

    def search_concepts(self, query: str, limit: int = 10) -> list[GraphNode]:
        if query in self._concept_cache:
            return self._concept_cache[query][:limit]

        results = self._client.search_concepts(query, limit=limit)
        self._concept_cache[query] = results
        return results

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._client.get_node(node_id)

    def get_neighbors(self, node_id: str, depth: int = 1) -> list[GraphNode]:
        return self._client.get_neighbors(node_id, depth=depth)

    def files_for_concept(self, concept: str) -> list[str]:
        return self._client.files_for_concept(concept)

    def tests_for_symbol(self, symbol: str) -> list[str]:
        neighbors = self._client.get_neighbors(symbol)
        return [
            n.label for n in neighbors
            if "test" in n.type.lower() or "test" in n.label.lower()
        ]

    def docs_for_concept(self, concept: str) -> list[str]:
        neighbors = self._client.get_neighbors(concept)
        return [
            n.label for n in neighbors
            if "doc" in n.type.lower() or n.label.endswith((".md", ".rst", ".txt"))
        ]

    def link_concept(self, memory_id: str, concept: str, node_id: str, relevance: float = 1.0, context: str = "") -> None:
        if memory_id not in self._link_store:
            self._link_store[memory_id] = []

        self._link_store[memory_id].append(ConceptLink(
            concept=concept,
            node_id=node_id,
            relevance=relevance,
            context=context,
        ))

    def get_links_for_memory(self, memory_id: str) -> list[ConceptLink]:
        return self._link_store.get(memory_id, [])

    def get_links_for_concept(self, concept: str) -> list[ConceptLink]:
        results = []
        for links in self._link_store.values():
            for link in links:
                if link.concept == concept:
                    results.append(link)
        return results

    def get_impact_subgraph(self, node_id: str, depth: int = 2) -> dict:
        visited = set()
        nodes = []
        edges = []

        def _traverse(nid: str, current_depth: int):
            if current_depth > depth or nid in visited:
                return
            visited.add(nid)

            node = self._client.get_node(nid)
            if node:
                nodes.append(node.model_dump())

            neighbors = self._client.get_neighbors(nid)
            for neighbor in neighbors:
                if neighbor.id not in visited:
                    edges.append({"source": nid, "target": neighbor.id})
                    _traverse(neighbor.id, current_depth + 1)

        _traverse(node_id, 0)
        return {"nodes": nodes, "edges": edges, "root": node_id}

    def get_architecture_overview(self) -> dict:
        stats = self._client.get_stats()
        graph = self._client.load_graph()

        god_nodes = []
        node_connections: dict[str, int] = {}

        for edge in graph.get("edges", []):
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            node_connections[src] = node_connections.get(src, 0) + 1
            node_connections[tgt] = node_connections.get(tgt, 0) + 1

        sorted_nodes = sorted(node_connections.items(), key=lambda x: x[1], reverse=True)
        god_nodes = [{"id": n[0], "connections": n[1]} for n in sorted_nodes[:10]]

        return {
            "stats": stats,
            "god_nodes": god_nodes,
            "snapshot_count": len(self._snapshots),
        }

    def get_stats(self) -> dict:
        stats = self._client.get_stats()
        stats["concept_cache_size"] = len(self._concept_cache)
        stats["link_store_size"] = len(self._link_store)
        stats["snapshot_count"] = len(self._snapshots)
        return stats


knowledge_graph = KnowledgeGraph()
