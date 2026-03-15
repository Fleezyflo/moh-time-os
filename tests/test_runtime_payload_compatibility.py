"""
Runtime payload compatibility tests for canonical intelligence routes.

Uses FastAPI TestClient with mocked backend functions to prove the actual
mounted app serves JSON payloads that match what the UI consumers expect.

This is NOT source inspection — every assertion is on a real HTTP response body.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import lib.paths  # noqa: E402
from tests.fixtures.fixture_db import create_fixture_db  # noqa: E402

# ---------------------------------------------------------------------------
# Mock data — shapes match what the backend libs actually return
# ---------------------------------------------------------------------------

MOCK_SCORECARD = {
    "entity_type": "client",
    "entity_id": "c-101",
    "entity_name": "Acme Corp",
    "composite_score": 72.5,
    "composite_classification": "healthy",
    "dimensions": [
        {
            "dimension": "Operational Health",
            "score": 80,
            "classification": "healthy",
            "metrics_used": {},
            "normalization": "percentile",
        },
        {
            "dimension": "Financial Health",
            "score": 45,
            "classification": "warning",
            "metrics_used": {},
            "normalization": "threshold",
        },
    ],
    "scored_at": "2026-03-16T10:00:00+00:00",
    "data_completeness": 1.0,
}

MOCK_PROJECT_SCORECARD = {
    "entity_type": "project",
    "entity_id": "p-201",
    "entity_name": "Widget Redesign",
    "composite_score": 65.0,
    "composite_classification": "at_risk",
    "dimensions": [
        {
            "dimension": "Velocity",
            "score": 70,
            "classification": "healthy",
            "metrics_used": {},
            "normalization": "percentile",
        },
    ],
    "scored_at": "2026-03-16T10:00:00+00:00",
    "data_completeness": 1.0,
}

MOCK_PERSON_SCORECARD = {
    "entity_type": "person",
    "entity_id": "per-301",
    "entity_name": "Jane Doe",
    "composite_score": 88.0,
    "composite_classification": "healthy",
    "dimensions": [
        {
            "dimension": "Load Balance",
            "score": 90,
            "classification": "healthy",
            "metrics_used": {},
            "normalization": "percentile",
        },
    ],
    "scored_at": "2026-03-16T10:00:00+00:00",
    "data_completeness": 1.0,
}

MOCK_PORTFOLIO_SCORECARD = {
    "entity_type": "portfolio",
    "entity_id": "all",
    "entity_name": "Portfolio",
    "composite_score": 60.0,
    "composite_classification": "at_risk",
    "dimensions": [
        {
            "dimension": "Revenue Concentration",
            "score": 55,
            "classification": "warning",
            "metrics_used": {},
            "normalization": "threshold",
        },
    ],
    "scored_at": "2026-03-16T10:00:00+00:00",
    "data_completeness": 1.0,
}

MOCK_CLIENT_INTELLIGENCE = {
    "client_id": "c-101",
    "generated_at": "2026-03-16T10:00:00+00:00",
    "success": True,
    "errors": [],
    "scorecard": dict(MOCK_SCORECARD),
    "active_signals": [],
    "signal_history": [],
    "trajectory": {},
    "proposals": [],
}

MOCK_PERSON_INTELLIGENCE = {
    "person_id": "per-301",
    "generated_at": "2026-03-16T10:00:00+00:00",
    "success": True,
    "errors": [],
    "scorecard": dict(MOCK_PERSON_SCORECARD),
    "active_signals": [],
    "signal_history": [],
    "operational_profile": {},
}

MOCK_PORTFOLIO_INTELLIGENCE = {
    "generated_at": "2026-03-16T10:00:00+00:00",
    "success": True,
    "errors": [],
    "portfolio_score": dict(MOCK_PORTFOLIO_SCORECARD),
    "signal_summary": {},
    "structural_patterns": [],
    "top_proposals": [],
}

MOCK_SIGNAL_HISTORY = [
    {"signal_id": f"sig-{i}", "entity_type": "client", "entity_id": "c-101"} for i in range(100)
]

MOCK_PATTERN_DETECTION = {
    "detected_at": "2026-03-16T10:00:00+00:00",
    "success": True,
    "total_detected": 2,
    "total_patterns": 10,
    "detection_errors": 0,
    "errors": [],
    "by_type": {},
    "by_severity": {},
    "patterns": [
        {
            "pattern_id": "conc-rev-001",
            "pattern_name": "Revenue Concentration",
            "pattern_type": "concentration",
            "severity": "warning",
            "detected_at": "2026-03-16T10:00:00+00:00",
            "entities_involved": ["c-101", "c-102"],
            "metrics": {"top_client_pct": 0.65},
            "supporting_signals": [],
            "evidence_narrative": "Top client represents 65% of revenue",
            "operational_meaning": "High dependency on a single client",
            "implied_action": "Diversify revenue sources",
            "confidence": "high",
        },
        {
            "pattern_id": "deg-qual-002",
            "pattern_name": "Quality Degradation",
            "pattern_type": "degradation",
            "severity": "critical",
            "detected_at": "2026-03-16T10:00:00+00:00",
            "entities_involved": ["p-201"],
            "metrics": {"defect_rate_trend": "increasing"},
            "supporting_signals": [],
            "evidence_narrative": "Defect rate increasing over 3 sprints",
            "operational_meaning": "Quality is declining for this project",
            "implied_action": "Review QA process",
            "confidence": "medium",
        },
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fixture_db_path(tmp_path_factory):
    """Create a fixture DB for the module."""
    tmp_path = tmp_path_factory.mktemp("runtime_payload")
    db_path = tmp_path / "fixture.db"
    conn = create_fixture_db(db_path)
    conn.close()
    return db_path


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped monkeypatch."""
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def test_client(fixture_db_path, monkeypatch_module):
    """TestClient with fixture DB injected before app import."""
    monkeypatch_module.setattr(lib.paths, "db_path", lambda: fixture_db_path)
    monkeypatch_module.setattr(lib.paths, "data_dir", lambda: fixture_db_path.parent)

    from api.server import app

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_scorecard_ui_shape(scorecard: dict, context: str) -> None:
    """Assert a scorecard dict has the shape the UI Scorecard component expects."""
    assert "computed_at" in scorecard, f"{context}: missing computed_at"
    dims = scorecard.get("dimensions")
    assert isinstance(dims, dict), (
        f"{context}: dimensions should be a dict/Record, got {type(dims).__name__}"
    )
    for key, dim in dims.items():
        assert "name" in dim, f"{context}: dimension '{key}' missing 'name'"
        assert "score" in dim, f"{context}: dimension '{key}' missing 'score'"
        assert "status" in dim, f"{context}: dimension '{key}' missing 'status'"


