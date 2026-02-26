"""
Integration validation for the intelligence wiring system (IW-5.1).

Verifies end-to-end data flow through the intelligence pipeline:
- Score → score_history persistence → HealthUnifier retrieval
- Pattern detection → pattern_snapshots persistence → cycle-based retrieval
- Event publish → consume → archive lifecycle
- Intelligence phase result structure and isolation guarantees
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from lib.intelligence.health_unifier import HealthUnifier
from lib.intelligence.persistence import (
    CostPersistence,
    CostSnapshotRecord,
    IntelligenceEvent,
    IntelligenceEventStore,
    PatternPersistence,
    PatternSnapshot,
    event_from_pattern,
    event_from_signal_change,
    make_id,
    snapshot_from_cost_profile,
    snapshot_from_pattern_evidence,
)
from lib.migrations.v31_intelligence_wiring import run_migration


@pytest.fixture
def integration_db(tmp_path):
    """Create a full integration test database with all intelligence tables."""
    db_path = tmp_path / "integration.db"
    conn = sqlite3.connect(str(db_path))
    # Pre-existing tables that intelligence depends on
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signal_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            severity TEXT NOT NULL,
            original_severity TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            evidence_json TEXT,
            first_detected_at TEXT NOT NULL,
            last_evaluated_at TEXT NOT NULL,
            escalated_at TEXT,
            cleared_at TEXT,
            acknowledged_at TEXT,
            evaluation_count INTEGER DEFAULT 1,
            UNIQUE(signal_id, entity_type, entity_id, status)
        );

        CREATE TABLE IF NOT EXISTS score_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            composite_score REAL NOT NULL,
            dimensions_json TEXT,
            data_completeness REAL,
            recorded_at TEXT NOT NULL,
            recorded_date TEXT NOT NULL,
            UNIQUE(entity_type, entity_id, recorded_date)
        );
    """)
    conn.close()

    # Run v31 migration
    result = run_migration(db_path)
    assert not result["errors"], f"Migration failed: {result['errors']}"

    return db_path


# =============================================================================
# VALIDATION 1: Score → Persist → Retrieve roundtrip
# =============================================================================


class TestScoreHistoryRoundtrip:
    """Verify scores persisted via HealthUnifier are retrievable."""

    def test_record_and_retrieve_matches(self, integration_db):
        """Score recorded via record_health matches get_latest_health."""
        hu = HealthUnifier(integration_db)
        dims = {"delivery": 80, "comms": 65, "cash": 75}

        hu.record_health("client", "c1", 72.5, dims, data_completeness=0.85)
        health = hu.get_latest_health("client", "c1")

        assert health is not None
        assert health.composite_score == 72.5
        assert health.classification == "good"
        assert health.dimensions["delivery"] == 80
        assert health.data_completeness == 0.85

    def test_one_row_per_entity_per_day(self, integration_db):
        """Recording twice on same day overwrites (not duplicates)."""
        hu = HealthUnifier(integration_db)

        hu.record_health("client", "c1", 60, {})
        hu.record_health("client", "c1", 70, {})

        trend = hu.get_health_trend("client", "c1", days=1)
        assert len(trend) == 1
        assert trend[0].composite_score == 70

    def test_multi_entity_scoring(self, integration_db):
        """Multiple entity types scored in one session."""
        hu = HealthUnifier(integration_db)

        hu.record_health("client", "c1", 72, {})
        hu.record_health("client", "c2", 55, {})
        hu.record_health("project", "p1", 88, {})
        hu.record_health("person", "per1", 63, {})

        all_clients = hu.get_all_latest_health("client")
        assert len(all_clients) == 2

        project = hu.get_latest_health("project", "p1")
        assert project.composite_score == 88

        person = hu.get_latest_health("person", "per1")
        assert person.composite_score == 63


# =============================================================================
# VALIDATION 2: Pattern → Persist → Cycle retrieval
# =============================================================================


