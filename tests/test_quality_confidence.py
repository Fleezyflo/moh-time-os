"""
Tests for QualityConfidenceAdjuster — quality-weighted confidence.

Brief 27 (DQ), Task DQ-3.1
"""

import pytest

from lib.intelligence.quality_confidence import (
    QualityConfidenceAdjuster,
    QualityFactors,
)


@pytest.fixture
def adjuster():
    return QualityConfidenceAdjuster()


class TestQualityFactors:
    def test_perfect_quality(self):
        f = QualityFactors(1.0, 1.0, 1.0, 1.0)
        assert f.quality_multiplier == pytest.approx(1.0)

    def test_zero_quality(self):
        f = QualityFactors(0.0, 0.0, 0.0, 0.0)
        assert f.quality_multiplier == 0.0

    def test_mixed_quality(self):
        f = QualityFactors(0.8, 0.6, 0.5, 0.9)
        # 0.8*0.3 + 0.6*0.3 + 0.5*0.2 + 0.9*0.2 = 0.24 + 0.18 + 0.10 + 0.18 = 0.70
        assert f.quality_multiplier == pytest.approx(0.70)

    def test_to_dict(self):
        f = QualityFactors(0.8, 0.6, 0.5, 0.9)
        d = f.to_dict()
        assert "freshness_score" in d
        assert "quality_multiplier" in d
        assert d["quality_multiplier"] == pytest.approx(0.70, abs=0.001)


class TestAdjustConfidence:
    def test_perfect_quality_no_penalty(self, adjuster):
        result = adjuster.adjust_confidence(
            confidence=0.85,
            freshness_score=1.0,
            completeness_score=1.0,
            source_coverage=1.0,
            sources=["harvest"],
        )
        # harvest reliability = 0.95
        # multiplier = 0.3*1.0 + 0.3*1.0 + 0.2*1.0 + 0.2*0.95 = 0.99
        assert result.adjusted_confidence == pytest.approx(0.85 * 0.99, abs=0.01)
        assert result.penalty_applied is True  # 0.99 < 1.0

    def test_poor_quality_reduces_confidence(self, adjuster):
        result = adjuster.adjust_confidence(
            confidence=0.85,
            freshness_score=0.2,
            completeness_score=0.3,
            source_coverage=0.5,
            sources=["manual"],
        )
        assert result.adjusted_confidence < 0.85
        assert result.penalty_applied is True
        assert result.quality_multiplier < 1.0

    def test_minimum_multiplier_floor(self, adjuster):
        result = adjuster.adjust_confidence(
            confidence=0.9,
            freshness_score=0.0,
            completeness_score=0.0,
            source_coverage=0.0,
            sources=["manual"],
        )
        # Floor is 0.3
        assert result.quality_multiplier >= 0.3
        assert result.adjusted_confidence >= 0.9 * 0.3

    def test_to_dict(self, adjuster):
        result = adjuster.adjust_confidence(
            confidence=0.8,
            freshness_score=0.7,
            completeness_score=0.8,
            source_coverage=0.6,
        )
        d = result.to_dict()
        assert "original_confidence" in d
        assert "adjusted_confidence" in d
        assert "quality_factors" in d


class TestIsReliable:
    def test_reliable_data(self, adjuster):
        assert adjuster.is_reliable(0.8, 0.8, 0.8) is True

    def test_unreliable_data(self, adjuster):
        assert adjuster.is_reliable(0.1, 0.1, 0.1) is False

    def test_borderline(self, adjuster):
        # 0.5*0.3 + 0.5*0.3 + 0.5*0.2 + 1.0*0.2 = 0.15+0.15+0.1+0.2 = 0.6
        assert adjuster.is_reliable(0.5, 0.5, 0.5) is True


class TestSourceReliability:
    def test_known_source(self, adjuster):
        assert adjuster.get_source_reliability("harvest") == 0.95
        assert adjuster.get_source_reliability("email") == 0.70

    def test_unknown_source(self, adjuster):
        assert adjuster.get_source_reliability("unknown_source") == 0.75

    def test_custom_reliability(self):
        custom = QualityConfidenceAdjuster(source_reliability={"api": 0.99, "default": 0.5})
        assert custom.get_source_reliability("api") == 0.99
        assert custom.get_source_reliability("other") == 0.5


class TestQualitySummary:
    def test_summary_with_entities(self, adjuster):
        entities = [
            {
                "freshness_score": 0.9,
                "completeness_score": 0.8,
                "source_coverage": 0.7,
                "sources": ["harvest"],
            },
            {"freshness_score": 0.3, "completeness_score": 0.2, "source_coverage": 0.1},
        ]
        summary = adjuster.compute_quality_summary(entities)
        assert summary["total_entities"] == 2
        assert summary["avg_quality_multiplier"] > 0
        assert (
            summary["quality_distribution"]["excellent"]
            + summary["quality_distribution"]["good"]
            + summary["quality_distribution"]["fair"]
            + summary["quality_distribution"]["poor"]
            == 2
        )

    def test_summary_empty(self, adjuster):
        summary = adjuster.compute_quality_summary([])
        assert summary["total_entities"] == 0
        assert summary["avg_quality_multiplier"] == 0.0

    def test_all_excellent(self, adjuster):
        entities = [
            {
                "freshness_score": 0.95,
                "completeness_score": 0.95,
                "source_coverage": 0.95,
                "sources": ["harvest"],
            },
        ]
        summary = adjuster.compute_quality_summary(entities)
        assert summary["quality_distribution"]["excellent"] == 1
        assert summary["unreliable_count"] == 0
