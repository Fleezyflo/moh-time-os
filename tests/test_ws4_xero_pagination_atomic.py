"""WS4 fold-in — Xero list_invoices pagination + atomic DELETE+reinsert.

These two findings were filed out-of-scope during WS3 adversarial verification
(verification log: list_invoices not paginated -> >100 ACCREC rows truncate ->
DELETE wipes the remainder and reports SUCCESS; DELETE+reinsert non-atomic since
StateStore opens a connection per CRUD). Chip B never started, so they are folded
into WS4. Salvage reference: audit-remediation/salvage/state_store_replace_source_rows.patch.
"""

import sqlite3

import pytest

import engine.xero_client as xc


def test_list_invoices_paginates_until_short_page(monkeypatch):
    """list_invoices must request successive pages until a short/empty page.

    Xero's Accounting Invoices endpoint returns at most 100 invoices per page.
    A single un-paged GET truncates at 100, so the collector's DELETE+reinsert
    would wipe everything past the first page. list_invoices must loop pages.
    """
    pages_requested = []

    def _fake_xero_get(endpoint):
        # endpoint looks like 'Invoices?where=Status=="AUTHORISED"&page=N'
        import re

        m = re.search(r"[?&]page=(\d+)", endpoint)
        page = int(m.group(1)) if m else 1
        pages_requested.append(page)
        if page == 1:
            return {"Invoices": [{"InvoiceID": f"g{i}"} for i in range(100)]}  # full page
        if page == 2:
            return {"Invoices": [{"InvoiceID": "g100"}, {"InvoiceID": "g101"}]}  # short page
        return {"Invoices": []}

    monkeypatch.setattr(xc, "xero_get", _fake_xero_get)

    invoices = xc.list_invoices(status="AUTHORISED")

    assert len(invoices) == 102  # 100 (page1) + 2 (page2), nothing dropped
    assert pages_requested[:2] == [1, 2]  # paged in order
    # Must NOT keep requesting after a short page (102 < 100*2 means page 2 was last).
    assert 3 not in pages_requested


def test_list_invoices_single_short_page_no_extra_request(monkeypatch):
    """A first page below the page size means there is nothing more to fetch."""
    pages_requested = []

    def _fake_xero_get(endpoint):
        import re

        m = re.search(r"[?&]page=(\d+)", endpoint)
        pages_requested.append(int(m.group(1)) if m else 1)
        return {"Invoices": [{"InvoiceID": "g0"}, {"InvoiceID": "g1"}]}  # 2 < 100

    monkeypatch.setattr(xc, "xero_get", _fake_xero_get)

    invoices = xc.list_invoices(status="PAID")
    assert len(invoices) == 2
    assert pages_requested == [1]  # stopped after the first short page


def _store_on(db_path):
    """Build a StateStore bound to db_path WITHOUT running __init__.

    __init__ calls db.ensure_migrations() which resolves the LIVE db path and
    trips the conftest determinism guard. replace_source_rows only needs
    self.db_path + self._get_conn, so construct via object.__new__ and set just
    those attrs — the same bypass the orchestrator tests use.
    """
    from lib.state_store import StateStore

    store = object.__new__(StateStore)
    store.db_path = str(db_path)
    store._initialized = True
    return store


def _seed_invoices(db_path, rows, *, amount_not_null=True):
    conn = sqlite3.connect(str(db_path))
    amount_decl = "amount REAL NOT NULL" if amount_not_null else "amount REAL"
    conn.execute(f"CREATE TABLE invoices (id TEXT PRIMARY KEY, source TEXT, {amount_decl})")
    conn.executemany("INSERT INTO invoices (id, source, amount) VALUES (?,?,?)", rows)
    conn.commit()
    conn.close()


def test_replace_source_rows_is_atomic_on_insert_failure(tmp_path):
    """A mid-reinsert failure must roll back the DELETE — never a half-cleared table."""
    db = tmp_path / "atomic.db"
    _seed_invoices(
        db,
        [("xero_old1", "xero", 10.0), ("xero_old2", "xero", 20.0), ("asana_x", "asana", 5.0)],
    )
    store = _store_on(db)

    # Second row violates NOT NULL (amount=None) -> insert fails mid-batch.
    bad_rows = [
        {"id": "xero_new1", "source": "xero", "amount": 100.0},
        {"id": "xero_new2", "source": "xero", "amount": None},
    ]

    with pytest.raises(sqlite3.Error):
        store.replace_source_rows("invoices", "source", "xero", bad_rows)

    # The DELETE must have rolled back: the original xero rows are still present,
    # and the asana row (different source) is untouched.
    check = sqlite3.connect(str(db))
    rows = {r[0] for r in check.execute("SELECT id FROM invoices").fetchall()}
    check.close()
    assert rows == {"xero_old1", "xero_old2", "asana_x"}


