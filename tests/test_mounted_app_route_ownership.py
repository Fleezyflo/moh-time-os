"""
Tests proving canonical route ownership at the mounted FastAPI app level.

Unlike test_canonical_route_ownership.py (which proves module-level ownership via
source inspection), these tests import the actual FastAPI app object and verify
that route resolution works correctly when both routers are mounted.

This proves:
1. intelligence_router handlers serve /api/v2/intelligence/* for all canonical paths
2. spec_router's /intelligence/patterns handler is the one actually registered
   (not intelligence_router's — which was removed)
3. No duplicate route registrations exist for the same path
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("MOH_TIME_OS_ENV", "test")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import lib.paths  # noqa: E402
from tests.fixtures.fixture_db import create_fixture_db  # noqa: E402


@pytest.fixture(scope="module")
def fixture_db_path(tmp_path_factory):
    """Create a fixture DB for the module."""
    tmp_path = tmp_path_factory.mktemp("mounted_app_routes")
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
def app_routes(fixture_db_path, monkeypatch_module):
    """Extract all routes from the mounted FastAPI app."""
    monkeypatch_module.setattr(lib.paths, "db_path", lambda: fixture_db_path)
    monkeypatch_module.setattr(lib.paths, "data_dir", lambda: fixture_db_path.parent)

    from api.server import app

    # Build a mapping of (method, path) → endpoint function name
    route_map = {}
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                key = (method, route.path)
                route_map[key] = {
                    "endpoint_name": route.endpoint.__name__,
                    "endpoint_module": route.endpoint.__module__,
                    "path": route.path,
                }
    return route_map


class TestMountedRouteResolution:
    """Prove the mounted app resolves intelligence routes to the correct handlers."""

    # Canonical intelligence routes that intelligence_router must own
    INTELLIGENCE_ROUTER_PATHS = [
        "/api/v2/intelligence/critical",
        "/api/v2/intelligence/briefing",
        "/api/v2/intelligence/signals",
        "/api/v2/intelligence/signals/summary",
        "/api/v2/intelligence/signals/active",
        "/api/v2/intelligence/signals/history",
        "/api/v2/intelligence/patterns/catalog",
        "/api/v2/intelligence/proposals",
        "/api/v2/intelligence/scores/client/{client_id}",
        "/api/v2/intelligence/scores/project/{project_id}",
        "/api/v2/intelligence/scores/person/{person_id}",
        "/api/v2/intelligence/scores/portfolio",
        "/api/v2/intelligence/entity/client/{client_id}",
        "/api/v2/intelligence/entity/person/{person_id}",
        "/api/v2/intelligence/entity/portfolio",
        "/api/v2/intelligence/projects/{project_id}/state",
        "/api/v2/intelligence/clients/{client_id}/profile",
        "/api/v2/intelligence/clients/{client_id}/trajectory",
        "/api/v2/intelligence/team/{person_id}/profile",
        "/api/v2/intelligence/team/{person_id}/trajectory",
    ]

    def test_intelligence_routes_resolve_to_intelligence_router(self, app_routes):
        """All canonical intelligence routes resolve to intelligence_router module."""
        missing = []
        wrong_module = []

        for path in self.INTELLIGENCE_ROUTER_PATHS:
            key = ("GET", path)
            if key not in app_routes:
                missing.append(path)
                continue
            route_info = app_routes[key]
            if route_info["endpoint_module"] != "api.intelligence_router":
                wrong_module.append(
                    f"{path} → {route_info['endpoint_module']}.{route_info['endpoint_name']}"
                )

        assert not missing, f"Routes not found in mounted app: {missing}"
        assert not wrong_module, (
            f"Routes resolve to wrong module (expected api.intelligence_router): {wrong_module}"
        )

    def test_patterns_resolves_to_spec_router(self, app_routes):
        """/api/v2/intelligence/patterns must resolve to spec_router (PatternDetectionResponse)."""
        key = ("GET", "/api/v2/intelligence/patterns")
        assert key in app_routes, "/api/v2/intelligence/patterns not found in mounted app routes"
        route_info = app_routes[key]
        assert route_info["endpoint_module"] == "api.spec_router", (
            f"/api/v2/intelligence/patterns should be served by spec_router "
            f"(PatternDetectionResponse), but resolves to "
            f"{route_info['endpoint_module']}.{route_info['endpoint_name']}"
        )
        assert route_info["endpoint_name"] == "get_intelligence_patterns", (
            f"Expected handler get_intelligence_patterns, got {route_info['endpoint_name']}"
        )

    def test_no_duplicate_intelligence_route_registrations(self, app_routes):
        """No intelligence path should be registered by both routers."""
        # Collect all /api/v2/intelligence/* routes
        from api.server import app

        intel_routes_by_path: dict[str, list[str]] = {}
        for route in app.routes:
            if hasattr(route, "path") and "/api/v2/intelligence" in route.path:
                module = route.endpoint.__module__
                path = route.path
                intel_routes_by_path.setdefault(path, []).append(module)

        duplicates = {
            path: modules for path, modules in intel_routes_by_path.items() if len(set(modules)) > 1
        }
        assert not duplicates, f"Duplicate route registrations from different modules: {duplicates}"

    def test_patterns_uses_pattern_detection_response_model(self, app_routes):
        """The /patterns route must use PatternDetectionResponse, not IntelligenceResponse."""
        from api.server import app

        for route in app.routes:
            if hasattr(route, "path") and route.path == "/api/v2/intelligence/patterns":
                # FastAPI stores response_model info on the route
                response_model = getattr(route, "response_model", None)
                if response_model is not None:
                    assert response_model.__name__ == "PatternDetectionResponse", (
                        f"/api/v2/intelligence/patterns uses {response_model.__name__}, "
                        f"expected PatternDetectionResponse"
                    )
                return

        pytest.fail("/api/v2/intelligence/patterns route not found in app")


class TestConsumerCompatibility:
    """Prove the UI API client's fetch calls align with mounted app routes.

    Every path in time-os-ui/src/intelligence/api.ts that calls
    fetchJson(`${API_BASE}/...`) must have a corresponding GET route
    registered in the mounted app at /api/v2/intelligence/....
    """

    # All paths called by api.ts (extracted from fetchJson calls).
    # Path parameters are expressed as FastAPI path param syntax.
    UI_API_PATHS = [
        # Primary
        "/api/v2/intelligence/critical",
        "/api/v2/intelligence/briefing",
        # Signals
        "/api/v2/intelligence/signals",
        "/api/v2/intelligence/signals/summary",
        "/api/v2/intelligence/signals/active",
        "/api/v2/intelligence/signals/history",
        # Patterns
        "/api/v2/intelligence/patterns",
        "/api/v2/intelligence/patterns/catalog",
        # Proposals
        "/api/v2/intelligence/proposals",
        # Scores
        "/api/v2/intelligence/scores/client/{client_id}",
        "/api/v2/intelligence/scores/project/{project_id}",
        "/api/v2/intelligence/scores/person/{person_id}",
        "/api/v2/intelligence/scores/portfolio",
        # Entity intelligence
        "/api/v2/intelligence/entity/client/{client_id}",
        "/api/v2/intelligence/entity/person/{person_id}",
        "/api/v2/intelligence/entity/portfolio",
        # Entity detail / operational profiles
        "/api/v2/intelligence/projects/{project_id}/state",
        "/api/v2/intelligence/clients/{client_id}/profile",
        "/api/v2/intelligence/team/{person_id}/profile",
        "/api/v2/intelligence/clients/{client_id}/trajectory",
        "/api/v2/intelligence/team/{person_id}/trajectory",
    ]

    def test_every_ui_fetch_has_a_route(self, app_routes):
        """Every path the UI api.ts calls must exist in the mounted app."""
        missing = []
        for path in self.UI_API_PATHS:
            if ("GET", path) not in app_routes:
                missing.append(path)

        assert not missing, (
            f"UI api.ts calls these paths but no GET route exists in the mounted app: {missing}"
        )

    def test_patterns_returns_richer_schema_for_ui(self, app_routes):
        """The /patterns route must serve PatternDetectionResponse for UI generated types."""
        route_info = app_routes.get(("GET", "/api/v2/intelligence/patterns"))
        assert route_info is not None, "patterns route missing"
        # spec_router's handler returns PatternDetectionResponse
        assert route_info["endpoint_module"] == "api.spec_router", (
            f"patterns served by {route_info['endpoint_module']}, "
            f"expected spec_router for PatternDetectionResponse"
        )

    def test_score_handlers_provide_computed_at_in_data(self):
        """Score handlers must inject computed_at into data (UI Scorecard expects it)."""
        import inspect

        from api.intelligence_router import (
            client_score,
            person_score,
            portfolio_score,
            project_score,
        )

        for handler in [client_score, project_score, person_score, portfolio_score]:
            source = inspect.getsource(handler)
            assert 'data["computed_at"]' in source, (
                f"{handler.__name__} must inject computed_at into scorecard data "
                f"(UI Scorecard interface expects it)"
            )

    def test_signal_history_does_not_pass_limit_to_backend(self):
        """signal_history must not pass limit to get_signal_history (no such param)."""
        import inspect

        from api.intelligence_router import signal_history

        source = inspect.getsource(signal_history)
        assert "limit=limit)" not in source, (
            "signal_history must NOT pass limit=limit to get_signal_history() "
            "(function has no limit parameter — apply post-fetch)"
        )

    def test_entity_intelligence_patches_scorecard_computed_at(self):
        """Entity intelligence handlers must patch computed_at into embedded scorecard.

        The scorecard lib returns scored_at, but UI Scorecard interface requires
        computed_at. The entity handlers (client, person) must patch it.
        """
        import inspect

        from api.intelligence_router import client_intelligence, person_intelligence

        for handler in [client_intelligence, person_intelligence]:
            source = inspect.getsource(handler)
            assert "_patch_scorecard_computed_at" in source, (
                f"{handler.__name__} must call _patch_scorecard_computed_at "
                f"to inject computed_at into embedded scorecard for UI compatibility"
            )

    def test_portfolio_intelligence_patches_score_computed_at(self):
        """Portfolio intelligence handler must patch computed_at into portfolio_score.

        Portfolio uses portfolio_score key (not scorecard), so needs its own patch.
        """
        import inspect

        from api.intelligence_router import portfolio_intelligence

        source = inspect.getsource(portfolio_intelligence)
        assert "_patch_portfolio_score_computed_at" in source, (
            "portfolio_intelligence must call _patch_portfolio_score_computed_at "
            "to inject computed_at into embedded portfolio_score for UI compatibility"
        )

    def test_patch_helpers_exist_and_are_correct(self):
        """The scorecard patch helpers must exist and handle the scored_at → computed_at mapping."""
        from api.intelligence_router import (
            _patch_portfolio_score_computed_at,
            _patch_scorecard_computed_at,
        )

        # Test _patch_scorecard_computed_at
        data_with_scorecard = {"scorecard": {"scored_at": "2026-01-01T00:00:00Z"}}
        _patch_scorecard_computed_at(data_with_scorecard)
        assert data_with_scorecard["scorecard"]["computed_at"] == "2026-01-01T00:00:00Z", (
            "Should use scored_at value for computed_at"
        )

        # Test with empty scorecard
        data_empty = {"scorecard": {}}
        _patch_scorecard_computed_at(data_empty)
        assert "computed_at" in data_empty["scorecard"], (
            "Should inject computed_at even when scored_at missing"
        )

        # Test idempotency — don't overwrite existing computed_at
        data_existing = {"scorecard": {"computed_at": "original", "scored_at": "different"}}
        _patch_scorecard_computed_at(data_existing)
        assert data_existing["scorecard"]["computed_at"] == "original", (
            "Should not overwrite existing computed_at"
        )

        # Test _patch_portfolio_score_computed_at
        portfolio_data = {"portfolio_score": {"scored_at": "2026-01-01T00:00:00Z"}}
        _patch_portfolio_score_computed_at(portfolio_data)
        assert portfolio_data["portfolio_score"]["computed_at"] == "2026-01-01T00:00:00Z", (
            "Should use scored_at value for computed_at in portfolio_score"
        )

    def test_normalize_scorecard_dimensions(self):
        """Dimensions must be normalized from backend list to UI Record format.

        Backend returns: [{"dimension": "name", "score": 75, "classification": "healthy"}]
        UI expects: {"name": {"name": "name", "score": 75, "status": "healthy"}}
        """
        from api.intelligence_router import _normalize_scorecard_dimensions

        scorecard = {
            "dimensions": [
                {
                    "dimension": "Operational Health",
                    "score": 72,
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
            ]
        }
        _normalize_scorecard_dimensions(scorecard)

        dims = scorecard["dimensions"]
        assert isinstance(dims, dict), (
            f"dimensions should be a dict (Record), got {type(dims).__name__}"
        )
        assert "Operational Health" in dims, "Missing Operational Health key"
        assert "Financial Health" in dims, "Missing Financial Health key"

        oh = dims["Operational Health"]
        assert oh["name"] == "Operational Health"
        assert oh["score"] == 72
        assert oh["status"] == "healthy"

        fh = dims["Financial Health"]
        assert fh["name"] == "Financial Health"
        assert fh["score"] == 45
        assert fh["status"] == "warning"

    def test_normalize_dimensions_handles_non_list(self):
        """If dimensions is already a dict, normalization should be a no-op."""
        from api.intelligence_router import _normalize_scorecard_dimensions

        # Already a dict — should not crash or change
        scorecard = {"dimensions": {"existing": {"name": "x", "score": 50, "status": "ok"}}}
        _normalize_scorecard_dimensions(scorecard)
        assert scorecard["dimensions"] == {"existing": {"name": "x", "score": 50, "status": "ok"}}

        # Missing dimensions — should not crash
        scorecard_empty = {}
        _normalize_scorecard_dimensions(scorecard_empty)
        assert "dimensions" not in scorecard_empty

    def test_score_handlers_normalize_dimensions(self):
        """All 4 score handlers must call _normalize_scorecard_dimensions."""
        import inspect

        from api.intelligence_router import (
            client_score,
            person_score,
            portfolio_score,
            project_score,
        )

        for handler in [client_score, project_score, person_score, portfolio_score]:
            source = inspect.getsource(handler)
            assert "_normalize_scorecard_dimensions" in source, (
                f"{handler.__name__} must call _normalize_scorecard_dimensions "
                f"to convert dimensions list to Record for UI compatibility"
            )

    def test_patterns_handler_normalizes_field_names(self):
        """spec_router patterns handler must normalize backend field names for UI.

        Backend PatternEvidence uses: pattern_name, pattern_type, entities_involved
        UI Pattern interface expects: name, type, affected_entities, description
        """
        import inspect

        from api.spec_router import get_intelligence_patterns

        source = inspect.getsource(get_intelligence_patterns)
        # Verify all 4 field normalizations are present
        assert '"name"' in source and '"pattern_name"' in source, (
            "patterns handler must map pattern_name → name"
        )
        assert '"type"' in source and '"pattern_type"' in source, (
            "patterns handler must map pattern_type → type"
        )
        assert '"affected_entities"' in source and '"entities_involved"' in source, (
            "patterns handler must map entities_involved → affected_entities"
        )
        assert '"description"' in source and '"operational_meaning"' in source, (
            "patterns handler must map operational_meaning → description"
        )
