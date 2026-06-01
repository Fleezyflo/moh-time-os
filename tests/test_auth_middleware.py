"""Unit tests for API security middleware and CORS configuration (WS2)."""

import importlib

import pytest

import lib.paths
from tests.fixtures.fixture_db import create_fixture_db


def _reload_server(monkeypatch, tmp_path, **env):
    """Reload api.server against a seeded FIXTURE DB so the module-level
    get_store() probe never touches the live DB (conftest determinism guard).

    The reliable pattern (matches tests/test_mounted_app_route_ownership.py):
    build a real fixture DB, patch lib.paths.db_path/data_dir to it, and RESET
    the StateStore singleton so the reload rebuilds against the fixture rather
    than returning a cached store bound to the live path. Setting MOH_TIME_OS_DB
    alone is insufficient because StateStore is a process-wide singleton.
    """
    db_path = tmp_path / "fixture.db"
    if not db_path.exists():
        conn = create_fixture_db(db_path)
        conn.close()

    monkeypatch.setenv("MOH_TIME_OS_ENV", "test")
    monkeypatch.setenv("MOH_TIME_OS_DB", str(db_path))
    monkeypatch.setenv("MOH_TIME_OS_API_KEY", "test-secret-key-for-proof")
    monkeypatch.setattr(lib.paths, "db_path", lambda: db_path)
    monkeypatch.setattr(lib.paths, "data_dir", lambda: db_path.parent)
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)

    # Reset the StateStore singleton so get_store() rebuilds on the fixture DB.
    import lib.state_store as state_store

    state_store.StateStore._instance = None

    import api.server as server

    return importlib.reload(server)


class TestCorsConfig:
    def test_missing_cors_origins_defaults_to_vite_localhost_not_wildcard(
        self, monkeypatch, tmp_path
    ):
        server = _reload_server(monkeypatch, tmp_path, CORS_ORIGINS=None)
        assert server.cors_origins == ["http://localhost:5173"]
        assert "*" not in server.cors_origins

    def test_explicit_origins_are_parsed(self, monkeypatch, tmp_path):
        server = _reload_server(monkeypatch, tmp_path, CORS_ORIGINS="http://a.test,http://b.test")
        assert server.cors_origins == ["http://a.test", "http://b.test"]

    def test_wildcard_with_credentials_is_hard_failure(self, monkeypatch, tmp_path):
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            _reload_server(monkeypatch, tmp_path, CORS_ORIGINS="*")
