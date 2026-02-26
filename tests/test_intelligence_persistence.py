"""
Tests for intelligence persistence layer.

Validates that pattern snapshots, cost snapshots, and intelligence events
are correctly stored, queried, and lifecycle-managed.
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

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
def test_db(tmp_path):
    """Create a test database with intelligence tables."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    # Create signal_state for completeness (already exists in production)
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
    """)
    conn.close()

    result = run_migration(db_path)
    assert not result["errors"], f"Migration failed: {result['errors']}"
    return db_path


# =============================================================================
# MIGRATION TESTS
# =============================================================================


class TestMigration:
    def test_creates_all_tables(self, test_db):
        conn = sqlite3.connect(str(test_db))
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()

        assert "pattern_snapshots" in tables
        assert "cost_snapshots" in tables
        assert "intelligence_events" in tables

    def test_idempotent(self, test_db):
        """Migration can be run multiple times safely."""
        result = run_migration(test_db)
        assert not result["errors"]
        # Second run should create 0 new tables
        assert result["tables_created"] == []

    def test_indexes_created(self, test_db):
        conn = sqlite3.connect(str(test_db))
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        conn.close()

        assert "idx_pattern_snap_time" in indexes
        assert "idx_pattern_snap_pattern" in indexes
        assert "idx_cost_snap_time" in indexes
        assert "idx_cost_snap_entity" in indexes
        assert "idx_intel_events_unconsumed" in indexes
        assert "idx_intel_events_entity" in indexes


# =============================================================================
# PATTERN PERSISTENCE TESTS
# =============================================================================


class TestPatternPersistence:
    def _make_pattern(self, pattern_id: str = "PAT_001", cycle_id: str = None) -> PatternSnapshot:
        return PatternSnapshot(
            id=make_id(),
            detected_at=datetime.now().isoformat(),
            pattern_id=pattern_id,
            pattern_name="Revenue Concentration",
            pattern_type="concentration",
            severity="structural",
            confidence="high",
            entities_involved=[
                {
                    "type": "client",
                    "id": "client-1",
                    "name": "ACME Corp",
                    "role_in_pattern": "dominant",
                }
            ],
            evidence={
                "metrics": {"top_3_share": 0.85},
                "evidence_narrative": "Top 3 clients represent 85% of revenue",
            },
            cycle_id=cycle_id,
        )

    def test_record_and_retrieve(self, test_db):
        pp = PatternPersistence(test_db)
        pattern = self._make_pattern()
        pp.record_pattern(pattern)

        recent = pp.get_recent_patterns(days=1)
        assert len(recent) == 1
        assert recent[0].pattern_id == "PAT_001"
        assert recent[0].confidence == "high"
        assert recent[0].entities_involved[0]["id"] == "client-1"

    def test_record_batch(self, test_db):
        pp = PatternPersistence(test_db)
        patterns = [self._make_pattern(f"PAT_{i:03d}") for i in range(5)]
        result = pp.record_batch(patterns)
        assert result["recorded"] == 5
        assert result["errors"] == 0

        recent = pp.get_recent_patterns(days=1)
        assert len(recent) == 5

    def test_get_by_entity(self, test_db):
        pp = PatternPersistence(test_db)
        pp.record_pattern(self._make_pattern("PAT_001"))
        pp.record_pattern(self._make_pattern("PAT_002"))

        entity_patterns = pp.get_patterns_for_entity("client", "client-1")
        assert len(entity_patterns) == 2

    def test_get_by_cycle(self, test_db):
        pp = PatternPersistence(test_db)
        pp.record_pattern(self._make_pattern("PAT_001", cycle_id="cycle-1"))
        pp.record_pattern(self._make_pattern("PAT_002", cycle_id="cycle-1"))
        pp.record_pattern(self._make_pattern("PAT_003", cycle_id="cycle-2"))

        cycle_1 = pp.get_patterns_in_cycle("cycle-1")
        assert len(cycle_1) == 2

        cycle_2 = pp.get_patterns_in_cycle("cycle-2")
        assert len(cycle_2) == 1

    def test_pattern_history(self, test_db):
        pp = PatternPersistence(test_db)
        for i in range(5):
            pp.record_pattern(self._make_pattern("PAT_001", cycle_id=f"cycle-{i}"))

        history = pp.get_pattern_history("PAT_001", cycles=3)
        assert len(history) == 3


# =============================================================================
# COST PERSISTENCE TESTS
# =============================================================================


class TestCostPersistence:
    def _make_cost(self, entity_id: str = "client-1") -> CostSnapshotRecord:
        return CostSnapshotRecord(
            id=make_id(),
            computed_at=datetime.now().isoformat(),
            snapshot_type="client",
            entity_id=entity_id,
            effort_score=42.5,
            efficiency_ratio=3.2,
            profitability_band="HIGH",
            cost_drivers=["high_task_volume", "overdue_tasks"],
            data={
                "effort_score": 42.5,
                "efficiency_ratio": 3.2,
                "profitability_band": "HIGH",
                "revenue_total": 136000,
            },
        )

    def test_record_and_retrieve(self, test_db):
        cp = CostPersistence(test_db)
        snapshot = self._make_cost()
        cp.record_snapshot(snapshot)

        latest = cp.get_latest_entity_snapshot("client-1")
        assert latest is not None
        assert latest.effort_score == 42.5
        assert latest.profitability_band == "HIGH"
        assert latest.data["revenue_total"] == 136000

    def test_record_batch(self, test_db):
        cp = CostPersistence(test_db)
        snapshots = [self._make_cost(f"client-{i}") for i in range(5)]
        result = cp.record_batch(snapshots)
        assert result["recorded"] == 5
        assert result["errors"] == 0

    def test_entity_cost_history(self, test_db):
        cp = CostPersistence(test_db)
        for _ in range(3):
            cp.record_snapshot(self._make_cost("client-1"))

        history = cp.get_entity_cost_history("client-1")
        assert len(history) == 3

    def test_portfolio_snapshot(self, test_db):
        cp = CostPersistence(test_db)
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
# INTELLIGENCE EVENT TESTS
# =============================================================================


class TestIntelligenceEvents:
    def _make_event(
        self,
        event_type: str = "signal_fired",
        severity: str = "warning",
    ) -> IntelligenceEvent:
        return IntelligenceEvent(
            id=make_id(),
            event_type=event_type,
            severity=severity,
            entity_type="client",
            entity_id="client-1",
            event_data={"signal_id": "SIG_001", "change_type": "new"},
            source_module="signals",
            created_at=datetime.now().isoformat(),
        )

    def test_publish_and_retrieve(self, test_db):
        es = IntelligenceEventStore(test_db)
        event = self._make_event()
        es.publish(event)

        unconsumed = es.get_unconsumed()
        assert len(unconsumed) == 1
        assert unconsumed[0].event_type == "signal_fired"
        assert unconsumed[0].consumed_at is None

    def test_publish_batch(self, test_db):
        es = IntelligenceEventStore(test_db)
        events = [self._make_event(f"signal_{i}") for i in range(5)]
        result = es.publish_batch(events)
        assert result["published"] == 5
        assert result["errors"] == 0

    def test_mark_consumed(self, test_db):
        es = IntelligenceEventStore(test_db)
        event = self._make_event()
        es.publish(event)

        success = es.mark_consumed(event.id, "preparation_engine")
        assert success

        unconsumed = es.get_unconsumed()
        assert len(unconsumed) == 0

    def test_double_consume_fails(self, test_db):
        es = IntelligenceEventStore(test_db)
        event = self._make_event()
        es.publish(event)

        assert es.mark_consumed(event.id, "consumer_1")
        assert not es.mark_consumed(event.id, "consumer_2")

    def test_filter_by_type(self, test_db):
        es = IntelligenceEventStore(test_db)
        es.publish(self._make_event("signal_fired"))
        es.publish(self._make_event("pattern_detected"))
        es.publish(self._make_event("signal_fired"))

        signals = es.get_unconsumed(event_type="signal_fired")
        assert len(signals) == 2

        patterns = es.get_unconsumed(event_type="pattern_detected")
        assert len(patterns) == 1

    def test_filter_by_severity(self, test_db):
        es = IntelligenceEventStore(test_db)
        es.publish(self._make_event(severity="critical"))
        es.publish(self._make_event(severity="warning"))
        es.publish(self._make_event(severity="critical"))

        critical = es.get_unconsumed(severity="critical")
        assert len(critical) == 2

    def test_entity_events(self, test_db):
        es = IntelligenceEventStore(test_db)
        es.publish(self._make_event())

        entity_events = es.get_entity_events("client", "client-1")
        assert len(entity_events) == 1

    def test_archive_old_events(self, test_db):
        """Consumed events older than threshold are archived."""
        es = IntelligenceEventStore(test_db)

        # Create archive table
        conn = sqlite3.connect(str(test_db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS intelligence_events_archive (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                event_data TEXT NOT NULL,
                source_module TEXT,
                created_at TEXT NOT NULL,
                consumed_at TEXT,
                consumer TEXT,
                archived_at TEXT NOT NULL
            )
        """)
        conn.close()

        # Publish and consume an event
        event = self._make_event()
        es.publish(event)
        es.mark_consumed(event.id, "test_consumer")

        # Backdate consumed_at to 60 days ago
        conn = sqlite3.connect(str(test_db))
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        conn.execute(
            "UPDATE intelligence_events SET consumed_at = ? WHERE id = ?",
            (old_date, event.id),
        )
        conn.commit()
        conn.close()

        # Archive events older than 30 days
        count = es.archive_old_events(days=30)
        assert count == 1

        # Main table should be empty
        es.get_unconsumed()
        conn = sqlite3.connect(str(test_db))
        remaining = conn.execute("SELECT COUNT(*) FROM intelligence_events").fetchone()[0]
        archived = conn.execute("SELECT COUNT(*) FROM intelligence_events_archive").fetchone()[0]
        conn.close()

        assert remaining == 0
        assert archived == 1

    def test_archive_skips_recent(self, test_db):
        """Recently consumed events are NOT archived."""
        es = IntelligenceEventStore(test_db)

        # Create archive table
        conn = sqlite3.connect(str(test_db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS intelligence_events_archive (
                id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
                severity TEXT NOT NULL, entity_type TEXT,
                entity_id TEXT, event_data TEXT NOT NULL,
                source_module TEXT, created_at TEXT NOT NULL,
                consumed_at TEXT, consumer TEXT,
                archived_at TEXT NOT NULL
            )
        """)
        conn.close()

        # Publish and consume an event (consumed just now)
        event = self._make_event()
        es.publish(event)
        es.mark_consumed(event.id, "test")

        count = es.archive_old_events(days=30)
        assert count == 0

    def test_archive_no_table(self, test_db):
        """If archive table doesn't exist, return 0 without error."""
        es = IntelligenceEventStore(test_db)
        # Don't create archive table — should handle gracefully
        count = es.archive_old_events(days=30)
        assert count == 0


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestHelpers:
    def test_snapshot_from_pattern_evidence(self):
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
        assert snapshot.pattern_id == "PAT_001"
        assert snapshot.cycle_id == "cyc-1"
        assert snapshot.confidence == "high"
        assert snapshot.evidence["metrics"]["hhi"] == 0.3

    def test_snapshot_from_cost_profile(self):
        cost_dict = {
            "effort_score": 42.5,
            "efficiency_ratio": 3.2,
            "profitability_band": "HIGH",
            "cost_drivers": ["overdue_tasks"],
        }

        snapshot = snapshot_from_cost_profile(cost_dict, "client", "c1", "cyc-1")
        assert snapshot.snapshot_type == "client"
        assert snapshot.entity_id == "c1"
        assert snapshot.effort_score == 42.5
        assert snapshot.cost_drivers == ["overdue_tasks"]

    def test_event_from_signal_change(self):
        event = event_from_signal_change(
            "SIG_001",
            "client",
            "c1",
            "warning",
            "new",
            details={"evidence": {"overdue_count": 5}},
        )
        assert event.event_type == "signal_fired"
        assert event.severity == "warning"
        assert event.event_data["signal_id"] == "SIG_001"
        assert event.source_module == "signals"

    def test_event_from_pattern(self):
        pattern_dict = {
            "pattern_id": "PAT_001",
            "pattern_name": "Revenue Concentration",
            "severity": "structural",
            "confidence": "high",
            "entities_involved": [{"type": "client", "id": "c1"}],
        }

        event = event_from_pattern(pattern_dict, change_type="detected")
        assert event.event_type == "pattern_detected"
        assert event.entity_type == "client"
        assert event.entity_id == "c1"
        assert event.source_module == "patterns"

    def test_make_id_unique(self):
        ids = {make_id() for _ in range(100)}
        assert len(ids) == 100
