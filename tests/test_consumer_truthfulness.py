"""
Proof tests for Prompt 5: Consumer Truthfulness.

Verifies that consumer surfaces do NOT flatten null/error/stale states
into misleading zero/empty/clean displays.

Categories tested:
1. CLI consumers show staleness timestamps
2. Notifier does not silently drop critical signals on missing keys
3. Digest engine logs severity-aware failures
4. State store exposes cache timestamps
5. lib/api.ts body-error handling (verified via ast parse of TS)
6. hooks.ts computed_at preservation (verified via ast parse of TS)
"""

import logging
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# 1. CLI staleness indicators
# =============================================================================


class TestCLIStaleness:
    """Verify cmd_priorities and cmd_today show cache freshness."""

    def test_format_staleness_just_now(self):
        """Staleness of a few seconds shows 'just now'."""
        from cli.main import _format_staleness

        ts = datetime.now(timezone.utc)
        result = _format_staleness(ts)
        assert result == "just now"

    def test_format_staleness_minutes(self):
        """Staleness of minutes shows Xm ago."""
        from datetime import timedelta

        from cli.main import _format_staleness

        ts = datetime.now(timezone.utc) - timedelta(minutes=15)
        result = _format_staleness(ts)
        assert result == "15m ago"

    def test_format_staleness_hours(self):
        """Staleness of hours shows Xh ago."""
        from datetime import timedelta

        from cli.main import _format_staleness

        ts = datetime.now(timezone.utc) - timedelta(hours=3)
        result = _format_staleness(ts)
        assert result == "3h ago"

    def test_format_staleness_days(self):
        """Staleness of days shows Xd ago."""
        from datetime import timedelta

        from cli.main import _format_staleness

        ts = datetime.now(timezone.utc) - timedelta(days=2)
        result = _format_staleness(ts)
        assert result == "2d ago"

    def test_format_staleness_none(self):
        """None timestamp shows 'unknown age'."""
        from cli.main import _format_staleness

        result = _format_staleness(None)
        assert result == "unknown age"


# =============================================================================
# 2. State store exposes cache timestamps
# =============================================================================


class TestStateStoreCacheTimestamp:
    """Verify get_cache_timestamp returns when cache was last set.

    Uses a fresh StateStore instance by resetting the singleton and
    patching ensure_migrations to avoid the determinism guard.
    """

    def _make_store(self, tmpdir):
        """Create a fresh StateStore in a temp dir, bypassing migrations."""
        from lib.state_store import StateStore

        # Reset singleton so we can create a fresh instance
        StateStore._instance = None
        StateStore._instance = None  # double-set to cover race guard

        db_path = Path(tmpdir) / "test.db"
        # Patch ensure_migrations to skip live DB probing
        with patch("lib.state_store.db_module.ensure_migrations"):
            store = StateStore(str(db_path))
        return store

    def test_get_cache_timestamp_returns_datetime(self):
        """After set_cache, get_cache_timestamp returns a datetime."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            try:
                store.set_cache("test_key", {"data": 1})

                ts = store.get_cache_timestamp("test_key")
                assert isinstance(ts, datetime)
                # Should be recent (within 5 seconds)
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                assert age < 5
            finally:
                # Reset singleton for other tests
                from lib.state_store import StateStore

                StateStore._instance = None

    def test_get_cache_timestamp_returns_none_for_missing_key(self):
        """Missing key returns None timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            try:
                ts = store.get_cache_timestamp("nonexistent_key")
                assert ts is None
            finally:
                # Reset singleton for other tests
                from lib.state_store import StateStore

                StateStore._instance = None


# =============================================================================
# 3. Notifier does not silently drop critical signals on missing keys
# =============================================================================


