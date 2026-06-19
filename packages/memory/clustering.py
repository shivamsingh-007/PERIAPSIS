from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("clustering")


class MemoryPoint(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    content: str
    embedding: list[float] = Field(default_factory=list)
    source_run_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Cluster(BaseModel):
    cluster_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    centroid: list[float] = Field(default_factory=list)
    points: list[uuid.UUID] = Field(default_factory=list)
    label: str = ""
    coherence_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReflectionCluster:
    def __init__(self, n_clusters: int = 5, max_iterations: int = 100):
        self.n_clusters = n_clusters
        self.max_iterations = max_iterations
        self._clusters: dict[uuid.UUID, Cluster] = {}
        self._points: dict[uuid.UUID, MemoryPoint] = {}

    def add_point(self, point: MemoryPoint) -> None:
        self._points[point.id] = point

    def add_points(self, points: list[MemoryPoint]) -> None:
        for p in points:
            self._points[p.id] = p

    def cluster(self) -> list[Cluster]:
        if len(self._points) < self.n_clusters:
            logger.warning("Not enough points for clustering")
            return []

        embeddings = []
        point_ids = []
        for pid, point in self._points.items():
            if point.embedding:
                embeddings.append(point.embedding)
                point_ids.append(pid)

        if len(embeddings) < self.n_clusters:
            return []

        X = np.array(embeddings)
        centroids, assignments = self._kmeans(X, self.n_clusters)

        self._clusters.clear()
        for k in range(self.n_clusters):
            cluster_points = [
                point_ids[i] for i in range(len(assignments)) if assignments[i] == k
            ]
            if cluster_points:
                cluster = Cluster(
                    centroid=centroids[k].tolist(),
                    points=cluster_points,
                    coherence_score=self._compute_coherence(X, assignments, k),
                )
                self._clusters[cluster.cluster_id] = cluster

        self._label_clusters()
        return list(self._clusters.values())

    def _kmeans(self, X: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        n_samples = X.shape[0]
        indices = np.random.choice(n_samples, k, replace=False)
        centroids = X[indices].copy()

        for _ in range(self.max_iterations):
            distances = np.linalg.norm(X[:, np.newaxis] - centroids, axis=2)
            assignments = np.argmin(distances, axis=1)

            new_centroids = np.array([
                X[assignments == i].mean(axis=0) if np.sum(assignments == i) > 0
                else centroids[i]
                for i in range(k)
            ])

            if np.allclose(centroids, new_centroids):
                break
            centroids = new_centroids

        return centroids, assignments

    def _compute_coherence(self, X: np.ndarray, assignments: np.ndarray, cluster_id: int) -> float:
        mask = assignments == cluster_id
        cluster_points = X[mask]
        if len(cluster_points) < 2:
            return 0.0

        centroid = cluster_points.mean(axis=0)
        distances = np.linalg.norm(cluster_points - centroid, axis=1)
        avg_distance = distances.mean()
        return float(1.0 / (1.0 + avg_distance))

    def _label_clusters(self) -> None:
        for cluster in self._clusters.values():
            all_tags: dict[str, int] = defaultdict(int)
            for pid in cluster.points:
                point = self._points.get(pid)
                if point:
                    for tag in point.tags:
                        all_tags[tag] += 1

            if all_tags:
                cluster.label = max(all_tags, key=all_tags.get)
            else:
                cluster.label = f"cluster-{str(cluster.cluster_id)[:8]}"

    def get_cluster(self, cluster_id: uuid.UUID) -> Cluster | None:
        return self._clusters.get(cluster_id)

    def find_nearest_cluster(self, embedding: list[float]) -> Cluster | None:
        if not self._clusters:
            return None

        X = np.array([embedding])
        best_cluster = None
        best_distance = float("inf")

        for cluster in self._clusters.values():
            centroid = np.array(cluster.centroid)
            dist = np.linalg.norm(X - centroid, axis=1)[0]
            if dist < best_distance:
                best_distance = dist
                best_cluster = cluster

        return best_cluster

    def get_summary(self) -> dict:
        return {
            "total_points": len(self._points),
            "total_clusters": len(self._clusters),
            "clusters": [
                {
                    "id": str(c.cluster_id),
                    "label": c.label,
                    "size": len(c.points),
                    "coherence": round(c.coherence_score, 3),
                }
                for c in self._clusters.values()
            ],
        }


reflection_clusterer = ReflectionCluster()
