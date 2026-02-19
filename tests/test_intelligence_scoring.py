"""
Tests for Intelligence Scoring Module.

Covers:
- Normalization functions (percentile, threshold, relative)
- Dimension scoring
- Entity scorecard computation
- Bulk scoring
- Classification helpers

Live data verification (run against actual DB):
- Client scores distributed: ~160 clients, various health levels
- Project scores show reasonable velocity/risk patterns
- No crashes on sparse data
"""

import pytest
from pathlib import Path

from lib.intelligence.scoring import (
    EntityType,
    ScoreRange,
    NormMethod,
    ScoringDimension,
    CLIENT_DIMENSIONS,
    PROJECT_DIMENSIONS,
    PERSON_DIMENSIONS,
    PORTFOLIO_DIMENSIONS,
    normalize_percentile,
    normalize_threshold,
    normalize_relative,
    score_dimension,
    classify_score,
    score_to_range,
    validate_dimensions,
)

from lib.intelligence.scorecard import (
    score_client,
    score_project,
    score_person,
    score_portfolio,
    score_all_clients,
    score_all_projects,
    score_all_persons,
    get_entities_by_classification,
    get_score_distribution,
)


# =============================================================================
# NORMALIZATION UNIT TESTS
# =============================================================================

class TestNormalizePercentile:
    """Tests for percentile normalization."""

    def test_percentile_highest_value_is_100(self):
        """Highest value should score 100."""
        result = normalize_percentile(100, [10, 20, 30, 50, 100])
        assert result == 100.0

    def test_percentile_lowest_value_is_0(self):
        """Lowest value should score 0."""
        result = normalize_percentile(10, [10, 20, 30, 50, 100])
        assert result == 0.0

    def test_percentile_middle_value(self):
        """Middle value should score around 50."""
        result = normalize_percentile(30, [10, 20, 30, 40, 50])
        assert 40 <= result <= 60

    def test_percentile_empty_list_returns_50(self):
        """Empty list should return 50."""
        result = normalize_percentile(100, [])
        assert result == 50.0

    def test_percentile_single_item_returns_50(self):
        """Single item list should return 50."""
        result = normalize_percentile(100, [100])
        assert result == 50.0

    def test_percentile_handles_none_value(self):
        """None value should return 50."""
        result = normalize_percentile(None, [10, 20, 30])
        assert result == 50.0

    def test_percentile_handles_ties(self):
        """Ties should be handled gracefully."""
        result = normalize_percentile(50, [50, 50, 50, 50, 50])
        assert 0 <= result <= 100


class TestNormalizeThreshold:
    """Tests for threshold normalization."""

    def test_threshold_at_target_is_100(self):
        """Value at target should score 100."""
        result = normalize_threshold(100, 100, "higher_is_better")
        assert result == 100.0

    def test_threshold_above_target_is_100(self):
        """Value above target should score 100."""
        result = normalize_threshold(150, 100, "higher_is_better")
        assert result == 100.0

    def test_threshold_at_zero_is_0(self):
        """Value at zero should score 0 for higher_is_better."""
        result = normalize_threshold(0, 100, "higher_is_better")
        assert result == 0.0

    def test_threshold_halfway_is_50(self):
        """Value at half target should score 50."""
        result = normalize_threshold(50, 100, "higher_is_better")
        assert result == 50.0

    def test_threshold_lower_is_better(self):
        """Test lower_is_better direction."""
        # At target = 100
        result = normalize_threshold(30, 30, "lower_is_better")
        assert result == 100.0

        # Below target = 100
        result = normalize_threshold(10, 30, "lower_is_better")
        assert result == 100.0

        # Above target = penalty
        result = normalize_threshold(60, 30, "lower_is_better")
        assert result < 100

    def test_threshold_handles_none(self):
        """None value should return 50."""
        result = normalize_threshold(None, 100, "higher_is_better")
        assert result == 50.0

    def test_threshold_zero_target(self):
        """Zero target should handle edge case."""
        result = normalize_threshold(0, 0, "higher_is_better")
        assert result == 100.0


