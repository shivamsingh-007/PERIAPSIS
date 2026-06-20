from __future__ import annotations
"""Tests for packages.intelligence.fact_checking - FactChecker."""

import uuid

import pytest

from packages.intelligence.fact_checking import FactChecker, FactClaim


class TestFactChecker:
    def setup_method(self):
        self.checker = FactChecker()

    @pytest.mark.asyncio
    async def test_check_claim_no_context(self):
        claim = await self.checker.check_claim("Python is a language")
        assert claim.verified is False
        assert claim.confidence == 0.3

    @pytest.mark.asyncio
    async def test_check_claim_with_matching_evidence(self):
        claim = await self.checker.check_claim(
            "Python is a programming language",
            memory_context=["Python is a programming language used for web dev"],
        )
        assert claim.verified is True
        assert claim.confidence > 0.5

    @pytest.mark.asyncio
    async def test_check_claim_with_contradiction(self):
        claim = await self.checker.check_claim(
            "Python is not a language",
            memory_context=["Python is a programming language"],
        )
        assert claim.verified is False
        assert claim.confidence == 0.2

    @pytest.mark.asyncio
    async def test_register_memory_fact(self):
        self.checker.register_memory_fact("key1", ["fact1", "fact2"])
        claim = await self.checker.check_claim("fact1")
        assert claim.verified is True

    def test_get_claim(self):
        claim = FactClaim(text="test")
        self.checker._claims[claim.claim_id] = claim
        found = self.checker.get_claim(claim.claim_id)
        assert found is not None

    def test_get_claim_not_found(self):
        assert self.checker.get_claim(uuid.uuid4()) is None

    def test_list_unverified(self):
        c1 = FactClaim(text="verified", verified=True)
        c2 = FactClaim(text="unverified", verified=False)
        self.checker._claims[c1.claim_id] = c1
        self.checker._claims[c2.claim_id] = c2
        unverified = self.checker.list_unverified()
        assert len(unverified) == 1

    def test_get_stats(self):
        c1 = FactClaim(text="v", verified=True)
        c2 = FactClaim(text="u", verified=False)
        c3 = FactClaim(text="c", verified=False, contradicted_by=["x"])
        self.checker._claims[c1.claim_id] = c1
        self.checker._claims[c2.claim_id] = c2
        self.checker._claims[c3.claim_id] = c3
        stats = self.checker.get_stats()
        assert stats["total_claims"] == 3
        assert stats["verified"] == 1
        assert stats["unverified"] == 2
        assert stats["contradicted"] == 1

    def test_fuzzy_match(self):
        assert self.checker._fuzzy_match(
            "Python is a language", "Python is a programming language"
        ) is True
        assert self.checker._fuzzy_match("cat", "Python is a language") is False

    def test_fuzzy_match_empty(self):
        assert self.checker._fuzzy_match("", "test") is False

    def test_contradicts(self):
        assert self.checker._contradicts(
            "Python is a language", "Python is not a language"
        ) is True
        assert self.checker._contradicts(
            "Python is a language", "Python is a language"
        ) is False
