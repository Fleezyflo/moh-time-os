"""
Threshold Tests — Validate quality gates.

Per IMPLEMENTATION_PLAN_V4_FROZEN.md Amendment 3:
- Thresholds must be justified
- Thresholds are environment-specific
"""

import pytest

from lib.contracts.thresholds import (
    DEFAULT_THRESHOLDS,
    THRESHOLDS,
    ResolutionStats,
    ThresholdViolation,
    enforce_thresholds,
    enforce_thresholds_strict,
    get_thresholds_for_environment,
)


class TestThresholdDefaults:
    """Test threshold default values."""

    def test_commitment_resolution_rate_is_85_percent(self):
        """Commitment resolution rate default is 85%."""
        assert THRESHOLDS["commitment_resolution_rate"] == 0.85

    def test_thread_client_linkage_is_70_percent(self):
        """Thread-client linkage default is 70%."""
        assert THRESHOLDS["thread_client_linkage"] == 0.70

    def test_invoice_validity_rate_is_90_percent(self):
        """Invoice validity rate default is 90%."""
        assert THRESHOLDS["invoice_validity_rate"] == 0.90

    def test_all_thresholds_have_justification(self):
        """All thresholds must have a justification in their config."""
        for name, config in DEFAULT_THRESHOLDS.items():
            assert config.justification, f"Threshold {name} missing justification"
            assert (
                len(config.justification) > 10
            ), f"Threshold {name} justification too short"


class TestEnvironmentSpecificThresholds:
    """Test environment-specific threshold overrides."""

    def test_production_thresholds_are_relaxed(self):
        """Production thresholds are more relaxed than defaults."""
        standard = get_thresholds_for_environment("standard_agency")
        production = get_thresholds_for_environment("production")

        # Production should be more permissive
        assert (
            production["commitment_resolution_rate"]
            <= standard["commitment_resolution_rate"]
        )
        assert production["invoice_validity_rate"] <= standard["invoice_validity_rate"]

    def test_development_thresholds_are_most_relaxed(self):
        """Development thresholds are most permissive."""
        production = get_thresholds_for_environment("production")
        development = get_thresholds_for_environment("development")

        # Development should be more permissive than production
        assert (
            development["commitment_resolution_rate"]
            <= production["commitment_resolution_rate"]
        )


class TestEnforceThresholds:
    """Test threshold enforcement."""

    def test_passes_when_all_above_threshold(self):
        """Passes when all stats are above thresholds."""
        stats = ResolutionStats()
        stats.commitments_total = 100
        stats.commitments_resolved = 90  # 90% > 85%
        stats.threads_total = 100
        stats.threads_with_client = 80  # 80% > 70%
        stats.invoices_total = 100
        stats.invoices_valid = 95  # 95% > 90%
        stats.people_total = 10
        stats.people_with_hours = 9  # 90% > 80%
        stats.projects_total = 20
        stats.projects_with_client = 18  # 90% > 75%

        violations = enforce_thresholds(stats)
        assert violations == []

    def test_fails_when_commitment_rate_below_threshold(self):
        """Fails when commitment resolution rate below 85%."""
        stats = ResolutionStats()
        stats.commitments_total = 100
        stats.commitments_resolved = 50  # 50% < 85%

        violations = enforce_thresholds(stats)
        assert len(violations) == 1
        assert "commitment_resolution_rate" in violations[0]
        assert "50.0%" in violations[0]

    def test_strict_mode_raises(self):
        """Strict mode raises on first violation."""
        stats = ResolutionStats()
        stats.commitments_total = 100
        stats.commitments_resolved = 50  # 50% < 85%

        with pytest.raises(ThresholdViolation):
            enforce_thresholds_strict(stats)

    def test_uses_environment_specific_thresholds(self):
        """Uses environment-specific thresholds when specified."""
        stats = ResolutionStats()
        stats.commitments_total = 100
        stats.commitments_resolved = (
            82  # 82% - fails standard (85%) but passes production (80%)
        )

        # Fails with standard thresholds
        violations_standard = enforce_thresholds(stats, "standard_agency")
        assert len(violations_standard) == 1

        # Passes with production thresholds
        violations_production = enforce_thresholds(stats, "production")
        assert len(violations_production) == 0


class TestResolutionStats:
    """Test ResolutionStats calculations."""

    def test_resolution_rate_calculation(self):
        """Resolution rate is computed correctly."""
        stats = ResolutionStats()
        stats.commitments_total = 100
        stats.commitments_resolved = 85

        assert stats.commitments_resolution_rate == 0.85

    def test_resolution_rate_zero_when_no_items(self):
        """Resolution rate is 0 when no items."""
        stats = ResolutionStats()
        stats.commitments_total = 0
        stats.commitments_resolved = 0

        assert stats.commitments_resolution_rate == 0.0