class TestPatternCycleRoundtrip:
    """Verify patterns persist with cycle_id and are retrievable."""

    def test_pattern_persists_with_cycle_id(self, integration_db):
        pp = PatternPersistence(integration_db)
        snapshot = PatternSnapshot(
            id=make_id(),
            detected_at=datetime.now().isoformat(),
            pattern_id="PAT_CONC_001",
            pattern_name="Revenue Concentration",
            pattern_type="concentration",
            severity="structural",
            confidence="high",
            entities_involved=[
                {"type": "client", "id": "c1", "name": "ACME", "role_in_pattern": "dominant"}
            ],
            evidence={"metrics": {"hhi": 0.4}, "evidence_narrative": "High concentration"},
            cycle_id="cycle_20260221T120000",
        )
        pp.record_pattern(snapshot)

        cycle_patterns = pp.get_patterns_in_cycle("cycle_20260221T120000")
        assert len(cycle_patterns) == 1
        assert cycle_patterns[0].pattern_id == "PAT_CONC_001"
        assert cycle_patterns[0].confidence == "high"

    def test_patterns_across_cycles(self, integration_db):
        """Patterns from different cycles are segregated correctly."""
        pp = PatternPersistence(integration_db)

        for i, cycle in enumerate(["cycle_A", "cycle_B", "cycle_C"]):
            for j in range(2):
                pp.record_pattern(
                    PatternSnapshot(
                        id=make_id(),
                        detected_at=datetime.now().isoformat(),
                        pattern_id=f"PAT_{i}_{j}",
                        pattern_name=f"Pattern {i}-{j}",
                        pattern_type="dependency",
                        severity="warning",
                        confidence="medium",
                        entities_involved=[{"type": "client", "id": f"c{j}"}],
                        evidence={"test": True},
                        cycle_id=cycle,
                    )
                )

        assert len(pp.get_patterns_in_cycle("cycle_A")) == 2
        assert len(pp.get_patterns_in_cycle("cycle_B")) == 2
        assert len(pp.get_patterns_in_cycle("cycle_C")) == 2


# =============================================================================
# VALIDATION 3: Event lifecycle (publish → consume → archive)
# =============================================================================


class TestEventLifecycle:
    """Full lifecycle of intelligence events."""

    def test_publish_consume_archive(self, integration_db):
        """Events flow through publish → consume → archive."""
        es = IntelligenceEventStore(integration_db)

        # Publish
        event = IntelligenceEvent(
            id=make_id(),
            event_type="signal_fired",
            severity="critical",
            entity_type="client",
            entity_id="c1",
            event_data={"signal_id": "SIG_001", "change_type": "new"},
            source_module="signals",
            created_at=datetime.now().isoformat(),
        )
        es.publish(event)

        # Verify unconsumed
        unconsumed = es.get_unconsumed(event_type="signal_fired")
        assert len(unconsumed) == 1
        assert unconsumed[0].id == event.id

        # Consume
        assert es.mark_consumed(event.id, "preparation_engine")

        # Verify consumed (no longer in unconsumed)
        unconsumed_after = es.get_unconsumed(event_type="signal_fired")
        assert len(unconsumed_after) == 0

        # Backdate consumed_at for archival
        conn = sqlite3.connect(str(integration_db))
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        conn.execute(
            "UPDATE intelligence_events SET consumed_at = ? WHERE id = ?",
            (old_date, event.id),
        )
        conn.commit()
        conn.close()

        # Archive
        count = es.archive_old_events(days=30)
        assert count == 1

        # Verify in archive, gone from main
        conn = sqlite3.connect(str(integration_db))
        main_count = conn.execute(
            "SELECT COUNT(*) FROM intelligence_events WHERE id = ?",
            (event.id,),
        ).fetchone()[0]
        archive_count = conn.execute(
            "SELECT COUNT(*) FROM intelligence_events_archive WHERE id = ?",
            (event.id,),
        ).fetchone()[0]
        conn.close()

        assert main_count == 0
        assert archive_count == 1

    def test_severity_filtering(self, integration_db):
        """Events can be filtered by severity for downstream consumers."""
        es = IntelligenceEventStore(integration_db)

        for sev in ["critical", "warning", "info", "critical"]:
            es.publish(
                IntelligenceEvent(
                    id=make_id(),
                    event_type="signal_fired",
                    severity=sev,
                    entity_type="client",
                    entity_id="c1",
                    event_data={"test": True},
                    source_module="signals",
                    created_at=datetime.now().isoformat(),
                )
            )

        critical = es.get_unconsumed(severity="critical")
        assert len(critical) == 2

        warning = es.get_unconsumed(severity="warning")
        assert len(warning) == 1

    def test_double_consume_rejected(self, integration_db):
        """An event can only be consumed once."""
        es = IntelligenceEventStore(integration_db)

        event = IntelligenceEvent(
            id=make_id(),
            event_type="pattern_detected",
            severity="warning",
            entity_type="client",
            entity_id="c1",
            event_data={},
            source_module="patterns",
            created_at=datetime.now().isoformat(),
        )
        es.publish(event)

        assert es.mark_consumed(event.id, "consumer_A")
        assert not es.mark_consumed(event.id, "consumer_B")


