"""
Tests for AuditTrail — intelligence operation audit logging.

Brief 28 (IO), Task IO-1.1
"""

import pytest

from lib.intelligence.audit_trail import AuditEntry, AuditTrail


@pytest.fixture
def trail(tmp_path):
    db_path = tmp_path / "test_audit.db"
    return AuditTrail(db_path=db_path)


class TestRecordEntry:
    def test_basic_record(self, trail):
        entry = trail.record(
            operation="health_score",
            entity_type="client",
            entity_id="c1",
            inputs_summary={"dimensions": 4},
            outputs_summary={"score": 82.5},
            duration_ms=12.5,
        )
        assert entry.id is not None
        assert entry.operation == "health_score"
        assert entry.status == "success"
        assert entry.duration_ms == 12.5

    def test_error_record(self, trail):
        entry = trail.record(
            operation="signal_detect",
            entity_type="client",
            entity_id="c1",
            status="error",
            error_message="Database timeout",
            duration_ms=5000,
        )
        assert entry.status == "error"
        assert entry.error_message == "Database timeout"

    def test_to_dict(self, trail):
        entry = trail.record("test_op", "client", "c1")
        d = entry.to_dict()
        assert "operation" in d
        assert "created_at" in d
        assert "duration_ms" in d


class TestQueryEntries:
    def test_get_by_entity(self, trail):
        trail.record("health_score", "client", "c1", duration_ms=10)
        trail.record("signal_detect", "client", "c1", duration_ms=5)
        trail.record("health_score", "client", "c2", duration_ms=8)

        entries = trail.get_entries(entity_type="client", entity_id="c1")
        assert len(entries) == 2

    def test_get_by_operation(self, trail):
        trail.record("health_score", "client", "c1")
        trail.record("signal_detect", "client", "c1")

        entries = trail.get_entries(operation="health_score")
        assert len(entries) == 1

    def test_get_by_status(self, trail):
        trail.record("op1", "client", "c1", status="success")
        trail.record("op2", "client", "c1", status="error", error_message="fail")

        entries = trail.get_entries(status="error")
        assert len(entries) == 1
        assert entries[0].error_message == "fail"

    def test_get_errors(self, trail):
        trail.record("op1", "client", "c1", status="success")
        trail.record("op2", "client", "c1", status="error", error_message="fail")

        errors = trail.get_error_entries()
        assert len(errors) == 1

    def test_limit(self, trail):
        for i in range(10):
            trail.record(f"op_{i}", "client", "c1")
        entries = trail.get_entries(limit=5)
        assert len(entries) == 5


class TestPerformanceStats:
    def test_stats(self, trail):
        trail.record("health_score", "client", "c1", duration_ms=10)
        trail.record("health_score", "client", "c2", duration_ms=20)
        trail.record("signal_detect", "client", "c1", duration_ms=5)
        trail.record(
            "signal_detect", "client", "c1", status="error", error_message="x", duration_ms=100
        )

        stats = trail.get_performance_stats()
        assert "health_score" in stats
        assert stats["health_score"]["count"] == 2
        assert stats["health_score"]["avg_duration_ms"] == 15.0
        assert stats["signal_detect"]["error_count"] == 1
        assert stats["signal_detect"]["error_rate"] == 0.5

    def test_stats_single_operation(self, trail):
        trail.record("health_score", "client", "c1", duration_ms=10)
        trail.record("health_score", "client", "c2", duration_ms=30)
        trail.record("signal_detect", "client", "c1", duration_ms=5)

        stats = trail.get_performance_stats(operation="health_score")
        assert "health_score" in stats
        assert "signal_detect" not in stats

    def test_stats_empty(self, trail):
        stats = trail.get_performance_stats()
        assert stats == {}
