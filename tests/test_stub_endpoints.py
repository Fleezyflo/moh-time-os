"""
Tests for stub endpoint 501 responses.

These tests verify that unimplemented endpoints return proper 501 errors
instead of fake success responses.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import lib.paths  # noqa: E402
from tests.fixtures.fixture_db import create_fixture_db  # noqa: E402


@pytest.fixture(scope="module")
def fixture_db_path(tmp_path_factory):
    """Create a fixture DB for the module."""
    tmp_path = tmp_path_factory.mktemp("stub_endpoints")
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
    monkeypatch_module.setattr(lib.paths, "db_path", lambda: fixture_db_path)

    # Now import and create the app (it will use the patched path)
    from api.server import app

    return TestClient(app)


class TestStubEndpoints:
    """Tests for stub endpoints returning 501."""

    def test_bulk_link_tasks_returns_501(self, client):
        """POST /api/tasks/link should return 501 Not Implemented."""
        response = client.post("/api/tasks/link")

        assert response.status_code == 501
        assert "not implemented" in response.json()["detail"].lower()


class TestStubHandlers:
    """Tests for stub handlers raising NotImplementedError."""

    def test_sync_to_asana_raises_not_implemented(self):
        """_sync_to_asana should raise NotImplementedError."""
        from lib.executor.handlers.task import TaskHandler

        mock_store = MagicMock()
        handler = TaskHandler(mock_store)

        with pytest.raises(NotImplementedError) as exc_info:
            handler._sync_to_asana("task_123", {"title": "Test"})

        assert "not implemented" in str(exc_info.value).lower()

    def test_complete_in_asana_raises_not_implemented(self):
        """_complete_in_asana should raise NotImplementedError."""
        from lib.executor.handlers.task import TaskHandler

        mock_store = MagicMock()
        handler = TaskHandler(mock_store)

        with pytest.raises(NotImplementedError) as exc_info:
            handler._complete_in_asana("asana_456")

        assert "not implemented" in str(exc_info.value).lower()


class TestErrorPropagation:
    """Tests for proper error propagation in collectors."""

    def test_tasks_collector_propagates_errors(self):
        """TasksCollector.collect() should propagate exceptions."""
        from unittest.mock import patch

        from lib.collectors.tasks import TasksCollector

        collector = TasksCollector(config={}, store=MagicMock())

        # Mock _run_command to raise an exception
        with patch.object(collector, "_run_command", side_effect=Exception("Command failed")):
            with pytest.raises(Exception) as exc_info:
                collector.collect()

            assert "Command failed" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