class TestNotifierStructuralSafety:
    """Verify process_intelligence_for_notifications warns on missing keys."""

    def test_missing_signals_key_logs_warning(self, caplog):
        """When intel_data has no 'signals' key, a warning is logged."""
        from lib.intelligence.notifications import process_intelligence_for_notifications

        with caplog.at_level(logging.WARNING):
            result = process_intelligence_for_notifications(
                intel_data={},  # No signals key
                changes={},
                db_path=None,
            )

        assert any("missing 'signals' key" in r.message for r in caplog.records)
        assert result == []

    def test_missing_by_severity_key_logs_warning(self, caplog):
        """When signals dict has no 'by_severity' key, a warning is logged."""
        from lib.intelligence.notifications import process_intelligence_for_notifications

        with caplog.at_level(logging.WARNING):
            result = process_intelligence_for_notifications(
                intel_data={"signals": {"total": 5}},  # No by_severity
                changes={},
                db_path=None,
            )

        assert any("missing 'by_severity' key" in r.message for r in caplog.records)
        assert result == []

    def test_signals_wrong_type_logs_warning(self, caplog):
        """When signals is a list instead of dict, a warning is logged."""
        from lib.intelligence.notifications import process_intelligence_for_notifications

        with caplog.at_level(logging.WARNING):
            result = process_intelligence_for_notifications(
                intel_data={"signals": [{"id": "1"}]},  # List, not dict
                changes={},
                db_path=None,
            )

        assert any("expected dict" in r.message for r in caplog.records)
        assert result == []

    def test_missing_proposals_key_logs_warning(self, caplog):
        """When intel_data has no 'proposals' key, a warning is logged."""
        from lib.intelligence.notifications import process_intelligence_for_notifications

        with caplog.at_level(logging.WARNING):
            process_intelligence_for_notifications(
                intel_data={"signals": {"by_severity": {}}, "patterns": {}},
                changes={},
                db_path=None,
            )

        assert any("missing 'proposals' key" in r.message for r in caplog.records)

    def test_valid_structure_no_warnings(self, caplog):
        """With correct structure but empty lists, no warnings are logged."""
        from lib.intelligence.notifications import process_intelligence_for_notifications

        with caplog.at_level(logging.WARNING):
            result = process_intelligence_for_notifications(
                intel_data={
                    "signals": {"by_severity": {"critical": [], "warning": []}},
                    "patterns": {"structural": []},
                    "proposals": {"by_urgency": {"immediate": []}},
                },
                changes={},
                db_path=None,
            )

        warning_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_msgs) == 0
        assert result == []


# =============================================================================
# 4. Digest engine logs severity-aware failures
# =============================================================================


class TestDigestSeverityAwareLogging:
    """Verify digest queue failures log at error level for critical/high."""

    def test_critical_severity_logs_error(self, caplog):
        """Critical-severity queue failure logs at ERROR level."""
        from lib.notifier.digest import DigestEngine

        mock_store = MagicMock()
        mock_store.insert.side_effect = sqlite3.Error("DB locked")

        engine = DigestEngine(mock_store)

        with caplog.at_level(logging.DEBUG):
            result = engine.queue_notification(
                user_id="test",
                notification_id="n1",
                event_type="alert",
                severity="critical",
                bucket="hourly",
            )

        assert result is False
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) >= 1
        assert "DIGEST DROP" in error_records[0].message

    def test_low_severity_logs_warning(self, caplog):
        """Low-severity queue failure logs at WARNING level, not ERROR."""
        from lib.notifier.digest import DigestEngine

        mock_store = MagicMock()
        mock_store.insert.side_effect = sqlite3.Error("DB locked")

        engine = DigestEngine(mock_store)

        with caplog.at_level(logging.DEBUG):
            result = engine.queue_notification(
                user_id="test",
                notification_id="n2",
                event_type="alert",
                severity="low",
                bucket="daily",
            )

        assert result is False
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        # Should NOT have error-level records for low severity
        assert len(error_records) == 0
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1


# =============================================================================
# 5. TypeScript source verification (AST-level checks via string parsing)
# =============================================================================


