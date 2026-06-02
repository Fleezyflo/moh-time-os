"""WS4 S4.2 — data-freshness wiring at the orchestrator choke point."""

from lib.intelligence.data_freshness import DataFreshnessTracker


def test_record_collection_for_source_inserts_row(tmp_path):
    tracker = DataFreshnessTracker(db_path=tmp_path / "fresh.db")
    tracker.record_collection_for_source("gmail", record_count=437)

    dash = tracker.get_freshness_dashboard()
    assert dash["total_tracked"] == 1
    assert "gmail" in dash["avg_freshness_by_source"]


def test_record_collection_for_source_uses_source_as_entity(tmp_path):
    tracker = DataFreshnessTracker(db_path=tmp_path / "fresh.db")
    tracker.record_collection_for_source("xero", record_count=10)

    records = tracker.get_freshness("source", "xero")
    assert len(records) == 1
    assert records[0].source == "xero"
    assert records[0].freshness_score > 0.9


def test_sync_one_records_freshness_on_success(tmp_path, monkeypatch):
    """A successful _sync_one must land a data_freshness row for the source."""
    from unittest.mock import MagicMock

    from lib.collectors import orchestrator as orch_mod

    # Build an orchestrator without running __init__ (avoids loading real collectors).
    orch = object.__new__(orch_mod.CollectorOrchestrator)
    orch.logger = MagicMock()
    fake_collector = MagicMock()
    fake_collector.sync.return_value = {"status": "success", "stored": 5, "source": "gmail"}
    orch.collectors = {"gmail": fake_collector}

    # Point the freshness tracker at a temp DB.
    fresh_db = tmp_path / "fresh.db"
    monkeypatch.setattr(orch_mod.paths, "db_path", lambda: fresh_db)

    # Neutralize the lock and mark_collected so the test is hermetic.
    monkeypatch.setattr(orch_mod, "mark_collected", lambda _name: None)

    class _NoLock:
        def __init__(self, *a, **k):
            self.acquired = True

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def break_lock(self):
            pass

    monkeypatch.setattr(orch_mod, "CollectorLock", _NoLock)

    result = orch._sync_one("gmail")
    assert result["status"] == "success"

    from lib.intelligence.data_freshness import DataFreshnessTracker

    tracker = DataFreshnessTracker(db_path=fresh_db)
    records = tracker.get_freshness("source", "gmail")
    assert len(records) == 1
    assert records[0].source == "gmail"


def test_dashboard_has_no_sources_key_but_has_avg_by_source(tmp_path):
    """Regression: autonomous_loop must NOT rely on a 'sources' key.

    get_freshness_dashboard() returns 'avg_freshness_by_source', never
    'sources'. This pins the contract so the loop's source-count is real.
    """
    tracker = DataFreshnessTracker(db_path=tmp_path / "fresh.db")
    tracker.record_collection_for_source("gmail")
    tracker.record_collection_for_source("xero")

    dash = tracker.get_freshness_dashboard()
    assert "sources" not in dash
    assert len(dash["avg_freshness_by_source"]) == 2
