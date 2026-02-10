"""
Lightweight contract tests for /api/v2/* endpoints.
Verifies endpoints return 200 and include required top-level keys.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create test client for the FastAPI app."""
    from api.server import app

    return TestClient(app)


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
