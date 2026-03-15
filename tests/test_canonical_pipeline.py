"""
Tests proving the canonical pipeline decisions from CANONICALIZATION.md.

These tests verify:
1. Daemon pipeline runs the 8 canonical stages in order
2. Daemon detection writes to detection_findings (not preview)
3. Daemon intelligence runs signal detection + V4 proposals (not in-memory engine)
4. Daemon notify is log-only (not Google Chat noise)
5. Autonomous loop is marked as non-canonical
6. Non-canonical routes exist but are documented as such
"""

import importlib
import inspect
import sqlite3
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_minimal_db(db_path: Path) -> None:
    """Create minimal tables needed for canonical pipeline testing."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS detection_findings (
            id TEXT PRIMARY KEY,
            detector TEXT,
            finding_type TEXT,
            entity_type TEXT,
            entity_id TEXT,
            entity_name TEXT,
            severity TEXT,
            severity_data TEXT,
            adjacent_data TEXT,
            related_findings TEXT,
            first_detected_at TEXT,
            last_detected_at TEXT,
            cycle_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS detection_findings_preview (
            id TEXT PRIMARY KEY,
            detector TEXT,
            finding_type TEXT,
            entity_type TEXT,
            entity_id TEXT,
            entity_name TEXT,
            severity TEXT,
            severity_data TEXT,
            adjacent_data TEXT,
            related_findings TEXT,
            first_detected_at TEXT,
            last_detected_at TEXT,
            cycle_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            resolved_at TEXT
        );

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

        CREATE TABLE IF NOT EXISTS proposals_v4 (
            id TEXT PRIMARY KEY,
            scope_type TEXT,
            scope_id TEXT,
            headline TEXT,
            body TEXT,
            urgency TEXT,
            status TEXT DEFAULT 'open',
            signal_ids TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_state (
            source TEXT PRIMARY KEY,
            last_sync TEXT,
            last_success TEXT,
            items_synced INTEGER
        );
    """)
    conn.close()


# ===========================================================================
# 1. Daemon pipeline stage order
# ===========================================================================


class TestDaemonPipelineOrder:
    """Verify the daemon's run_once executes the canonical 8-stage pipeline."""

    def test_run_once_jobs_match_canonical_order(self):
        """The daemon's run_once job list matches CANONICALIZATION.md §F."""
        from lib.daemon import TimeOSDaemon

        daemon = TimeOSDaemon.__new__(TimeOSDaemon)
        # Inspect the run_once method source for the job list
        source = inspect.getsource(daemon.run_once)

        # The canonical order from CANONICALIZATION.md:
        canonical_order = [
            "collect",
            "lane_assignment",
            "truth_cycle",
            "detection",
            "intelligence",
            "snapshot",
            "morning_brief",
            "notify",
        ]

        # Verify each stage appears in order in run_once
        last_pos = -1
        for stage in canonical_order:
            pos = source.find(f'"{stage}"')
            assert pos > last_pos, (
                f"Stage '{stage}' not found in expected order in run_once. "
                f"Expected after position {last_pos}, found at {pos}"
            )
            last_pos = pos


# ===========================================================================
# 2. Detection writes to canonical table
# ===========================================================================


class TestDetectionCanonicalTable:
    """Verify detection writes to detection_findings, not preview."""

    def test_daemon_detection_uses_dry_run_false(self):
        """Daemon's _handle_detection passes dry_run=False."""
        source = inspect.getsource(
            importlib.import_module("lib.daemon").TimeOSDaemon._handle_detection
        )
        assert "dry_run=False" in source, (
            "Daemon _handle_detection must use dry_run=False "
            "to write to canonical detection_findings table"
        )
        assert "dry_run=True" not in source, "Daemon _handle_detection must NOT use dry_run=True"

    def test_run_all_detectors_table_selection(self, tmp_path):
        """run_all_detectors with dry_run=False writes to detection_findings."""
        db_path = tmp_path / "test.db"
        _create_minimal_db(db_path)

        with (
            patch("lib.detectors.CollisionDetector") as mock_col,
            patch("lib.detectors.DriftDetector") as mock_drift,
            patch("lib.detectors.BottleneckDetector") as mock_bn,
        ):
            mock_col.return_value.detect.return_value = []
            mock_drift.return_value.detect.return_value = []
            mock_bn.return_value.detect.return_value = []

            from lib.detectors import run_all_detectors

            result = run_all_detectors(str(db_path), dry_run=False)

            assert result["table"] == "detection_findings"
            assert result["dry_run"] is False

    def test_run_all_detectors_preview_is_non_canonical(self, tmp_path):
        """run_all_detectors with dry_run=True writes to preview (non-canonical)."""
        db_path = tmp_path / "test.db"
        _create_minimal_db(db_path)

        with (
            patch("lib.detectors.CollisionDetector") as mock_col,
            patch("lib.detectors.DriftDetector") as mock_drift,
            patch("lib.detectors.BottleneckDetector") as mock_bn,
        ):
            mock_col.return_value.detect.return_value = []
            mock_drift.return_value.detect.return_value = []
            mock_bn.return_value.detect.return_value = []

            from lib.detectors import run_all_detectors

            result = run_all_detectors(str(db_path), dry_run=True)

            # This path exists but is non-canonical
            assert result["table"] == "detection_findings_preview"


