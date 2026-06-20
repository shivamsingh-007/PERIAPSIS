from __future__ import annotations
"""Tests for packages.memory.write_filter - MemoryWriteFilter."""

import pytest

from packages.memory.write_filter import (
    FilterDecision,
    FilterResult,
    MemoryCandidate,
    MemoryType,
    MemoryWriteFilter,
)


class TestMemoryWriteFilterEvaluate:
    def setup_method(self):
        self.filter = MemoryWriteFilter()

    def test_fact_without_source_requires_source(self):
        candidate = MemoryCandidate(
            content="Python is a language",
            memory_type=MemoryType.FACT,
            confidence=0.8,
            has_source_attribution=False,
        )
        result = self.filter.evaluate(candidate)
        assert result.decision == FilterDecision.REQUIRE_SOURCE

    def test_fact_with_source_allowed(self):
        candidate = MemoryCandidate(
            content="Python is a language",
            memory_type=MemoryType.FACT,
            confidence=0.8,
            has_source_attribution=True,
        )
        result = self.filter.evaluate(candidate)
        assert result.decision == FilterDecision.ALLOW

    def test_low_confidence_rejected(self):
        candidate = MemoryCandidate(
            content="Maybe this is true",
            memory_type=MemoryType.FACT,
            confidence=0.2,
            has_source_attribution=True,
        )
        result = self.filter.evaluate(candidate)
        assert result.decision == FilterDecision.LOW_CONFIDENCE

    def test_lesson_confidence_adjusted(self):
        candidate = MemoryCandidate(
            content="Always validate inputs",
            memory_type=MemoryType.LESSON,
            confidence=1.0,
            has_source_attribution=True,
        )
        result = self.filter.evaluate(candidate)
        assert result.decision == FilterDecision.ALLOW
        assert result.adjusted_confidence < 1.0

    def test_preference_confidence_adjusted(self):
        candidate = MemoryCandidate(
            content="User prefers dark mode",
            memory_type=MemoryType.PREFERENCE,
            confidence=1.0,
            has_source_attribution=True,
        )
        result = self.filter.evaluate(candidate)
        assert result.decision == FilterDecision.ALLOW
        assert result.adjusted_confidence < 1.0

    def test_boundary_confidence_below(self):
        # 0.29 < 0.3 threshold
        candidate = MemoryCandidate(
            content="test",
            memory_type=MemoryType.FACT,
            confidence=0.29,
            has_source_attribution=True,
        )
        result = self.filter.evaluate(candidate)
        assert result.decision == FilterDecision.LOW_CONFIDENCE

    def test_boundary_confidence_at_threshold(self):
        # 0.3 is NOT < 0.3, so it passes
        candidate = MemoryCandidate(
            content="test",
            memory_type=MemoryType.FACT,
            confidence=0.3,
            has_source_attribution=True,
        )
        result = self.filter.evaluate(candidate)
        assert result.decision == FilterDecision.ALLOW

    def test_just_above_threshold(self):
        candidate = MemoryCandidate(
            content="test",
            memory_type=MemoryType.FACT,
            confidence=0.31,
            has_source_attribution=True,
        )
        result = self.filter.evaluate(candidate)
        assert result.decision == FilterDecision.ALLOW

    def test_high_confidence_fact_no_source_blocked(self):
        candidate = MemoryCandidate(
            content="unverified claim",
            memory_type=MemoryType.FACT,
            confidence=0.75,
            has_source_attribution=False,
        )
        result = self.filter.evaluate(candidate)
        assert result.decision == FilterDecision.REQUIRE_SOURCE


class TestMemoryWriteFilterTTL:
    def setup_method(self):
        self.filter = MemoryWriteFilter()

    def test_fact_ttl(self):
        assert self.filter.get_ttl_days(MemoryType.FACT, 0.8) == 365

    def test_lesson_ttl(self):
        assert self.filter.get_ttl_days(MemoryType.LESSON, 0.8) == 730

    def test_preference_ttl(self):
        assert self.filter.get_ttl_days(MemoryType.PREFERENCE, 0.8) == 365

    def test_incident_ttl(self):
        assert self.filter.get_ttl_days(MemoryType.INCIDENT, 0.8) == 180

    def test_summary_ttl(self):
        assert self.filter.get_ttl_days(MemoryType.SUMMARY, 0.8) == 90

    def test_constraint_ttl(self):
        assert self.filter.get_ttl_days(MemoryType.CONSTRAINT, 0.8) == 365

    def test_low_confidence_reduces_ttl(self):
        ttl = self.filter.get_ttl_days(MemoryType.FACT, 0.2)
        assert ttl == 14  # _expire_low_confidence_days

    def test_high_confidence_keeps_full_ttl(self):
        ttl = self.filter.get_ttl_days(MemoryType.FACT, 0.9)
        assert ttl == 365

    def test_summary_low_confidence(self):
        ttl = self.filter.get_ttl_days(MemoryType.SUMMARY, 0.1)
        assert ttl == 14  # 14 < 90 so min applies
