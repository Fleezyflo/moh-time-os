"""
Tests for the intelligence phase wired into the daemon cycle.

Validates that the intelligence phase:
- Runs scoring, signals, patterns, cost, and event emission
- Isolates sub-step failures (one failing doesn't block others)
- Persists results to the correct tables
- Emits events for critical/warning findings
"""

import sqlite3
import sys
from datetime import datetime
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _create_tables(db_path):
    """Create all tables needed for intelligence phase testing."""
    conn = sqlite3.connect(str(db_path))
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

        CREATE TABLE IF NOT EXISTS pattern_snapshots (
            id TEXT PRIMARY KEY,
            detected_at TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            pattern_name TEXT NOT NULL,
            pattern_type TEXT,
            severity TEXT NOT NULL,
            confidence TEXT,
            entities_involved TEXT NOT NULL,
            evidence TEXT NOT NULL,
            cycle_id TEXT
        );

        CREATE TABLE IF NOT EXISTS cost_snapshots (
            id TEXT PRIMARY KEY,
            computed_at TEXT NOT NULL,
            snapshot_type TEXT NOT NULL,
            entity_id TEXT,
            effort_score REAL,
            efficiency_ratio REAL,
            profitability_band TEXT,
            cost_drivers TEXT,
            data TEXT NOT NULL,
            cycle_id TEXT
        );

        CREATE TABLE IF NOT EXISTS intelligence_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            event_data TEXT,
            source_module TEXT,
            created_at TEXT NOT NULL,
            consumed_at TEXT,
            consumer TEXT
        );
    """)
    conn.close()


@pytest.fixture
def test_db(tmp_path):
    """Create a minimal test database with required tables."""
    db_path = tmp_path / "test.db"
    _create_tables(db_path)
    return db_path


@pytest.fixture
def mock_loop(test_db):
    """
    Create an AutonomousLoop-like object that has _intelligence_phase.

    We avoid importing AutonomousLoop directly because its __init__ chain
    pulls in collectors/calendar.py which requires Python 3.11+ (datetime.UTC).
    Instead we import the module and extract the unbound method.
    """
    # Stub out problematic collector imports before importing autonomous_loop
    stub_collectors = ModuleType("lib.collectors")
    stub_collectors.CollectorOrchestrator = MagicMock
    stub_calendar = ModuleType("lib.collectors.calendar")
    stub_calendar.CalendarCollector = MagicMock

    saved = {}
    for mod_name in ["lib.collectors", "lib.collectors.calendar"]:
        saved[mod_name] = sys.modules.get(mod_name)
        sys.modules[mod_name] = stub_collectors if mod_name == "lib.collectors" else stub_calendar

    try:
        # Force reimport with stubs
        if "lib.autonomous_loop" in sys.modules:
            del sys.modules["lib.autonomous_loop"]

        from lib.autonomous_loop import AutonomousLoop

        with patch.object(AutonomousLoop, "__init__", lambda self, *a, **kw: None):
            loop = AutonomousLoop.__new__(AutonomousLoop)
            loop.store = MagicMock()
            loop.store.db_path = str(test_db)
            return loop
    finally:
        # Restore original modules
        for mod_name, original in saved.items():
            if original is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = original


class TestIntelligencePhaseWiring:
    """Test that the intelligence phase method exists and returns expected shape."""

    def test_method_exists(self, mock_loop):
        assert hasattr(mock_loop, "_intelligence_phase")

    def test_returns_results_dict(self, mock_loop, test_db):
        """Even with all sub-steps mocked out, returns correct shape."""
        with (
            patch("lib.intelligence.scorecard.score_all_clients", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_projects", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_persons", return_value=[]),
            patch(
                "lib.intelligence.signals.detect_all_signals",
                return_value={"signals": [], "total_signals": 0},
            ),
            patch(
                "lib.intelligence.patterns.detect_all_patterns",
                return_value={"patterns": [], "total_detected": 0},
            ),
        ):
            results = mock_loop._intelligence_phase()

        assert "scores_recorded" in results
        assert "signals_detected" in results
        assert "patterns_detected" in results
        assert "events_emitted" in results
        assert "cost_snapshots" in results


class TestScoringPersistence:
    """Test that scoring results are persisted to score_history."""

    def test_scores_written_to_db(self, mock_loop, test_db):
        fake_scorecards = [
            {
                "entity_type": "client",
                "entity_id": "c1",
                "entity_name": "ACME",
                "composite_score": 72.5,
                "dimensions": [
                    {"dimension": "delivery", "score": 80},
                    {"dimension": "comms", "score": 65},
                ],
                "data_completeness": 0.85,
                "scored_at": datetime.now().isoformat(),
            },
            {
                "entity_type": "client",
                "entity_id": "c2",
                "entity_name": "BigCo",
                "composite_score": 55.0,
                "dimensions": [{"dimension": "delivery", "score": 55}],
                "data_completeness": 0.5,
                "scored_at": datetime.now().isoformat(),
            },
        ]

        with (
            patch("lib.intelligence.scorecard.score_all_clients", return_value=fake_scorecards),
            patch("lib.intelligence.scorecard.score_all_projects", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_persons", return_value=[]),
            patch(
                "lib.intelligence.signals.detect_all_signals",
                return_value={"signals": [], "total_signals": 0},
            ),
            patch(
                "lib.intelligence.patterns.detect_all_patterns",
                return_value={"patterns": [], "total_detected": 0},
            ),
        ):
            results = mock_loop._intelligence_phase()

        assert results["scores_recorded"] == 2

        # Verify in DB
        conn = sqlite3.connect(str(test_db))
        rows = conn.execute("SELECT * FROM score_history").fetchall()
        conn.close()
        assert len(rows) == 2

    def test_null_score_skipped(self, mock_loop, test_db):
        """Entities with composite_score=None are not persisted."""
        fake_scorecards = [
            {
                "entity_type": "client",
                "entity_id": "c1",
                "composite_score": None,
                "composite_classification": "data_unavailable",
                "dimensions": [],
                "scored_at": datetime.now().isoformat(),
            },
        ]

        with (
            patch("lib.intelligence.scorecard.score_all_clients", return_value=fake_scorecards),
            patch("lib.intelligence.scorecard.score_all_projects", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_persons", return_value=[]),
            patch(
                "lib.intelligence.signals.detect_all_signals",
                return_value={"signals": [], "total_signals": 0},
            ),
            patch(
                "lib.intelligence.patterns.detect_all_patterns",
                return_value={"patterns": [], "total_detected": 0},
            ),
        ):
            results = mock_loop._intelligence_phase()

        assert results["scores_recorded"] == 0


class TestSignalDetection:
    """Test signal detection and state update in intelligence phase."""

    def test_signals_detected_and_state_updated(self, mock_loop, test_db):
        fake_signals = {
            "signals": [
                {
                    "signal_id": "SIG_001",
                    "entity_type": "client",
                    "entity_id": "c1",
                    "severity": "warning",
                    "description": "Overdue tasks",
                },
            ],
            "total_signals": 1,
        }
        fake_state = {"new": 1, "escalated": 0, "cleared": 0, "ongoing": 0}

        with (
            patch("lib.intelligence.scorecard.score_all_clients", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_projects", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_persons", return_value=[]),
            patch("lib.intelligence.signals.detect_all_signals", return_value=fake_signals),
            patch(
                "lib.intelligence.signals.update_signal_state", return_value=fake_state
            ) as mock_update,
            patch(
                "lib.intelligence.patterns.detect_all_patterns",
                return_value={"patterns": [], "total_detected": 0},
            ),
        ):
            results = mock_loop._intelligence_phase()

        assert results["signals_detected"] == 1
        assert results["signal_state_changes"] == 1
        mock_update.assert_called_once()


class TestPatternPersistence:
    """Test pattern detection and persistence."""

    def test_patterns_persisted(self, mock_loop, test_db):
        fake_patterns = {
            "patterns": [
                {
                    "pattern_id": "PAT_001",
                    "pattern_name": "Revenue Concentration",
                    "pattern_type": "concentration",
                    "severity": "structural",
                    "detected_at": datetime.now().isoformat(),
                    "entities_involved": [{"type": "client", "id": "c1"}],
                    "metrics": {"hhi": 0.3},
                    "evidence_narrative": "High concentration",
                    "confidence": "high",
                },
            ],
            "total_detected": 1,
        }

        with (
            patch("lib.intelligence.scorecard.score_all_clients", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_projects", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_persons", return_value=[]),
            patch(
                "lib.intelligence.signals.detect_all_signals",
                return_value={"signals": [], "total_signals": 0},
            ),
            patch("lib.intelligence.patterns.detect_all_patterns", return_value=fake_patterns),
        ):
            results = mock_loop._intelligence_phase()

        assert results["patterns_detected"] == 1

        # Verify pattern persisted in DB
        conn = sqlite3.connect(str(test_db))
        rows = conn.execute("SELECT * FROM pattern_snapshots").fetchall()
        conn.close()
        assert len(rows) == 1


class TestEventEmission:
    """Test intelligence event emission for critical findings."""

    def test_critical_signal_emits_event(self, mock_loop, test_db):
        fake_signals = {
            "signals": [
                {
                    "signal_id": "SIG_001",
                    "entity_type": "client",
                    "entity_id": "c1",
                    "severity": "critical",
                    "description": "Revenue cliff",
                },
            ],
            "total_signals": 1,
        }

        with (
            patch("lib.intelligence.scorecard.score_all_clients", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_projects", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_persons", return_value=[]),
            patch("lib.intelligence.signals.detect_all_signals", return_value=fake_signals),
            patch(
                "lib.intelligence.signals.update_signal_state",
                return_value={"new": 1, "escalated": 0, "cleared": 0},
            ),
            patch(
                "lib.intelligence.patterns.detect_all_patterns",
                return_value={"patterns": [], "total_detected": 0},
            ),
        ):
            results = mock_loop._intelligence_phase()

        assert results["events_emitted"] == 1

        # Verify event in DB
        conn = sqlite3.connect(str(test_db))
        rows = conn.execute("SELECT * FROM intelligence_events").fetchall()
        conn.close()
        assert len(rows) == 1

    def test_warning_pattern_emits_event(self, mock_loop, test_db):
        fake_patterns = {
            "patterns": [
                {
                    "pattern_id": "PAT_001",
                    "pattern_name": "Single Point of Failure",
                    "pattern_type": "dependency",
                    "severity": "warning",
                    "detected_at": datetime.now().isoformat(),
                    "entities_involved": [{"type": "person", "id": "p1"}],
                    "metrics": {},
                    "evidence_narrative": "Person handles all design",
                    "confidence": "medium",
                },
            ],
            "total_detected": 1,
        }

        with (
            patch("lib.intelligence.scorecard.score_all_clients", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_projects", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_persons", return_value=[]),
            patch(
                "lib.intelligence.signals.detect_all_signals",
                return_value={"signals": [], "total_signals": 0},
            ),
            patch("lib.intelligence.patterns.detect_all_patterns", return_value=fake_patterns),
        ):
            results = mock_loop._intelligence_phase()

        assert results["events_emitted"] == 1

    def test_watch_severity_no_event(self, mock_loop, test_db):
        """Watch-level signals should NOT emit events."""
        fake_signals = {
            "signals": [
                {
                    "signal_id": "SIG_002",
                    "entity_type": "client",
                    "entity_id": "c1",
                    "severity": "watch",
                    "description": "Minor delay",
                },
            ],
            "total_signals": 1,
        }

        with (
            patch("lib.intelligence.scorecard.score_all_clients", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_projects", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_persons", return_value=[]),
            patch("lib.intelligence.signals.detect_all_signals", return_value=fake_signals),
            patch(
                "lib.intelligence.signals.update_signal_state",
                return_value={"new": 1, "escalated": 0, "cleared": 0},
            ),
            patch(
                "lib.intelligence.patterns.detect_all_patterns",
                return_value={"patterns": [], "total_detected": 0},
            ),
        ):
            results = mock_loop._intelligence_phase()

        assert results["events_emitted"] == 0


class TestIsolation:
    """Test that sub-step failures are isolated."""

    def test_scoring_failure_doesnt_block_signals(self, mock_loop, test_db):
        """If scoring raises, signals should still run."""
        fake_signals = {
            "signals": [
                {
                    "signal_id": "SIG_001",
                    "entity_type": "client",
                    "entity_id": "c1",
                    "severity": "warning",
                },
            ],
            "total_signals": 1,
        }

        with (
            patch(
                "lib.intelligence.scorecard.score_all_clients", side_effect=Exception("DB error")
            ),
            patch("lib.intelligence.scorecard.score_all_projects", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_persons", return_value=[]),
            patch("lib.intelligence.signals.detect_all_signals", return_value=fake_signals),
            patch(
                "lib.intelligence.signals.update_signal_state",
                return_value={"new": 1, "escalated": 0, "cleared": 0},
            ),
            patch(
                "lib.intelligence.patterns.detect_all_patterns",
                return_value={"patterns": [], "total_detected": 0},
            ),
        ):
            results = mock_loop._intelligence_phase()

        # Scoring failed but signals still ran
        assert results["scores_recorded"] == 0
        assert results["signals_detected"] == 1

    def test_signal_failure_doesnt_block_patterns(self, mock_loop, test_db):
        """If signal detection raises, patterns should still run."""
        fake_patterns = {
            "patterns": [
                {
                    "pattern_id": "PAT_001",
                    "pattern_name": "Test",
                    "pattern_type": "concentration",
                    "severity": "structural",
                    "detected_at": datetime.now().isoformat(),
                    "entities_involved": [{"type": "client", "id": "c1"}],
                    "metrics": {},
                    "evidence_narrative": "test",
                    "confidence": "high",
                },
            ],
            "total_detected": 1,
        }

        with (
            patch("lib.intelligence.scorecard.score_all_clients", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_projects", return_value=[]),
            patch("lib.intelligence.scorecard.score_all_persons", return_value=[]),
            patch(
                "lib.intelligence.signals.detect_all_signals", side_effect=Exception("Signal crash")
            ),
            patch("lib.intelligence.patterns.detect_all_patterns", return_value=fake_patterns),
        ):
            results = mock_loop._intelligence_phase()

        # Signals failed but patterns still ran
        assert results["signals_detected"] == 0
        assert results["patterns_detected"] == 1

    def test_all_sub_steps_fail_gracefully(self, mock_loop, test_db):
        """If everything raises, still return a valid results dict."""
        with (
            patch("lib.intelligence.scorecard.score_all_clients", side_effect=Exception("fail")),
            patch("lib.intelligence.scorecard.score_all_projects", side_effect=Exception("fail")),
            patch("lib.intelligence.scorecard.score_all_persons", side_effect=Exception("fail")),
            patch("lib.intelligence.signals.detect_all_signals", side_effect=Exception("fail")),
            patch("lib.intelligence.patterns.detect_all_patterns", side_effect=Exception("fail")),
        ):
            results = mock_loop._intelligence_phase()

        assert results["scores_recorded"] == 0
        assert results["signals_detected"] == 0
        assert results["patterns_detected"] == 0
        assert results["events_emitted"] == 0
