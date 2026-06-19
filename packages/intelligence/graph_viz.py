from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("graph_viz")


class GraphNode(BaseModel):
    node_id: str
    label: str
    type: str = "default"
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str = ""
    weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphData(BaseModel):
    graph_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GraphVisualizer:
    def __init__(self):
        self._graphs: dict[str, GraphData] = {}

    def create_graph(self, name: str) -> GraphData:
        graph = GraphData(name=name)
        self._graphs[name] = graph
        return graph

    def add_node(self, graph_name: str, node: GraphNode) -> None:
        graph = self._graphs.get(graph_name)
        if graph:
            graph.nodes.append(node)

    def add_edge(self, graph_name: str, edge: GraphEdge) -> None:
        graph = self._graphs.get(graph_name)
        if graph:
            graph.edges.append(edge)

    def to_d3_format(self, graph_name: str) -> dict:
        graph = self._graphs.get(graph_name)
        if not graph:
            return {}

        return {
            "nodes": [{"id": n.node_id, "label": n.label, "type": n.type, **n.properties} for n in graph.nodes],
            "links": [{"source": e.source, "target": e.target, "label": e.label, "weight": e.weight} for e in graph.edges],
        }

    def to_mermaid(self, graph_name: str) -> str:
        graph = self._graphs.get(graph_name)
        if not graph:
            return ""

        lines = ["graph TD"]
        for node in graph.nodes:
            lines.append(f"    {node.node_id}[{node.label}]")
        for edge in graph.edges:
            label = f"|{edge.label}|" if edge.label else ""
            lines.append(f"    {edge.source} -->{label} {edge.target}")

        return "\n".join(lines)

    def to_json(self, graph_name: str) -> str:
        data = self.to_d3_format(graph_name)
        return json.dumps(data, indent=2)

    def get_graph(self, graph_name: str) -> GraphData | None:
        return self._graphs.get(graph_name)

    def list_graphs(self) -> list[str]:
        return list(self._graphs.keys())


graph_visualizer = GraphVisualizer()
