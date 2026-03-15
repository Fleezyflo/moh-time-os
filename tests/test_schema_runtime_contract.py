"""
Schema/Runtime Contract Tests.

Regression tests that verify runtime SQL code can operate against a
fresh database created by schema_engine.  These tests catch:
  - Tables/views referenced at runtime but missing from schema.py
  - Columns referenced at runtime but missing from schema.py
  - Views that only exist in test fixtures, not canonical schema
  - Runtime DDL that masks drift instead of fixing it

If any test here fails, a production fresh-DB bootstrap is broken.
"""

import sqlite3
from pathlib import Path

import pytest

from lib import schema, schema_engine

REPO_ROOT = Path(__file__).parent.parent


# ──────────────────────────────────────────────────────────────
# Fixture: fresh in-memory DB built by schema_engine
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_db():
    """Create a completely fresh DB using only schema_engine — no runtime DDL."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    result = schema_engine.create_fresh(conn)
    assert not result["errors"], f"schema_engine.create_fresh had errors: {result['errors']}"
    yield conn
    conn.close()


# ──────────────────────────────────────────────────────────────
# Test 1: All canonical tables exist
# ──────────────────────────────────────────────────────────────


class TestFreshDBTables:
    """Verify every table declared in schema.py exists in a fresh DB."""

    def test_all_tables_created(self, fresh_db):
        cursor = fresh_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        existing = {row[0] for row in cursor.fetchall()}

        for table_name in schema.TABLES:
            assert table_name in existing, (
                f"Table '{table_name}' declared in schema.py but not created "
                f"by schema_engine.create_fresh()"
            )

    def test_all_views_created(self, fresh_db):
        cursor = fresh_db.execute("SELECT name FROM sqlite_master WHERE type='view'")
        existing = {row[0] for row in cursor.fetchall()}

        for view_name in schema.VIEWS:
            assert view_name in existing, (
                f"View '{view_name}' declared in schema.py VIEWS but not created "
                f"by schema_engine.create_fresh()"
            )

    def test_governance_history_exists(self, fresh_db):
        """Regression: governance_history was phantom-referenced in server.py."""
        cursor = fresh_db.execute("PRAGMA table_info(governance_history)")
        cols = {row[1] for row in cursor.fetchall()}
        required = {
            "id",
            "decision_id",
            "action",
            "type",
            "target_id",
            "processed_by",
            "created_at",
        }
        assert required.issubset(cols), f"governance_history missing columns: {required - cols}"


# ──────────────────────────────────────────────────────────────
# Test 2: All canonical views are queryable on fresh DB
# ──────────────────────────────────────────────────────────────


class TestFreshDBViews:
    """Verify cross-entity views work on a fresh DB (no data, just no crash)."""

    def test_v_task_with_client_queryable(self, fresh_db):
        fresh_db.execute("SELECT * FROM [v_task_with_client] LIMIT 1").fetchall()

    def test_v_client_operational_profile_queryable(self, fresh_db):
        fresh_db.execute("SELECT * FROM [v_client_operational_profile] LIMIT 1").fetchall()

    def test_v_project_operational_state_queryable(self, fresh_db):
        fresh_db.execute("SELECT * FROM [v_project_operational_state] LIMIT 1").fetchall()

    def test_v_person_load_profile_queryable(self, fresh_db):
        fresh_db.execute("SELECT * FROM [v_person_load_profile] LIMIT 1").fetchall()

    def test_v_communication_client_link_queryable(self, fresh_db):
        fresh_db.execute("SELECT * FROM [v_communication_client_link] LIMIT 1").fetchall()

    def test_v_invoice_client_project_queryable(self, fresh_db):
        fresh_db.execute("SELECT * FROM [v_invoice_client_project] LIMIT 1").fetchall()

    def test_views_not_only_in_fixture(self):
        """Verify views are defined in schema.py, not just fixture_db.py."""
        expected_views = {
            "v_task_with_client",
            "v_client_operational_profile",
            "v_project_operational_state",
            "v_person_load_profile",
            "v_communication_client_link",
            "v_invoice_client_project",
        }
        for view in expected_views:
            assert view in schema.VIEWS, (
                f"View '{view}' must be in schema.VIEWS (canonical), not only in test fixtures"
            )


# ──────────────────────────────────────────────────────────────
# Test 3: Signals table has full v4 column set
# ──────────────────────────────────────────────────────────────


class TestSignalsSchema:
    """Regression: v4/signal_service.py needs columns beyond the minimal set."""

    def test_signals_columns_complete(self, fresh_db):
        """All columns used by SignalService must exist in the canonical schema."""
        cursor = fresh_db.execute("PRAGMA table_info(signals)")
        cols = {row[1] for row in cursor.fetchall()}

        # Columns required by lib/v4/signal_service.py
        required = {
            "signal_id",
            "signal_type",
            "entity_ref_type",
            "entity_ref_id",
            "value",
            "severity",
            "detected_at",
            "interpretation_confidence",
            "linkage_confidence_floor",
            "evidence_excerpt_ids",
            "evidence_artifact_ids",
            "detector_id",
            "detector_version",
            "status",
            "consumed_by_proposal_id",
            "expires_at",
            "resolved_at",
            "resolution",
            "created_at",
        }
        missing = required - cols
        assert not missing, f"signals table missing columns for v4 service: {missing}"

    def test_signal_support_tables_exist(self, fresh_db):
        """Signal ecosystem tables must be in canonical schema."""
        cursor = fresh_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}

        for table in [
            "signal_definitions",
            "detector_versions",
            "detector_runs",
            "signal_feedback",
        ]:
            assert table in existing, (
                f"Table '{table}' required by SignalService but missing from schema"
            )


# ──────────────────────────────────────────────────────────────
# Test 4: Issue service tables exist
# ──────────────────────────────────────────────────────────────


class TestIssueServiceSchema:
    """Regression: v4/issue_service.py tables must be in canonical schema."""

    @pytest.mark.parametrize(
        "table",
        ["issues", "issue_signals", "issue_evidence", "decision_log", "watchers", "handoffs"],
    )
    def test_issue_table_exists(self, fresh_db, table):
        cursor = fresh_db.execute(f"PRAGMA table_info([{table}])")
        cols = [row[1] for row in cursor.fetchall()]
        assert len(cols) > 0, f"Table '{table}' has no columns or does not exist"


# ──────────────────────────────────────────────────────────────
# Test 5: Runtime code SQL references resolve
# ──────────────────────────────────────────────────────────────


class TestRuntimeSQLReferences:
    """Verify that SQL in runtime code references tables/columns that exist."""

    def test_governance_history_insert(self, fresh_db):
        """Simulate the governance_history INSERT from server.py L2292."""
        fresh_db.execute(
            """
            INSERT INTO governance_history (id, decision_id, action, type, target_id, processed_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            ("gh_test", "dec_1", "approved", "risk", "tgt_1", "moh"),
        )
        row = fresh_db.execute("SELECT * FROM governance_history WHERE id = 'gh_test'").fetchone()
        assert row is not None
        assert row["action"] == "approved"

    def test_governance_history_query(self, fresh_db):
        """Simulate the GET /api/governance/history query from server.py L3160."""
        # Should not crash on empty table
        rows = fresh_db.execute(
            "SELECT * FROM governance_history ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        assert isinstance(rows, list)

    def test_signals_insert_v4_columns(self, fresh_db):
        """Simulate SignalService.create_signal INSERT."""
        fresh_db.execute(
            """
            INSERT INTO signals
            (signal_id, signal_type, entity_ref_type, entity_ref_id, value,
             severity, interpretation_confidence, linkage_confidence_floor,
             evidence_excerpt_ids, evidence_artifact_ids, detector_id,
             detector_version, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                "sig_test",
                "risk",
                "client",
                "c_1",
                '{"detail": "test"}',
                "high",
                0.9,
                0.7,
                "[]",
                "[]",
                "det_1",
                "1.0",
                None,
            ),
        )
        row = fresh_db.execute("SELECT * FROM signals WHERE signal_id = 'sig_test'").fetchone()
        assert row is not None
        assert row["severity"] == "high"

    def test_signals_resolve_update(self, fresh_db):
        """Simulate SignalService.resolve_signal UPDATE (uses resolved_at, resolution)."""
        fresh_db.execute(
            """
            INSERT INTO signals (signal_id, signal_type, status, created_at)
            VALUES ('sig_res', 'test', 'active', datetime('now'))
            """
        )
        fresh_db.execute(
            """
            UPDATE signals
            SET status = 'resolved', resolved_at = datetime('now'), resolution = 'completed'
            WHERE signal_id = 'sig_res' AND status = 'active'
            """
        )
        row = fresh_db.execute("SELECT * FROM signals WHERE signal_id = 'sig_res'").fetchone()
        assert row["status"] == "resolved"
        assert row["resolution"] == "completed"


# ──────────────────────────────────────────────────────────────
# Test 6: No runtime DDL in v4 services
# ──────────────────────────────────────────────────────────────


class TestNoRuntimeDDL:
    """Verify services no longer contain CREATE TABLE statements."""

    @pytest.mark.parametrize(
        "path",
        [
            "lib/v4/signal_service.py",
            "lib/v4/issue_service.py",
            "lib/v4/proposal_service.py",
            "lib/v4/coupling_service.py",
            "lib/intelligence/drift_detection.py",
            "lib/intelligence/signal_suppression.py",
            "lib/ui_spec_v21/engagement_lifecycle.py",
            "lib/outbox.py",
        ],
    )
    def test_no_create_table(self, path):
        source = (REPO_ROOT / path).read_text()
        assert "CREATE TABLE" not in source, (
            f"{path} still contains CREATE TABLE DDL. Tables must be owned by schema.py."
        )


# ──────────────────────────────────────────────────────────────
# Test 6b: Outbox tables — canonical ownership and column completeness
# ──────────────────────────────────────────────────────────────


class TestOutboxSchema:
    """Proof that outbox tables are canonically owned and operational."""

    def test_side_effect_outbox_in_schema(self):
        """side_effect_outbox must be declared in schema.TABLES."""
        assert "side_effect_outbox" in schema.TABLES, (
            "side_effect_outbox not registered in schema.py"
        )

    def test_idempotency_keys_in_schema(self):
        """idempotency_keys must be declared in schema.TABLES."""
        assert "idempotency_keys" in schema.TABLES, "idempotency_keys not registered in schema.py"

    def test_side_effect_outbox_created_fresh(self, fresh_db):
        """schema_engine.create_fresh() must create side_effect_outbox."""
        cursor = fresh_db.execute("PRAGMA table_info(side_effect_outbox)")
        cols = {row[1] for row in cursor.fetchall()}
        required = {
            "id",
            "idempotency_key",
            "handler",
            "action",
            "payload",
            "status",
            "external_resource_id",
            "error",
            "created_at",
            "fulfilled_at",
            "attempts",
        }
        missing = required - cols
        assert not missing, f"side_effect_outbox missing columns: {missing}"

    def test_idempotency_keys_created_fresh(self, fresh_db):
        """schema_engine.create_fresh() must create idempotency_keys."""
        cursor = fresh_db.execute("PRAGMA table_info(idempotency_keys)")
        cols = {row[1] for row in cursor.fetchall()}
        required = {"key", "action_id", "created_at"}
        missing = required - cols
        assert not missing, f"idempotency_keys missing columns: {missing}"

    def test_outbox_runtime_sql_against_fresh_db(self, fresh_db):
        """Core outbox SQL operations must work against a fresh schema DB."""
        # INSERT — record_intent path
        fresh_db.execute(
            "INSERT INTO side_effect_outbox "
            "(id, idempotency_key, handler, action, payload, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            ["intent_test1", "key_1", "calendar", "create_event", "{}", "2025-01-01T00:00:00Z"],
        )

        # SELECT — get_fulfilled_intent path
        row = fresh_db.execute(
            "SELECT * FROM side_effect_outbox WHERE idempotency_key = ? AND status = 'fulfilled'",
            ["key_1"],
        ).fetchone()
        assert row is None  # not fulfilled yet

        # UPDATE — mark_fulfilled path
        fresh_db.execute(
            "UPDATE side_effect_outbox SET "
            "status = 'fulfilled', external_resource_id = ?, fulfilled_at = ?, "
            "attempts = attempts + 1 WHERE id = ?",
            ["ext_123", "2025-01-01T00:01:00Z", "intent_test1"],
        )
        row = fresh_db.execute(
            "SELECT * FROM side_effect_outbox WHERE idempotency_key = ? AND status = 'fulfilled'",
            ["key_1"],
        ).fetchone()
        assert row is not None
        assert row["external_resource_id"] == "ext_123"

        # Idempotency key table operations
        fresh_db.execute(
            "INSERT OR IGNORE INTO idempotency_keys (key, action_id, created_at) VALUES (?, ?, ?)",
            ["idem_1", "action_abc", "2025-01-01T00:00:00Z"],
        )
        row = fresh_db.execute(
            "SELECT action_id FROM idempotency_keys WHERE key = ?",
            ["idem_1"],
        ).fetchone()
        assert row["action_id"] == "action_abc"

    def test_outbox_ddl_derived_from_schema(self):
        """lib/outbox._outbox_ddl() must derive DDL from schema.TABLES, not hardcode it."""
        from lib.outbox import _outbox_ddl

        outbox_sql, idem_sql = _outbox_ddl()
        # DDL comes from _build_create_sql which wraps table name in brackets
        assert "[side_effect_outbox]" in outbox_sql
        assert "[idempotency_keys]" in idem_sql
        # Must include all declared columns
        for col_name, _ in schema.TABLES["side_effect_outbox"]["columns"]:
            assert col_name in outbox_sql, f"Column {col_name} missing from outbox DDL"
        for col_name, _ in schema.TABLES["idempotency_keys"]["columns"]:
            assert col_name in idem_sql, f"Column {col_name} missing from idempotency DDL"


# ──────────────────────────────────────────────────────────────
# Test 7: proposals_v4 canonical schema
# ──────────────────────────────────────────────────────────────


class TestProposalsV4Schema:
    """Regression: proposals_v4 had split-brain between schema.py and proposal_service.py."""

    def test_proposals_v4_pk_is_proposal_id(self, fresh_db):
        """PK must be proposal_id (not 'id') — matches all runtime callers."""
        cursor = fresh_db.execute("PRAGMA table_info(proposals_v4)")
        pk_cols = [row[1] for row in cursor.fetchall() if row[5] == 1]
        assert pk_cols == ["proposal_id"], (
            f"proposals_v4 PK should be ['proposal_id'], got {pk_cols}"
        )

    def test_proposals_v4_v4_service_columns(self, fresh_db):
        """Columns used by ProposalService INSERT/UPDATE must exist."""
        cursor = fresh_db.execute("PRAGMA table_info(proposals_v4)")
        cols = {row[1] for row in cursor.fetchall()}

        # From proposal_service.py generate_proposals_from_signals INSERT (L218-256)
        # and snooze/dismiss/accept UPDATE paths
        v4_required = {
            "proposal_id",
            "proposal_type",
            "primary_ref_type",
            "primary_ref_id",
            "scope_refs",
            "headline",
            "summary",
            "impact",
            "top_hypotheses",
            "signal_ids",
            "proof_excerpt_ids",
            "score",
            "first_seen_at",
            "last_seen_at",
            "ui_exposure_level",
            "status",
            "created_at",
            "updated_at",
            "occurrence_count",
            "trend",
            "snoozed_until",
            "dismissed_reason",
        }
        missing = v4_required - cols
        assert not missing, f"proposals_v4 missing v4 service columns: {missing}"

    def test_proposals_v4_no_dead_columns(self, fresh_db):
        """Columns with zero runtime callers must not exist in schema."""
        cursor = fresh_db.execute("PRAGMA table_info(proposals_v4)")
        cols = {row[1] for row in cursor.fetchall()}
        # These columns had zero readers and zero writers in all runtime code
        dead = {"missing_confirmations", "supersedes_proposal_id"} & cols
        assert not dead, f"proposals_v4 contains dead columns with no runtime callers: {dead}"

    def test_proposals_v4_aggregator_columns(self, fresh_db):
        """Columns used by spec_router.py and proposal_aggregator.py must exist."""
        cursor = fresh_db.execute("PRAGMA table_info(proposals_v4)")
        cols = {row[1] for row in cursor.fetchall()}

        # From spec_router.py SELECT and proposal_aggregator.py writes
        aggregator_required = {
            "scope_level",
            "scope_name",
            "client_id",
            "client_name",
            "client_tier",
            "brand_id",
            "brand_name",
            "engagement_type",
            "signal_summary_json",
            "score_breakdown_json",
            "affected_task_ids_json",
        }
        missing = aggregator_required - cols
        assert not missing, f"proposals_v4 missing aggregator columns: {missing}"

    def test_proposals_v4_insert_v4_service(self, fresh_db):
        """Simulate ProposalService.generate_proposals_from_signals INSERT."""
        fresh_db.execute(
            """
            INSERT INTO proposals_v4
            (proposal_id, proposal_type, primary_ref_type, primary_ref_id,
             scope_refs, headline, impact, top_hypotheses, signal_ids,
             proof_excerpt_ids, score, ui_exposure_level, status,
             scope_level, scope_name, client_id, client_name, client_tier,
             brand_id, brand_name, engagement_type,
             signal_summary_json, score_breakdown_json, affected_task_ids_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'surfaced', 'open',
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "prop_test_1",
                "risk",
                "project",
                "proj_1",
                '[{"type": "project", "id": "proj_1"}]',
                "Test: 3 issues requiring attention",
                '{"severity": "high"}',
                "[]",
                '["sig_1"]',
                '["exc_1"]',
                75.0,
                "project",
                "My Project",
                "c_1",
                "Acme Corp",
                "gold",
                "b_1",
                "Acme Brand",
                "retainer",
                '{"total": 3}',
                '{"base": 50}',
                '["t_1"]',
            ),
        )
        row = fresh_db.execute(
            "SELECT proposal_id, scope_level, client_name, score "
            "FROM proposals_v4 WHERE proposal_id = 'prop_test_1'"
        ).fetchone()
        assert row is not None
        assert row[0] == "prop_test_1"
        assert row[1] == "project"
        assert row[2] == "Acme Corp"
        assert row[3] == 75.0


class TestCouplingsSchema:
    """Regression: couplings table was runtime-DDL-only in coupling_service.py."""

    def test_couplings_columns_complete(self, fresh_db):
        """All columns used by CouplingService must exist."""
        cursor = fresh_db.execute("PRAGMA table_info(couplings)")
        cols = {row[1] for row in cursor.fetchall()}

        # From coupling_service.py INSERT and SELECT statements
        required = {
            "coupling_id",
            "anchor_ref_type",
            "anchor_ref_id",
            "entity_refs",
            "coupling_type",
            "strength",
            "why",
            "investigation_path",
            "confidence",
            "created_at",
            "updated_at",
        }
        missing = required - cols
        assert not missing, f"couplings table missing columns: {missing}"

    def test_couplings_insert_shared_signals(self, fresh_db):
        """Simulate CouplingService.discover_couplings INSERT."""
        fresh_db.execute(
            """
            INSERT INTO couplings
            (coupling_id, anchor_ref_type, anchor_ref_id, entity_refs,
             coupling_type, strength, why, investigation_path, confidence,
             created_at, updated_at)
            VALUES (?, 'signal_type', ?, ?, 'shared_signals', ?, ?, ?, ?,
                    datetime('now'), datetime('now'))
            """,
            (
                "cpl_test_1",
                "risk",
                '[{"type": "client", "id": "c_1"}, {"type": "client", "id": "c_2"}]',
                0.6,
                '{"signal_type": "risk", "shared_count": 3}',
                '["client", "c_1", "client", "c_2"]',
                0.8,
            ),
        )
        row = fresh_db.execute(
            "SELECT coupling_id, strength FROM couplings WHERE coupling_id = 'cpl_test_1'"
        ).fetchone()
        assert row is not None
        assert row[1] == 0.6


# ──────────────────────────────────────────────────────────────
# Test 7b: Drift detection tables
# ──────────────────────────────────────────────────────────────


class TestDriftDetectionSchema:
    """Regression: drift tables were runtime-DDL-only in drift_detection.py."""

    def test_drift_baselines_columns(self, fresh_db):
        cursor = fresh_db.execute("PRAGMA table_info(drift_baselines)")
        cols = {row[1] for row in cursor.fetchall()}
        required = {
            "metric_name",
            "entity_type",
            "entity_id",
            "mean_value",
            "stddev_value",
            "sample_count",
            "last_updated",
        }
        missing = required - cols
        assert not missing, f"drift_baselines missing columns: {missing}"

    def test_drift_baselines_composite_pk(self, fresh_db):
        """Composite PK allows ON CONFLICT(metric_name, entity_type, entity_id)."""
        # Insert then upsert — should not raise
        fresh_db.execute(
            """
            INSERT INTO drift_baselines
            (metric_name, entity_type, entity_id, mean_value, stddev_value, sample_count, last_updated)
            VALUES ('health_score', 'client', 'c_1', 75.0, 5.0, 10, '2025-01-01')
            """
        )
        fresh_db.execute(
            """
            INSERT INTO drift_baselines
            (metric_name, entity_type, entity_id, mean_value, stddev_value, sample_count, last_updated)
            VALUES ('health_score', 'client', 'c_1', 80.0, 4.0, 15, '2025-02-01')
            ON CONFLICT(metric_name, entity_type, entity_id)
            DO UPDATE SET mean_value = excluded.mean_value,
                         stddev_value = excluded.stddev_value,
                         sample_count = excluded.sample_count,
                         last_updated = excluded.last_updated
            """
        )
        row = fresh_db.execute(
            "SELECT mean_value, sample_count FROM drift_baselines "
            "WHERE metric_name = 'health_score' AND entity_type = 'client' AND entity_id = 'c_1'"
        ).fetchone()
        assert row[0] == 80.0
        assert row[1] == 15

    def test_drift_alerts_columns(self, fresh_db):
        cursor = fresh_db.execute("PRAGMA table_info(drift_alerts)")
        cols = {row[1] for row in cursor.fetchall()}
        required = {
            "id",
            "metric_name",
            "entity_type",
            "entity_id",
            "current_value",
            "baseline_mean",
            "baseline_stddev",
            "deviation_sigma",
            "direction",
            "severity",
            "detected_at",
        }
        missing = required - cols
        assert not missing, f"drift_alerts missing columns: {missing}"


class TestSignalSuppressionSchema:
    """Regression: suppression tables were runtime-DDL-only in signal_suppression.py."""

    def test_signal_suppressions_columns(self, fresh_db):
        cursor = fresh_db.execute("PRAGMA table_info(signal_suppressions)")
        cols = {row[1] for row in cursor.fetchall()}
        required = {
            "id",
            "signal_key",
            "entity_type",
            "entity_id",
            "reason",
            "suppressed_at",
            "expires_at",
            "dismiss_count",
            "is_active",
        }
        missing = required - cols
        assert not missing, f"signal_suppressions missing columns: {missing}"

    def test_signal_dismiss_log_columns(self, fresh_db):
        cursor = fresh_db.execute("PRAGMA table_info(signal_dismiss_log)")
        cols = {row[1] for row in cursor.fetchall()}
        required = {"id", "signal_key", "entity_type", "entity_id", "event_type", "created_at"}
        missing = required - cols
        assert not missing, f"signal_dismiss_log missing columns: {missing}"


class TestEngagementTransitionsSchema:
    """Regression: engagement_transitions was runtime-DDL-only in engagement_lifecycle.py."""

    def test_engagement_transitions_columns(self, fresh_db):
        cursor = fresh_db.execute("PRAGMA table_info(engagement_transitions)")
        cols = {row[1] for row in cursor.fetchall()}
        required = {
            "id",
            "engagement_id",
            "from_state",
            "to_state",
            "trigger",
            "actor",
            "note",
            "transitioned_at",
            "created_at",
        }
        missing = required - cols
        assert not missing, f"engagement_transitions missing columns: {missing}"


# ──────────────────────────────────────────────────────────────
# Test 8: No _ensure_tables methods
# ──────────────────────────────────────────────────────────────


class TestNoEnsureTables:
    """Verify services have no _ensure_tables methods or calls."""

    @pytest.mark.parametrize(
        "path",
        [
            "lib/v4/signal_service.py",
            "lib/v4/issue_service.py",
            "lib/v4/proposal_service.py",
            "lib/v4/coupling_service.py",
            "lib/intelligence/drift_detection.py",
            "lib/intelligence/signal_suppression.py",
            "lib/ui_spec_v21/engagement_lifecycle.py",
        ],
    )
    def test_no_ensure_tables_method(self, path):
        source = (REPO_ROOT / path).read_text()
        assert "_ensure_tables" not in source, (
            f"{path} still contains _ensure_tables reference. "
            f"Schema ownership belongs exclusively to schema_engine."
        )


# ──────────────────────────────────────────────────────────────
# Test 9: Required indexes exist for query patterns
# ──────────────────────────────────────────────────────────────


class TestRequiredIndexes:
    """Verify indexes exist for runtime query patterns."""

    def _get_indexes(self, fresh_db, table_name):
        """Get all index names for a table."""
        cursor = fresh_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name = ?",
            (table_name,),
        )
        return {row[0] for row in cursor.fetchall()}

    def test_couplings_has_anchor_index(self, fresh_db):
        """spec_router.py WHERE anchor_ref_type = ? AND anchor_ref_id = ?"""
        indexes = self._get_indexes(fresh_db, "couplings")
        assert "idx_couplings_anchor" in indexes, (
            f"couplings missing idx_couplings_anchor for anchor WHERE queries. Existing: {indexes}"
        )

    def test_couplings_has_strength_index(self, fresh_db):
        """coupling_service.py ORDER BY strength DESC LIMIT ?"""
        indexes = self._get_indexes(fresh_db, "couplings")
        assert "idx_couplings_strength" in indexes, (
            f"couplings missing idx_couplings_strength for ORDER BY queries. Existing: {indexes}"
        )

    def test_couplings_has_type_index(self, fresh_db):
        """coupling_service.py GROUP BY coupling_type"""
        indexes = self._get_indexes(fresh_db, "couplings")
        assert "idx_couplings_type" in indexes, (
            f"couplings missing idx_couplings_type for GROUP BY queries. Existing: {indexes}"
        )

    def test_proposals_v4_has_scope_status_index(self, fresh_db):
        """proposal_service.py WHERE scope_level = ? AND primary_ref_id = ? AND status = 'open'"""
        indexes = self._get_indexes(fresh_db, "proposals_v4")
        assert "idx_proposals_v4_scope_status" in indexes, (
            f"proposals_v4 missing idx_proposals_v4_scope_status for UPDATE lookup. "
            f"Existing: {indexes}"
        )

    def test_proposals_v4_has_status_index(self, fresh_db):
        """Used in 6+ queries across proposal_service.py and spec_router.py"""
        indexes = self._get_indexes(fresh_db, "proposals_v4")
        assert "idx_proposals_v4_status" in indexes

    def test_proposals_v4_has_score_index(self, fresh_db):
        """ORDER BY score DESC in multiple list queries"""
        indexes = self._get_indexes(fresh_db, "proposals_v4")
        assert "idx_proposals_v4_score" in indexes

    def test_drift_alerts_has_time_index(self, fresh_db):
        """drift_detection.py ORDER BY detected_at DESC"""
        indexes = self._get_indexes(fresh_db, "drift_alerts")
        assert "idx_drift_time" in indexes

    def test_signal_suppressions_has_indexes(self, fresh_db):
        """signal_suppression.py WHERE signal_key, entity, is_active"""
        indexes = self._get_indexes(fresh_db, "signal_suppressions")
        assert "idx_suppress_signal" in indexes
        assert "idx_suppress_entity" in indexes
        assert "idx_suppress_active" in indexes

    def test_dismiss_log_has_signal_index(self, fresh_db):
        """signal_suppression.py WHERE signal_key"""
        indexes = self._get_indexes(fresh_db, "signal_dismiss_log")
        assert "idx_dismiss_log_signal" in indexes

    def test_engagement_transitions_has_engagement_index(self, fresh_db):
        """engagement_lifecycle.py WHERE engagement_id"""
        indexes = self._get_indexes(fresh_db, "engagement_transitions")
        assert "idx_engagement_transitions_engagement_id" in indexes


