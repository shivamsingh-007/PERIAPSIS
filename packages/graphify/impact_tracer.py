from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from packages.graphify.knowledge_graph import KnowledgeGraph, knowledge_graph
from packages.logging.structured import get_logger

logger = get_logger("impact_tracer")


class ImpactResult(BaseModel):
    node_id: str
    impacted_nodes: list[str] = Field(default_factory=list)
    impacted_files: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    upstream_count: int = 0
    downstream_count: int = 0
    subgraph: dict[str, Any] = Field(default_factory=dict)


class ImpactTracer:
    HIGH_RISK_THRESHOLD = 20
    MEDIUM_RISK_THRESHOLD = 5

    def __init__(self, graph: KnowledgeGraph | None = None):
        self._graph = graph or knowledge_graph

    def trace_change_impact(self, node_id: str, depth: int = 2) -> ImpactResult:
        subgraph = self._graph.get_impact_subgraph(node_id, depth=depth)

        impacted_nodes = [n["id"] for n in subgraph["nodes"] if n["id"] != node_id]
        impacted_files = self._graph.files_for_concept(node_id)

        upstream = self._trace_upstream(node_id)
        downstream = self._trace_downstream(node_id)

        risk_level = self._assess_risk(len(impacted_nodes), len(upstream), len(downstream))

        return ImpactResult(
            node_id=node_id,
            impacted_nodes=impacted_nodes,
            impacted_files=impacted_files,
            risk_level=risk_level,
            upstream_count=len(upstream),
            downstream_count=len(downstream),
            subgraph=subgraph,
        )

    def _trace_upstream(self, node_id: str, depth: int = 1) -> list[str]:
        upstream = []
        visited = set()

        def _traverse(nid: str, current_depth: int):
            if current_depth > depth or nid in visited:
                return
            visited.add(nid)

            neighbors = self._graph.get_neighbors(nid)
            for n in neighbors:
                if n.id not in upstream:
                    upstream.append(n.id)
                    _traverse(n.id, current_depth + 1)

        _traverse(node_id, 0)
        return upstream

    def _trace_downstream(self, node_id: str, depth: int = 1) -> list[str]:
        downstream = []
        visited = set()

        def _traverse(nid: str, current_depth: int):
            if current_depth > depth or nid in visited:
                return
            visited.add(nid)

            neighbors = self._graph.get_neighbors(nid)
            for n in neighbors:
                if n.id not in downstream:
                    downstream.append(n.id)
                    _traverse(n.id, current_depth + 1)

        _traverse(node_id, 0)
        return downstream

    def _assess_risk(self, impacted: int, upstream: int, downstream: int) -> str:
        total = impacted + upstream + downstream
        if total > self.HIGH_RISK_THRESHOLD:
            return "high"
        elif total > self.MEDIUM_RISK_THRESHOLD:
            return "medium"
        return "low"

    def get_architectural_critique(self, node_id: str) -> dict:
        neighbors = self._graph.get_neighbors(node_id, depth=2)
        subgraph = self._graph.get_impact_subgraph(node_id, depth=2)

        high_coupling = [n.id for n in neighbors if self._is_high_coupling(n.id, node_id)]

        concerns = []
        if len(neighbors) > 10:
            concerns.append("High fan-out: node depends on many others")
        if len(subgraph["nodes"]) > 50:
            concerns.append("Large blast radius: changes affect many nodes")
        if high_coupling:
            concerns.append(f"Tight coupling with: {', '.join(high_coupling[:3])}")

        return {
            "node_id": node_id,
            "neighbor_count": len(neighbors),
            "blast_radius": len(subgraph["nodes"]),
            "high_coupling_nodes": high_coupling,
            "concerns": concerns,
            "risk_level": "high" if len(concerns) > 2 else "medium" if concerns else "low",
        }

    def _is_high_coupling(self, node_a: str, node_b: str) -> bool:
        neighbors_a = self._graph.get_neighbors(node_a)
        neighbors_b = self._graph.get_neighbors(node_b)

        shared = set(n.id for n in neighbors_a) & set(n.id for n in neighbors_b)
        return len(shared) > 3


impact_tracer = ImpactTracer()
