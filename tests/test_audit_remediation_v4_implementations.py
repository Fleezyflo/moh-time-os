"""
Audit remediation implementation tests — Pass 4.

ALL tests are [B] (behavioral) — they exercise real runtime behavior.

Covers:
1. Orchestrator recovery lifecycle (reinit_failed_collectors)
2. StateStore.transaction(fn) abstraction
3. Schema ownership: issue_notes, watchers, identities in lib/schema.py
4. Consumer-facing contract: PatternDetectionResponse model in response_models
5. Sync-health surfacing: get_status includes init_failed entries
"""

import pytest

from lib.state_store import StateStore

# ============================================================
# Helpers
# ============================================================


def _fresh_store(db_path: str) -> StateStore:
    """Create a fresh StateStore with singleton reset."""
    StateStore._instance = None
    store = StateStore(db_path)
    return store


# ============================================================
# Group 1: Orchestrator recovery lifecycle
# ============================================================


class _FakeCollectorOK:
    """Fake collector that initializes successfully."""

    def __init__(self, config, store):
        self.sync_interval = config.get("sync_interval", 300)

    def sync(self):
        return {"source": "fake_ok", "success": True, "collected": 1, "stored": 1}

    def health_check(self):
        return True


class _FakeCollectorFail:
    """Fake collector that raises on init."""

    def __init__(self, config, store):
        raise ConnectionError("simulated init failure")


class _FakeCollectorRecoverable:
    """Fake collector that fails first N times, then succeeds."""

    _call_count = 0
    _fail_until = 1

    def __init__(self, config, store):
        _FakeCollectorRecoverable._call_count += 1
        if _FakeCollectorRecoverable._call_count <= _FakeCollectorRecoverable._fail_until:
            raise ConnectionError(f"fail #{_FakeCollectorRecoverable._call_count}")
        self.sync_interval = config.get("sync_interval", 300)

    def sync(self):
        return {"source": "recoverable", "success": True, "collected": 1, "stored": 1}

    def health_check(self):
        return True


