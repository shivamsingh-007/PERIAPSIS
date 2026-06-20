from __future__ import annotations

import pytest

from packages.graphify.graph_router import (
    AgentSpecialization,
    GraphRouter,
    RoutingDecision,
    DEFAULT_SPECIALIZATIONS,
)


class TestAgentSpecialization:
    def test_create_spec(self):
        spec = AgentSpecialization(
            name="security",
            concepts=["auth", "security"],
            file_patterns=["auth/"],
        )
        assert spec.name == "security"
        assert len(spec.concepts) == 2

    def test_spec_defaults(self):
        spec = AgentSpecialization(name="test")
        assert spec.concepts == []
        assert spec.file_patterns == []
        assert spec.node_types == []


class TestRoutingDecision:
    def test_create_decision(self):
        decision = RoutingDecision(
            target_agent="security",
            reason="matched auth concept",
            confidence=0.8,
        )
        assert decision.target_agent == "security"
        assert decision.confidence == 0.8

    def test_decision_defaults(self):
        decision = RoutingDecision(target_agent="general", reason="fallback")
        assert decision.confidence == 0.0
        assert decision.matched_concepts == []


class TestGraphRouter:
    def test_init(self):
        router = GraphRouter()
        assert router is not None

    def test_default_specializations(self):
        assert len(DEFAULT_SPECIALIZATIONS) == 8
        names = [s.name for s in DEFAULT_SPECIALIZATIONS]
        assert "security" in names
        assert "backend" in names
        assert "frontend" in names
        assert "governance" in names

    def test_route_task_security(self):
        router = GraphRouter()
        decision = router.route_task("Fix security vulnerability in auth module")
        assert decision.target_agent == "security"
        assert decision.confidence > 0

    def test_route_task_backend(self):
        router = GraphRouter()
        decision = router.route_task("Add new API endpoint for users")
        assert decision.target_agent == "backend"

    def test_route_task_frontend(self):
        router = GraphRouter()
        decision = router.route_task("Create UI component for login form")
        assert decision.target_agent == "frontend"

    def test_route_task_governance(self):
        router = GraphRouter()
        decision = router.route_task("Update compliance policy for GDPR")
        assert decision.target_agent == "governance"

    def test_route_task_memory(self):
        router = GraphRouter()
        decision = router.route_task("Consolidate memory lessons from reflection")
        assert decision.target_agent == "memory"

    def test_route_task_testing(self):
        router = GraphRouter()
        decision = router.route_task("Write unit tests for harness scoring")
        assert decision.target_agent == "testing"

    def route_task_infrastructure(self):
        router = GraphRouter()
        decision = router.route_task("Deploy Docker container to staging")
        assert decision.target_agent == "infrastructure"

    def test_route_task_fallback(self):
        router = GraphRouter()
        decision = router.route_task("do something vague")
        assert decision.target_agent is not None

    def test_route_file_edit(self):
        router = GraphRouter()
        decision = router.route_file_edit("src/routes/auth.py")
        assert decision.target_agent is not None

    def test_route_file_edit_frontend(self):
        router = GraphRouter()
        decision = router.route_file_edit("app/components/Button.tsx")
        assert decision.target_agent == "frontend"

    def test_get_available_agents(self):
        router = GraphRouter()
        agents = router.get_available_agents()
        assert len(agents) == 8
        assert all("name" in a and "concepts" in a for a in agents)

    def test_add_specialization(self):
        router = GraphRouter()
        custom = AgentSpecialization(name="custom", concepts=["custom"])
        router.add_specialization(custom)
        agents = router.get_available_agents()
        assert any(a["name"] == "custom" for a in agents)

    def test_get_stats(self):
        router = GraphRouter()
        stats = router.get_stats()
        assert "specialization_count" in stats
        assert stats["specialization_count"] == 8

    def test_route_empty_task(self):
        router = GraphRouter()
        decision = router.route_task("")
        assert decision.target_agent == "general"
