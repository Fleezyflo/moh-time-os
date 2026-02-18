"""
Tests for Intelligence API Router.

Tests the intelligence layer functions that back the API endpoints.
Uses fixture DB to avoid determinism violations.
"""

import pytest
import tempfile
from pathlib import Path

from tests.fixtures.fixture_db import create_fixture_db


@pytest.fixture
def db_path():
    """Create fixture DB for testing (file-based, returns Path)."""
    # Create temp file
    fd, path = tempfile.mkstemp(suffix=".db")
    db_file = Path(path)

    # Create fixture DB at that path
    conn = create_fixture_db(db_file)
    conn.close()

    yield db_file

    # Cleanup
    if db_file.exists():
        db_file.unlink()


# =============================================================================
# PATTERN CATALOG TESTS (No DB needed)
# =============================================================================

class TestPatternCatalog:
    """Pattern catalog doesn't need DB."""

    def test_pattern_catalog_has_all_patterns(self):
        """pattern_catalog should have all 14 patterns."""
        from lib.intelligence.patterns import PATTERN_LIBRARY

        assert len(PATTERN_LIBRARY) == 14

    def test_pattern_catalog_structure(self):
        """Each pattern should have required fields."""
        from lib.intelligence.patterns import PATTERN_LIBRARY

        for pat_id, pat in PATTERN_LIBRARY.items():
            assert pat.id is not None
            assert pat.name is not None
            assert pat.pattern_type is not None
            assert pat.severity is not None
            assert pat.implied_action is not None


# =============================================================================
# SIGNAL CATALOG TESTS (No DB needed)
# =============================================================================

class TestSignalCatalog:
    """Signal catalog doesn't need DB."""

    def test_signal_catalog_has_all_signals(self):
        """signal_catalog should have all 21 signals."""
        from lib.intelligence.signals import SIGNAL_CATALOG

        assert len(SIGNAL_CATALOG) == 21

    def test_signal_catalog_structure(self):
        """Each signal should have required fields."""
        from lib.intelligence.signals import SIGNAL_CATALOG

        for sig_id, sig in SIGNAL_CATALOG.items():
            assert sig.id is not None
            assert sig.name is not None
            assert sig.category is not None
            assert sig.severity is not None
            assert sig.conditions is not None


# =============================================================================
# SCORING FUNCTION TESTS
# =============================================================================

class TestScoringFunctions:
    """Tests for scoring functions with fixture DB."""

    def test_score_portfolio_returns_dict(self, db_path):
        """score_portfolio should return scorecard dict."""
        from lib.intelligence import score_portfolio

        result = score_portfolio(db_path)

        assert isinstance(result, dict)

    def test_score_all_clients_returns_list(self, db_path):
        """score_all_clients should return list."""
        from lib.intelligence.scorecard import score_all_clients

        result = score_all_clients(db_path)

        assert isinstance(result, list)


# =============================================================================
# SIGNAL DETECTION TESTS
# =============================================================================

class TestSignalDetection:
    """Tests for signal detection with fixture DB."""

    def test_detect_all_signals_returns_dict(self, db_path):
        """detect_all_signals should return structured dict."""
        from lib.intelligence import detect_all_signals

        result = detect_all_signals(db_path, quick=True)

        assert isinstance(result, dict)
        assert "signals" in result or "total_signals" in result

    def test_get_signal_summary_structure(self, db_path):
        """get_signal_summary should return counts."""
        from lib.intelligence.signals import get_signal_summary

        result = get_signal_summary(db_path)

        assert isinstance(result, dict)
        assert "total_active" in result
        assert "by_severity" in result


# =============================================================================
# PATTERN DETECTION TESTS
# =============================================================================

class TestPatternDetection:
    """Tests for pattern detection with fixture DB."""

    def test_detect_all_patterns_returns_dict(self, db_path):
        """detect_all_patterns should return structured dict."""
        from lib.intelligence import detect_all_patterns

        result = detect_all_patterns(db_path)

        assert isinstance(result, dict)
        assert "patterns" in result or "total_detected" in result


# =============================================================================
# PROPOSAL GENERATION TESTS
# =============================================================================

class TestProposalGeneration:
    """Tests for proposal generation with fixture DB."""

    def test_generate_proposals_returns_list(self, db_path):
        """generate_proposals should return list."""
        from lib.intelligence import detect_all_signals, detect_all_patterns, generate_proposals

        signals = detect_all_signals(db_path, quick=True)
        patterns = detect_all_patterns(db_path)

        signal_input = {"signals": signals.get("signals", [])}
        pattern_input = {"patterns": patterns.get("patterns", [])}

        proposals = generate_proposals(signal_input, pattern_input, db_path)

        assert isinstance(proposals, list)

    def test_generate_daily_briefing_structure(self, db_path):
        """generate_daily_briefing should return complete briefing."""
        from lib.intelligence import (
            detect_all_signals,
            detect_all_patterns,
            generate_proposals,
            generate_daily_briefing,
        )

        signals = detect_all_signals(db_path, quick=True)
        patterns = detect_all_patterns(db_path)

        signal_input = {"signals": signals.get("signals", [])}
        pattern_input = {"patterns": patterns.get("patterns", [])}

        proposals = generate_proposals(signal_input, pattern_input, db_path)
        briefing = generate_daily_briefing(proposals, db_path)

        assert isinstance(briefing, dict)
        assert "summary" in briefing


# =============================================================================
# ENGINE FUNCTION TESTS
# =============================================================================

class TestEngineFunctions:
    """Tests for engine functions with fixture DB."""

    def test_get_critical_items_returns_dict_with_items(self, db_path):
        """get_critical_items should return dict with items list."""
        from lib.intelligence import get_critical_items

        result = get_critical_items(db_path)

        assert isinstance(result, dict)
        assert "items" in result
        assert isinstance(result["items"], list)

    def test_get_portfolio_intelligence_structure(self, db_path):
        """get_portfolio_intelligence should return complete structure."""
        from lib.intelligence import get_portfolio_intelligence

        result = get_portfolio_intelligence(db_path)

        assert isinstance(result, dict)
        assert "portfolio_score" in result
        assert "signal_summary" in result
        assert "top_proposals" in result


# =============================================================================
# API RESPONSE ENVELOPE TESTS (Mock-based)
# =============================================================================

class TestAPIResponseEnvelope:
    """Test API response envelope structure."""

    def test_wrap_response_structure(self):
        """_wrap_response should create standard envelope."""
        from api.intelligence_router import _wrap_response

        result = _wrap_response({"test": "data"})

        assert "status" in result
        assert "data" in result
        assert "computed_at" in result
        assert result["status"] == "ok"
        assert result["data"] == {"test": "data"}

    def test_wrap_response_with_params(self):
        """_wrap_response should include params."""
        from api.intelligence_router import _wrap_response

        result = _wrap_response({"test": "data"}, {"param1": "value1"})

        assert result["params"] == {"param1": "value1"}
