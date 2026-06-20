from __future__ import annotations

import pytest

from packages.intelligence.fact_checking import FactChecker


@pytest.fixture
def checker():
    return FactChecker()


class TestFactChecker:
    def test_init(self, checker):
        assert checker is not None

    async def test_check_claim(self, checker):
        result = await checker.check_claim(
            claim_text="Python is a programming language",
            memory_context=["Python is widely used for web development and data science"],
        )
        assert result is not None

    async def test_check_contradiction(self, checker):
        result = await checker.check_claim(
            claim_text="Python is not a programming language",
            memory_context=["Python is a popular programming language"],
        )
        assert result is not None

    async def test_check_with_evidence(self, checker):
        result = await checker.check_claim(
            claim_text="The sky is blue",
            memory_context=["The sky appears blue due to Rayleigh scattering"],
        )
        assert result is not None

    async def test_check_empty_claim(self, checker):
        result = await checker.check_claim(claim_text="", memory_context=[])
        assert result is not None

    def test_get_stats(self, checker):
        stats = checker.get_stats()
        assert isinstance(stats, dict)
