"""
Tests for Intelligence Patterns Module.

Covers:
- Helper computations (HHI, correlation, CV)
- Pattern type detectors
- Evidence assembly
- Full pattern detection
"""

import pytest
from pathlib import Path

from lib.intelligence.patterns import (
    PatternType,
    PatternSeverity,
    PatternDefinition,
    PatternEvidence,
    PATTERN_LIBRARY,
    get_pattern,
    get_patterns_by_type,
    get_patterns_by_severity,
    get_structural_patterns,
    validate_pattern_library,
    get_library_summary,
    # Helper functions
    _compute_herfindahl,
    _compute_top_n_share,
    _compute_coefficient_of_variation,
    _compute_correlation,
    _find_co_declining,
    # Detection functions
    detect_pattern,
    detect_all_patterns,
)


# =============================================================================
# HELPER COMPUTATION TESTS
# =============================================================================

class TestHelperComputations:
    """Tests for statistical helper functions."""

    def test_herfindahl_monopoly(self):
        """HHI of single entity = 1.0 (monopoly)."""
        shares = [1.0]
        hhi = _compute_herfindahl(shares)
        assert hhi == 1.0

    def test_herfindahl_perfect_distribution(self):
        """HHI of N equal shares = 1/N."""
        shares = [0.25, 0.25, 0.25, 0.25]
        hhi = _compute_herfindahl(shares)
        assert abs(hhi - 0.25) < 0.001

    def test_herfindahl_concentrated(self):
        """HHI increases with concentration."""
        distributed = [0.1] * 10
        concentrated = [0.5, 0.3, 0.1, 0.1]

        hhi_dist = _compute_herfindahl(distributed)
        hhi_conc = _compute_herfindahl(concentrated)

        assert hhi_conc > hhi_dist

    def test_herfindahl_empty(self):
        """HHI of empty list = 0."""
        assert _compute_herfindahl([]) == 0.0

    def test_top_n_share_basic(self):
        """Top N share calculation."""
        values = [100, 50, 30, 20]

        top1 = _compute_top_n_share(values, 1)
        assert abs(top1 - 0.5) < 0.001  # 100/200

        top2 = _compute_top_n_share(values, 2)
        assert abs(top2 - 0.75) < 0.001  # 150/200

    def test_top_n_share_empty(self):
        """Top N share of empty list = 0."""
        assert _compute_top_n_share([], 3) == 0.0

    def test_coefficient_of_variation(self):
        """CV calculation."""
        # All same values = 0 CV
        same = [10, 10, 10, 10]
        assert _compute_coefficient_of_variation(same) == 0.0

        # Varied values = positive CV
        varied = [5, 10, 15, 20]
        cv = _compute_coefficient_of_variation(varied)
        assert cv > 0

    def test_correlation_perfect_positive(self):
        """Perfect positive correlation = 1.0."""
        a = [1, 2, 3, 4, 5]
        b = [2, 4, 6, 8, 10]

        r = _compute_correlation(a, b)
        assert r is not None
        assert abs(r - 1.0) < 0.001

    def test_correlation_perfect_negative(self):
        """Perfect negative correlation = -1.0."""
        a = [1, 2, 3, 4, 5]
        b = [10, 8, 6, 4, 2]

        r = _compute_correlation(a, b)
        assert r is not None
        assert abs(r - (-1.0)) < 0.001

    def test_correlation_insufficient_data(self):
        """Correlation with < 4 points = None."""
        a = [1, 2, 3]
        b = [4, 5, 6]

        r = _compute_correlation(a, b)
        assert r is None

    def test_correlation_mismatched_length(self):
        """Correlation with mismatched lengths = None."""
        a = [1, 2, 3, 4, 5]
        b = [1, 2, 3]

        r = _compute_correlation(a, b)
        assert r is None

    def test_find_co_declining(self):
        """Find co-declining entities."""
        entities = [
            {"id": 1, "trend": {"direction": "declining", "magnitude_pct": -15}},
            {"id": 2, "trend": {"direction": "declining", "magnitude_pct": -20}},
            {"id": 3, "trend": {"direction": "declining", "magnitude_pct": -10}},
            {"id": 4, "trend": {"direction": "stable", "magnitude_pct": 0}},
            {"id": 5, "trend": {"direction": "growing", "magnitude_pct": 10}},
        ]

        declining = _find_co_declining(entities, min_entities=3)
        assert declining is not None
        assert len(declining) == 3

    def test_find_co_declining_insufficient(self):
        """Return None if fewer than min_entities declining."""
        entities = [
            {"id": 1, "trend": {"direction": "declining"}},
            {"id": 2, "trend": {"direction": "stable"}},
            {"id": 3, "trend": {"direction": "stable"}},
        ]

        declining = _find_co_declining(entities, min_entities=3)
        assert declining is None


# =============================================================================
# PATTERN LIBRARY TESTS
# =============================================================================