# ===========================================================================
# 3. Intelligence uses signals + V4 proposals (not full engine)
# ===========================================================================


class TestIntelligenceCanonicalPath:
    """Verify daemon intelligence uses the focused canonical path."""

    def test_handle_intelligence_calls_detect_all_signals(self):
        """Daemon intelligence calls detect_all_signals, not generate_intelligence_snapshot."""
        source = inspect.getsource(
            importlib.import_module("lib.daemon").TimeOSDaemon._handle_intelligence
        )
        assert "detect_all_signals" in source
        assert "update_signal_state" in source
        assert "ProposalService" in source
        assert "generate_intelligence_snapshot" not in source, (
            "Daemon must NOT call generate_intelligence_snapshot — "
            "that's for API-time use per CANONICALIZATION.md §C1"
        )

    def test_handle_intelligence_does_not_import_in_memory_proposals(self):
        """Daemon intelligence must not use lib.intelligence.proposals (in-memory)."""
        source = inspect.getsource(
            importlib.import_module("lib.daemon").TimeOSDaemon._handle_intelligence
        )
        assert "from lib.intelligence.proposals" not in source, (
            "Daemon must NOT use lib.intelligence.proposals — "
            "that's the in-memory path. Use lib.v4.proposal_service instead."
        )


# ===========================================================================
# 4. Daemon notify is log-only
# ===========================================================================


class TestNotifyLogOnly:
    """Verify daemon notify doesn't send external messages."""

    def test_handle_notify_is_log_only(self):
        """Daemon _handle_notify should only log, not send Google Chat."""
        source = inspect.getsource(
            importlib.import_module("lib.daemon").TimeOSDaemon._handle_notify
        )
        assert "GoogleChatChannel" not in source, (
            "Daemon notify must not send Google Chat — "
            "that's handled by morning_brief per CANONICALIZATION.md §5"
        )
        assert "webhook" not in source.lower(), "Daemon notify must not touch webhooks"


# ===========================================================================
# 5. Autonomous loop is non-canonical
# ===========================================================================


class TestAutonomousLoopNonCanonical:
    """Verify autonomous loop is clearly marked as non-canonical."""

    def test_autonomous_loop_docstring_warns(self):
        """The autonomous_loop module docstring marks it as non-canonical."""
        import lib.autonomous_loop as al

        assert "NON-CANONICAL" in (al.__doc__ or ""), (
            "lib/autonomous_loop.py must be marked NON-CANONICAL in its docstring"
        )

    def test_in_memory_proposals_docstring_warns(self):
        """The intelligence/proposals.py module warns against daemon use."""
        import lib.intelligence.proposals as ip

        doc = ip.__doc__ or ""
        assert "NOT" in doc or "not" in doc, (
            "lib/intelligence/proposals.py should warn against daemon use"
        )
        assert "canonical" in doc.lower() or "CANONICAL" in doc, (
            "lib/intelligence/proposals.py should reference canonical path"
        )


# ===========================================================================
# 6. Non-canonical route documentation
# ===========================================================================


class TestDuplicateIntelligenceRoutesRemoved:
    """Verify duplicate intelligence handlers no longer exist in spec_router."""

    def test_spec_router_no_longer_has_duplicate_handlers(self):
        """Removed intelligence handlers must not exist in spec_router."""
        import api.spec_router as sr

        removed_handlers = [
            "get_briefing",
            "get_intelligence_signals",
            "get_intelligence_signal_summary",
            "get_intelligence_active_signals",
            "get_intelligence_signal_history",
            "get_intelligence_proposals",
            "get_intelligence_pattern_catalog",
            "get_critical_items",
            "get_client_score",
            "get_project_score",
            "get_person_score",
            "get_portfolio_score",
            "get_client_intelligence",
            "get_person_intelligence",
            "get_portfolio_intelligence",
            "get_project_state",
            "get_client_profile",
            "get_person_profile",
            "get_client_trajectory",
            "get_person_trajectory",
        ]
        for func_name in removed_handlers:
            assert not hasattr(sr, func_name), (
                f"spec_router.{func_name} still exists — it should have been "
                f"removed so intelligence_router serves this route"
            )

    def test_patterns_handler_preserved_for_response_model(self):
        """The patterns handler is kept because it uses PatternDetectionResponse."""
        import api.spec_router as sr

        assert hasattr(sr, "get_intelligence_patterns"), (
            "spec_router.get_intelligence_patterns must be preserved "
            "(it returns PatternDetectionResponse, not IntelligenceResponse)"
        )
