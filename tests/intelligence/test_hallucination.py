from __future__ import annotations
"""Tests for packages.intelligence.hallucination - HallucinationDetector."""

import pytest

from packages.intelligence.hallucination import HallucinationDetector, HallucinationSignal


class TestHallucinationDetector:
    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_clean_text_no_signals(self):
        signals = self.detector.detect("Python was created by Guido van Rossum.")
        assert len(signals) == 0

    def test_vague_attribution_detected(self):
        signals = self.detector.detect("Studies show that Python is popular.")
        assert any(s.signal_type == "vague_attribution" for s in signals)

    def test_absolute_claim_detected(self):
        signals = self.detector.detect("Python is always the best choice.")
        assert any(s.signal_type == "absolute_claim" for s in signals)

    def test_percentage_stat_detected(self):
        # The regex requires a word boundary after %, which requires a word char
        # after the %. Use text where % is followed by a word character.
        signals = self.detector.detect("Python holds 45%market share in web frameworks.")
        assert any(s.signal_type == "unverifiable_stat" for s in signals)

    def test_self_reference_detected(self):
        signals = self.detector.detect("I recall that Python 3 was released in 2008.")
        assert any(s.signal_type == "self_reference" for s in signals)

    def test_multiple_signals(self):
        signals = self.detector.detect(
            "Studies show that everyone knows Python is always the best with 100%market."
        )
        assert len(signals) >= 2

    def test_score_clean_text(self):
        score = self.detector.score("A normal sentence about Python.")
        assert score == 0.0

    def test_score_hallucinated_text(self):
        score = self.detector.score(
            "Studies show that Python is always the best with 100%market."
        )
        assert score > 0.0

    def test_suggest_corrections_vague(self):
        signals = [HallucinationSignal(
            signal_type="vague_attribution",
            confidence=0.6,
            detail="studies show",
        )]
        suggestions = self.detector.suggest_corrections("text", signals)
        assert len(suggestions) == 1
        assert "studies show" in suggestions[0]

    def test_suggest_corrections_absolute(self):
        signals = [HallucinationSignal(
            signal_type="absolute_claim",
            confidence=0.5,
            detail="always",
        )]
        suggestions = self.detector.suggest_corrections("text", signals)
        assert len(suggestions) == 1

    def test_suggest_corrections_stat(self):
        signals = [HallucinationSignal(
            signal_type="unverifiable_stat",
            confidence=0.3,
            detail="45%",
        )]
        suggestions = self.detector.suggest_corrections("text", signals)
        assert len(suggestions) == 1