class TestPatternLibrary:
    """Tests for pattern library structure."""

    def test_library_not_empty(self):
        """Library should have patterns."""
        assert len(PATTERN_LIBRARY) >= 12

    def test_library_validation_passes(self):
        """All patterns should pass validation."""
        errors = validate_pattern_library()
        assert errors == [], f"Validation errors: {errors}"

    def test_all_types_represented(self):
        """All pattern types should have at least one pattern."""
        for ptype in PatternType:
            patterns = get_patterns_by_type(ptype)
            assert len(patterns) > 0, f"No patterns for type {ptype.value}"

    def test_get_pattern_by_id(self):
        """get_pattern should return correct pattern."""
        pattern = get_pattern("pat_revenue_concentration")
        assert pattern is not None
        assert pattern.id == "pat_revenue_concentration"

    def test_get_nonexistent_pattern(self):
        """get_pattern should return None for unknown ID."""
        pattern = get_pattern("pat_does_not_exist")
        assert pattern is None

    def test_structural_patterns_exist(self):
        """Should have structural severity patterns."""
        structural = get_structural_patterns()
        assert len(structural) >= 3

    def test_library_summary(self):
        """get_library_summary should return valid structure."""
        summary = get_library_summary()

        assert "total_patterns" in summary
        assert "by_type" in summary
        assert "by_severity" in summary
        assert summary["total_patterns"] == len(PATTERN_LIBRARY)


# =============================================================================
# PATTERN DETECTION TESTS
# =============================================================================

class TestPatternDetection:
    """Tests for pattern detection functions."""

    @pytest.fixture
    def db_path(self, fixture_db_path):
        """Use fixture DB for deterministic testing."""
        return fixture_db_path

    def test_detect_all_patterns_structure(self, db_path):
        """detect_all_patterns should return valid structure."""
        result = detect_all_patterns(db_path)

        assert "detected_at" in result
        assert "total_detected" in result
        assert "total_patterns" in result
        assert "by_type" in result
        assert "by_severity" in result
        assert "patterns" in result

        assert isinstance(result["patterns"], list)

    def test_detect_all_patterns_runs_without_crash(self, db_path):
        """Full detection should complete without errors."""
        result = detect_all_patterns(db_path)

        # Should have evaluated all patterns
        assert result["total_patterns"] == len(PATTERN_LIBRARY)

        # At least some patterns should fire on live data
        # (If zero, detection might not be working)
        # Note: It's valid for few patterns to fire on healthy data

    def test_detected_pattern_has_evidence(self, db_path):
        """Detected patterns should have complete evidence."""
        result = detect_all_patterns(db_path)

        for pattern in result["patterns"]:
            assert "pattern_id" in pattern
            assert "pattern_name" in pattern
            assert "evidence_narrative" in pattern
            assert "operational_meaning" in pattern
            assert "confidence" in pattern

            # Evidence narrative should not be empty
            assert len(pattern["evidence_narrative"]) > 0

    def test_detect_single_pattern(self, db_path):
        """detect_pattern should work for individual patterns."""
        pattern_def = get_pattern("pat_revenue_concentration")

        # Should not crash
        evidence = detect_pattern(pattern_def, db_path)

        # Evidence is either None (not detected) or PatternEvidence
        if evidence is not None:
            assert evidence.pattern_id == "pat_revenue_concentration"

    def test_pattern_evidence_to_dict(self, db_path):
        """PatternEvidence.to_dict should work."""
        result = detect_all_patterns(db_path)

        # All returned patterns should be dicts (from to_dict)
        for pattern in result["patterns"]:
            assert isinstance(pattern, dict)


# =============================================================================
# CONCENTRATION DETECTION TESTS
# =============================================================================

class TestConcentrationDetection:
    """Tests for concentration pattern detection."""

    @pytest.fixture
    def db_path(self, fixture_db_path):
        """Use fixture DB for deterministic testing."""
        return fixture_db_path

    def test_revenue_concentration_detection(self, db_path):
        """Revenue concentration should detect or not based on data."""
        pattern_def = get_pattern("pat_revenue_concentration")
        evidence = detect_pattern(pattern_def, db_path)

        if evidence:
            assert "top_1_share_pct" in evidence.metrics
            assert "herfindahl_index" in evidence.metrics


# =============================================================================
# EVIDENCE ASSEMBLY TESTS
# =============================================================================

class TestEvidenceAssembly:
    """Tests for evidence structure and content."""

    @pytest.fixture
    def db_path(self, fixture_db_path):
        """Use fixture DB for deterministic testing."""
        return fixture_db_path

    def test_evidence_has_entities(self, db_path):
        """Detected patterns should list involved entities."""
        result = detect_all_patterns(db_path)

        for pattern in result["patterns"]:
            assert "entities_involved" in pattern
            assert isinstance(pattern["entities_involved"], list)

    def test_evidence_has_metrics(self, db_path):
        """Detected patterns should have metrics."""
        result = detect_all_patterns(db_path)

        for pattern in result["patterns"]:
            assert "metrics" in pattern
            assert isinstance(pattern["metrics"], dict)

    def test_evidence_has_confidence(self, db_path):
        """Detected patterns should have confidence level."""
        result = detect_all_patterns(db_path)

        for pattern in result["patterns"]:
            assert pattern["confidence"] in ["high", "medium", "low"]