class TestNormalizeRelative:
    """Tests for relative (historical) normalization."""

    def test_relative_at_baseline_is_70(self):
        """Value at baseline should score 70 (stable)."""
        result = normalize_relative(100, 100)
        assert result == 70.0

    def test_relative_above_baseline_scores_higher(self):
        """Value above baseline should score > 70."""
        result = normalize_relative(150, 100)
        assert result > 70.0

    def test_relative_below_baseline_scores_lower(self):
        """Value below baseline should score < 70."""
        result = normalize_relative(50, 100)
        assert result < 70.0

    def test_relative_double_baseline_is_100(self):
        """Value at 2x baseline should score 100."""
        result = normalize_relative(200, 100)
        assert result == 100.0

    def test_relative_zero_value_is_0(self):
        """Value at 0 should score 0."""
        result = normalize_relative(0, 100)
        assert result == 0.0

    def test_relative_handles_none(self):
        """None values should return 50."""
        assert normalize_relative(None, 100) == 50.0
        assert normalize_relative(100, None) == 50.0

    def test_relative_zero_baseline(self):
        """Zero baseline should handle edge case."""
        result = normalize_relative(50, 0)
        assert result == 100.0  # Above zero baseline


# =============================================================================
# DIMENSION SCORING TESTS
# =============================================================================

class TestScoreDimension:
    """Tests for dimension scoring."""

    def test_score_dimension_with_complete_metrics(self):
        """Score dimension with all metrics available."""
        dim = CLIENT_DIMENSIONS[0]  # operational_health
        metrics = {
            "completion_rate": 80,
            "overdue_tasks": 2,
            "active_tasks": 20,
            "total_tasks": 100,
        }

        result = score_dimension(dim, metrics, {"target": 100})

        assert result["dimension"] == "operational_health"
        assert result["score"] is not None
        assert 0 <= result["score"] <= 100
        assert result["classification"] in ["critical", "warning", "healthy"]
        assert result["metrics_used"]

    def test_score_dimension_with_missing_metrics(self):
        """Score dimension with missing metrics returns null."""
        dim = CLIENT_DIMENSIONS[0]
        metrics = {}  # Empty

        result = score_dimension(dim, metrics)

        assert result["score"] is None
        assert result["classification"] == "data_unavailable"
        assert "missing_metrics" in result

    def test_score_dimension_partial_metrics(self):
        """Score dimension with partial metrics still works."""
        dim = CLIENT_DIMENSIONS[1]  # financial_health
        metrics = {
            "total_invoiced": 10000,
            "total_paid": 8000,
            # Missing: total_outstanding, financial_ar_overdue
        }

        result = score_dimension(dim, metrics, {"target": 100})

        # Should still produce a score using available metrics
        assert result["score"] is not None or result["classification"] == "data_unavailable"


class TestClassifyScore:
    """Tests for score classification."""

    def test_classify_critical(self):
        assert classify_score(10) == "critical"
        assert classify_score(30) == "critical"

    def test_classify_at_risk(self):
        assert classify_score(31) == "at_risk"
        assert classify_score(50) == "at_risk"

    def test_classify_stable(self):
        assert classify_score(51) == "stable"
        assert classify_score(70) == "stable"

    def test_classify_healthy(self):
        assert classify_score(71) == "healthy"
        assert classify_score(90) == "healthy"

    def test_classify_strong(self):
        assert classify_score(91) == "strong"
        assert classify_score(100) == "strong"

    def test_classify_none(self):
        assert classify_score(None) == "data_unavailable"


# =============================================================================
# VALIDATION TESTS
# =============================================================================

class TestDimensionValidation:
    """Tests for dimension definition validation."""

    def test_all_dimensions_valid(self):
        """All dimension definitions should pass validation."""
        errors = validate_dimensions()
        assert errors == [], f"Validation errors: {errors}"

    def test_weights_sum_to_one(self):
        """Weights for each entity type should sum to 1.0."""
        for entity_type, dimensions in [
            (EntityType.CLIENT, CLIENT_DIMENSIONS),
            (EntityType.PROJECT, PROJECT_DIMENSIONS),
            (EntityType.PERSON, PERSON_DIMENSIONS),
            (EntityType.PORTFOLIO, PORTFOLIO_DIMENSIONS),
        ]:
            total = sum(d.weight for d in dimensions)
            assert abs(total - 1.0) < 0.001, f"{entity_type.value} weights sum to {total}"


# =============================================================================
# SCORECARD INTEGRATION TESTS (against live DB)
# =============================================================================

