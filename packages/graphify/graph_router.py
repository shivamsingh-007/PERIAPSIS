from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from packages.graphify.knowledge_graph import KnowledgeGraph, knowledge_graph
from packages.logging.structured import get_logger

logger = get_logger("graph_router")


class RoutingDecision(BaseModel):
    target_agent: str
    reason: str
    confidence: float = 0.0
    matched_concepts: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentSpecialization(BaseModel):
    name: str
    concepts: list[str] = Field(default_factory=list)
    file_patterns: list[str] = Field(default_factory=list)
    node_types: list[str] = Field(default_factory=list)


DEFAULT_SPECIALIZATIONS = [
    AgentSpecialization(
        name="security",
        concepts=["auth", "security", "pii", "injection", "encryption", "token", "secret"],
        node_types=["security"],
    ),
    AgentSpecialization(
        name="backend",
        concepts=["api", "endpoint", "route", "database", "model", "schema", "migration"],
        file_patterns=["routes/", "models/", "schemas/", "migrations/"],
    ),
    AgentSpecialization(
        name="frontend",
        concepts=["ui", "component", "page", "layout", "css", "style", "form"],
        file_patterns=["components/", "pages/", "app/"],
    ),
    AgentSpecialization(
        name="governance",
        concepts=["policy", "compliance", "audit", "rule", "governance", "approval"],
        node_types=["governance", "policy"],
    ),
    AgentSpecialization(
        name="memory",
        concepts=["memory", "lesson", "reflection", "consolidation", "embedding"],
        node_types=["memory"],
    ),
    AgentSpecialization(
        name="fleet",
        concepts=["swarm", "worker", "fleet", "orchestration", "dispatch"],
        node_types=["fleet"],
    ),
    AgentSpecialization(
        name="testing",
        concepts=["test", "eval", "harness", "scoring", "assertion"],
        file_patterns=["tests/", "test_"],
    ),
    AgentSpecialization(
        name="infrastructure",
        concepts=["docker", "deploy", "ci", "cd", "pipeline", "monitoring", "health"],
        file_patterns=["infra/", "scripts/", ".github/"],
    ),
]


class GraphRouter:
    def __init__(
        self,
        graph: KnowledgeGraph | None = None,
        specializations: list[AgentSpecialization] | None = None,
    ):
        self._graph = graph or knowledge_graph
        self._specializations = specializations or list(DEFAULT_SPECIALIZATIONS)

    def route_task(self, task_description: str) -> RoutingDecision:
        task_lower = task_description.lower()

        best_agent = "general"
        best_score = 0.0
        matched = []

        for spec in self._specializations:
            score = 0.0
            spec_matched = []

            for concept in spec.concepts:
                if concept.lower() in task_lower:
                    score += 0.3
                    spec_matched.append(concept)

            for pattern in spec.file_patterns:
                if pattern.lower() in task_lower:
                    score += 0.2
                    spec_matched.append(pattern)

            if score > best_score:
                best_score = score
                best_agent = spec.name
                matched = spec_matched

        if best_score < 0.1:
            graph_nodes = self._graph.search_concepts(task_description, limit=5)
            if graph_nodes:
                node_types = set(n.type for n in graph_nodes)
                for spec in self._specializations:
                    if any(t in spec.node_types for t in node_types):
                        best_agent = spec.name
                        best_score = 0.4
                        matched = [n.label for n in graph_nodes[:3]]
                        break

        return RoutingDecision(
            target_agent=best_agent,
            reason=f"Matched concepts: {', '.join(matched[:3])}" if matched else "General fallback",
            confidence=min(best_score, 1.0),
            matched_concepts=matched,
        )

    def route_file_edit(self, file_path: str) -> RoutingDecision:
        file_lower = file_path.lower()

        for spec in self._specializations:
            for pattern in spec.file_patterns:
                if pattern.lower() in file_lower:
                    return RoutingDecision(
                        target_agent=spec.name,
                        reason=f"File matches pattern: {pattern}",
                        confidence=0.9,
                        matched_concepts=[pattern],
                    )

        neighbors = self._graph.get_neighbors(file_path)
        neighbor_types = set(n.type for n in neighbors)

        for spec in self._specializations:
            if any(t in spec.node_types for t in neighbor_types):
                return RoutingDecision(
                    target_agent=spec.name,
                    reason=f"Connected to {spec.name} nodes",
                    confidence=0.7,
                    matched_concepts=[n.label for n in neighbors[:3]],
                )

        return RoutingDecision(
            target_agent="general",
            reason="No specialization match",
            confidence=0.3,
        )

    def get_available_agents(self) -> list[dict]:
        return [
            {"name": spec.name, "concepts": spec.concepts}
            for spec in self._specializations
        ]

    def add_specialization(self, spec: AgentSpecialization) -> None:
        self._specializations.append(spec)

    def get_stats(self) -> dict:
        return {
            "specialization_count": len(self._specializations),
            "agents": [spec.name for spec in self._specializations],
        }


graph_router = GraphRouter()
