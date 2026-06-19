from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("hallucination")


class HallucinationSignal(BaseModel):
    signal_type: str
    confidence: float
    detail: str
    location: str | None = None


class HallucinationDetector:
    HALLUCINATION_PATTERNS = [
        {
            "type": "vague_attribution",
            "pattern": re.compile(r'(?i)(studies show|research suggests|experts say|it is known that|everyone knows)'),
            "confidence": 0.6,
        },
        {
            "type": "absolute_claim",
            "pattern": re.compile(r'(?i)(always|never|impossible|guaranteed|100%|zero risk)'),
            "confidence": 0.5,
        },
        {
            "type": "unverifiable_stat",
            "pattern": re.compile(r'\b\d+\.?\d*%\b'),
            "confidence": 0.3,
        },
        {
            "type": "self_reference",
            "pattern": re.compile(r'(?i)(I recall|I remember|as I said|I mentioned)'),
            "confidence": 0.4,
        },
    ]

    def detect(self, text: str) -> list[HallucinationSignal]:
        signals = []
        for pattern_info in self.HALLUCINATION_PATTERNS:
            matches = pattern_info["pattern"].finditer(text)
            for match in matches:
                signals.append(HallucinationSignal(
                    signal_type=pattern_info["type"],
                    confidence=pattern_info["confidence"],
                    detail=match.group(),
                    location=f"pos {match.start()}-{match.end()}",
                ))
        return signals

    def score(self, text: str) -> float:
        signals = self.detect(text)
        if not signals:
            return 0.0

        total_confidence = sum(s.confidence for s in signals)
        return min(1.0, total_confidence / max(len(text) / 100, 1))

    def suggest_corrections(self, text: str, signals: list[HallucinationSignal]) -> list[str]:
        suggestions = []
        for signal in signals:
            if signal.signal_type == "vague_attribution":
                suggestions.append(f"Replace '{signal.detail}' with specific sources")
            elif signal.signal_type == "absolute_claim":
                suggestions.append(f"Qualify '{signal.detail}' with evidence")
            elif signal.signal_type == "unverifiable_stat":
                suggestions.append(f"Verify statistic '{signal.detail}' with source")
        return suggestions


hallucination_detector = HallucinationDetector()
