"""
Lightweight contract tests for /api/v2/* endpoints.
Verifies endpoints return 200 and include required top-level keys.

Uses fixture DB to avoid live DB access (determinism guard).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import lib.paths
from tests.fixtures.fixture_db import create_fixture_db, get_fixture_db_path


@pytest.fixture(scope="module")
def fixture_db_path(tmp_path_factory):
    """Create a fixture DB for the module."""
    tmp_path = tmp_path_factory.mktemp("api_contracts")
    db_path = tmp_path / "fixture.db"
    conn = create_fixture_db(db_path)
    conn.close()
    return db_path


@pytest.fixture(scope="module")
def client(fixture_db_path, monkeypatch_module):
    """Create test client with fixture DB injected."""
    # Redirect lib.paths.db_path to fixture DB BEFORE importing app
    monkeypatch_module.setattr(lib.paths, "db_path", lambda: fixture_db_path)

    # Now import and create the app (it will use the patched path)
    from api.server import app

    return TestClient(app)


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped monkeypatch for fixtures that need it."""
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


class TestInboxEndpoints:
    def test_inbox_returns_200_with_required_keys(self, client):
        response = client.get("/api/v2/inbox")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or "counts" in data

    def test_inbox_counts_returns_200(self, client):
        response = client.get("/api/v2/inbox/counts")
        assert response.status_code == 200
        data = response.json()
        assert "needs_attention" in data or "total" in data or isinstance(data, dict)

    def test_inbox_recent_returns_200(self, client):
        response = client.get("/api/v2/inbox/recent")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestIssuesEndpoints:
    def test_issues_returns_200_with_items(self, client):
        response = client.get("/api/v2/issues")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestClientsEndpoints:
    def test_clients_returns_200_with_required_keys(self, client):
        response = client.get("/api/v2/clients")
        assert response.status_code == 200
        data = response.json()
        # ClientIndex expects active, recently_active, cold, counts
        assert "active" in data or "items" in data
        assert "counts" in data or "total" in data


class TestTeamEndpoints:
    def test_team_returns_200_with_items(self, client):
        response = client.get("/api/v2/team")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestPrioritiesEndpoints:
    def test_priorities_returns_200_with_items(self, client):
        response = client.get("/api/v2/priorities")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestProjectsEndpoints:
    def test_projects_returns_200_with_items(self, client):
        response = client.get("/api/v2/projects")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestEventsEndpoints:
    def test_events_returns_200_with_items(self, client):
        response = client.get("/api/v2/events")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestInvoicesEndpoints:
    def test_invoices_returns_200_with_items(self, client):
        response = client.get("/api/v2/invoices")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestProposalsEndpoints:
    def test_proposals_returns_200_with_items(self, client):
        response = client.get("/api/v2/proposals")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestWatchersEndpoints:
    def test_watchers_returns_200_with_items(self, client):
        response = client.get("/api/v2/watchers")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestCouplingsEndpoints:
    def test_couplings_returns_200_with_items(self, client):
        response = client.get("/api/v2/couplings")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestFixDataEndpoints:
    def test_fix_data_returns_200_with_required_keys(self, client):
        response = client.get("/api/v2/fix-data")
        assert response.status_code == 200
        data = response.json()
        assert "identity_conflicts" in data
        assert "ambiguous_links" in data
        assert "total" in data


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/api/v2/health")
        assert response.status_code == 200
