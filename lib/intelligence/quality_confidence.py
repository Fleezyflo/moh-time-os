"""
Quality-Weighted Confidence — MOH TIME OS

Adjusts intelligence confidence scores based on underlying data quality.
Combines freshness, completeness, and source reliability into a quality
multiplier that modulates confidence of signals, patterns, and scores.

Brief 27 (DQ), Task DQ-3.1
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QualityFactors:
    """Data quality factors for confidence adjustment."""

    freshness_score: float  # 0.0 to 1.0
    completeness_score: float  # 0.0 to 1.0
    source_coverage: float  # 0.0 to 1.0
    source_reliability: float  # 0.0 to 1.0 (from known source quality)

    @property
    def quality_multiplier(self) -> float:
        """
        Compute combined quality multiplier.

        Weighted average:
        - Freshness: 30%
        - Completeness: 30%
        - Source coverage: 20%
        - Source reliability: 20%

        Returns value between 0.0 and 1.0.
        """
        return (
            self.freshness_score * 0.30
            + self.completeness_score * 0.30
            + self.source_coverage * 0.20
            + self.source_reliability * 0.20
        )

    def to_dict(self) -> dict:
        return {
            "freshness_score": round(self.freshness_score, 4),
            "completeness_score": round(self.completeness_score, 4),
            "source_coverage": round(self.source_coverage, 4),
            "source_reliability": round(self.source_reliability, 4),
            "quality_multiplier": round(self.quality_multiplier, 4),
        }


@dataclass
class AdjustedConfidence:
    """A confidence score adjusted for data quality."""

    original_confidence: float
    quality_multiplier: float
    adjusted_confidence: float
    quality_factors: QualityFactors
    penalty_applied: bool

    def to_dict(self) -> dict:
        return {
            "original_confidence": round(self.original_confidence, 4),
            "quality_multiplier": round(self.quality_multiplier, 4),
            "adjusted_confidence": round(self.adjusted_confidence, 4),
            "penalty_applied": self.penalty_applied,
            "quality_factors": self.quality_factors.to_dict(),
        }


# Source reliability ratings (0.0 to 1.0)
DEFAULT_SOURCE_RELIABILITY = {
    "harvest": 0.95,  # Time tracking — structured, reliable
    "email": 0.70,  # Email analysis — unstructured, noisy
    "project_mgmt": 0.85,  # PM tools — structured, some lag
    "financial": 0.90,  # Financial data — structured, periodic
    "manual": 0.60,  # Manual input — prone to staleness
    "default": 0.75,
}


class QualityConfidenceAdjuster:
    """Adjusts confidence scores based on data quality."""

    # Minimum quality multiplier — confidence can never be reduced below this fraction
    MIN_MULTIPLIER = 0.3

    # Below this quality multiplier, flag as unreliable
    UNRELIABLE_THRESHOLD = 0.5

    def __init__(
        self,
        source_reliability: dict[str, float] | None = None,
    ):
        self.source_reliability = source_reliability or DEFAULT_SOURCE_RELIABILITY

    def adjust_confidence(
        self,
        confidence: float,
        freshness_score: float,
        completeness_score: float,
        source_coverage: float,
        sources: list[str] | None = None,
    ) -> AdjustedConfidence:
        """
        Adjust a confidence score based on data quality.

        Returns adjusted confidence and quality breakdown.
        """
        # Compute source reliability as avg of sources
        reliability = self._compute_source_reliability(sources)

        factors = QualityFactors(
            freshness_score=freshness_score,
            completeness_score=completeness_score,
            source_coverage=source_coverage,
            source_reliability=reliability,
        )

        multiplier = max(self.MIN_MULTIPLIER, factors.quality_multiplier)
        adjusted = confidence * multiplier
        penalty = multiplier < 1.0

        return AdjustedConfidence(
            original_confidence=confidence,
            quality_multiplier=multiplier,
            adjusted_confidence=adjusted,
            quality_factors=factors,
            penalty_applied=penalty,
        )

    def is_reliable(
        self,
        freshness_score: float,
        completeness_score: float,
        source_coverage: float,
    ) -> bool:
        """Quick check if data quality is above the reliability threshold."""
        factors = QualityFactors(
            freshness_score=freshness_score,
            completeness_score=completeness_score,
            source_coverage=source_coverage,
            source_reliability=1.0,  # Ignore source reliability for this check
        )
        return factors.quality_multiplier >= self.UNRELIABLE_THRESHOLD

    def get_source_reliability(self, source: str) -> float:
        """Get reliability score for a data source."""
        return self.source_reliability.get(source, self.source_reliability.get("default", 0.75))

    def _compute_source_reliability(self, sources: list[str] | None) -> float:
        """Average reliability across provided sources."""
        if not sources:
            return self.source_reliability.get("default", 0.75)

        reliabilities = [
            self.source_reliability.get(s, self.source_reliability.get("default", 0.75))
            for s in sources
        ]
        return sum(reliabilities) / len(reliabilities)

    def compute_quality_summary(
        self,
        entities: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Compute quality summary across multiple entities.

        Each entity dict should have: freshness_score, completeness_score,
        source_coverage, sources (optional list)
        """
        if not entities:
            return {
                "total_entities": 0,
                "avg_quality_multiplier": 0.0,
                "unreliable_count": 0,
                "quality_distribution": {},
            }

        multipliers = []
        unreliable = 0

        for entity in entities:
            factors = QualityFactors(
                freshness_score=entity.get("freshness_score", 0.5),
                completeness_score=entity.get("completeness_score", 0.5),
                source_coverage=entity.get("source_coverage", 0.5),
                source_reliability=self._compute_source_reliability(entity.get("sources")),
            )
            m = factors.quality_multiplier
            multipliers.append(m)
            if m < self.UNRELIABLE_THRESHOLD:
                unreliable += 1

        # Distribution buckets
        dist = {
            "excellent": sum(1 for m in multipliers if m >= 0.8),
            "good": sum(1 for m in multipliers if 0.6 <= m < 0.8),
            "fair": sum(1 for m in multipliers if 0.4 <= m < 0.6),
            "poor": sum(1 for m in multipliers if m < 0.4),
        }

        return {
            "total_entities": len(entities),
            "avg_quality_multiplier": round(sum(multipliers) / len(multipliers), 4),
            "unreliable_count": unreliable,
            "quality_distribution": dist,
        }
