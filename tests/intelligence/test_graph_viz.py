from __future__ import annotations
"""Tests for packages.intelligence.graph_viz - GraphVisualizer."""

import json

import pytest

from packages.intelligence.graph_viz import GraphData, GraphEdge, GraphNode, GraphVisualizer


class TestGraphVisualizer:
    def setup_method(self):
        self.viz = GraphVisualizer()

    def test_create_graph(self):
        graph = self.viz.create_graph("test")
        assert graph.name == "test"
        assert graph.nodes == []
        assert graph.edges == []

    def test_add_node(self):
        self.viz.create_graph("g")
        node = GraphNode(node_id="n1", label="Node 1")
        self.viz.add_node("g", node)
        graph = self.viz.get_graph("g")
        assert len(graph.nodes) == 1

    def test_add_node_nonexistent_graph(self):
        node = GraphNode(node_id="n1", label="N1")
        # Should not raise
        self.viz.add_node("nonexistent", node)

    def test_add_edge(self):
        self.viz.create_graph("g")
        self.viz.add_node("g", GraphNode(node_id="n1", label="A"))
        self.viz.add_node("g", GraphNode(node_id="n2", label="B"))
        edge = GraphEdge(source="n1", target="n2", label="connects")
        self.viz.add_edge("g", edge)
        graph = self.viz.get_graph("g")
        assert len(graph.edges) == 1

    def test_to_d3_format(self):
        self.viz.create_graph("g")
        self.viz.add_node("g", GraphNode(node_id="n1", label="A"))
        self.viz.add_edge("g", GraphEdge(source="n1", target="n1", label="self"))
        d3 = self.viz.to_d3_format("g")
        assert len(d3["nodes"]) == 1
        assert len(d3["links"]) == 1

    def test_to_d3_nonexistent(self):
        assert self.viz.to_d3_format("nonexistent") == {}

    def test_to_mermaid(self):
        self.viz.create_graph("g")
        self.viz.add_node("g", GraphNode(node_id="n1", label="Start"))
        self.viz.add_node("g", GraphNode(node_id="n2", label="End"))
        self.viz.add_edge("g", GraphEdge(source="n1", target="n2", label="go"))
        mermaid = self.viz.to_mermaid("g")
        assert "graph TD" in mermaid
        assert "n1[Start]" in mermaid
        assert "-->|go| n2" in mermaid

    def test_to_mermaid_nonexistent(self):
        assert self.viz.to_mermaid("nonexistent") == ""

    def test_to_json(self):
        self.viz.create_graph("g")
        self.viz.add_node("g", GraphNode(node_id="n1", label="A"))
        json_str = self.viz.to_json("g")
        data = json.loads(json_str)
        assert "nodes" in data

    def test_get_graph(self):
        self.viz.create_graph("g")
        assert self.viz.get_graph("g") is not None

    def test_get_graph_nonexistent(self):
        assert self.viz.get_graph("nonexistent") is None

    def test_list_graphs(self):
        self.viz.create_graph("g1")
        self.viz.create_graph("g2")
        graphs = self.viz.list_graphs()
        assert "g1" in graphs
        assert "g2" in graphs
