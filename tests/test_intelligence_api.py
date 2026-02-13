"""
Intelligence API Tests — Task 3.3

Tests for api/intelligence_router.py endpoints.
Uses TestClient to test FastAPI endpoints directly.

Uses fixture DB to avoid live DB access (determinism guard).
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

import lib.paths as lib_paths
import lib.query_engine as query_engine_module
from tests.fixtures.fixture_db import create_fixture_db


@pytest.fixture(scope="module")
def fixture_db_path(tmp_path_factory):
    """Create a fixture DB for the module."""
    tmp_path = tmp_path_factory.mktemp("intelligence_api")
    db_path = tmp_path / "fixture.db"
    conn = create_fixture_db(db_path)
    conn.close()
    return db_path


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped monkeypatch for fixtures that need it."""
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def client(fixture_db_path, monkeypatch_module):
    """Create test client with fixture DB injected."""
    # Redirect lib.paths.db_path to fixture DB BEFORE importing app
    monkeypatch_module.setattr(lib_paths, "db_path", lambda: fixture_db_path)

    # Also patch the query engine's default path
    monkeypatch_module.setattr(query_engine_module, "DEFAULT_DB_PATH", fixture_db_path)

    # Clear any cached engine instance
    query_engine_module._engine = None

    # Now import and create the app (it will use the patched path)
    from api.server import app

    return TestClient(app)


class TestPortfolioEndpoints:
    """Tests for /api/v2/intelligence/portfolio/* endpoints."""

    def test_portfolio_overview_returns_200(self, client):
        """GET /portfolio/overview returns 200 with list of clients."""
        response = client.get("/api/v2/intelligence/portfolio/overview")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "data" in data
        assert isinstance(data["data"], list)
        assert "computed_at" in data

    def test_portfolio_overview_supports_ordering(self, client):
        """Portfolio overview accepts order_by parameter."""
        response = client.get(
            "/api/v2/intelligence/portfolio/overview",
            params={"order_by": "ytd_revenue", "desc": True},
        )
        assert response.status_code == 200
        assert response.json()["params"]["order_by"] == "ytd_revenue"

    def test_portfolio_risks_returns_200(self, client):
        """GET /portfolio/risks returns 200 with risk list."""
        response = client.get("/api/v2/intelligence/portfolio/risks")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert isinstance(data["data"], list)

    def test_portfolio_risks_accepts_thresholds(self, client):
        """Portfolio risks accepts threshold parameters."""
        response = client.get(
            "/api/v2/intelligence/portfolio/risks",
            params={"overdue_threshold": 10, "aging_threshold": 60},
        )
        assert response.status_code == 200
        assert response.json()["params"]["overdue_threshold"] == 10
        assert response.json()["params"]["aging_threshold"] == 60

    def test_portfolio_trajectory_returns_200(self, client):
        """GET /portfolio/trajectory returns 200 with trajectory data."""
        response = client.get("/api/v2/intelligence/portfolio/trajectory")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert isinstance(data["data"], list)


