from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("fact_checking")


class FactClaim(BaseModel):
    claim_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    text: str
    source: str = ""
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    contradicted_by: list[str] = Field(default_factory=list)
    verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FactChecker:
    def __init__(self):
        self._claims: dict[uuid.UUID, FactClaim] = {}
        self._memory_facts: dict[str, list[str]] = {}

    def register_memory_fact(self, key: str, facts: list[str]) -> None:
        self._memory_facts[key] = facts

    async def check_claim(
        self,
        claim_text: str,
        memory_context: list[str] | None = None,
    ) -> FactClaim:
        claim = FactClaim(text=claim_text)

        evidence = []
        contradictions = []

        if memory_context:
            for fact in memory_context:
                if self._fuzzy_match(claim_text, fact):
                    evidence.append(fact)
                if self._contradicts(claim_text, fact):
                    contradictions.append(fact)

        all_facts = []
        for facts in self._memory_facts.values():
            all_facts.extend(facts)

        for fact in all_facts:
            if self._fuzzy_match(claim_text, fact) and fact not in evidence:
                evidence.append(fact)
            if self._contradicts(claim_text, fact) and fact not in contradictions:
                contradictions.append(fact)

        claim.evidence = evidence
        claim.contradicted_by = contradictions

        if contradictions:
            claim.confidence = 0.2
            claim.verified = False
        elif evidence:
            claim.confidence = min(0.9, 0.5 + len(evidence) * 0.1)
            claim.verified = True
        else:
            claim.confidence = 0.3
            claim.verified = False

        self._claims[claim.claim_id] = claim
        return claim

    def _fuzzy_match(self, text1: str, text2: str) -> bool:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return False
        overlap = len(words1 & words2) / max(len(words1), len(words2))
        return overlap > 0.5

    def _contradicts(self, text1: str, text2: str) -> bool:
        negations = ["not", "never", "no", "false", "incorrect"]
        words1 = text1.lower().split()
        words2 = text2.lower().split()

        has_negation1 = any(w in negations for w in words1)
        has_negation2 = any(w in negations for w in words2)

        if has_negation1 != has_negation2:
            content_words1 = set(words1) - set(negations)
            content_words2 = set(words2) - set(negations)
            overlap = len(content_words1 & content_words2)
            return overlap > len(content_words1) * 0.5

        return False

    def get_claim(self, claim_id: uuid.UUID) -> FactClaim | None:
        return self._claims.get(claim_id)

    def list_unverified(self) -> list[FactClaim]:
        return [c for c in self._claims.values() if not c.verified]

    def get_stats(self) -> dict:
        claims = list(self._claims.values())
        return {
            "total_claims": len(claims),
            "verified": sum(1 for c in claims if c.verified),
            "unverified": sum(1 for c in claims if not c.verified),
            "contradicted": sum(1 for c in claims if c.contradicted_by),
        }


fact_checker = FactChecker()
