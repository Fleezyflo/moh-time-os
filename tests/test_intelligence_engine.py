"""
Tests for Intelligence Engine Module.

Covers:
- Full pipeline execution
- Error isolation
- Targeted intelligence functions
- Data validation

Uses fixture DB for deterministic testing.
"""

from pathlib import Path

import pytest

from lib.intelligence.engine import (
    _compute_data_completeness,
    _count_entities,
    _run_pattern_stage,
    _run_proposal_stage,
    _run_scoring_stage,
    _run_signal_stage,
    generate_intelligence_snapshot,
    get_client_intelligence,
    get_critical_items,
    get_person_intelligence,
    get_portfolio_intelligence,
)

# =============================================================================
# PIPELINE TESTS
# =============================================================================


class TestIntelligencePipeline:
    """Tests for the full intelligence pipeline."""

    @pytest.fixture
    def db_path(self, fixture_db_path):
        """Use fixture DB for deterministic testing."""
        return fixture_db_path

    def test_snapshot_has_required_keys(self, db_path):
        """Snapshot should contain all top-level keys."""
        snapshot = generate_intelligence_snapshot(db_path)

        required_keys = [
            "generated_at",
            "generation_time_seconds",
            "scores",
            "signals",
            "patterns",
            "proposals",
            "briefing",
            "meta",
        ]

        for key in required_keys:
            assert key in snapshot, f"Missing key: {key}"

    def test_snapshot_scores_structure(self, db_path):
        """Scores section should have entity type keys."""
        snapshot = generate_intelligence_snapshot(db_path)

        scores = snapshot["scores"]
        assert "clients" in scores
        assert "projects" in scores
        assert "persons" in scores
        assert "portfolio" in scores

    def test_snapshot_meta_has_counts(self, db_path):
        """Meta section should have entity counts."""
        snapshot = generate_intelligence_snapshot(db_path)

        meta = snapshot["meta"]
        assert "entities_scored" in meta
        assert "signals_evaluated" in meta
        assert "patterns_evaluated" in meta
        assert "data_completeness" in meta

        # Should have scored some entities
        assert meta["entities_scored"]["clients"] >= 0

    def test_snapshot_generation_time_recorded(self, db_path):
        """Generation time should be recorded."""
        snapshot = generate_intelligence_snapshot(db_path)

        assert snapshot["generation_time_seconds"] > 0
        assert snapshot["generation_time_seconds"] < 300  # Should complete in <5min


# =============================================================================
# STAGE TESTS
# =============================================================================


class TestPipelineStages:
    """Tests for individual pipeline stages."""

    @pytest.fixture
    def db_path(self, fixture_db_path):
        """Use fixture DB for deterministic testing."""
        return fixture_db_path

    def test_scoring_stage_returns_dict(self, db_path):
        """Scoring stage should return dict with entity types."""
        result = _run_scoring_stage(db_path)

        assert isinstance(result, dict)
        assert "clients" in result
        assert "projects" in result
        assert "persons" in result
        assert "portfolio" in result

    def test_signal_stage_returns_dict(self, db_path):
        """Signal stage should return structured dict."""
        result = _run_signal_stage(db_path)

        assert isinstance(result, dict)
        assert "total_active" in result
        assert "by_severity" in result

    def test_pattern_stage_returns_dict(self, db_path):
        """Pattern stage should return structured dict."""
        result = _run_pattern_stage(db_path)

        assert isinstance(result, dict)
        assert "total_detected" in result
        assert "structural" in result
        assert "operational" in result


# =============================================================================
# ERROR ISOLATION TESTS
# =============================================================================


class TestErrorIsolation:
    """Tests for error isolation in the pipeline."""

    def test_scoring_stage_doesnt_crash_on_missing_db(self):
        """Scoring should return error dict, not crash."""
        result = _run_scoring_stage(Path("/nonexistent/path.db"))

        # Should return dict with error indicators, not raise
        assert isinstance(result, dict)

    def test_signal_stage_doesnt_crash_on_missing_db(self):
        """Signal stage should return error dict, not crash."""
        result = _run_signal_stage(Path("/nonexistent/path.db"))

        assert isinstance(result, dict)

    def test_pattern_stage_doesnt_crash_on_missing_db(self):
        """Pattern stage should return error dict, not crash."""
        result = _run_pattern_stage(Path("/nonexistent/path.db"))

        assert isinstance(result, dict)


# =============================================================================
# TARGETED INTELLIGENCE TESTS
# =============================================================================