class TestClientEndpoints:
    """Tests for /api/v2/intelligence/clients/* endpoints."""

    def test_client_profile_returns_404_for_invalid(self, client):
        """GET /clients/{id}/profile returns 404 for nonexistent client."""
        response = client.get("/api/v2/intelligence/clients/nonexistent-id-12345/profile")
        assert response.status_code == 404

    def test_client_tasks_returns_200(self, client):
        """GET /clients/{id}/tasks returns 200 with task summary."""
        # Use a nonexistent client - should return empty but 200
        response = client.get("/api/v2/intelligence/clients/test-client/tasks")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "total_tasks" in data["data"]

    def test_client_communication_returns_200(self, client):
        """GET /clients/{id}/communication returns 200."""
        response = client.get("/api/v2/intelligence/clients/test-client/communication")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "total_communications" in data["data"]

    def test_client_trajectory_returns_200(self, client):
        """GET /clients/{id}/trajectory returns 200 with windows."""
        response = client.get("/api/v2/intelligence/clients/test-client/trajectory")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "windows" in data["data"]

    def test_client_compare_returns_200(self, client):
        """GET /clients/{id}/compare returns 200 with period comparison."""
        response = client.get(
            "/api/v2/intelligence/clients/test-client/compare",
            params={
                "period_a_start": "2024-01-01",
                "period_a_end": "2024-06-30",
                "period_b_start": "2024-07-01",
                "period_b_end": "2024-12-31",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "period_a" in data["data"]
        assert "period_b" in data["data"]
        assert "deltas" in data["data"]

    def test_clients_compare_returns_200(self, client):
        """GET /clients/compare returns 200 with portfolio comparison."""
        response = client.get(
            "/api/v2/intelligence/clients/compare",
            params={
                "period_a_start": "2024-01-01",
                "period_a_end": "2024-06-30",
                "period_b_start": "2024-07-01",
                "period_b_end": "2024-12-31",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert isinstance(data["data"], list)


class TestTeamEndpoints:
    """Tests for /api/v2/intelligence/team/* endpoints."""

    def test_team_distribution_returns_200(self, client):
        """GET /team/distribution returns 200 with people list."""
        response = client.get("/api/v2/intelligence/team/distribution")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert isinstance(data["data"], list)

    def test_team_capacity_returns_200(self, client):
        """GET /team/capacity returns 200 with capacity metrics."""
        response = client.get("/api/v2/intelligence/team/capacity")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "total_people" in data["data"]
        assert "distribution" in data["data"]

    def test_team_person_profile_returns_404_for_invalid(self, client):
        """GET /team/{id}/profile returns 404 for nonexistent person."""
        response = client.get("/api/v2/intelligence/team/nonexistent-id-12345/profile")
        assert response.status_code == 404

    def test_team_person_trajectory_returns_200(self, client):
        """GET /team/{id}/trajectory returns 200 with trajectory data."""
        # Will return error dict if person not found, but still 200
        response = client.get("/api/v2/intelligence/team/test-person/trajectory")
        assert response.status_code == 200


class TestProjectEndpoints:
    """Tests for /api/v2/intelligence/projects/* endpoints."""

    def test_project_state_returns_404_for_invalid(self, client):
        """GET /projects/{id}/state returns 404 for nonexistent project."""
        response = client.get("/api/v2/intelligence/projects/nonexistent-id-12345/state")
        assert response.status_code == 404

    def test_projects_health_returns_200(self, client):
        """GET /projects/health returns 200 with project list."""
        response = client.get("/api/v2/intelligence/projects/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert isinstance(data["data"], list)

    def test_projects_health_accepts_min_tasks(self, client):
        """Projects health accepts min_tasks parameter."""
        response = client.get(
            "/api/v2/intelligence/projects/health",
            params={"min_tasks": 5},
        )
        assert response.status_code == 200
        assert response.json()["params"]["min_tasks"] == 5


class TestFinancialEndpoints:
    """Tests for /api/v2/intelligence/financial/* endpoints."""

    def test_financial_aging_returns_200(self, client):
        """GET /financial/aging returns 200 with aging report."""
        response = client.get("/api/v2/intelligence/financial/aging")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "total_outstanding" in data["data"]
        assert "by_bucket" in data["data"]


class TestResponseEnvelope:
    """Tests for consistent response format."""

    def test_success_response_has_required_fields(self, client):
        """Successful responses have status, data, computed_at."""
        response = client.get("/api/v2/intelligence/portfolio/overview")
        data = response.json()

        assert "status" in data
        assert data["status"] == "ok"
        assert "data" in data
        assert "computed_at" in data

    def test_error_response_format(self, client):
        """Error responses have status, error, detail."""
        response = client.get("/api/v2/intelligence/clients/nonexistent/profile")
        assert response.status_code == 404
        # FastAPI wraps HTTPException in {"detail": ...}
        assert "detail" in response.json()