# =============================================================================
# VALIDATION 4: Cost snapshot persistence
# =============================================================================


class TestCostSnapshotRoundtrip:
    """Verify cost snapshots persist and retrieve correctly."""

    def test_client_cost_roundtrip(self, integration_db):
        cp = CostPersistence(integration_db)

        snapshot = CostSnapshotRecord(
            id=make_id(),
            computed_at=datetime.now().isoformat(),
            snapshot_type="client",
            entity_id="c1",
            effort_score=42.5,
            efficiency_ratio=3.2,
            profitability_band="HIGH",
            cost_drivers=["overdue_tasks", "high_volume"],
            data={"revenue_total": 136000, "effort_score": 42.5},
        )
        cp.record_snapshot(snapshot)

        latest = cp.get_latest_entity_snapshot("c1")
        assert latest is not None
        assert latest.effort_score == 42.5
        assert latest.profitability_band == "HIGH"
        assert "overdue_tasks" in latest.cost_drivers

    def test_portfolio_snapshot(self, integration_db):
        cp = CostPersistence(integration_db)

        portfolio = CostSnapshotRecord(
            id=make_id(),
            computed_at=datetime.now().isoformat(),
            snapshot_type="portfolio",
            entity_id=None,
            effort_score=500.0,
            efficiency_ratio=2.8,
            profitability_band="MED",
            cost_drivers=[],
            data={"total_clients": 25, "avg_efficiency": 2.8},
        )
        cp.record_snapshot(portfolio)

        latest = cp.get_latest_portfolio_snapshot()
        assert latest is not None
        assert latest.snapshot_type == "portfolio"
        assert latest.data["total_clients"] == 25


# =============================================================================
# VALIDATION 5: Helper conversion functions
# =============================================================================


class TestConversionHelpers:
    """Verify helper functions that convert from detection output to persistence format."""

    def test_pattern_evidence_to_snapshot(self):
        """Pattern dict from detect_all_patterns → PatternSnapshot."""
        pattern_dict = {
            "pattern_id": "PAT_001",
            "pattern_name": "Revenue Concentration",
            "pattern_type": "concentration",
            "severity": "structural",
            "detected_at": "2026-02-21T12:00:00",
            "entities_involved": [{"type": "client", "id": "c1"}],
            "metrics": {"hhi": 0.3},
            "evidence_narrative": "High concentration",
            "confidence": "high",
        }

        snapshot = snapshot_from_pattern_evidence(pattern_dict, cycle_id="cyc-1")
        assert isinstance(snapshot, PatternSnapshot)
        assert snapshot.pattern_id == "PAT_001"
        assert snapshot.cycle_id == "cyc-1"
        assert snapshot.evidence["metrics"]["hhi"] == 0.3

    def test_cost_profile_to_snapshot(self):
        """Cost dict from CostToServeEngine → CostSnapshotRecord."""
        cost_dict = {
            "effort_score": 42.5,
            "efficiency_ratio": 3.2,
            "profitability_band": "HIGH",
            "cost_drivers": ["overdue_tasks"],
        }

        snapshot = snapshot_from_cost_profile(cost_dict, "client", "c1")
        assert isinstance(snapshot, CostSnapshotRecord)
        assert snapshot.snapshot_type == "client"
        assert snapshot.entity_id == "c1"
        assert snapshot.effort_score == 42.5

    def test_signal_change_to_event(self):
        """Signal state change → IntelligenceEvent."""
        event = event_from_signal_change(
            "SIG_001",
            "client",
            "c1",
            "warning",
            "new",
            details={"evidence": {"overdue_count": 5}},
        )
        assert isinstance(event, IntelligenceEvent)
        assert event.event_type == "signal_fired"
        assert event.severity == "warning"
        assert event.source_module == "signals"

    def test_pattern_to_event(self):
        """Detected pattern → IntelligenceEvent."""
        pattern_dict = {
            "pattern_id": "PAT_001",
            "pattern_name": "Revenue Concentration",
            "severity": "structural",
            "confidence": "high",
            "entities_involved": [{"type": "client", "id": "c1"}],
        }

        event = event_from_pattern(pattern_dict, change_type="detected")
        assert isinstance(event, IntelligenceEvent)
        assert event.event_type == "pattern_detected"
        assert event.entity_type == "client"
        assert event.entity_id == "c1"
        assert event.source_module == "patterns"


