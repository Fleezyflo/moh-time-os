"""WS4 S4.1 — credential client contract.

These tests do NOT use real credentials or the network. They verify that
when config/.credentials.json is the wrong schema (a Google SA JSON), both
clients raise a clear RuntimeError naming the env-var fallback — and that a
correctly-shaped file/env loads.
"""

import json

import pytest


def test_xero_load_credentials_raises_clear_error_on_wrong_schema(tmp_path, monkeypatch):
    import engine.xero_client as xc

    # A Google SA JSON — the exact wrong schema found in production.
    bad = tmp_path / ".credentials.json"
    bad.write_text(json.dumps({"type": "service_account", "project_id": "xero-to-sheets"}))
    monkeypatch.setattr(xc, "_CONFIG_PATH", str(bad))
    for var in ("XERO_CLIENT_ID", "XERO_CLIENT_SECRET", "XERO_REFRESH_TOKEN", "XERO_TENANT_ID"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(RuntimeError, match="Xero credentials not found"):
        xc.load_credentials()


def test_xero_load_credentials_from_env(monkeypatch):
    import engine.xero_client as xc

    monkeypatch.setenv("XERO_CLIENT_ID", "cid")
    monkeypatch.setenv("XERO_CLIENT_SECRET", "secret")
    monkeypatch.setenv("XERO_REFRESH_TOKEN", "rtok")
    monkeypatch.setenv("XERO_TENANT_ID", "tid")
    monkeypatch.setattr(xc.os.path, "exists", lambda _p: False)

    creds = xc.load_credentials()
    assert creds.client_id == "cid"
    assert creds.tenant_id == "tid"


def test_asana_load_pat_raises_clear_error_on_wrong_schema(tmp_path, monkeypatch):
    import engine.asana_client as ac

    bad = tmp_path / ".credentials.json"
    bad.write_text(json.dumps({"type": "service_account", "project_id": "xero-to-sheets"}))
    monkeypatch.setattr(ac, "_CONFIG_PATH", str(bad))
    monkeypatch.delenv("ASANA_PAT", raising=False)

    with pytest.raises(RuntimeError, match="Asana PAT not found"):
        ac.load_pat()


def test_asana_load_pat_from_env(monkeypatch):
    import engine.asana_client as ac

    monkeypatch.setenv("ASANA_PAT", "1/abc:def")
    assert ac.load_pat() == "1/abc:def"
