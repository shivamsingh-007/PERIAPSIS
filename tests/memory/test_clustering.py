from __future__ import annotations
"""Tests for packages.memory.clustering - ReflectionCluster."""

import uuid

import numpy as np
import pytest

from packages.memory.clustering import Cluster, MemoryPoint, ReflectionCluster


class TestReflectionCluster:
    def setup_method(self):
        self.clusterer = ReflectionCluster(n_clusters=3, max_iterations=50)

    def test_add_point(self):
        point = MemoryPoint(content="test", embedding=[1.0, 0.0, 0.0])
        self.clusterer.add_point(point)
        assert len(self.clusterer._points) == 1

    def test_add_points(self):
        points = [
            MemoryPoint(content=f"test{i}", embedding=[float(i), 0.0, 0.0])
            for i in range(10)
        ]
        self.clusterer.add_points(points)
        assert len(self.clusterer._points) == 10

    def test_cluster_not_enough_points(self):
        for i in range(2):
            self.clusterer.add_point(
                MemoryPoint(content=f"p{i}", embedding=[float(i), 0.0])
            )
        clusters = self.clusterer.cluster()
        assert len(clusters) == 0

    def test_cluster_with_enough_points(self):
        np.random.seed(42)
        for i in range(20):
            embedding = [float(np.random.random()) for _ in range(3)]
            self.clusterer.add_point(
                MemoryPoint(content=f"p{i}", embedding=embedding)
            )
        clusters = self.clusterer.cluster()
        assert len(clusters) > 0

    def test_cluster_labels(self):
        np.random.seed(42)
        for i in range(20):
            self.clusterer.add_point(
                MemoryPoint(
                    content=f"p{i}",
                    embedding=[float(np.random.random()) for _ in range(3)],
                    tags=["tag_a"] if i < 10 else ["tag_b"],
                )
            )
        clusters = self.clusterer.cluster()
        for c in clusters:
            assert c.label != ""

    def test_find_nearest_cluster(self):
        np.random.seed(42)
        for i in range(20):
            self.clusterer.add_point(
                MemoryPoint(
                    content=f"p{i}",
                    embedding=[float(np.random.random()) for _ in range(3)],
                )
            )
        self.clusterer.cluster()
        nearest = self.clusterer.find_nearest_cluster([0.5, 0.5, 0.5])
        assert nearest is not None

    def test_find_nearest_empty(self):
        assert self.clusterer.find_nearest_cluster([1.0, 2.0]) is None

    def test_get_summary(self):
        np.random.seed(42)
        for i in range(20):
            self.clusterer.add_point(
                MemoryPoint(
                    content=f"p{i}",
                    embedding=[float(np.random.random()) for _ in range(3)],
                )
            )
        self.clusterer.cluster()
        summary = self.clusterer.get_summary()
        assert summary["total_points"] == 20
        assert summary["total_clusters"] > 0

    def test_get_cluster(self):
        np.random.seed(42)
        for i in range(20):
            self.clusterer.add_point(
                MemoryPoint(
                    content=f"p{i}",
                    embedding=[float(np.random.random()) for _ in range(3)],
                )
            )
        clusters = self.clusterer.cluster()
        if clusters:
            cid = clusters[0].cluster_id
            found = self.clusterer.get_cluster(cid)
            assert found is not None

    def test_get_cluster_not_found(self):
        assert self.clusterer.get_cluster(uuid.uuid4()) is None