# ──────────────────────────────────────────────────────────────
# Test 10: Schema version incremented
# ──────────────────────────────────────────────────────────────


class TestSchemaVersion:
    """Verify schema version is set correctly."""

    def test_fresh_db_version(self, fresh_db):
        row = fresh_db.execute("PRAGMA user_version").fetchone()
        assert row[0] == schema.SCHEMA_VERSION

    def test_schema_version_at_least_23(self):
        """Schema v23 added side_effect_outbox and idempotency_keys."""
        assert schema.SCHEMA_VERSION >= 23, (
            f"Schema version {schema.SCHEMA_VERSION} < 23; outbox tables require v23+"
        )


# ──────────────────────────────────────────────────────────────
# Test 11: Converge on existing DB adds missing objects
# ──────────────────────────────────────────────────────────────


class TestConverge:
    """Verify converge() adds missing tables/columns/views to an existing DB."""

    def test_converge_adds_governance_history(self):
        """If an old DB lacks governance_history, converge adds it."""
        conn = sqlite3.connect(":memory:")
        # Create a minimal old DB with just one table
        conn.execute("CREATE TABLE clients (id TEXT PRIMARY KEY, name TEXT)")
        conn.execute("PRAGMA user_version = 21")

        result = schema_engine.converge(conn)
        assert "governance_history" in result["tables_created"]

        cursor = conn.execute("PRAGMA table_info(governance_history)")
        cols = {row[1] for row in cursor.fetchall()}
        assert "decision_id" in cols
        conn.close()

    def test_converge_creates_views(self):
        """Converge creates missing canonical views."""
        conn = sqlite3.connect(":memory:")
        # Build tables first (views need underlying tables)
        schema_engine.create_fresh(conn)
        # Drop one view
        conn.execute("DROP VIEW IF EXISTS v_task_with_client")

        result = schema_engine.converge(conn)
        assert "v_task_with_client" in result.get("views_created", [])
        conn.close()