# =============================================================================
# VALIDATION 6: SQL injection safety
# =============================================================================


class TestParameterizedQueries:
    """Verify no SQL injection vectors in persistence layer."""

    def test_pattern_with_quotes_in_name(self, integration_db):
        """Pattern names with SQL-special chars don't cause injection."""
        pp = PatternPersistence(integration_db)
        snapshot = PatternSnapshot(
            id=make_id(),
            detected_at=datetime.now().isoformat(),
            pattern_id="PAT_INJECT",
            pattern_name="Robert'); DROP TABLE pattern_snapshots;--",
            pattern_type="test",
            severity="info",
            confidence="low",
            entities_involved=[{"type": "client", "id": "c1"}],
            evidence={"test": True},
            cycle_id=None,
        )
        pp.record_pattern(snapshot)

        recent = pp.get_recent_patterns(days=1)
        assert len(recent) == 1
        assert "DROP TABLE" in recent[0].pattern_name

    def test_event_with_json_injection(self, integration_db):
        """Event data with malicious JSON doesn't cause issues."""
        es = IntelligenceEventStore(integration_db)
        event = IntelligenceEvent(
            id=make_id(),
            event_type="test",
            severity="info",
            entity_type="client",
            entity_id="'; DROP TABLE intelligence_events;--",
            event_data={"malicious": "'; DROP TABLE intelligence_events;--"},
            source_module="test",
            created_at=datetime.now().isoformat(),
        )
        es.publish(event)

        # Table should still exist and have data
        entity_events = es.get_entity_events("client", "'; DROP TABLE intelligence_events;--")
        assert len(entity_events) == 1


# =============================================================================
# VALIDATION 7: Migration idempotency
# =============================================================================


class TestMigrationSafety:
    """Verify migration can be run multiple times safely."""

    def test_idempotent_migration(self, integration_db):
        """Running migration twice doesn't error or duplicate data."""
        # Migration already ran in fixture; run again
        result = run_migration(integration_db)
        assert not result["errors"]
        assert result["tables_created"] == []  # Nothing new created

    def test_all_tables_exist(self, integration_db):
        """All intelligence tables exist after migration."""
        conn = sqlite3.connect(str(integration_db))
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()

        assert "pattern_snapshots" in tables
        assert "cost_snapshots" in tables
        assert "intelligence_events" in tables
        assert "intelligence_events_archive" in tables

    def test_all_indexes_exist(self, integration_db):
        """All intelligence indexes exist after migration."""
        conn = sqlite3.connect(str(integration_db))
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        conn.close()

        expected = {
            "idx_pattern_snap_time",
            "idx_pattern_snap_pattern",
            "idx_pattern_snap_cycle",
            "idx_cost_snap_time",
            "idx_cost_snap_entity",
            "idx_cost_snap_type",
            "idx_intel_events_unconsumed",
            "idx_intel_events_entity",
            "idx_intel_events_type",
        }
        assert expected.issubset(indexes)