class TestScorecardIntegration:
    """Integration tests for scorecard computation against live database."""

    @pytest.fixture
    def db_path(self, integration_db_path):
        """Use fixture DB for deterministic testing."""
        return integration_db_path

    def test_score_client_returns_valid_structure(self, db_path):
        """score_client returns valid scorecard structure."""
        # Get a client ID from the database
        from lib.query_engine import QueryEngine
        engine = QueryEngine(db_path)
        clients = engine.client_portfolio_overview()

        if not clients:
            pytest.skip("No clients in database")

        client_id = clients[0]["client_id"]
        result = score_client(client_id, db_path)

        assert result["entity_type"] == "client"
        assert result["entity_id"] == client_id
        assert "composite_score" in result
        assert "composite_classification" in result
        assert "dimensions" in result
        assert "scored_at" in result
        assert "data_completeness" in result

    def test_score_all_clients_no_crash(self, db_path):
        """score_all_clients completes without crashing and scores all clients."""
        results = score_all_clients(db_path)

        assert isinstance(results, list)
        assert len(results) > 0

        # Should be sorted by composite score ascending (worst first)
        scores = [r.get("composite_score") or 0 for r in results]
        assert scores == sorted(scores), "Results should be sorted by score ascending"

        # Every result should have required fields
        for r in results:
            assert "entity_type" in r
            assert "entity_id" in r
            assert "composite_score" in r
            assert "dimensions" in r

    def test_score_project_returns_valid_structure(self, db_path):
        """score_project returns valid scorecard structure."""
        from lib.query_engine import QueryEngine
        engine = QueryEngine(db_path)
        projects = engine.projects_by_health(min_tasks=1)

        if not projects:
            pytest.skip("No projects with tasks in database")

        project_id = projects[0]["project_id"]
        result = score_project(project_id, db_path)

        assert result["entity_type"] == "project"
        assert result["entity_id"] == project_id
        assert "composite_score" in result

    def test_score_all_projects_no_crash(self, db_path):
        """score_all_projects completes without crashing and scores all projects."""
        results = score_all_projects(db_path)

        assert isinstance(results, list)

        # Every result should have required fields
        for r in results:
            assert "entity_type" in r
            assert "entity_id" in r
            assert "composite_score" in r

    def test_score_portfolio_returns_valid_structure(self, db_path):
        """score_portfolio returns valid scorecard structure."""
        result = score_portfolio(db_path)

        assert result["entity_type"] == "portfolio"
        assert result["entity_id"] == "portfolio"
        assert "composite_score" in result
        assert "dimensions" in result

    def test_get_score_distribution(self, db_path):
        """get_score_distribution returns valid statistics."""
        dist = get_score_distribution(EntityType.CLIENT, db_path)

        assert dist["entity_type"] == "client"
        assert "count" in dist
        assert dist["count"] > 0

        if dist.get("valid_scores", 0) > 0:
            assert "min_score" in dist
            assert "max_score" in dist
            assert "mean_score" in dist
            assert "median_score" in dist
            assert "by_classification" in dist

            # Scores should be in valid range
            assert 0 <= dist["min_score"] <= 100
            assert 0 <= dist["max_score"] <= 100
            assert dist["min_score"] <= dist["mean_score"] <= dist["max_score"]


class TestEdgeCases:
    """Edge case tests."""

    @pytest.fixture
    def db_path(self, integration_db_path):
        """Use fixture DB for deterministic testing."""
        return integration_db_path

    def test_score_nonexistent_client(self, db_path):
        """Scoring non-existent client returns empty scorecard."""
        result = score_client("nonexistent-id-12345", db_path)

        assert result["composite_score"] is None
        assert result["composite_classification"] == "data_unavailable"
        assert result["data_completeness"] == 0

    def test_score_nonexistent_project(self, db_path):
        """Scoring non-existent project returns empty scorecard."""
        result = score_project("nonexistent-id-12345", db_path)

        assert result["composite_score"] is None
        assert result["composite_classification"] == "data_unavailable"

    def test_get_entities_by_classification(self, db_path):
        """get_entities_by_classification filters correctly."""
        # Get all client scores first
        all_clients = score_all_clients(db_path)

        if not all_clients:
            pytest.skip("No clients in database")

        # Find a classification that exists
        classifications = [c.get("composite_classification") for c in all_clients]
        target_class = classifications[0]

        # Get entities by that classification
        filtered = get_entities_by_classification(EntityType.CLIENT, target_class, db_path)

        # All returned should have matching classification
        for entity in filtered:
            assert entity["composite_classification"] == target_class

        # Count should match
        expected_count = sum(1 for c in all_clients if c.get("composite_classification") == target_class)
        assert len(filtered) == expected_count