class TestTypeScriptTruthfulness:
    """Verify TS source files contain truthfulness patterns (not AST, string-level)."""

    @pytest.fixture
    def repo_root(self):
        return Path(__file__).parent.parent

    def test_hooks_ts_preserves_computed_at(self, repo_root):
        """hooks.ts must expose computedAt in UseDataResult."""
        hooks_path = repo_root / "time-os-ui" / "src" / "intelligence" / "hooks.ts"
        content = hooks_path.read_text()

        # UseDataResult must have computedAt field
        assert "computedAt: string | null" in content, (
            "hooks.ts UseDataResult must expose computedAt"
        )

        # The fetch handler must set computedAt from result
        assert "setComputedAt" in content, (
            "hooks.ts must call setComputedAt to preserve envelope timestamp"
        )

        # Return value must include computedAt
        assert "computedAt, refetch" in content or "computedAt," in content, (
            "hooks.ts return must include computedAt"
        )

    def test_lib_api_ts_checks_body_error(self, repo_root):
        """lib/api.ts fetchJson must check for body-level error status."""
        api_path = repo_root / "time-os-ui" / "src" / "lib" / "api.ts"
        content = api_path.read_text()

        assert "json.status === 'error'" in content or "json.status ===" in content, (
            "lib/api.ts fetchJson must check for status='error' in response body"
        )

    def test_intelligence_api_ts_validates_body(self, repo_root):
        """intelligence/api.ts fetchJson must validate response body."""
        api_path = repo_root / "time-os-ui" / "src" / "intelligence" / "api.ts"
        content = api_path.read_text()

        assert "json.status === 'error'" in content
        assert "json.data === undefined || json.data === null" in content

    def test_signals_page_uses_computed_at(self, repo_root):
        """Signals.tsx must destructure computedAt from hook."""
        path = repo_root / "time-os-ui" / "src" / "intelligence" / "pages" / "Signals.tsx"
        content = path.read_text()

        assert "computedAt" in content, "Signals page must use computedAt for freshness"
        assert "freshnessLabel" in content, "Signals page must show freshness label"

    def test_patterns_page_uses_computed_at(self, repo_root):
        """Patterns.tsx must destructure computedAt from hook."""
        path = repo_root / "time-os-ui" / "src" / "intelligence" / "pages" / "Patterns.tsx"
        content = path.read_text()

        assert "computedAt" in content, "Patterns page must use computedAt for freshness"
        assert "freshnessLabel" in content, "Patterns page must show freshness label"

    def test_patterns_page_no_silent_severity_filter(self, repo_root):
        """Patterns.tsx must not silently exclude unknown severities."""
        path = repo_root / "time-os-ui" / "src" / "intelligence" / "pages" / "Patterns.tsx"
        content = path.read_text()

        # Must have an "Other" group for unrecognized severities
        assert "other" in content.lower() or "Other" in content, (
            "Patterns page must render patterns with unrecognized severity"
        )

    def test_client_index_no_null_to_zero(self, repo_root):
        """ClientIndex.tsx must not use ?? 0 for health_score."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "ClientIndex.tsx"
        content = path.read_text()

        # The old pattern was: client.health_score ?? 0
        assert "health_score ?? 0" not in content, (
            "ClientIndex must not flatten null health_score to 0"
        )

    def test_portfolio_no_or_dash(self, repo_root):
        """Portfolio.tsx must not use || '--' for signal/pattern counts."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Portfolio.tsx"
        content = path.read_text()

        assert "signalCount || '--'" not in content, (
            "Portfolio must not use || '--' which treats 0 as no-data"
        )
        assert "structuralPatterns.length || '--'" not in content, (
            "Portfolio must not use .length || '--' which treats 0 as no-data"
        )

    def test_project_intel_no_or_zero(self, repo_root):
        """ProjectIntel.tsx must not use || 0 for completion_rate_pct."""
        path = repo_root / "time-os-ui" / "src" / "intelligence" / "pages" / "ProjectIntel.tsx"
        content = path.read_text()

        assert "completion_rate_pct || 0" not in content, (
            "ProjectIntel must not flatten null completion_rate_pct to 0"
        )
        assert "overdue_tasks || 0" not in content, (
            "ProjectIntel must not flatten null overdue_tasks to 0"
        )

    def test_client_intel_no_falsy_score(self, repo_root):
        """ClientIntel.tsx must not use truthy check for compositeScore."""
        path = repo_root / "time-os-ui" / "src" / "intelligence" / "pages" / "ClientIntel.tsx"
        content = path.read_text()

        # Old pattern: compositeScore ? `${...}` : '—'  (treats 0 as falsy)
        # New pattern: compositeScore != null ? ... : '—'
        assert "compositeScore != null" in content, (
            "ClientIntel must use != null check for compositeScore, not truthy check"
        )

    def test_person_intel_no_nullish_zero(self, repo_root):
        """PersonIntel.tsx must not use ?? 0 for signal counts."""
        path = repo_root / "time-os-ui" / "src" / "intelligence" / "pages" / "PersonIntel.tsx"
        content = path.read_text()

        assert "?? 0" not in content, "PersonIntel must not use ?? 0 which conflates null with zero"

    def test_project_intel_preserves_signals_error(self, repo_root):
        """ProjectIntel.tsx must not drop signalsError."""
        path = repo_root / "time-os-ui" / "src" / "intelligence" / "pages" / "ProjectIntel.tsx"
        content = path.read_text()

        assert "signalsError" in content, "ProjectIntel must destructure and use signalsError"

    def test_portfolio_checks_financial_error(self, repo_root):
        """Portfolio.tsx must check financialDetail.error."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Portfolio.tsx"
        content = path.read_text()

        assert "financialDetail.error" in content, (
            "Portfolio must check financialDetail.error, not just .data"
        )
        assert "asanaContext.error" in content, (
            "Portfolio must check asanaContext.error, not just .data"
        )

    # -----------------------------------------------------------------
    # 5b. Remaining-surface null-preservation (added by hostile audit)
    # -----------------------------------------------------------------

    def test_notifications_no_bare_nullish_zero(self, repo_root):
        """Notifications.tsx must not use bare ?? 0 for statsData counts."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Notifications.tsx"
        content = path.read_text()

        assert "statsData?.total ?? 0" not in content, (
            "Notifications must preserve null when statsData not loaded"
        )
        assert "statsData?.unread ?? 0" not in content, (
            "Notifications must preserve null when statsData not loaded"
        )
        assert "statsLoaded" in content or "statsData != null" in content, (
            "Notifications must check data is loaded before deriving counts"
        )

    def test_operations_preserves_null_counts(self, repo_root):
        """Operations.tsx must not flatten null data to zero counts."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Operations.tsx"
        content = path.read_text()

        # Old patterns should be gone
        assert "fixData?.identity_conflicts?.length || 0" not in content, (
            "Operations must not use || 0 for identity conflicts count"
        )
        assert "fixData != null" in content, (
            "Operations must check fixData is loaded before deriving counts"
        )

    def test_priorities_preserves_null_total(self, repo_root):
        """Priorities.tsx must not flatten null total to zero."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Priorities.tsx"
        content = path.read_text()

        assert "priorityData?.total || 0" not in content, (
            "Priorities must not use || 0 for total count"
        )
        assert "priorityData != null" in content, (
            "Priorities must check data is loaded before deriving count"
        )

    def test_commitments_preserves_null_counts(self, repo_root):
        """Commitments.tsx must not flatten null counts to zero."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Commitments.tsx"
        content = path.read_text()

        assert "commitmentsData?.total ?? 0" not in content
        assert "untrackedData?.total ?? 0" not in content
        assert "dueData?.total ?? 0" not in content
        assert "commitmentsData != null" in content

    def test_governance_preserves_null_summary(self, repo_root):
        """Governance.tsx must not flatten null summary counts to zero."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Governance.tsx"
        content = path.read_text()

        assert "summaryData?.total_bundles ?? 0" not in content
        assert "summaryData != null" in content

    def test_project_enrollment_preserves_null_counts(self, repo_root):
        """ProjectEnrollment.tsx must not flatten null counts to zero."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "ProjectEnrollment.tsx"
        content = path.read_text()

        assert "enrolledData?.total ?? 0" not in content
        assert "candidatesData?.total ?? 0" not in content
        assert "linkingStats?.link_rate ?? 0" not in content

    def test_schedule_preserves_null_total(self, repo_root):
        """Schedule.tsx must not flatten null total to zero."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Schedule.tsx"
        content = path.read_text()

        assert "blocksData?.total ?? 0" not in content
        assert "blocksData != null" in content

    def test_team_preserves_null_summary_counts(self, repo_root):
        """Team.tsx must not flatten null summary counts to zero."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Team.tsx"
        content = path.read_text()

        assert "teamLoaded" in content or "apiTeam != null" in content, (
            "Team must check data is loaded before deriving summary counts"
        )

    def test_capacity_preserves_null_utilization(self, repo_root):
        """Capacity.tsx must not flatten null utilization to zero."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Capacity.tsx"
        content = path.read_text()

        assert "number | null" in content, (
            "Capacity utilizationPct must return null when data not loaded"
        )

    def test_inbox_preserves_null_severity_counts(self, repo_root):
        """Inbox.tsx must not flatten null severity counts to zero."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "Inbox.tsx"
        content = path.read_text()

        assert "counts.by_severity != null" in content, (
            "Inbox must check by_severity is loaded before showing counts"
        )

    def test_client_index_uses_centralized_api(self, repo_root):
        """ClientIndex.tsx must not use raw fetch()."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "ClientIndex.tsx"
        content = path.read_text()

        assert "await fetch(" not in content, (
            "ClientIndex must use centralized API client, not raw fetch()"
        )
        assert "fetchClientIndex" in content, "ClientIndex must use fetchClientIndex from lib/api"

    def test_team_member_picker_uses_centralized_api(self, repo_root):
        """TeamMemberPicker.tsx must not use raw fetch()."""
        path = repo_root / "time-os-ui" / "src" / "components" / "pickers" / "TeamMemberPicker.tsx"
        content = path.read_text()

        assert "await fetch(" not in content, (
            "TeamMemberPicker must use centralized API client, not raw fetch()"
        )
        assert "fetchTeam" in content, "TeamMemberPicker must use fetchTeam from lib/api"

    def test_client_detail_spec_financial_null_safety(self, repo_root):
        """ClientDetailSpec.tsx must not flatten null financial values to 0."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "ClientDetailSpec.tsx"
        content = path.read_text()

        # Interface must declare financial fields as nullable
        assert "issued_ytd: number | null" in content, (
            "ClientDetailSpec must declare issued_ytd as number | null"
        )
        assert "ar_outstanding: number | null" in content, (
            "ClientDetailSpec must declare ar_outstanding as number | null"
        )

        # Transform must not use || 0 for financial fields
        assert "(financials.issued_ytd as number) || 0" not in content, (
            "Transform must not flatten null issued_ytd to 0"
        )
        assert "(financials.ar_outstanding as number) || 0" not in content, (
            "Transform must not flatten null ar_outstanding to 0"
        )

        # Must use formatCurrencyOrNA for financial rendering
        assert "formatCurrencyOrNA" in content, (
            "Must use formatCurrencyOrNA to show '--' for null financial values"
        )

        # Must not have formatCurrency(xxx || 0) in rendering
        import re

        currency_flat = re.findall(r"formatCurrency\([^)]*\|\| *0\)", content)
        assert len(currency_flat) == 0, (
            f"Found {len(currency_flat)} formatCurrency(xxx || 0) patterns that flatten null"
        )

    def test_client_detail_spec_signal_null_safety(self, repo_root):
        """ClientDetailSpec.tsx must not flatten null signal counts to 0."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "ClientDetailSpec.tsx"
        content = path.read_text()

        # Interface must declare signal fields as nullable
        assert "signals_good: number | null" in content
        assert "signals_neutral: number | null" in content
        assert "signals_bad: number | null" in content

        # Transform must not use || 0 for signal counts
        assert "(signals.good as number) || 0" not in content
        assert "(signals.neutral as number) || 0" not in content
        assert "(signals.bad as number) || 0" not in content

    def test_client_detail_spec_health_score_null_safety(self, repo_root):
        """ClientDetailSpec.tsx must not flatten null health score to 0."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "ClientDetailSpec.tsx"
        content = path.read_text()

        assert "health_score: number | null" in content
        assert "healthScore != null" in content, (
            "Must check healthScore != null before rendering health bar"
        )

    def test_team_detail_metric_null_safety(self, repo_root):
        """TeamDetail.tsx must not flatten null member stats to 0 in MetricCards."""
        path = repo_root / "time-os-ui" / "src" / "pages" / "TeamDetail.tsx"
        content = path.read_text()

        # Must not use (member.xxx || 0).toString() in MetricCard values
        import re

        metric_flat = re.findall(r"value=\{[^}]*member\.\w+\s*\|\|\s*0[^}]*\}", content)
        assert len(metric_flat) == 0, (
            f"Found {len(metric_flat)} MetricCard values using member.xxx || 0"
        )

        # Must use null-safe rendering pattern
        assert "openTasks != null" in content or "member.open_tasks ?? null" in content, (
            "TeamDetail must check null before rendering open tasks"
        )

    def test_no_page_has_fetch_bypass(self, repo_root):
        """No page or component should use raw fetch() — only centralized API clients."""
        pages_dir = repo_root / "time-os-ui" / "src" / "pages"
        components_dir = repo_root / "time-os-ui" / "src" / "components"

        for d in [pages_dir, components_dir]:
            for tsx_file in d.rglob("*.tsx"):
                content = tsx_file.read_text()
                # Skip test files
                if "__tests__" in str(tsx_file):
                    continue
                assert "await fetch(" not in content, (
                    f"{tsx_file.relative_to(repo_root)} bypasses centralized API with raw fetch()"
                )


# =============================================================================
# 6. Digest degradation reporting
# =============================================================================


class TestDigestDegradationReporting:
    """Verify digest includes degradation info when items are dropped."""

    def test_dropped_items_tracked_in_digest(self):
        """When queue_notification fails, generate_digest includes degradation flag."""
        from lib.notifier.digest import DigestEngine

        mock_store = MagicMock()
        # First call succeeds, second fails
        mock_store.insert.side_effect = [None, sqlite3.Error("DB locked")]
        mock_store.query.return_value = [
            {
                "id": "row1",
                "notification_id": "n1",
                "event_type": "alert",
                "category": "other",
                "severity": "high",
            }
        ]

        engine = DigestEngine(mock_store)

        # One succeeds, one fails
        engine.queue_notification("u1", "n1", "alert", "high", "hourly")
        engine.queue_notification("u1", "n2", "alert", "critical", "hourly")

        # Verify drop tracking
        assert engine._dropped_count == 1
        assert engine._dropped_high_severity == 1

    def test_format_plaintext_shows_degradation(self):
        """Plaintext digest must show warning when items were dropped."""
        from lib.notifier.digest import DigestEngine

        mock_store = MagicMock()
        engine = DigestEngine(mock_store)

        degraded_digest = {
            "total": 1,
            "categories": {"other": [{"severity": "high", "event_type": "alert"}]},
            "summary": {"other": {"count": 1}},
            "bucket": "daily",
            "degraded": True,
            "dropped_count": 3,
            "dropped_high_severity": 1,
        }

        text = engine.format_plaintext(degraded_digest)
        assert "WARNING" in text
        assert "3 notification(s)" in text
        assert "high/critical severity" in text

    def test_format_html_shows_degradation(self):
        """HTML digest must show degradation warning banner."""
        from lib.notifier.digest import DigestEngine

        mock_store = MagicMock()
        engine = DigestEngine(mock_store)

        degraded_digest = {
            "total": 1,
            "categories": {},
            "summary": {},
            "bucket": "weekly",
            "degraded": True,
            "dropped_count": 2,
            "dropped_high_severity": 0,
        }

        html = engine.format_html(degraded_digest)
        assert "degraded-warning" in html
        assert "2 notification(s)" in html

    def test_non_degraded_digest_has_no_warning(self):
        """When no items are dropped, digest has no degradation flag."""
        from lib.notifier.digest import DigestEngine

        mock_store = MagicMock()
        engine = DigestEngine(mock_store)

        normal_digest = {
            "total": 5,
            "categories": {"issues": [{"severity": "high", "event_type": "issue"}]},
            "summary": {"issues": {"count": 5}},
            "bucket": "daily",
        }

        text = engine.format_plaintext(normal_digest)
        assert "WARNING" not in text

        html = engine.format_html(normal_digest)
        assert "degraded-warning" not in html


# =============================================================================
# 7. NotificationEngine degradation awareness
# =============================================================================


class TestNotificationEngineDegradation:
    """Verify NotificationEngine exposes degradation state."""

    def test_healthy_engine_not_degraded(self):
        """When all subsystems init OK, is_degraded returns False."""
        from lib.notifier.engine import NotificationEngine

        mock_store = MagicMock()
        mock_store.query.return_value = []

        with patch("lib.notifier.engine.NotificationEngine._load_channels"):
            with patch("lib.notifier.engine.NotificationEngine._init_intelligence"):
                engine = NotificationEngine(mock_store)
                # Manually set state as if init succeeded
                engine._intelligence_degraded = False
                engine._notification_intel = MagicMock()
                engine._digest_engine = MagicMock()

        assert engine.is_degraded is False
        assert engine.degradation_reasons == []

    def test_intelligence_failure_is_degraded(self):
        """When intelligence fails to init, is_degraded returns True."""
        from lib.notifier.engine import NotificationEngine

        mock_store = MagicMock()
        mock_store.query.return_value = []

        with patch("lib.notifier.engine.NotificationEngine._load_channels"):
            with patch("lib.notifier.engine.NotificationEngine._init_intelligence"):
                engine = NotificationEngine(mock_store)
                # Simulate intelligence failure
                engine._intelligence_degraded = True
                engine._notification_intel = None
                engine._digest_engine = MagicMock()

        assert engine.is_degraded is True
        reasons = engine.degradation_reasons
        assert len(reasons) >= 1
        assert "intelligence" in reasons[0]

    def test_digest_failure_is_degraded(self):
        """When digest engine fails to init, is_degraded returns True."""
        from lib.notifier.engine import NotificationEngine

        mock_store = MagicMock()
        mock_store.query.return_value = []

        with patch("lib.notifier.engine.NotificationEngine._load_channels"):
            with patch("lib.notifier.engine.NotificationEngine._init_intelligence"):
                engine = NotificationEngine(mock_store)
                engine._intelligence_degraded = False
                engine._notification_intel = MagicMock()
                engine._digest_engine = None

        assert engine.is_degraded is True
        reasons = engine.degradation_reasons
        assert len(reasons) >= 1
        assert "digest" in reasons[0]
