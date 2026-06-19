from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    FACT = "fact"
    LESSON = "lesson"
    PREFERENCE = "preference"
    INCIDENT = "incident"
    SUMMARY = "summary"
    CONSTRAINT = "constraint"


class FilterDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_SOURCE = "require_source"
    LOW_CONFIDENCE = "low_confidence"


class MemoryCandidate(BaseModel):
    content: str
    memory_type: MemoryType
    source_ref: dict | None = None
    confidence: float = 0.5
    scope: str = "run"
    has_source_attribution: bool = False


class FilterResult(BaseModel):
    decision: FilterDecision
    reason: str = ""
    adjusted_confidence: float = 0.0
    require_source: bool = False


class MemoryWriteFilter:
    def __init__(self):
        self._require_source_for_facts = True
        self._allow_user_preferences = True
        self._allow_operator_feedback = True
        self._expire_low_confidence_days = 14
        self._block_unverified_external_claims = True
        self._min_confidence_threshold = 0.3

    def evaluate(self, candidate: MemoryCandidate) -> FilterResult:
        if self._block_unverified_external_claims:
            if candidate.memory_type == MemoryType.FACT and not candidate.has_source_attribution:
                if candidate.confidence < 0.7:
                    return FilterResult(
                        decision=FilterDecision.REQUIRE_SOURCE,
                        reason="Factual claims require source attribution with confidence >= 0.7",
                        adjusted_confidence=candidate.confidence,
                        require_source=True,
                    )

        if self._require_source_for_facts:
            if candidate.memory_type == MemoryType.FACT and not candidate.has_source_attribution:
                return FilterResult(
                    decision=FilterDecision.REQUIRE_SOURCE,
                    reason="Factual memories require source attribution",
                    adjusted_confidence=candidate.confidence * 0.5,
                    require_source=True,
                )

        if candidate.confidence < self._min_confidence_threshold:
            return FilterResult(
                decision=FilterDecision.LOW_CONFIDENCE,
                reason=f"Confidence {candidate.confidence} below threshold {self._min_confidence_threshold}",
                adjusted_confidence=candidate.confidence,
            )

        adjusted = candidate.confidence
        if candidate.memory_type == MemoryType.LESSON:
            adjusted = min(candidate.confidence * 0.8, 1.0)
        elif candidate.memory_type == MemoryType.PREFERENCE:
            adjusted = min(candidate.confidence * 0.9, 1.0)

        return FilterResult(
            decision=FilterDecision.ALLOW,
            reason="Passed all filters",
            adjusted_confidence=adjusted,
        )

    def get_ttl_days(self, memory_type: MemoryType, confidence: float) -> int:
        base_ttl = {
            MemoryType.FACT: 365,
            MemoryType.LESSON: 730,
            MemoryType.PREFERENCE: 365,
            MemoryType.INCIDENT: 180,
            MemoryType.SUMMARY: 90,
            MemoryType.CONSTRAINT: 365,
        }
        ttl = base_ttl.get(memory_type, 365)

        if confidence < 0.5:
            ttl = min(ttl, self._expire_low_confidence_days)

        return ttl


memory_write_filter = MemoryWriteFilter()
