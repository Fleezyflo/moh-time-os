"""WS4 S4.5 — Xero access-token caching (no refresh-per-call)."""

import json
import time
from unittest.mock import patch

import engine.xero_client as xc


def _write_cache(path, access_token, expires_at):
    path.write_text(json.dumps({"access_token": access_token, "expires_at": expires_at}))


def test_get_access_token_reuses_unexpired_cache(tmp_path, monkeypatch):
    cache = tmp_path / ".xero_token_cache.json"
    _write_cache(cache, "cached-tok", time.time() + 600)  # 10 min in the future
    monkeypatch.setattr(xc, "TOKEN_CACHE_PATH", str(cache))

    monkeypatch.setenv("XERO_CLIENT_ID", "cid")
    monkeypatch.setenv("XERO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("XERO_REFRESH_TOKEN", "rtok")
    monkeypatch.setenv("XERO_TENANT_ID", "tid")

    with patch.object(xc, "refresh_access_token") as mock_refresh:
        token, tenant = xc.get_access_token()

    assert token == "cached-tok"
    assert tenant == "tid"
    mock_refresh.assert_not_called()


def test_get_access_token_refreshes_when_expired(tmp_path, monkeypatch):
    cache = tmp_path / ".xero_token_cache.json"
    _write_cache(cache, "stale-tok", time.time() - 10)  # already expired
    monkeypatch.setattr(xc, "TOKEN_CACHE_PATH", str(cache))

    monkeypatch.setenv("XERO_CLIENT_ID", "cid")
    monkeypatch.setenv("XERO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("XERO_REFRESH_TOKEN", "rtok")
    monkeypatch.setenv("XERO_TENANT_ID", "tid")

    with patch.object(xc, "refresh_access_token", return_value="fresh-tok") as mock_refresh:
        token, tenant = xc.get_access_token()

    assert token == "fresh-tok"
    mock_refresh.assert_called_once()


def test_save_tokens_writes_expires_at(tmp_path, monkeypatch):
    cache = tmp_path / ".xero_token_cache.json"
    monkeypatch.setattr(xc, "TOKEN_CACHE_PATH", str(cache))
    monkeypatch.setenv("XERO_REFRESH_TOKEN", "rtok")  # env mode -> no file write-back

    xc.save_tokens("new-access", "rtok")
    data = json.loads(cache.read_text())
    assert data["access_token"] == "new-access"
    assert data["expires_at"] > time.time()