def test_replace_source_rows_replaces_on_success(tmp_path):
    """On success, old source rows are gone and new ones present; other sources kept."""
    db = tmp_path / "atomic2.db"
    _seed_invoices(db, [("xero_old1", "xero", 10.0), ("asana_x", "asana", 5.0)])
    store = _store_on(db)

    inserted = store.replace_source_rows(
        "invoices",
        "source",
        "xero",
        [
            {"id": "xero_new1", "source": "xero", "amount": 100.0},
            {"id": "xero_new2", "source": "xero", "amount": 200.0},
        ],
    )
    assert inserted == 2

    check = sqlite3.connect(str(db))
    rows = {r[0] for r in check.execute("SELECT id FROM invoices").fetchall()}
    check.close()
    assert rows == {"xero_new1", "xero_new2", "asana_x"}  # old xero gone, asana kept


def test_replace_all_rows_is_atomic_on_insert_failure(tmp_path):
    """A mid-reinsert failure must roll back the full-table DELETE (line_items must
    not be left empty if the reinsert fails)."""
    db = tmp_path / "lineitems.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE xero_line_items (id INTEGER PRIMARY KEY, invoice_id TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO xero_line_items (invoice_id) VALUES (?)", [("xero_a",), ("xero_b",)]
    )
    conn.commit()
    conn.close()

    store = _store_on(db)
    # Second row violates NOT NULL on invoice_id -> insert fails mid-batch.
    bad_rows = [{"invoice_id": "xero_c"}, {"invoice_id": None}]
    with pytest.raises(sqlite3.Error):
        store.replace_all_rows("xero_line_items", bad_rows)

    # The DELETE rolled back -> original rows still present.
    check = sqlite3.connect(str(db))
    fks = {r[0] for r in check.execute("SELECT invoice_id FROM xero_line_items").fetchall()}
    check.close()
    assert fks == {"xero_a", "xero_b"}


def test_xero_line_items_cleared_before_reinsert_and_fk_matches(tmp_path, monkeypatch):
    """line_items must be cleared each sync (no unbounded duplicate growth) and the
    line_items invoice_id must equal the invoice row id (same GUID derivation)."""
    from unittest.mock import MagicMock

    import lib.collectors.xero as xero_mod

    invoice_ids = []
    line_item_fks = []
    line_items_replaced = {"n": 0}

    store = MagicMock()
    store.db_path = str(tmp_path / "x.db")
    store.query.return_value = []

    def _capture_replace(table, source_column, source_value, rows):
        if table == "invoices":
            invoice_ids.extend(r["id"] for r in rows)
        return len(rows)

    def _capture_replace_all(table, rows):
        # line_items now go through the atomic full-table replace (not query+insert).
        if table == "xero_line_items":
            line_items_replaced["n"] += 1
            line_item_fks.extend(r["invoice_id"] for r in rows)
        return len(rows)

    store.replace_source_rows.side_effect = _capture_replace
    store.replace_all_rows.side_effect = _capture_replace_all

    collector = xero_mod.XeroCollector({}, store=store)

    inv = {
        "Type": "ACCREC",
        "InvoiceID": "guid-xyz",
        "InvoiceNumber": "INV 9",
        "Contact": {"Name": "C"},
        "Status": "AUTHORISED",
        "Total": 10,
        "AmountDue": 10,
        "LineItems": [{"Description": "Item", "Quantity": 1, "UnitAmount": 10, "LineAmount": 10}],
    }
    _calls = iter([[inv], [], [inv], []])  # two syncs: (PAID,AUTHORISED) each
    # Patch via the string target so pytest resolves the live
    # sys.modules["engine.xero_client"] — the exact object the collector's lazy
    # `from engine.xero_client import ...` reads — immune to module-cache churn
    # left by other tests (the `import ... as xc` alias can diverge from it).
    monkeypatch.setattr("engine.xero_client.list_invoices", lambda *a, **k: next(_calls))
    monkeypatch.setattr("engine.xero_client.list_contacts", lambda *a, **k: [])
    monkeypatch.setattr("engine.xero_client.list_credit_notes", lambda *a, **k: [])
    monkeypatch.setattr("engine.xero_client.list_bank_transactions", lambda *a, **k: [])
    monkeypatch.setattr("engine.xero_client.list_tax_rates", lambda *a, **k: [])

    collector.sync()
    collector.sync()

    # line_items go through the atomic full-table replace each sync (2 syncs ->
    # 2 replaces), so rows do not accumulate across syncs.
    assert line_items_replaced["n"] == 2
    # FK consistency: every line_items.invoice_id equals an invoice row id.
    assert set(line_item_fks) <= set(invoice_ids)
    assert "xero_guid-xyz" in invoice_ids
    assert line_item_fks == ["xero_guid-xyz", "xero_guid-xyz"]  # one per sync, GUID-keyed


def test_replace_source_rows_empty_clears_source(tmp_path):
    """Passing [] deletes the source rows (caller is responsible for empty-guarding)."""
    db = tmp_path / "atomic3.db"
    _seed_invoices(
        db, [("xero_old1", "xero", 10.0), ("asana_x", "asana", 5.0)], amount_not_null=False
    )
    store = _store_on(db)

    inserted = store.replace_source_rows("invoices", "source", "xero", [])
    assert inserted == 0

    check = sqlite3.connect(str(db))
    rows = {r[0] for r in check.execute("SELECT id FROM invoices").fetchall()}
    check.close()
    assert rows == {"asana_x"}  # xero cleared, asana kept
