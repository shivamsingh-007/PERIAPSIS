from __future__ import annotations

import random
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("ab_testing")


class Variant(BaseModel):
    variant_id: str
    name: str
    config: dict = Field(default_factory=dict)
    weight: float = 1.0


class Experiment(BaseModel):
    experiment_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    description: str = ""
    variants: list[Variant] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    results: dict[str, list[float]] = Field(default_factory=dict)


class ABTestManager:
    def __init__(self):
        self._experiments: dict[str, Experiment] = {}

    def create_experiment(
        self,
        name: str,
        variants: list[dict],
        description: str = "",
    ) -> Experiment:
        variant_objects = [Variant(**v) for v in variants]
        experiment = Experiment(
            name=name,
            description=description,
            variants=variant_objects,
        )
        self._experiments[name] = experiment
        logger.info(f"Created experiment: {name}")
        return experiment

    def assign_variant(self, experiment_name: str, user_id: str) -> Variant | None:
        experiment = self._experiments.get(experiment_name)
        if not experiment or not experiment.is_active:
            return None

        total_weight = sum(v.weight for v in experiment.variants)
        r = random.random() * total_weight
        cumulative = 0.0

        for variant in experiment.variants:
            cumulative += variant.weight
            if r <= cumulative:
                return variant

        return experiment.variants[0] if experiment.variants else None

    def record_outcome(
        self,
        experiment_name: str,
        variant_id: str,
        metric: float,
    ) -> None:
        experiment = self._experiments.get(experiment_name)
        if not experiment:
            return

        if variant_id not in experiment.results:
            experiment.results[variant_id] = []
        experiment.results[variant_id].append(metric)

    def get_results(self, experiment_name: str) -> dict:
        experiment = self._experiments.get(experiment_name)
        if not experiment:
            return {}

        results = {}
        for variant in experiment.variants:
            metrics = experiment.results.get(variant.variant_id, [])
            if metrics:
                results[variant.variant_id] = {
                    "name": variant.name,
                    "count": len(metrics),
                    "mean": sum(metrics) / len(metrics),
                    "min": min(metrics),
                    "max": max(metrics),
                }

        return {
            "experiment": experiment_name,
            "is_active": experiment.is_active,
            "variants": results,
        }

    def get_winning_variant(self, experiment_name: str) -> str | None:
        results = self.get_results(experiment_name)
        variants = results.get("variants", {})

        if not variants:
            return None

        return max(variants, key=lambda v: variants[v].get("mean", 0))

    def list_experiments(self) -> list[dict]:
        return [
            {
                "name": e.name,
                "description": e.description,
                "is_active": e.is_active,
                "variants": len(e.variants),
                "created_at": e.created_at.isoformat(),
            }
            for e in self._experiments.values()
        ]


ab_test_manager = ABTestManager()
