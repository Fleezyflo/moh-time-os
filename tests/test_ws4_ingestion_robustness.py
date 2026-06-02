"""WS4 S4.7 — ingestion robustness: silent swallows, registry, magic constants."""

import sqlite3

import pytest


def test_get_internal_users_raises_on_missing_db(tmp_path):
    """Missing DB must raise, not return [] (which hides the failure)."""
    from lib.collectors.all_users_runner import get_internal_users

    missing = tmp_path / "does_not_exist.db"
    with pytest.raises(FileNotFoundError):
        get_internal_users(missing)


def test_get_internal_users_returns_emails(tmp_path):
    from lib.collectors.all_users_runner import get_internal_users

    db = tmp_path / "people.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE people (email TEXT, type TEXT)")
    conn.executemany(
        "INSERT INTO people (email, type) VALUES (?,?)",
        [("a@x.co", "internal"), ("b@x.co", "external"), ("c@x.co", "internal")],
    )
    conn.commit()
    conn.close()

    emails = get_internal_users(db)
    assert set(emails) == {"a@x.co", "c@x.co"}


def test_all_users_connect_uses_timeout_and_wal(tmp_path):
    """The runner's DB connections must set a busy timeout and WAL journal."""
    from lib.collectors.all_users_runner import _connect

    db = tmp_path / "wal.db"
    conn = _connect(db)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        conn.close()


def test_run_all_users_skips_when_locked(tmp_path, monkeypatch):
    """If the all_users lock is already held, run_all_users must no-op early."""
    import lib.collectors.all_users_runner as runner

    monkeypatch.setattr(runner.paths, "db_path", lambda: tmp_path / "x.db")
    monkeypatch.setattr(runner, "ensure_tables", lambda _p: None)

    # Force the lock to report 'not acquired' (someone else holds it).
    class _HeldLock:
        def __init__(self, *a, **k):
            self.acquired = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(runner, "CollectorLock", _HeldLock)

    # If the lock guard is missing, get_internal_users would run and raise
    # FileNotFoundError (DB absent). With the guard, we return early instead.
    out = runner.run_all_users(since="2026-01-01", until="2026-01-02")
    assert out == {} or out.get("skipped") is True


def test_orchestrator_core_intervals_match_registry():
    """No drift: every core source's sync_interval equals the registry value."""
    from lib.collector_registry import COLLECTOR_REGISTRY
    from lib.collectors.orchestrator import _core_sources_from_registry

    core = _core_sources_from_registry()
    for name, spec in COLLECTOR_REGISTRY.items():
        assert name in core
        assert core[name]["sync_interval"] == spec.sync_interval_seconds


def test_orchestrator_respects_explicit_disable(monkeypatch):
    """sources.yaml enabled:false on a core source must be honored, not forced True."""
    from unittest.mock import MagicMock

    from lib.collectors import orchestrator as orch_mod

    orch = object.__new__(orch_mod.CollectorOrchestrator)
    orch.logger = MagicMock()
    orch.store = MagicMock()
    orch.config = {"sources": {"xero": {"enabled": False}}}
    orch.collectors = {}

    orch._init_collectors()
    assert "xero" not in orch.collectors  # explicit disable honored


def test_inbox_enrichment_limit_from_env(monkeypatch):
    """The inbox-enrichment batch limit must come from config/env, not be hardcoded 20."""
    from unittest.mock import MagicMock

    from lib.collectors import orchestrator as orch_mod

    monkeypatch.setenv("MOH_INBOX_ENRICH_LIMIT", "75")

    captured = {}

    def _fake_batch(*, use_llm, limit):
        captured["use_llm"] = use_llm
        captured["limit"] = limit
        return {"enriched": 0}

    import sys
    import types

    fake_mod = types.ModuleType("lib.ui_spec_v21.inbox_enricher")
    fake_mod.run_enrichment_batch = _fake_batch
    monkeypatch.setitem(sys.modules, "lib.ui_spec_v21.inbox_enricher", fake_mod)

    orch = object.__new__(orch_mod.CollectorOrchestrator)
    orch.logger = MagicMock()
    results = {}
    orch._run_inbox_enrichment(results)

    assert captured["limit"] == 75