# ---------------------------------------------------------------------------
# /api/v2/intelligence/patterns — canonical owner is spec_router
# ---------------------------------------------------------------------------


class TestPatternsPayload:
    """Prove /patterns serves UI-compatible pattern fields via real HTTP response."""

    def test_patterns_payload_has_ui_fields(self, test_client):
        with patch(
            "lib.intelligence.patterns.detect_all_patterns",
            return_value=MOCK_PATTERN_DETECTION,
        ):
            resp = test_client.get("/api/v2/intelligence/patterns")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"

        patterns = body["data"]["patterns"]
        assert len(patterns) == 2

        for p in patterns:
            # UI Pattern interface fields
            assert "name" in p, f"missing 'name' in pattern {p.get('pattern_id')}"
            assert "type" in p, f"missing 'type' in pattern {p.get('pattern_id')}"
            assert "affected_entities" in p, (
                f"missing 'affected_entities' in pattern {p.get('pattern_id')}"
            )
            assert "description" in p, f"missing 'description' in pattern {p.get('pattern_id')}"

        # Verify actual mapped values
        p0 = patterns[0]
        assert p0["name"] == "Revenue Concentration"
        assert p0["type"] == "concentration"
        assert p0["affected_entities"] == ["c-101", "c-102"]
        assert p0["description"] == "High dependency on a single client"

        # Original backend fields preserved
        assert p0["pattern_name"] == "Revenue Concentration"
        assert p0["pattern_type"] == "concentration"
        assert p0["entities_involved"] == ["c-101", "c-102"]

    def test_patterns_response_has_detection_metadata(self, test_client):
        with patch(
            "lib.intelligence.patterns.detect_all_patterns",
            return_value=MOCK_PATTERN_DETECTION,
        ):
            resp = test_client.get("/api/v2/intelligence/patterns")

        body = resp.json()
        data = body["data"]
        # PatternDetectionResponse fields
        assert "detection_success" in data
        assert "detection_errors" in data
        assert "total_detected" in data


# ---------------------------------------------------------------------------
# /api/v2/intelligence/scores/* — computed_at + dimensions normalization
# ---------------------------------------------------------------------------


