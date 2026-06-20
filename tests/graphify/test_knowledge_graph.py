from __future__ import annotations

import pytest

from packages.graphify.knowledge_graph import (
    ConceptLink,
    GraphSnapshot,
    KnowledgeGraph,
)


class TestGraphSnapshot:
    def test_create_snapshot(self):
        snap = GraphSnapshot(node_count=10, edge_count=5)
        assert snap.node_count == 10
        assert snap.snapshot_id is not None

    def test_snapshot_defaults(self):
        snap = GraphSnapshot()
        assert snap.node_count == 0
        assert snap.hash == ""


class TestConceptLink:
    def test_create_link(self):
        link = ConceptLink(
            concept="auth",
            node_id="n1",
            relevance=0.9,
            context="authentication module",
        )
        assert link.concept == "auth"
        assert link.relevance == 0.9

    def test_link_defaults(self):
        link = ConceptLink(concept="test", node_id="n1")
        assert link.relevance == 0.0
        assert link.context == ""


class TestKnowledgeGraph:
    def test_init(self):
        kg = KnowledgeGraph()
        assert kg is not None

    def test_search_concepts(self):
        kg = KnowledgeGraph()
        results = kg.search_concepts("test")
        assert isinstance(results, list)

    def test_get_node(self):
        kg = KnowledgeGraph()
        result = kg.get_node("nonexistent")
        assert result is None

    def test_get_neighbors(self):
        kg = KnowledgeGraph()
        result = kg.get_neighbors("nonexistent")
        assert isinstance(result, list)

    def test_files_for_concept(self):
        kg = KnowledgeGraph()
        result = kg.files_for_concept("test")
        assert isinstance(result, list)

    def test_tests_for_symbol(self):
        kg = KnowledgeGraph()
        result = kg.tests_for_symbol("test_func")
        assert isinstance(result, list)

    def test_docs_for_concept(self):
        kg = KnowledgeGraph()
        result = kg.docs_for_concept("test")
        assert isinstance(result, list)

    def test_link_concept(self):
        kg = KnowledgeGraph()
        kg.link_concept(
            memory_id="mem-1",
            concept="auth",
            node_id="n1",
            relevance=0.9,
        )
        links = kg.get_links_for_memory("mem-1")
        assert len(links) == 1
        assert links[0].concept == "auth"

    def test_get_links_for_concept(self):
        kg = KnowledgeGraph()
        kg.link_concept(memory_id="mem-1", concept="auth", node_id="n1")
        kg.link_concept(memory_id="mem-2", concept="auth", node_id="n2")
        links = kg.get_links_for_concept("auth")
        assert len(links) == 2

    def test_get_links_empty(self):
        kg = KnowledgeGraph()
        links = kg.get_links_for_memory("nonexistent")
        assert links == []

    def test_get_impact_subgraph(self):
        kg = KnowledgeGraph()
        result = kg.get_impact_subgraph("nonexistent")
        assert "nodes" in result
        assert "edges" in result
        assert result["root"] == "nonexistent"

    def test_get_architecture_overview(self):
        kg = KnowledgeGraph()
        result = kg.get_architecture_overview()
        assert "stats" in result
        assert "god_nodes" in result

    def test_get_stats(self):
        kg = KnowledgeGraph()
        stats = kg.get_stats()
        assert "total_nodes" in stats
        assert "concept_cache_size" in stats
        assert "link_store_size" in stats
        assert "snapshot_count" in stats
