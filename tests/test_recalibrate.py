"""Tests for signal recalibration module."""

import json
import sqlite3
import tempfile

import pytest

from lib.intelligence.recalibrate import (
    _recalibrate_ar_aging,
    _recalibrate_deadline_overdue,
    full_recalibration,
    recalibrate_active_signals,
    signal_distribution_report,
    update_priority_weights,
)


@pytest.fixture
def test_db():
    """Create test DB with signals and signal_definitions tables."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(tmp.name)

    conn.executescript("""
        CREATE TABLE signals (
            signal_id TEXT PRIMARY KEY,
            signal_type TEXT NOT NULL,
            entity_ref_type TEXT NOT NULL,
            entity_ref_id TEXT NOT NULL,
            value TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'medium',
            detected_at TEXT NOT NULL DEFAULT (datetime('now')),
            interpretation_confidence REAL NOT NULL DEFAULT 0.8,
            linkage_confidence_floor REAL NOT NULL DEFAULT 0.7,
            evidence_excerpt_ids TEXT NOT NULL DEFAULT '[]',
            evidence_artifact_ids TEXT NOT NULL DEFAULT '[]',
            detector_id TEXT NOT NULL DEFAULT 'test',
            detector_version TEXT NOT NULL DEFAULT '1.0',
            status TEXT NOT NULL DEFAULT 'active',
            consumed_by_proposal_id TEXT,
            expires_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            resolved_at TEXT,
            resolution TEXT
        );

        CREATE TABLE signal_definitions (
            signal_type TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            required_evidence_types TEXT NOT NULL DEFAULT '[]',
            formula_version TEXT NOT NULL DEFAULT '1.0',
            min_link_confidence REAL NOT NULL DEFAULT 0.7,
            min_interpretation_confidence REAL NOT NULL DEFAULT 0.6,
            priority_weight REAL NOT NULL DEFAULT 1.0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Deadline overdue signals with varying days
        -- s1, s2: have client_id → graduated severity applies
        -- s3, s4: no client_id → stale/orphan → always low
        INSERT INTO signals (signal_id, signal_type, entity_ref_type, entity_ref_id, value, severity, status)
        VALUES
            ('s1', 'deadline_overdue', 'task', 't1',
             '{"days_overdue": 30, "title": "Old task", "client_id": "c1"}', 'critical', 'active'),
            ('s2', 'deadline_overdue', 'task', 't2',
             '{"days_overdue": 10, "title": "Medium old", "client_id": "c2"}', 'critical', 'active'),
            ('s3', 'deadline_overdue', 'task', 't3',
             '{"days_overdue": 3, "title": "Recent"}', 'critical', 'active'),
            ('s4', 'deadline_overdue', 'task', 't4',
             '{"days_overdue": 0, "title": "Just due"}', 'critical', 'active');

        -- AR aging signals
        INSERT INTO signals (signal_id, signal_type, entity_ref_type, entity_ref_id, value, severity, status)
        VALUES
            ('s5', 'ar_aging_risk', 'client', 'c1',
             '{"aging_bucket": "90+", "ar_overdue": 100000}', 'critical', 'active'),
            ('s6', 'ar_aging_risk', 'client', 'c2',
             '{"aging_bucket": "60", "ar_overdue": 50000}', 'critical', 'active'),
            ('s7', 'ar_aging_risk', 'client', 'c3',
             '{"aging_bucket": "30", "ar_overdue": 20000}', 'high', 'active'),
            ('s8', 'ar_aging_risk', 'client', 'c4',
             '{"aging_bucket": "current", "ar_overdue": 10000}', 'high', 'active');

        -- Data quality issues (should be capped at medium)
        INSERT INTO signals (signal_id, signal_type, entity_ref_type, entity_ref_id, value, severity, status)
        VALUES
            ('s9', 'data_quality_issue', 'client', 'c1',
             '{"issue_type": "missing_data"}', 'critical', 'active'),
            ('s10', 'data_quality_issue', 'client', 'c2',
             '{"issue_type": "stale_task"}', 'medium', 'active');

        -- Hierarchy violations (should be capped at low)
        INSERT INTO signals (signal_id, signal_type, entity_ref_type, entity_ref_id, value, severity, status)
        VALUES
            ('s11', 'hierarchy_violation', 'task', 't5',
             '{"violation_type": "task_no_project"}', 'medium', 'active'),
            ('s12', 'hierarchy_violation', 'task', 't6',
             '{"violation_type": "task_no_project"}', 'low', 'active');

        -- An expired signal (should not be touched)
        INSERT INTO signals (signal_id, signal_type, entity_ref_type, entity_ref_id, value, severity, status)
        VALUES
            ('s_exp', 'deadline_overdue', 'task', 't99',
             '{"days_overdue": 100}', 'critical', 'expired');

        -- Signal definitions
        INSERT INTO signal_definitions (signal_type, description, category, priority_weight)
        VALUES
            ('deadline_overdue', 'Overdue deadline', 'deadline', 1.0),
            ('deadline_approaching', 'Approaching deadline', 'deadline', 1.0),
            ('deadline_at_risk', 'At-risk deadline', 'deadline', 1.0),
            ('ar_aging_risk', 'AR aging', 'health', 1.0),
            ('client_health_declining', 'Declining health', 'health', 1.0),
            ('data_quality_issue', 'Data quality', 'protocol', 1.0),
            ('hierarchy_violation', 'Hierarchy issue', 'protocol', 1.0),
            ('activity_spike', 'Activity spike', 'anomaly', 1.0),
            ('commitment_made', 'Commitment', 'commitment', 1.0);
    """)

    conn.commit()
    conn.close()
    return tmp.name


class TestDeadlineOverdueCalibration:
    """Tests for deadline_overdue severity rules."""

    def test_over_14_days_with_client_is_critical(self):
        val = json.dumps({"days_overdue": 30, "client_id": "c1"})
        assert _recalibrate_deadline_overdue(val) == "critical"

    def test_7_to_14_days_with_client_is_high(self):
        val = json.dumps({"days_overdue": 10, "client_id": "c1"})
        assert _recalibrate_deadline_overdue(val) == "high"

    def test_1_to_7_days_with_client_is_medium(self):
        val = json.dumps({"days_overdue": 3, "client_id": "c1"})
        assert _recalibrate_deadline_overdue(val) == "medium"

    def test_zero_days_is_low(self):
        val = json.dumps({"days_overdue": 0, "client_id": "c1"})
        assert _recalibrate_deadline_overdue(val) == "low"

    def test_no_client_id_is_low_regardless_of_days(self):
        val = json.dumps({"days_overdue": 30})
        assert _recalibrate_deadline_overdue(val) == "low"

    def test_no_client_id_empty_string_is_low(self):
        val = json.dumps({"days_overdue": 15, "client_id": ""})
        assert _recalibrate_deadline_overdue(val) == "low"

    def test_invalid_json_returns_medium(self):
        assert _recalibrate_deadline_overdue("not json") == "medium"


class TestArAgingCalibration:
    """Tests for ar_aging_risk severity rules."""

    def test_90plus_is_critical(self):
        val = json.dumps({"aging_bucket": "90+"})
        assert _recalibrate_ar_aging(val) == "critical"

    def test_60_is_high(self):
        val = json.dumps({"aging_bucket": "60"})
        assert _recalibrate_ar_aging(val) == "high"

    def test_30_is_medium(self):
        val = json.dumps({"aging_bucket": "30"})
        assert _recalibrate_ar_aging(val) == "medium"

    def test_current_is_low(self):
        val = json.dumps({"aging_bucket": "current"})
        assert _recalibrate_ar_aging(val) == "low"


class TestRecalibrateActiveSignals:
    """Tests for the full recalibration pipeline."""

    def test_reduces_critical_count(self, test_db):
        result = recalibrate_active_signals(test_db)
        after = result["after"]
        # Originally 6 critical (4 deadline + 1 ar + 1 data_quality)
        # After: only s1 (30d) stays critical + s5 (90+) stays critical = 2
        assert after["by_severity"]["critical"] <= 2

    def test_dry_run_no_changes(self, test_db):
        result = recalibrate_active_signals(test_db, dry_run=True)
        assert result["dry_run"] is True
        # Verify DB unchanged — original has 7 critical active signals
        # (4 deadline_overdue + 2 ar_aging_risk + 1 data_quality_issue)
        conn = sqlite3.connect(test_db)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE severity='critical' AND status='active'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 7

    def test_data_quality_capped_at_medium(self, test_db):
        recalibrate_active_signals(test_db)
        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT severity FROM signals WHERE signal_id = 's9'"
        ).fetchone()
        conn.close()
        assert row[0] == "medium"

    def test_hierarchy_capped_at_low(self, test_db):
        recalibrate_active_signals(test_db)
        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT severity FROM signals WHERE signal_id = 's11'"
        ).fetchone()
        conn.close()
        assert row[0] == "low"

    def test_expired_signals_untouched(self, test_db):
        recalibrate_active_signals(test_db)
        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT severity FROM signals WHERE signal_id = 's_exp'"
        ).fetchone()
        conn.close()
        assert row[0] == "critical"  # Expired signal not touched


class TestDistributionReport:
    """Tests for signal_distribution_report."""

    def test_report_totals(self, test_db):
        report = signal_distribution_report(test_db)
        assert report["total_active"] == 12
        assert report["critical_pct"] > 0

    def test_report_by_type(self, test_db):
        report = signal_distribution_report(test_db)
        assert "deadline_overdue" in report["by_type"]
        assert report["by_type"]["deadline_overdue"]["critical"] == 4


class TestPriorityWeights:
    """Tests for priority weight updates."""

    def test_updates_weights_by_category(self, test_db):
        result = update_priority_weights(test_db)
        assert result["dry_run"] is False

        # Verify in DB
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT signal_type, priority_weight FROM signal_definitions ORDER BY signal_type"
        ).fetchall()
        conn.close()

        weights = {r["signal_type"]: r["priority_weight"] for r in rows}
        assert weights["deadline_overdue"] == 0.8  # deadline category
        assert weights["ar_aging_risk"] == 1.0  # health category
        assert weights["data_quality_issue"] == 0.3  # protocol category
        assert weights["activity_spike"] == 0.6  # anomaly category
        assert weights["commitment_made"] == 0.8  # commitment category

    def test_dry_run_preserves_weights(self, test_db):
        update_priority_weights(test_db, dry_run=True)
        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT priority_weight FROM signal_definitions WHERE signal_type='deadline_overdue'"
        ).fetchone()
        conn.close()
        assert row[0] == 1.0  # Original preserved


class TestFullRecalibration:
    """Tests for full_recalibration."""

    def test_combines_both(self, test_db):
        result = full_recalibration(test_db)
        assert "severity_recalibration" in result
        assert "priority_weights" in result
        assert result["dry_run"] is False