class TestTargetedIntelligence:
    """Tests for targeted intelligence functions."""

    @pytest.fixture
    def db_path(self, fixture_db_path):
        """Use fixture DB for deterministic testing."""
        return fixture_db_path

    def test_client_intelligence_structure(self, db_path):
        """get_client_intelligence should return complete structure."""
        from lib.query_engine import QueryEngine

        engine = QueryEngine(db_path)
        clients = engine.client_portfolio_overview()

        if not clients:
            pytest.skip("No clients in database")

        client_id = clients[0]["client_id"]
        intel = get_client_intelligence(client_id, db_path)

        assert "client_id" in intel
        assert "scorecard" in intel
        assert "active_signals" in intel
        assert "signal_history" in intel

    def test_person_intelligence_structure(self, db_path):
        """get_person_intelligence should return complete structure."""
        from lib.query_engine import QueryEngine

        engine = QueryEngine(db_path)
        people = engine.resource_load_distribution()

        if not people:
            pytest.skip("No people in database")

        person_id = people[0]["person_id"]
        intel = get_person_intelligence(person_id, db_path)

        assert "person_id" in intel
        assert "scorecard" in intel
        assert "active_signals" in intel

    def test_portfolio_intelligence_structure(self, db_path):
        """get_portfolio_intelligence should return complete structure."""
        intel = get_portfolio_intelligence(db_path)

        assert "portfolio_score" in intel
        assert "signal_summary" in intel
        assert "structural_patterns" in intel
        assert "top_proposals" in intel

    def test_critical_items_returns_list(self, db_path):
        """get_critical_items should return list."""
        items = get_critical_items(db_path)

        assert isinstance(items, list)

        # Items should have expected structure
        for item in items:
            assert "headline" in item
            assert "entity" in item
            assert "implied_action" in item


# =============================================================================
# DATA VALIDATION TESTS
# =============================================================================


class TestDataValidation:
    """Tests for data integrity and validation."""

    @pytest.fixture
    def db_path(self, fixture_db_path):
        """Use fixture DB for deterministic testing."""
        return fixture_db_path

    def test_proposals_are_ranked(self, db_path):
        """Proposals in snapshot should be sorted by priority."""
        snapshot = generate_intelligence_snapshot(db_path)

        ranked = snapshot["proposals"]["ranked"]

        if len(ranked) >= 2:
            # Check that priority scores are descending
            scores = [p.get("priority_score", {}).get("raw_score", 0) for p in ranked]
            assert scores == sorted(scores, reverse=True)

    def test_briefing_has_summary(self, db_path):
        """Briefing should have summary counts."""
        snapshot = generate_intelligence_snapshot(db_path)

        briefing = snapshot["briefing"]

        if briefing:  # May be empty if no proposals
            assert "summary" in briefing or briefing == {}

    def test_data_completeness_is_valid(self, db_path):
        """Data completeness should be between 0 and 1."""
        snapshot = generate_intelligence_snapshot(db_path)

        completeness = snapshot["meta"]["data_completeness"]

        assert 0 <= completeness <= 1


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestHelperFunctions:
    """Tests for engine helper functions."""

    def test_compute_data_completeness_empty(self):
        """Empty scores should return 0."""
        completeness = _compute_data_completeness({})
        assert completeness == 0.0

    def test_count_entities_empty(self):
        """Empty scores should return zero counts."""
        counts = _count_entities({})

        assert counts["clients"] == 0
        assert counts["projects"] == 0
        assert counts["persons"] == 0

    def test_count_entities_with_data(self):
        """Should count entities correctly."""
        scores = {
            "clients": [{"id": 1}, {"id": 2}, {"id": 3}],
            "projects": [{"id": 1}],
            "persons": [{"id": 1}, {"id": 2}],
        }

        counts = _count_entities(scores)

        assert counts["clients"] == 3
        assert counts["projects"] == 1
        assert counts["persons"] == 2


# =============================================================================
# PUBLIC API TESTS
# =============================================================================


class TestPublicAPI:
    """Tests for the public API via __init__.py."""

    def test_imports_work(self):
        """All public API imports should work."""
        from lib.intelligence import (
            detect_all_patterns,
            detect_all_signals,
            generate_daily_briefing,
            generate_intelligence_snapshot,
            generate_proposals,
            get_client_intelligence,
            get_critical_items,
            get_person_intelligence,
            get_portfolio_intelligence,
            rank_proposals,
            score_client,
        )

        # All should be callable
        assert callable(generate_intelligence_snapshot)
        assert callable(get_client_intelligence)
        assert callable(score_client)
        assert callable(detect_all_signals)
