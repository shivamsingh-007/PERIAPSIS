from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("what_if")


class WhatIfScenario(BaseModel):
    scenario_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    description: str = ""
    original_state: dict = Field(default_factory=dict)
    modified_state: dict = Field(default_factory=dict)
    predicted_outcome: dict = Field(default_factory=dict)
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WhatIfAnalysis:
    def __init__(self):
        self._scenarios: dict[uuid.UUID, WhatIfScenario] = {}
        self._run_history: list[dict] = []

    def record_run(self, run_data: dict) -> None:
        self._run_history.append(run_data)

    def create_scenario(
        self,
        name: str,
        original_state: dict,
        modifications: dict,
        description: str = "",
    ) -> WhatIfScenario:
        modified = {**original_state, **modifications}

        predicted = self._predict_outcome(original_state, modified)

        scenario = WhatIfScenario(
            name=name,
            description=description,
            original_state=original_state,
            modified_state=modified,
            predicted_outcome=predicted,
            confidence=self._calculate_confidence(original_state, modified),
        )
        self._scenarios[scenario.scenario_id] = scenario
        return scenario

    def _predict_outcome(self, original: dict, modified: dict) -> dict:
        outcome = {}

        if "budget_limit" in modified and "budget_limit" in original:
            ratio = modified["budget_limit"] / max(original["budget_limit"], 0.01)
            outcome["estimated_cost_ratio"] = ratio

        if "risk_tier" in modified:
            risk_impact = {"low": 1.0, "medium": 1.2, "high": 1.5, "critical": 2.0}
            outcome["risk_multiplier"] = risk_impact.get(modified["risk_tier"], 1.0)

        if "goal" in modified and modified["goal"] != original.get("goal"):
            outcome["goal_changed"] = True
            outcome["estimated_additional_steps"] = 2

        return outcome

    def _calculate_confidence(self, original: dict, modified: dict) -> float:
        if not self._run_history:
            return 0.3

        similar_runs = 0
        for run in self._run_history:
            overlap = len(set(original.keys()) & set(run.keys()))
            if overlap > 0:
                similar_runs += 1

        return min(0.9, 0.3 + (similar_runs / max(len(self._run_history), 1)) * 0.6)

    def get_scenario(self, scenario_id: uuid.UUID) -> WhatIfScenario | None:
        return self._scenarios.get(scenario_id)

    def list_scenarios(self) -> list[WhatIfScenario]:
        return list(self._scenarios.values())

    def compare_scenarios(self, scenario_ids: list[uuid.UUID]) -> dict:
        scenarios = [self._scenarios.get(sid) for sid in scenario_ids if sid in self._scenarios]
        return {
            "scenarios": [
                {
                    "name": s.name,
                    "predicted_outcome": s.predicted_outcome,
                    "confidence": s.confidence,
                }
                for s in scenarios
            ]
        }


what_if_analysis = WhatIfAnalysis()
