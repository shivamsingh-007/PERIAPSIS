from __future__ import annotations

import json
import os
import tempfile

import pytest

from packages.graphify.client import (
    GraphEdge,
    GraphNode,
    GraphPathResult,
    GraphQueryResult,
    GraphifyClient,
)


@pytest.fixture
def client():
    return GraphifyClient()


@pytest.fixture
def client_with_graph():
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_data = {
            "nodes": [
                {"id": "n1", "label": "auth.py", "type": "file", "source": "auth.py"},
                {"id": "n2", "label": "login()", "type": "function", "source": "auth.py"},
                {"id": "n3", "label": "user.py", "type": "file", "source": "user.py"},
            ],
            "edges": [
                {"source": "n1", "target": "n2", "label": "contains"},
                {"source": "n2", "target": "n3", "label": "calls"},
            ],
        }
        graph_path = os.path.join(tmpdir, "graph.json")
        with open(graph_path, "w") as f:
            json.dump(graph_data, f)

        c = GraphifyClient(graph_dir=tmpdir)
        yield c


class TestGraphNode:
    def test_create_node(self):
        node = GraphNode(id="n1", label="test", type="file")
        assert node.id == "n1"
        assert node.type == "file"

    def test_node_defaults(self):
        node = GraphNode(id="n1", label="test")
        assert node.type == "default"
        assert node.properties == {}
        assert node.confidence == "EXTRACTED"


class TestGraphEdge:
    def test_create_edge(self):
        edge = GraphEdge(source="n1", target="n2", label="contains")
        assert edge.source == "n1"
        assert edge.target == "n2"

    def test_edge_defaults(self):
        edge = GraphEdge(source="n1", target="n2")
        assert edge.label == ""
        assert edge.weight == 1.0


class TestGraphQueryResult:
    def test_create_result(self):
        result = GraphQueryResult(query="test", node_count=5)
        assert result.query == "test"
        assert result.node_count == 5

    def test_result_defaults(self):
        result = GraphQueryResult()
        assert result.nodes == []
        assert result.edges == []


class TestGraphPathResult:
    def test_create_result(self):
        result = GraphPathResult(path=["a", "b", "c"], found=True)
        assert result.path == ["a", "b", "c"]
        assert result.found is True

    def test_result_defaults(self):
        result = GraphPathResult()
        assert result.path == []
        assert result.found is False


class TestGraphifyClient:
    def test_init(self, client):
        assert client is not None
        assert client.graph_dir is not None

    def test_load_graph_empty(self, client):
        graph = client.load_graph()
        assert "nodes" in graph
        assert "edges" in graph

    def test_load_graph_from_file(self, client_with_graph):
        graph = client_with_graph.load_graph()
        assert len(graph["nodes"]) == 3
        assert len(graph["edges"]) == 2

    def test_get_node(self, client_with_graph):
        node = client_with_graph.get_node("n1")
        assert node is not None
        assert node.label == "auth.py"

    def test_get_node_not_found(self, client_with_graph):
        result = client_with_graph.get_node("nonexistent")
        assert result is None

    def test_get_neighbors(self, client_with_graph):
        neighbors = client_with_graph.get_neighbors("n2")
        assert len(neighbors) == 2
        labels = [n.label for n in neighbors]
        assert "auth.py" in labels
        assert "user.py" in labels

    def test_get_neighbors_empty(self, client_with_graph):
        neighbors = client_with_graph.get_neighbors("nonexistent")
        assert len(neighbors) == 0

    def test_search_concepts(self, client_with_graph):
        results = client_with_graph.search_concepts("auth")
        assert len(results) == 1
        assert results[0].label == "auth.py"

    def test_search_concepts_no_match(self, client_with_graph):
        results = client_with_graph.search_concepts("nonexistent")
        assert len(results) == 0

    def test_files_for_concept(self, client_with_graph):
        files = client_with_graph.files_for_concept("auth")
        assert "auth.py" in files

    def test_get_stats(self, client_with_graph):
        stats = client_with_graph.get_stats()
        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 2
        assert stats["graph_exists"] is True

    def test_parse_query_output(self, client):
        output = "Node: auth.py\nNode: login()"
        result = client._parse_query_output(output, "test")
        assert result.node_count == 2

    def test_parse_path_output(self, client):
        output = "auth.py -> login() -> user.py"
        result = client._parse_path_output(output)
        assert result.found is True
        assert len(result.path) == 3

    def test_parse_path_output_not_found(self, client):
        output = "No path found"
        result = client._parse_path_output(output)
        assert result.found is False

    def test_graph_caching(self, client_with_graph):
        g1 = client_with_graph.load_graph()
        g2 = client_with_graph.load_graph()
        assert g1 is g2
