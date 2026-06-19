from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("graphify_client")


class GraphNode(BaseModel):
    id: str
    label: str
    type: str = "default"
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: str = "EXTRACTED"


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str = ""
    weight: float = 1.0
    confidence: str = "EXTRACTED"
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphQueryResult(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    query: str = ""
    node_count: int = 0
    edge_count: int = 0


class GraphPathResult(BaseModel):
    path: list[str] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    found: bool = False


class GraphifyClient:
    def __init__(self, graph_dir: str | None = None, graphify_path: str | None = None):
        self.graph_dir = graph_dir or os.path.join(os.getcwd(), "graphify-out")
        self.graphify_path = graphify_path or self._find_graphify()
        self._graph_json_path = os.path.join(self.graph_dir, "graph.json")
        self._cached_graph: dict | None = None

    def _find_graphify(self) -> str:
        found = shutil.which("graphify")
        if found:
            return found
        uv_path = shutil.which("uv")
        if uv_path:
            return uv_path
        raise FileNotFoundError("graphify CLI not found. Install with: uv tool install graphifyy")

    async def build_graph(
        self,
        target_dir: str = ".",
        force: bool = False,
        mode: str = "default",
    ) -> dict:
        cmd = [self.graphify_path, target_dir]
        if force:
            cmd.append("--force")
        if mode == "deep":
            cmd.extend(["--mode", "deep"])

        logger.info(f"Building graph for {target_dir}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Graphify build failed: {stderr.decode()}")

        self._cached_graph = None
        return {"status": "built", "target": target_dir}

    async def update_graph(self, target_dir: str = ".") -> dict:
        cmd = [self.graphify_path, target_dir, "--update"]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Graphify update failed: {stderr.decode()}")

        self._cached_graph = None
        return {"status": "updated", "target": target_dir}

    async def query(self, question: str, budget: int | None = None) -> GraphQueryResult:
        cmd = [self.graphify_path, "query", question]
        if budget:
            cmd.extend(["--budget", str(budget)])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"Graphify query failed: {stderr.decode()}")
            return GraphQueryResult(query=question)

        output = stdout.decode()
        return self._parse_query_output(output, question)

    async def find_path(self, source: str, target: str) -> GraphPathResult:
        cmd = [self.graphify_path, "path", source, target]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return GraphPathResult(found=False)

        output = stdout.decode()
        return self._parse_path_output(output)

    async def explain(self, concept: str) -> dict:
        cmd = [self.graphify_path, "explain", concept]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return {"concept": concept, "error": stderr.decode()}

        return {"concept": concept, "explanation": stdout.decode()}

    def load_graph(self) -> dict:
        if self._cached_graph:
            return self._cached_graph

        if not os.path.exists(self._graph_json_path):
            return {"nodes": [], "edges": []}

        with open(self._graph_json_path) as f:
            self._cached_graph = json.load(f)

        return self._cached_graph

    def get_node(self, node_id: str) -> GraphNode | None:
        graph = self.load_graph()
        for node in graph.get("nodes", []):
            if node.get("id") == node_id or node.get("label") == node_id:
                return GraphNode(
                    id=node.get("id", ""),
                    label=node.get("label", ""),
                    type=node.get("type", "default"),
                    properties={k: v for k, v in node.items() if k not in ("id", "label", "type")},
                )
        return None

    def get_neighbors(self, node_id: str, depth: int = 1) -> list[GraphNode]:
        graph = self.load_graph()
        neighbors = set()
        node_map = {n.get("id"): n for n in graph.get("nodes", [])}

        for edge in graph.get("edges", []):
            src = edge.get("source", "")
            tgt = edge.get("target", "")

            if src == node_id:
                neighbors.add(tgt)
            elif tgt == node_id:
                neighbors.add(src)

        return [
            GraphNode(
                id=n.get("id", ""),
                label=n.get("label", ""),
                type=n.get("type", "default"),
                properties={k: v for k, v in n.items() if k not in ("id", "label", "type")},
            )
            for n_id in neighbors
            if (n := node_map.get(n_id))
        ]

    def search_concepts(self, query: str, limit: int = 10) -> list[GraphNode]:
        graph = self.load_graph()
        query_lower = query.lower()
        results = []

        for node in graph.get("nodes", []):
            label = node.get("label", "").lower()
            node_type = node.get("type", "").lower()

            if query_lower in label or query_lower in node_type:
                results.append(GraphNode(
                    id=node.get("id", ""),
                    label=node.get("label", ""),
                    type=node.get("type", "default"),
                    properties={k: v for k, v in node.items() if k not in ("id", "label", "type")},
                ))

        return results[:limit]

    def files_for_concept(self, concept: str) -> list[str]:
        graph = self.load_graph()
        files = set()

        for node in graph.get("nodes", []):
            if concept.lower() in node.get("label", "").lower():
                source = node.get("source", node.get("file", ""))
                if source:
                    files.add(source)

        return list(files)

    def get_stats(self) -> dict:
        graph = self.load_graph()
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        node_types = {}
        for n in nodes:
            t = n.get("type", "unknown")
            node_types[t] = node_types.get(t, 0) + 1

        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": node_types,
            "graph_exists": os.path.exists(self._graph_json_path),
            "graph_dir": self.graph_dir,
        }

    def _parse_query_output(self, output: str, question: str) -> GraphQueryResult:
        try:
            lines = output.strip().split("\n")
            nodes = []
            edges = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("Node:") or line.startswith("- "):
                    parts = line.lstrip("- ").split(":", 1)
                    if len(parts) == 2:
                        nodes.append(GraphNode(
                            id=parts[0].strip(),
                            label=parts[1].strip() if len(parts) > 1 else parts[0].strip(),
                        ))

            return GraphQueryResult(
                nodes=nodes,
                edges=edges,
                query=question,
                node_count=len(nodes),
                edge_count=len(edges),
            )
        except Exception as e:
            logger.error(f"Failed to parse query output: {e}")
            return GraphQueryResult(query=question)

    def _parse_path_output(self, output: str) -> GraphPathResult:
        try:
            lines = output.strip().split("\n")
            path = []

            for line in lines:
                line = line.strip()
                if line and not line.startswith("No path"):
                    parts = line.split(" -> ")
                    if len(parts) > 1:
                        path = [p.strip() for p in parts]

            return GraphPathResult(
                path=path,
                found=len(path) > 0,
            )
        except Exception:
            return GraphPathResult(found=False)


graphify_client = GraphifyClient()
