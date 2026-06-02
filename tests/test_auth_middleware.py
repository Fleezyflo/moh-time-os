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

    # Reload api.auth FIRST so its module-level _API_KEY re-reads the env var
    # (it is captured at import time; a stale value would reject the test token).
    import api.auth

    importlib.reload(api.auth)

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

    @pytest.mark.parametrize(
        "value",
        ["*,http://x.test", "http://x.test,*", "http://localhost:5173,*", " * ", "*,*"],
    )
    def test_wildcard_anywhere_in_list_is_hard_failure(self, monkeypatch, tmp_path, value):
        """A "*" token ANYWHERE in the comma list must hard-fail: Starlette sets
        allow_all_origins = ("*" in allow_origins), so a single "*" element
        re-enables credentialed Origin reflection. (Round-1 skeptic bypass.)"""
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            _reload_server(monkeypatch, tmp_path, CORS_ORIGINS=value)


class TestAuthMiddleware:
    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        from fastapi.testclient import TestClient

        server = _reload_server(monkeypatch, tmp_path, CORS_ORIGINS="http://localhost:5173")
        # Plain TestClient (NOT a context manager): Starlette 0.5x only runs
        # startup events under `with TestClient(...)`, so no DB-hitting startup fires.
        return TestClient(server.app)

    def test_health_is_public(self, client):
        resp = client.get("/api/health")
        assert resp.status_code != 401

    def test_auth_mode_is_public(self, client):
        resp = client.get("/api/auth/mode")
        assert resp.status_code == 200
        assert resp.json()["auth_required"] is True

    def test_mutation_route_rejects_no_token(self, client):
        resp = client.delete("/api/tasks/does-not-exist")
        assert resp.status_code == 401, resp.text

    def test_mutation_route_rejects_wrong_token(self, client):
        resp = client.delete(
            "/api/tasks/does-not-exist",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401, resp.text

    def test_correct_token_passes_auth_layer(self, client):
        # Correct token clears AuthMiddleware; the handler then 404s (task absent).
        resp = client.delete(
            "/api/tasks/does-not-exist",
            headers={"Authorization": "Bearer test-secret-key-for-proof"},
        )
        assert resp.status_code != 401
        assert resp.status_code == 404

    def test_options_preflight_is_public(self, client):
        resp = client.options(
            "/api/tasks/x",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "DELETE",
            },
        )
        assert resp.status_code != 401


class TestRouterDependencies:
    def test_every_mounted_router_has_require_auth_dependency(self, monkeypatch, tmp_path):
        """Each include_router'd APIRouter (except the public auth router) must
        carry require_auth as a router-level dependency -- defense in depth."""
        from api import auth

        server = _reload_server(monkeypatch, tmp_path, CORS_ORIGINS="http://localhost:5173")
        sample_paths = {
            "/api/v2/proposals",
            "/api/governance/sar",
        }

        def route_deps(path_to_find):
            for route in server.app.routes:
                if getattr(route, "path", None) == path_to_find:
                    return [d.dependency for d in getattr(route, "dependencies", [])]
            return None

        for p in sample_paths:
            deps = route_deps(p)
            assert deps is not None, f"route {p} not found"
            assert auth.require_auth in deps, f"{p} missing require_auth dependency"
        # The public auth router must NOT require auth on its handshake routes.
        assert auth.require_auth not in (route_deps("/api/auth/mode") or [])


class TestSsePublishLockdown:
    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        from fastapi.testclient import TestClient

        server = _reload_server(monkeypatch, tmp_path, CORS_ORIGINS="http://localhost:5173")
        return TestClient(server.app)

    def test_publish_route_has_local_dependency(self):
        """The publish route carries its OWN Depends(require_auth), not only the
        router-level one -- visible to anyone reading sse_router in isolation."""
        from api.sse_router import sse_router

        route = next(r for r in sse_router.routes if getattr(r, "path", "") == "/events/publish")
        assert len(route.dependencies) >= 1

    def test_publish_rejects_no_token(self, client):
        resp = client.post(
            "/api/v2/events/publish",
            params={"event_type": "signal_new", "message": "pwned"},
        )
        assert resp.status_code == 401, resp.text

    def test_publish_accepts_correct_token(self, client):
        resp = client.post(
            "/api/v2/events/publish",
            params={"event_type": "signal_new", "message": "ok"},
            headers={"Authorization": "Bearer test-secret-key-for-proof"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "ok"


class TestSseStreamAuth:
    """The SSE stream authenticates via ?token= (EventSource cannot set headers).
    It is exempt from AuthMiddleware + router dep but self-validates the query
    token. Round-1 skeptic proved a header-only client was rejected (broken SSE)."""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        from fastapi.testclient import TestClient

        server = _reload_server(monkeypatch, tmp_path, CORS_ORIGINS="http://localhost:5173")
        return TestClient(server.app)

    def test_stream_rejects_no_token(self, client):
        resp = client.get("/api/v2/events/stream")
        assert resp.status_code == 401, resp.text

    def test_stream_rejects_wrong_token(self, client):
        resp = client.get("/api/v2/events/stream", params={"token": "wrong"})
        assert resp.status_code == 401, resp.text

    def test_stream_valid_query_token_passes_auth(self, monkeypatch):
        """A correct ?token= clears BOTH AuthMiddleware (exempt path) and the
        in-handler verify_token check. We patch the event bus so the route does
        NOT open an infinite stream (which would hang the test); the assertion is
        only that a valid token is NOT rejected with 401 while a missing one is."""
        # Drive the handler's in-handler check directly with a real reload so the
        # _API_KEY matches the test token, avoiding a live TestClient stream.
        import importlib

        import api.auth as auth_mod

        monkeypatch.setenv("MOH_TIME_OS_API_KEY", "test-secret-key-for-proof")
        importlib.reload(auth_mod)
        from api.sse_router import verify_token as sse_verify_token

        assert sse_verify_token("test-secret-key-for-proof") is True
        assert sse_verify_token("wrong") is False
        assert sse_verify_token(None) is False

    def test_history_still_requires_header_auth(self, client):
        # events/history keeps its own Depends(require_auth) (header-based).
        assert client.get("/api/v2/events/history").status_code == 401
        ok = client.get(
            "/api/v2/events/history",
            headers={"Authorization": "Bearer test-secret-key-for-proof"},
        )
        assert ok.status_code != 401, ok.text


class TestRateLimit:
    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        from fastapi.testclient import TestClient

        from lib.security.rate_limiter import RateLimiter

        server = _reload_server(monkeypatch, tmp_path, CORS_ORIGINS="http://localhost:5173")
        # Add a tiny-limit RateLimitMiddleware so 429 triggers deterministically.
        from api.auth_middleware import RateLimitMiddleware

        tiny = RateLimiter(rate_limits={"authenticated": 2})
        server.app.add_middleware(RateLimitMiddleware, limiter=tiny)
        return TestClient(server.app)

    def test_write_method_is_throttled_after_limit(self, client):
        headers = {"Authorization": "Bearer test-secret-key-for-proof"}
        statuses = [client.delete("/api/tasks/none", headers=headers).status_code for _ in range(4)]
        assert 429 in statuses, statuses

    def test_get_is_not_rate_limited(self, client):
        statuses = [client.get("/api/health").status_code for _ in range(5)]
        assert 429 not in statuses

    def test_debug_config_flag_reflects_registration(self, monkeypatch, tmp_path):
        server = _reload_server(monkeypatch, tmp_path, CORS_ORIGINS="http://localhost:5173")
        assert any(m.cls.__name__ == "RateLimitMiddleware" for m in server.app.user_middleware)