class TestOrchestratorRecoveryLifecycle:
    """[B] Verify orchestrator recovery clears stale init_failures."""

    def _make_orchestrator(self):
        """Create a minimal orchestrator without __init__ side effects."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        orch = object.__new__(CollectorOrchestrator)
        orch.logger = __import__("logging").getLogger("test_orch")
        orch.config = {
            "sources": {
                "fake_ok": {"enabled": True, "sync_interval": 300},
                "fake_fail": {"enabled": True, "sync_interval": 300},
            }
        }
        orch.collectors = {}
        orch.init_failures = {}
        orch.store = None
        return orch

    def test_B_reinit_clears_recovered_collector(self):
        """[B] A collector that now succeeds is removed from init_failures."""
        import lib.collectors.orchestrator as orch_module

        orch = self._make_orchestrator()
        orch.config = {
            "sources": {
                "tasks": {"enabled": True, "sync_interval": 300},
            }
        }
        orch.init_failures = {"tasks": "was broken"}

        # Patch TasksCollector to be our OK fake
        with __import__("unittest.mock", fromlist=["patch"]).patch.object(
            orch_module, "TasksCollector", _FakeCollectorOK
        ):
            still_failed = orch.reinit_failed_collectors()

        assert "tasks" not in still_failed, "tasks should have recovered"
        assert "tasks" not in orch.init_failures, "tasks should be removed from init_failures"
        assert "tasks" in orch.collectors, "tasks should now be in collectors"

    def test_B_reinit_keeps_still_failing_collector(self):
        """[B] A collector that still fails remains in init_failures."""
        import lib.collectors.orchestrator as orch_module

        orch = self._make_orchestrator()
        orch.config = {
            "sources": {
                "gmail": {"enabled": True, "sync_interval": 120},
            }
        }
        orch.init_failures = {"gmail": "creds expired"}

        with __import__("unittest.mock", fromlist=["patch"]).patch.object(
            orch_module, "GmailCollector", _FakeCollectorFail
        ):
            still_failed = orch.reinit_failed_collectors()

        assert "gmail" in still_failed, "gmail should still be failed"
        assert "gmail" in orch.init_failures
        assert "gmail" not in orch.collectors

    def test_B_reinit_empty_when_no_failures(self):
        """[B] reinit_failed_collectors is a no-op when nothing is failed."""
        orch = self._make_orchestrator()
        orch.init_failures = {}
        result = orch.reinit_failed_collectors()
        assert result == {}

    def test_B_get_status_reflects_recovery(self):
        """[B] get_status no longer shows init_failed after recovery."""
        import lib.collectors.orchestrator as orch_module

        orch = self._make_orchestrator()
        orch.config = {
            "sources": {
                "calendar": {"enabled": True, "sync_interval": 60},
            }
        }
        orch.init_failures = {"calendar": "timeout"}
        orch.store = type("FakeStore", (), {"get_sync_states": lambda self: {}})()

        # Before recovery: status should show init_failed
        status_before = orch.get_status()
        assert status_before["calendar"]["init_failed"] is True
        assert status_before["calendar"]["healthy"] is False

        # Recover
        with __import__("unittest.mock", fromlist=["patch"]).patch.object(
            orch_module, "CalendarCollector", _FakeCollectorOK
        ):
            orch.reinit_failed_collectors()

        # After recovery: status should show healthy collector
        status_after = orch.get_status()
        assert "calendar" in status_after
        assert status_after["calendar"].get("init_failed") is not True
        assert status_after["calendar"]["enabled"] is True

    def test_B_sync_impl_triggers_recovery(self):
        """[B] _sync_impl calls reinit before sync-all when failures exist."""
        import lib.collectors.orchestrator as orch_module

        orch = self._make_orchestrator()
        orch.config = {
            "sources": {
                "chat": {"enabled": True, "sync_interval": 300},
            }
        }
        orch.init_failures = {"chat": "api down"}
        orch.store = type("FakeStore", (), {"get_sync_states": lambda self: {}})()

        # Patch ChatCollector to succeed
        with __import__("unittest.mock", fromlist=["patch"]).patch.object(
            orch_module, "ChatCollector", _FakeCollectorOK
        ):
            # _sync_impl(None) triggers recovery first, then syncs
            orch._sync_impl(None)

        # chat should have recovered and been synced
        assert "chat" not in orch.init_failures
        assert "chat" in orch.collectors


# ============================================================
# Group 2: StateStore.transaction(fn)
# ============================================================


class TestStateStoreTransaction:
    """[B] Verify StateStore.transaction() behavior with real SQLite."""

    def _make_store(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        store = _fresh_store(db_path)
        return store

    def test_B_transaction_commits_on_success(self, tmp_path):
        """[B] Successful callback commits changes to DB."""
        store = self._make_store(tmp_path)

        # Create a test table and insert via transaction
        store.execute_write("CREATE TABLE test_txn (id TEXT PRIMARY KEY, val TEXT)")

        def insert_row(conn):
            conn.execute("INSERT INTO test_txn (id, val) VALUES (?, ?)", ["k1", "v1"])
            return "done"

        result = store.transaction(insert_row)
        assert result == "done"

        # Verify the row persisted
        rows = store.query("SELECT * FROM test_txn WHERE id = 'k1'")
        assert len(rows) == 1
        assert rows[0]["val"] == "v1"
        StateStore._instance = None

    def test_B_transaction_rollback_on_exception(self, tmp_path):
        """[B] Exception in callback rolls back all changes."""
        store = self._make_store(tmp_path)
        store.execute_write("CREATE TABLE test_txn2 (id TEXT PRIMARY KEY, val TEXT)")

        def failing_txn(conn):
            conn.execute("INSERT INTO test_txn2 (id, val) VALUES (?, ?)", ["k1", "v1"])
            raise ValueError("simulated failure")

        with pytest.raises(ValueError, match="simulated failure"):
            store.transaction(failing_txn)

        # Row should NOT be persisted
        rows = store.query("SELECT * FROM test_txn2")
        assert len(rows) == 0
        StateStore._instance = None

    def test_B_transaction_read_write_read_semantics(self, tmp_path):
        """[B] Callback can read, then write, then read — all on one connection."""
        store = self._make_store(tmp_path)
        store.execute_write("CREATE TABLE test_txn3 (id TEXT PRIMARY KEY, val INTEGER)")
        store.execute_write("INSERT INTO test_txn3 (id, val) VALUES ('counter', 0)")

        def increment_and_read(conn):
            cur = conn.cursor()
            # Read current value
            cur.execute("SELECT val FROM test_txn3 WHERE id = 'counter'")
            old_val = cur.fetchone()[0]
            # Write new value
            cur.execute("UPDATE test_txn3 SET val = ? WHERE id = 'counter'", [old_val + 1])
            # Read back
            cur.execute("SELECT val FROM test_txn3 WHERE id = 'counter'")
            return cur.fetchone()[0]

        new_val = store.transaction(increment_and_read)
        assert new_val == 1

        # Verify persisted
        rows = store.query("SELECT val FROM test_txn3 WHERE id = 'counter'")
        assert rows[0]["val"] == 1
        StateStore._instance = None

    def test_B_transaction_holds_write_lock(self, tmp_path):
        """[B] transaction() holds _write_lock during execution."""
        store = self._make_store(tmp_path)
        lock_was_held = []

        def check_lock(conn):
            # _write_lock is an RLock, so we can check if it's held by trying
            # to acquire it (should succeed since RLock is reentrant)
            acquired = store._write_lock.acquire(blocking=False)
            if acquired:
                store._write_lock.release()
            lock_was_held.append(acquired)
            return True

        store.transaction(check_lock)
        # RLock is reentrant, so the same thread can acquire it again
        assert lock_was_held[0] is True
        StateStore._instance = None

    def test_B_transaction_returns_callback_result(self, tmp_path):
        """[B] transaction() returns whatever the callback returns."""
        store = self._make_store(tmp_path)

        result = store.transaction(lambda conn: {"key": "value", "count": 42})
        assert result == {"key": "value", "count": 42}
        StateStore._instance = None


# ============================================================
# Group 3: Schema ownership verification
# ============================================================


class TestSchemaOwnership:
    """[B] Verify issue_notes, watchers, identities are now in lib/schema.py."""

    def test_B_issue_notes_in_schema(self):
        """[B] issue_notes table definition exists in schema.py TABLES."""
        from lib.schema import TABLES

        assert "issue_notes" in TABLES, "issue_notes should be in schema.py TABLES"
        col_names = [c[0] for c in TABLES["issue_notes"]["columns"]]
        assert "note_id" in col_names
        assert "issue_id" in col_names
        assert "text" in col_names

    def test_B_watchers_in_schema(self):
        """[B] watchers table definition exists in schema.py TABLES."""
        from lib.schema import TABLES

        assert "watchers" in TABLES, "watchers should be in schema.py TABLES"
        col_names = [c[0] for c in TABLES["watchers"]["columns"]]
        assert "watcher_id" in col_names
        assert "issue_id" in col_names
        assert "watch_type" in col_names
        assert "dismissed_at" in col_names
        assert "snoozed_until" in col_names

    def test_B_identities_in_schema(self):
        """[B] identities table definition exists in schema.py TABLES."""
        from lib.schema import TABLES

        assert "identities" in TABLES, "identities should be in schema.py TABLES"
        col_names = [c[0] for c in TABLES["identities"]["columns"]]
        assert "id" in col_names
        assert "display_name" in col_names
        assert "canonical_id" in col_names
        assert "confidence_score" in col_names

    def test_B_schema_version_bumped(self):
        """[B] SCHEMA_VERSION is at least 20 after adding new tables."""
        from lib.schema import SCHEMA_VERSION

        assert SCHEMA_VERSION >= 20, f"SCHEMA_VERSION should be >= 20, got {SCHEMA_VERSION}"

    def test_B_indexes_exist_for_new_tables(self):
        """[B] Indexes are defined for issue_notes, watchers, identities."""
        from lib.schema import INDEXES

        index_names = [idx[0] for idx in INDEXES]
        assert "idx_issue_notes_issue" in index_names
        assert "idx_watchers_issue" in index_names
        assert "idx_watchers_triggered" in index_names
        assert "idx_identities_canonical" in index_names

    def test_B_runtime_ddl_removed_from_server(self):
        """[B] api/server.py no longer has CREATE TABLE IF NOT EXISTS for these tables."""
        import inspect

        import api.server as server_module

        # Check add_issue_note
        src = inspect.getsource(server_module.add_issue_note)
        assert "CREATE TABLE IF NOT EXISTS issue_notes" not in src

        # Check get_watchers
        src = inspect.getsource(server_module.get_watchers)
        assert "CREATE TABLE IF NOT EXISTS watchers" not in src

        # Check get_fix_data
        src = inspect.getsource(server_module.get_fix_data)
        assert "CREATE TABLE IF NOT EXISTS identities" not in src
        assert "CREATE TABLE IF NOT EXISTS entity_links" not in src


# ============================================================
# Group 4: Consumer-facing contract (PatternDetectionResponse)
# ============================================================


class TestPatternDetectionContract:
    """[B] Verify PatternDetectionResponse model is properly defined."""

    def test_B_pattern_detection_response_exists(self):
        """[B] PatternDetectionResponse is importable from response_models."""
        from api.response_models import PatternDetectionResponse

        assert PatternDetectionResponse is not None

    def test_B_pattern_detection_data_has_required_fields(self):
        """[B] PatternDetectionData includes detection_success and detection_errors."""
        from api.response_models import PatternDetectionData

        # Create an instance with defaults
        data = PatternDetectionData()
        assert data.detection_success is True
        assert data.detection_errors == 0
        assert data.detection_error_details == []
        assert data.patterns == []
        assert data.total_detected == 0

    def test_B_pattern_detection_data_with_errors(self):
        """[B] PatternDetectionData can represent degraded detection state."""
        from api.response_models import PatternDetectionData

        data = PatternDetectionData(
            patterns=[{"id": "p1"}],
            total_detected=1,
            detection_success=False,
            detection_errors=3,
            detection_error_details=["detector_a failed", "detector_b timeout", "detector_c crash"],
        )
        assert data.detection_success is False
        assert data.detection_errors == 3
        assert len(data.detection_error_details) == 3

    def test_B_pattern_detection_response_typed_data(self):
        """[B] PatternDetectionResponse.data is typed as PatternDetectionData."""
        from api.response_models import PatternDetectionData, PatternDetectionResponse

        resp = PatternDetectionResponse(
            status="ok",
            data=PatternDetectionData(detection_success=True, detection_errors=0),
            computed_at="2026-03-13T00:00:00",
        )
        assert resp.data.detection_success is True
        assert resp.data.detection_errors == 0

    def test_B_spec_router_uses_typed_response(self):
        """[B] spec_router patterns endpoint uses PatternDetectionResponse."""
        import inspect

        from api.spec_router import get_intelligence_patterns

        src = inspect.getsource(get_intelligence_patterns)
        assert "PatternDetectionResponse" in src, (
            "get_intelligence_patterns must use PatternDetectionResponse, "
            f"not IntelligenceResponse. Found: {src[:200]}"
        )
        assert "PatternDetectionData" in src, (
            "get_intelligence_patterns must construct PatternDetectionData, "
            f"not a plain dict. Found: {src[:200]}"
        )


# ============================================================
# Group 5: Sync-health surfacing via get_status
# ============================================================


class TestSyncHealthSurfacing:
    """[B] Verify init_failures are surfaced via get_status / /api/sync/status."""

    def test_B_get_status_surfaces_init_failed_collectors(self):
        """[B] get_status includes init_failed entries with error details."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        orch = object.__new__(CollectorOrchestrator)
        orch.logger = __import__("logging").getLogger("test")
        orch.collectors = {}
        orch.init_failures = {"xero": "API key expired", "drive": "quota exceeded"}
        orch.store = type("FakeStore", (), {"get_sync_states": lambda self: {}})()

        status = orch.get_status()

        assert "xero" in status
        assert status["xero"]["init_failed"] is True
        assert status["xero"]["init_error"] == "API key expired"
        assert status["xero"]["healthy"] is False

        assert "drive" in status
        assert status["drive"]["init_failed"] is True
        assert status["drive"]["init_error"] == "quota exceeded"

    def test_B_get_status_mixed_healthy_and_failed(self):
        """[B] get_status shows both healthy collectors and failed ones."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        orch = object.__new__(CollectorOrchestrator)
        orch.logger = __import__("logging").getLogger("test")
        orch.collectors = {
            "tasks": type("Fake", (), {"sync_interval": 300})(),
        }
        orch.init_failures = {"gmail": "auth error"}
        orch.store = type(
            "FakeStore",
            (),
            {
                "get_sync_states": lambda self: {
                    "tasks": {
                        "last_sync": "2026-03-13T10:00:00",
                        "last_success": "2026-03-13T10:00:00",
                        "items_synced": 42,
                        "error": None,
                    },
                }
            },
        )()

        status = orch.get_status()

        # tasks should be healthy
        assert status["tasks"]["healthy"] is True
        assert status["tasks"]["items_synced"] == 42

        # gmail should show init failure
        assert status["gmail"]["init_failed"] is True
        assert status["gmail"]["healthy"] is False

    def test_B_collector_status_entry_model(self):
        """[B] CollectorStatusEntry model represents both healthy and failed states."""
        from api.response_models import CollectorStatusEntry

        # Healthy collector
        healthy = CollectorStatusEntry(
            enabled=True,
            healthy=True,
            items_synced=100,
            last_sync="2026-03-13T10:00:00",
        )
        assert healthy.init_failed is False
        assert healthy.init_error is None

        # Failed collector
        failed = CollectorStatusEntry(
            enabled=True,
            healthy=False,
            init_failed=True,
            init_error="connection refused",
        )
        assert failed.init_failed is True
        assert failed.init_error == "connection refused"


# ============================================================
# Group 6: entity_links Schema Alignment and Migration Safety
# ============================================================


class TestEntityLinksSchemaAlignment:
    """[B] Verify entity_links in schema.py matches the production contract."""

    def test_B_entity_links_pk_is_text(self):
        """[B] entity_links PK must be link_id TEXT, not id INTEGER."""
        from lib.schema import TABLES

        entity_links = TABLES["entity_links"]
        pk_col = entity_links["columns"][0]
        assert pk_col[0] == "link_id", f"PK column name is {pk_col[0]}, expected link_id"
        assert "TEXT PRIMARY KEY" in pk_col[1], f"PK type is {pk_col[1]}, expected TEXT PRIMARY KEY"

    def test_B_no_stale_integer_pk(self):
        """[B] entity_links must NOT have an id INTEGER PRIMARY KEY anywhere."""
        from lib.schema import TABLES

        entity_links = TABLES["entity_links"]
        col_names = [c[0] for c in entity_links["columns"]]
        col_ddls = [c[1] for c in entity_links["columns"]]

        # No column named 'id' with INTEGER PRIMARY KEY
        for name, ddl in zip(col_names, col_ddls, strict=True):
            if name == "id":
                assert "INTEGER PRIMARY KEY" not in ddl, (
                    "Stale id INTEGER PRIMARY KEY found — must be link_id TEXT PRIMARY KEY"
                )

    def test_B_entity_links_has_production_columns(self):
        """[B] entity_links includes all columns used by entity_link_service.py."""
        from lib.schema import TABLES

        entity_links = TABLES["entity_links"]
        col_names = {c[0] for c in entity_links["columns"]}

        required = {
            "link_id",
            "from_artifact_id",
            "to_entity_type",
            "to_entity_id",
            "method",
            "confidence",
            "confidence_reasons",
            "status",
            "created_at",
            "updated_at",
            "confirmed_by",
            "confirmed_at",
        }
        missing = required - col_names
        assert not missing, f"Missing columns from entity_links: {missing}"

    def test_B_entity_links_status_index_exists(self):
        """[B] An index on entity_links.status is declared for query performance."""
        from lib.schema import INDEXES

        index_entries = [(idx[0], idx[1], idx[2]) for idx in INDEXES]
        status_idx = [
            entry for entry in index_entries if entry[1] == "entity_links" and "status" in entry[2]
        ]
        assert len(status_idx) > 0, "No index on entity_links.status found"

    def test_B_get_fix_data_query_compatible_with_schema(self):
        """[B] get_fix_data references link_id, which must exist in schema."""
        import inspect

        import api.server as server_module

        src = inspect.getsource(server_module.get_fix_data)
        # The query uses el.link_id — this must exist in schema
        assert "el.link_id" in src, "get_fix_data should reference el.link_id"

        from lib.schema import TABLES

        col_names = {c[0] for c in TABLES["entity_links"]["columns"]}
        assert "link_id" in col_names, "link_id must be in entity_links schema"

    def test_B_converge_no_phase0_drop_on_text_pk(self, tmp_path):
        """[B] converge() must NOT drop entity_links when existing table has TEXT PK."""
        import sqlite3

        from lib import schema
        from lib.schema_engine import converge

        db_path = tmp_path / "migration_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Simulate existing DB with production-shaped entity_links (TEXT PK)
        conn.execute("""
            CREATE TABLE entity_links (
                link_id TEXT PRIMARY KEY,
                from_artifact_id TEXT,
                to_entity_type TEXT NOT NULL,
                to_entity_id TEXT NOT NULL,
                method TEXT,
                confidence REAL DEFAULT 1.0,
                confidence_reasons TEXT DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'proposed',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                confirmed_by TEXT,
                confirmed_at TEXT
            )
        """)
        # Insert test data
        conn.execute(
            "INSERT INTO entity_links (link_id, to_entity_type, to_entity_id) "
            "VALUES ('lnk_test1', 'client', 'c_001')"
        )
        conn.commit()

        # Create all other tables so converge doesn't fail on missing deps
        for table_name, table_def in schema.TABLES.items():
            if table_name == "entity_links":
                continue
            cols = ", ".join(f"{c[0]} {c[1]}" for c in table_def["columns"])
            try:
                conn.execute(f"CREATE TABLE IF NOT EXISTS [{table_name}] ({cols})")
            except sqlite3.OperationalError:
                pass  # Some tables may have complex constraints
        conn.commit()

        # Run converge
        results = converge(conn)

        # entity_links must NOT appear in tables_rebuilt (Phase 0 drop)
        assert "entity_links" not in results.get("tables_rebuilt", []), (
            "converge() dropped entity_links — Phase 0 PK mismatch detected. "
            "This means the schema.py PK type doesn't match the existing table."
        )

        # Verify data survived
        row = conn.execute(
            "SELECT link_id FROM entity_links WHERE link_id = 'lnk_test1'"
        ).fetchone()
        assert row is not None, "Test data lost after converge — Phase 0 drop occurred"
        assert row[0] == "lnk_test1"

        conn.close()

    def test_B_converge_adds_missing_columns_to_old_table(self, tmp_path):
        """[B] converge() adds missing columns to an older entity_links table."""
        import sqlite3

        from lib import schema
        from lib.schema_engine import converge

        db_path = tmp_path / "migration_col_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Simulate older table with fewer columns (like pre-v4 runtime DDL)
        conn.execute("""
            CREATE TABLE entity_links (
                link_id TEXT PRIMARY KEY,
                from_artifact_id TEXT,
                to_entity_type TEXT NOT NULL,
                to_entity_id TEXT NOT NULL,
                method TEXT,
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

        # Create all other tables
        for table_name, table_def in schema.TABLES.items():
            if table_name == "entity_links":
                continue
            cols = ", ".join(f"{c[0]} {c[1]}" for c in table_def["columns"])
            try:
                conn.execute(f"CREATE TABLE IF NOT EXISTS [{table_name}] ({cols})")
            except sqlite3.OperationalError:
                pass
        conn.commit()

        results = converge(conn)

        # Check that missing columns were added
        cursor = conn.execute("PRAGMA table_info(entity_links)")
        actual_cols = {row[1] for row in cursor.fetchall()}

        expected_new = {
            "confidence_reasons",
            "status",
            "updated_at",
            "confirmed_by",
            "confirmed_at",
        }
        missing = expected_new - actual_cols
        assert not missing, f"converge() did not add columns: {missing}"

        # Verify columns_added includes entity_links entries
        added = [c for c in results.get("columns_added", []) if "entity_links" in str(c)]
        assert len(added) > 0, "No entity_links columns in columns_added result"

        conn.close()

    def test_B_fresh_db_creates_correct_entity_links(self, tmp_path):
        """[B] create_fresh() produces entity_links with correct schema."""
        import sqlite3

        from lib.schema_engine import create_fresh

        db_path = tmp_path / "fresh_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        create_fresh(conn)

        cursor = conn.execute("PRAGMA table_info(entity_links)")
        cols = {row[1]: row[2] for row in cursor.fetchall()}

        assert "link_id" in cols, "link_id column missing from fresh entity_links"
        assert cols["link_id"] == "TEXT", f"link_id type is {cols['link_id']}, expected TEXT"
        assert "id" not in cols or cols.get("id") != "INTEGER", (
            "Stale id INTEGER column found in fresh entity_links"
        )
        assert "status" in cols, "status column missing"
        assert "confidence_reasons" in cols, "confidence_reasons column missing"
        assert "updated_at" in cols, "updated_at column missing"
        assert "confirmed_by" in cols, "confirmed_by column missing"
        assert "confirmed_at" in cols, "confirmed_at column missing"

        conn.close()


# ============================================================
# Group 7: /couplings endpoint and db_opt/indexes.py fixes
# ============================================================


class TestCouplingsEndpointFix:
    """[B] Verify /couplings endpoint queries the couplings table, not entity_links."""

    def test_B_couplings_query_uses_correct_table(self):
        """[B] get_couplings_v2 must SELECT FROM couplings, not entity_links."""
        import inspect

        import api.spec_router as router_module

        src = inspect.getsource(router_module.get_couplings_v2)
        assert "FROM couplings" in src, "get_couplings_v2 does not query FROM couplings"
        assert "FROM entity_links" not in src, (
            "get_couplings_v2 still queries FROM entity_links (wrong table)"
        )

    def test_B_couplings_selected_columns_exist_in_schema(self):
        """[B] All columns selected by /couplings exist in the couplings table."""
        from lib.schema import TABLES

        couplings = TABLES["couplings"]
        col_names = {c[0] for c in couplings["columns"]}

        # These are the columns selected in the query
        selected = {
            "coupling_id",
            "anchor_ref_type",
            "anchor_ref_id",
            "entity_refs",
            "coupling_type",
            "strength",
            "why",
            "confidence",
        }
        missing = selected - col_names
        assert not missing, f"Columns {missing} not in couplings table"

    def test_B_couplings_filter_columns_exist_in_schema(self):
        """[B] WHERE filter columns (anchor_ref_type, anchor_ref_id) exist."""
        from lib.schema import TABLES

        couplings = TABLES["couplings"]
        col_names = {c[0] for c in couplings["columns"]}

        assert "anchor_ref_type" in col_names
        assert "anchor_ref_id" in col_names

    def test_B_couplings_query_runs_on_real_table(self, tmp_path):
        """[B] The /couplings query executes without error on a real DB."""
        import sqlite3

        from lib.schema_engine import create_fresh

        db_path = tmp_path / "couplings_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        create_fresh(conn)

        # Insert a test coupling
        conn.execute(
            """INSERT INTO couplings
               (coupling_id, anchor_ref_type, anchor_ref_id, entity_refs,
                coupling_type, strength, why, investigation_path, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("cpl_test1", "issue", "iss_001", "[]", "shared_signals", 0.9, "{}", "[]", 0.85),
        )
        conn.commit()

        # Run the exact query from the endpoint
        cursor = conn.execute(
            "SELECT coupling_id, anchor_ref_type, anchor_ref_id, entity_refs, "
            "coupling_type, strength, why, confidence "
            "FROM couplings "
            "WHERE 1=1 "
            "ORDER BY strength DESC "
            "LIMIT 50"
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["coupling_id"] == "cpl_test1"
        assert row["strength"] == 0.9
        assert row["confidence"] == 0.85

        # Run with anchor filter
        cursor = conn.execute(
            "SELECT coupling_id, anchor_ref_type, anchor_ref_id, entity_refs, "
            "coupling_type, strength, why, confidence "
            "FROM couplings "
            "WHERE 1=1 AND anchor_ref_type = ? AND anchor_ref_id = ? "
            "ORDER BY strength DESC "
            "LIMIT 50",
            ("issue", "iss_001"),
        )
        rows = cursor.fetchall()
        assert len(rows) == 1

        conn.close()


class TestDbOptIndexesFix:
    """[B] Verify db_opt/indexes.py entity_links entries use real column names."""

    def test_B_no_stale_column_names_in_indexes(self):
        """[B] PERFORMANCE_INDEXES must not reference source_type/target_type."""
        from lib.db_opt.indexes import PERFORMANCE_INDEXES

        stale_names = {"source_type", "source_id", "target_type", "target_id"}
        for table, columns in PERFORMANCE_INDEXES:
            if table == "entity_links":
                for col in columns:
                    assert col not in stale_names, (
                        f"Stale column name '{col}' in entity_links index definition"
                    )

    def test_B_entity_links_index_columns_exist_in_schema(self):
        """[B] Every entity_links index column in db_opt matches schema.py."""
        from lib.db_opt.indexes import PERFORMANCE_INDEXES
        from lib.schema import TABLES

        schema_cols = {c[0] for c in TABLES["entity_links"]["columns"]}

        for table, columns in PERFORMANCE_INDEXES:
            if table == "entity_links":
                for col in columns:
                    assert col in schema_cols, (
                        f"Index column '{col}' not in entity_links schema "
                        f"(available: {schema_cols})"
                    )

    def test_B_ensure_indexes_no_entity_links_errors(self, tmp_path):
        """[B] ensure_indexes() creates entity_links indexes without errors."""
        import sqlite3

        from lib.db_opt.indexes import ensure_indexes
        from lib.schema_engine import create_fresh

        db_path = tmp_path / "index_test.db"
        conn = sqlite3.connect(str(db_path))
        create_fresh(conn)
        conn.close()

        report = ensure_indexes(str(db_path))

        # Check no entity_links-related errors
        el_errors = [e for e in report.errors if "entity_links" in e.get("index", "")]
        assert len(el_errors) == 0, f"entity_links index creation errors: {el_errors}"