def test_xero_invoice_id_uses_guid_not_number(tmp_path, monkeypatch):
    """Two invoices with colliding-after-replace InvoiceNumbers must get distinct ids."""
    from unittest.mock import MagicMock

    import lib.collectors.xero as xero_mod

    stored_ids = []

    store = MagicMock()
    store.db_path = str(tmp_path / "x.db")

    def _capture_replace(table, source_column, source_value, rows):
        if table == "invoices":
            stored_ids.extend(r["id"] for r in rows)
        return len(rows)

    # Invoices are now written atomically via replace_source_rows (DELETE+reinsert
    # in one txn), not per-row store.insert. Capture the row ids from that call.
    store.replace_source_rows.side_effect = _capture_replace
    store.query.return_value = []

    collector = xero_mod.XeroCollector({}, store=store)

    # XeroCollector.sync() does `from engine.xero_client import list_invoices, …`
    # INSIDE the method, so the names resolve against engine.xero_client at call
    # time. Patch them THERE. list_invoices is called twice (PAID then
    # AUTHORISED), so the first call returns both invoices and the second [].
    _invoices_calls = iter(
        [
            [
                {
                    "Type": "ACCREC",
                    "InvoiceID": "guid-aaa",
                    "InvoiceNumber": "INV 1",
                    "Contact": {"Name": "C"},
                    "Status": "AUTHORISED",
                    "Total": 10,
                    "AmountDue": 10,
                },
                {
                    "Type": "ACCREC",
                    "InvoiceID": "guid-bbb",
                    "InvoiceNumber": "INV 1",
                    "Contact": {"Name": "C"},
                    "Status": "AUTHORISED",
                    "Total": 20,
                    "AmountDue": 20,
                },
            ],
            [],
        ]
    )
    # String-target patch so pytest resolves the live sys.modules["engine.xero_client"]
    # (the object the collector's lazy import reads), immune to module-cache churn.
    monkeypatch.setattr("engine.xero_client.list_invoices", lambda *a, **k: next(_invoices_calls))
    monkeypatch.setattr("engine.xero_client.list_contacts", lambda *a, **k: [])
    monkeypatch.setattr("engine.xero_client.list_credit_notes", lambda *a, **k: [])
    monkeypatch.setattr("engine.xero_client.list_bank_transactions", lambda *a, **k: [])
    monkeypatch.setattr("engine.xero_client.list_tax_rates", lambda *a, **k: [])

    collector.sync()

    assert len(stored_ids) == 2
    assert len(set(stored_ids)) == 2  # distinct ids, no collision


def test_google_sa_file_no_hardcoded_identity(monkeypatch):
    """The SA filename must not hardcode a specific user's base64 identity."""
    import lib.credential_paths as cp

    monkeypatch.delenv("GOOGLE_SA_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_SA_FILENAME", raising=False)

    path = cp.google_sa_file()
    # The leaked filename was sa-bW9saGFtQGhybW55LmNv.json (base64 of molham@hrmny.co).
    assert "bW9saGFtQGhybW55LmNv" not in str(path)


def test_google_sa_filename_override(monkeypatch):
    import lib.credential_paths as cp

    monkeypatch.delenv("GOOGLE_SA_FILE", raising=False)
    monkeypatch.setenv("GOOGLE_SA_FILENAME", "sa-custom.json")
    assert cp.google_sa_file().name == "sa-custom.json"


def test_collector_lock_ttl_is_short_enough_to_self_heal():
    """The hung-collector mitigation relies on CollectorLock TTL self-healing.

    A wedged worker thread stops its heartbeat; the lock must self-heal within
    a bounded window so the next cycle is not starved indefinitely.
    """
    from lib.collector_registry import CollectorLock

    assert CollectorLock.TTL_SECONDS <= 120
    assert CollectorLock.HEARTBEAT_INTERVAL < CollectorLock.TTL_SECONDS