class TestScorePayloads:
    """Prove all 4 score endpoints serve UI-compatible scorecard shapes."""

    def test_client_score_payload(self, test_client):
        with patch(
            "lib.intelligence.score_client",
            return_value=dict(MOCK_SCORECARD),
        ):
            resp = test_client.get("/api/v2/intelligence/scores/client/c-101")

        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        _assert_scorecard_ui_shape(data, "/scores/client")

        # Verify actual dimension content
        assert "Operational Health" in data["dimensions"]
        oh = data["dimensions"]["Operational Health"]
        assert oh["name"] == "Operational Health"
        assert oh["score"] == 80
        assert oh["status"] == "healthy"

    def test_project_score_payload(self, test_client):
        with patch(
            "lib.intelligence.score_project",
            return_value=dict(MOCK_PROJECT_SCORECARD),
        ):
            resp = test_client.get("/api/v2/intelligence/scores/project/p-201")

        assert resp.status_code == 200
        data = resp.json()["data"]
        _assert_scorecard_ui_shape(data, "/scores/project")

    def test_person_score_payload(self, test_client):
        with patch(
            "lib.intelligence.score_person",
            return_value=dict(MOCK_PERSON_SCORECARD),
        ):
            resp = test_client.get("/api/v2/intelligence/scores/person/per-301")

        assert resp.status_code == 200
        data = resp.json()["data"]
        _assert_scorecard_ui_shape(data, "/scores/person")

    def test_portfolio_score_payload(self, test_client):
        with patch(
            "lib.intelligence.score_portfolio",
            return_value=dict(MOCK_PORTFOLIO_SCORECARD),
        ):
            resp = test_client.get("/api/v2/intelligence/scores/portfolio")

        assert resp.status_code == 200
        data = resp.json()["data"]
        _assert_scorecard_ui_shape(data, "/scores/portfolio")


# ---------------------------------------------------------------------------
# /api/v2/intelligence/entity/* — embedded scorecard normalization
# ---------------------------------------------------------------------------


class TestEntityIntelligencePayloads:
    """Prove entity intelligence responses have normalized embedded scorecards."""

    def test_client_intelligence_payload(self, test_client):
        mock_data = {
            k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
            for k, v in MOCK_CLIENT_INTELLIGENCE.items()
        }
        # Ensure nested scorecard is a fresh copy with original backend shape
        mock_data["scorecard"] = dict(MOCK_SCORECARD)

        with patch(
            "lib.intelligence.get_client_intelligence",
            return_value=mock_data,
        ):
            resp = test_client.get("/api/v2/intelligence/entity/client/c-101")

        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        scorecard = data["scorecard"]
        _assert_scorecard_ui_shape(scorecard, "/entity/client scorecard")

    def test_person_intelligence_payload(self, test_client):
        mock_data = {
            k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
            for k, v in MOCK_PERSON_INTELLIGENCE.items()
        }
        mock_data["scorecard"] = dict(MOCK_PERSON_SCORECARD)

        with patch(
            "lib.intelligence.get_person_intelligence",
            return_value=mock_data,
        ):
            resp = test_client.get("/api/v2/intelligence/entity/person/per-301")

        assert resp.status_code == 200
        data = resp.json()["data"]
        scorecard = data["scorecard"]
        _assert_scorecard_ui_shape(scorecard, "/entity/person scorecard")

    def test_portfolio_intelligence_payload(self, test_client):
        mock_data = {
            k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
            for k, v in MOCK_PORTFOLIO_INTELLIGENCE.items()
        }
        mock_data["portfolio_score"] = dict(MOCK_PORTFOLIO_SCORECARD)

        with patch(
            "lib.intelligence.get_portfolio_intelligence",
            return_value=mock_data,
        ):
            resp = test_client.get("/api/v2/intelligence/entity/portfolio")

        assert resp.status_code == 200
        data = resp.json()["data"]
        portfolio_score = data["portfolio_score"]
        _assert_scorecard_ui_shape(portfolio_score, "/entity/portfolio portfolio_score")


# ---------------------------------------------------------------------------
# /api/v2/intelligence/signals/history — limit enforcement
# ---------------------------------------------------------------------------


class TestSignalHistoryPayload:
    """Prove signal_history respects limit without crashing."""

    def test_signal_history_respects_limit(self, test_client):
        with patch(
            "lib.intelligence.signals.get_signal_history",
            return_value=list(MOCK_SIGNAL_HISTORY),
        ):
            resp = test_client.get(
                "/api/v2/intelligence/signals/history?entity_type=client&entity_id=c-101&limit=10"
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) == 10, f"Expected 10 items (limit=10 from 100 total), got {len(data)}"

    def test_signal_history_default_limit(self, test_client):
        with patch(
            "lib.intelligence.signals.get_signal_history",
            return_value=list(MOCK_SIGNAL_HISTORY),
        ):
            resp = test_client.get(
                "/api/v2/intelligence/signals/history?entity_type=client&entity_id=c-101"
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) == 50, f"Expected 50 items (default limit from 100 total), got {len(data)}"
