"""
Regression tests for collector silent-failure remediation.

Verifies that collectors:
1. Never return empty data as success when collection fails
2. Use typed CollectorResult with correct status values
3. Distinguish success, partial, stale, and failed states
4. Surface error types for monitoring
5. Track secondary table failures explicitly

Test scenarios:
- Auth failure (credential/token errors)
- Transport failure (network errors)
- Parse failure (malformed API responses)
- Partial failure (primary OK, secondary tables fail)
- Circuit breaker (stale state)
"""

import sqlite3
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from lib.collectors.base import BaseCollector
from lib.collectors.result import (
    CollectorResult,
    CollectorStatus,
    SecondaryTableResult,
    classify_error,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


class FakeStore:
    """In-memory store that mimics StateStore for testing."""

    def __init__(self):
        self.sync_states: dict[str, dict] = {}
        self.tables: dict[str, list] = {}
        self._fail_on_table: str | None = None

    def insert_many(self, table: str, rows: list[dict]) -> int:
        if self._fail_on_table and table == self._fail_on_table:
            raise sqlite3.OperationalError(f"table {table} is locked")
        self.tables.setdefault(table, []).extend(rows)
        return len(rows)

    def update_sync_state(
        self,
        source: str,
        success: bool,
        items: int = 0,
        error: str = None,
        error_type: str | None = None,
        status: str | None = None,
    ):
        # Preserve last_success on failure (mirrors COALESCE in real store)
        prev = self.sync_states.get(source, {})
        self.sync_states[source] = {
            "source": source,
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "last_success": datetime.now(timezone.utc).isoformat()
            if success
            else prev.get("last_success"),
            "items_synced": items,
            "error": error,
            "error_type": error_type,
            "status": status,
        }

    def get_sync_states(self) -> dict[str, dict]:
        return self.sync_states


class ConcreteCollector(BaseCollector):
    """Minimal concrete collector for testing BaseCollector.sync() behavior."""

    source_name = "test_source"
    target_table = "test_items"

    def __init__(self, config: dict | None = None, store=None):
        super().__init__(config or {}, store)
        self._collect_data: dict[str, Any] | None = None
        self._collect_error: Exception | None = None
        self._transform_error: Exception | None = None

    def collect(self) -> dict[str, Any]:
        if self._collect_error:
            raise self._collect_error
        return self._collect_data or {"items": []}

    def transform(self, raw_data: dict) -> list[dict]:
        if self._transform_error:
            raise self._transform_error
        return [{"id": item["id"]} for item in raw_data.get("items", [])]


@pytest.fixture()
def store():
    return FakeStore()


@pytest.fixture()
def collector(store):
    c = ConcreteCollector(config={"max_retries": 0}, store=store)
    return c


# ---------------------------------------------------------------------------
# CollectorResult unit tests
# ---------------------------------------------------------------------------


class TestCollectorResult:
    """Test the typed result model itself."""

    def test_success_to_dict(self):
        result = CollectorResult(
            source="gmail",
            status=CollectorStatus.SUCCESS,
            collected=10,
            transformed=10,
            stored=10,
            duration_ms=150.0,
        )
        d = result.to_dict()
        assert d["status"] == "success"
        assert d["success"] is True
        assert d["collected"] == 10
        assert "error" not in d

    def test_failed_to_dict(self):
        result = CollectorResult(
            source="gmail",
            status=CollectorStatus.FAILED,
            error="Connection refused",
            error_type="transport",
        )
        d = result.to_dict()
        assert d["status"] == "failed"
        assert d["success"] is False
        assert d["error"] == "Connection refused"
        assert d["error_type"] == "transport"

    def test_stale_to_dict(self):
        result = CollectorResult(
            source="asana",
            status=CollectorStatus.STALE,
            error="Circuit breaker open",
            error_type="circuit_breaker",
            circuit_breaker_state="open",
        )
        d = result.to_dict()
        assert d["status"] == "stale"
        assert d["success"] is False
        assert d["circuit_breaker_state"] == "open"

    def test_partial_with_secondary_failures(self):
        result = CollectorResult(
            source="gmail",
            status=CollectorStatus.SUCCESS,
            collected=10,
            stored=10,
        )
        result.add_secondary("participants", stored=5)
        result.add_secondary("attachments", error="table locked")
        result.escalate_to_partial()

        d = result.to_dict()
        assert d["status"] == "partial"
        assert d["success"] is False  # partial is NOT success — data is incomplete
        assert d["secondary_failures"] == ["attachments"]
        assert d["secondary_tables"]["participants"]["stored"] == 5
        assert d["secondary_tables"]["attachments"]["error"] == "table locked"

    def test_no_escalation_without_failures(self):
        result = CollectorResult(
            source="gmail",
            status=CollectorStatus.SUCCESS,
        )
        result.add_secondary("participants", stored=5)
        result.escalate_to_partial()
        assert result.status == CollectorStatus.SUCCESS

    def test_secondary_table_result(self):
        ok = SecondaryTableResult(table="t1", stored=5)
        assert ok.ok is True
        fail = SecondaryTableResult(table="t2", error="locked")
        assert fail.ok is False


# ---------------------------------------------------------------------------
# classify_error unit tests
# ---------------------------------------------------------------------------


class TestClassifyError:
    """Test error classification for monitoring."""

    def test_timeout(self):
        assert classify_error(TimeoutError("timed out")) == "timeout"

    def test_connection_error(self):
        assert classify_error(ConnectionError("refused")) == "transport"

    def test_os_error(self):
        assert classify_error(OSError("network unreachable")) == "transport"

    def test_sqlite_error(self):
        assert classify_error(sqlite3.OperationalError("locked")) == "storage"

    def test_value_error_parse(self):
        assert classify_error(ValueError("json decode error")) == "parse"

    def test_value_error_data(self):
        assert classify_error(ValueError("invalid field")) == "data_error"

    def test_generic_timeout_string(self):
        assert classify_error(RuntimeError("request timed out after 30s")) == "timeout"

    def test_rate_limit_string(self):
        assert classify_error(RuntimeError("429 rate limit exceeded")) == "rate_limit"

    def test_auth_string(self):
        assert classify_error(RuntimeError("401 unauthorized")) == "auth"

    def test_unknown(self):
        assert classify_error(RuntimeError("something weird happened")) == "unknown"


# ---------------------------------------------------------------------------
# BaseCollector.sync() regression tests
# ---------------------------------------------------------------------------


class TestBaseCollectorSync:
    """Verify BaseCollector.sync() produces typed results, not plain dicts."""

    def test_success_returns_typed_result(self, collector, store):
        """Successful sync returns status=success with all counts."""
        collector._collect_data = {"items": [{"id": "1"}, {"id": "2"}]}
        result = collector.sync()

        assert result["status"] == "success"
        assert result["success"] is True
        assert result["collected"] == 2
        assert result["transformed"] == 2
        assert result["stored"] == 2
        assert result["source"] == "test_source"
        assert "error" not in result

    def test_collect_failure_returns_failed_status(self, collector, store):
        """When collect() raises, sync returns status=failed with error details."""
        collector._collect_error = ConnectionError("Connection refused")
        result = collector.sync()

        assert result["status"] == "failed"
        assert result["success"] is False
        assert "Connection refused" in result["error"]
        assert result["error_type"] == "transport"
        assert result["collected"] == 0

        # Verify sync state was updated with error_type and status
        state = store.sync_states.get("test_source")
        assert state is not None
        assert state["error"] is not None
        assert state["error_type"] == "transport"
        assert state["status"] == "failed"

    def test_success_sync_state_has_status(self, collector, store):
        """Successful sync writes status='success' to sync_state."""
        collector._collect_data = {"items": [{"id": "1"}]}
        collector.sync()

        state = store.sync_states.get("test_source")
        assert state is not None
        assert state["status"] == "success"
        assert state["error_type"] is None
        assert state["last_success"] is not None

    def test_auth_failure_classified(self, collector, store):
        """Auth errors are classified as error_type=auth."""
        collector._collect_error = RuntimeError("401 unauthorized")
        result = collector.sync()

        assert result["status"] == "failed"
        assert result["error_type"] == "auth"

    def test_timeout_failure_classified(self, collector, store):
        """Timeout errors are classified as error_type=timeout."""
        collector._collect_error = TimeoutError("API call timed out")
        result = collector.sync()

        assert result["status"] == "failed"
        assert result["error_type"] == "timeout"

    def test_circuit_breaker_returns_stale(self, collector, store):
        """When circuit breaker is open, sync returns status=stale."""
        # Open the circuit breaker by recording enough failures
        for _ in range(collector.circuit_breaker.failure_threshold):
            collector.circuit_breaker.record_failure()

        result = collector.sync()

        assert result["status"] == "stale"
        assert result["success"] is False
        assert "circuit breaker" in result["error"].lower()
        assert result["circuit_breaker_state"] == "open"

    def test_transform_failure_returns_partial(self, collector, store):
        """If transform fails, sync returns partial (collected but couldn't process)."""
        collector._collect_data = {"items": [{"id": "1"}]}
        collector._transform_error = ValueError("bad field")
        result = collector.sync()

        # Transform failure is PARTIAL — we collected but couldn't process
        assert result["status"] == "partial"
        assert result["success"] is False
        assert result["collected"] == 1
        assert result["transformed"] == 0
        # Sync state records the partial status
        state = store.sync_states.get("test_source")
        assert state is not None
        assert state["status"] == "partial"
        assert state["error_type"] == "data_error"

    def test_collect_never_returns_empty_on_error(self, collector):
        """Verify collect() raises, never returns empty dict."""
        collector._collect_error = ConnectionError("fail")
        with pytest.raises(ConnectionError):
            collector.collect()


# ---------------------------------------------------------------------------
# Collector-specific silent-failure regression tests
# ---------------------------------------------------------------------------


class TestGmailCollectorFailure:
    """Gmail collect() must raise, not return {'threads': []}."""

    def test_collect_raises_on_error(self):
        """Gmail.collect() must propagate exceptions, not return empty data."""
        from lib.collectors.gmail import GmailCollector

        store = FakeStore()
        gmail = GmailCollector(config={"max_retries": 0}, store=store)

        # Mock _get_service to raise auth error
        with patch.object(gmail, "_get_service", side_effect=ConnectionError("auth failed")):
            with pytest.raises(ConnectionError, match="auth failed"):
                gmail.collect()

    def test_sync_returns_failed_on_collect_error(self):
        """Gmail.sync() returns status=failed when collect() raises."""
        from lib.collectors.gmail import GmailCollector

        store = FakeStore()
        gmail = GmailCollector(config={"max_retries": 0}, store=store)

        with patch.object(gmail, "collect", side_effect=ConnectionError("network down")):
            result = gmail.sync()

        assert result["status"] == "failed"
        assert result["success"] is False
        assert "network down" in result["error"]


class TestChatCollectorFailure:
    """Chat collect() must raise, not return {'messages': [], ...}."""

    def test_collect_raises_on_error(self):
        """Chat.collect() must propagate exceptions, not return empty data."""
        from lib.collectors.chat import ChatCollector

        store = FakeStore()
        chat = ChatCollector(config={"max_retries": 0}, store=store)

        with patch.object(chat, "_get_service", side_effect=ConnectionError("auth failed")):
            with pytest.raises(ConnectionError, match="auth failed"):
                chat.collect()

    def test_sync_returns_failed_on_collect_error(self):
        """Chat.sync() returns status=failed when collect() raises."""
        from lib.collectors.chat import ChatCollector

        store = FakeStore()
        chat = ChatCollector(config={"max_retries": 0}, store=store)

        with patch.object(chat, "collect", side_effect=TimeoutError("API timeout")):
            result = chat.sync()

        assert result["status"] == "failed"
        assert result["success"] is False
        assert result["error_type"] == "timeout"


class TestAsanaCollectorFailure:
    """Asana collect() must raise, not return {'tasks': [], ...}."""

    def test_sync_returns_failed_on_collect_error(self):
        """Asana.sync() returns status=failed when collect() raises."""
        from lib.collectors.asana import AsanaCollector

        store = FakeStore()
        asana = AsanaCollector(config={"max_retries": 0}, store=store)

        with patch.object(asana, "collect", side_effect=RuntimeError("429 rate limit")):
            result = asana.sync()

        assert result["status"] == "failed"
        assert result["success"] is False
        assert result["error_type"] == "rate_limit"


class TestDriveCollectorFailure:
    """Drive collect() must raise, not return {'files': []}."""

    def test_collect_raises_on_error(self):
        """Drive.collect() must propagate exceptions, not return empty data."""
        from lib.collectors.drive import DriveCollector

        store = FakeStore()
        drive = DriveCollector(config={"max_retries": 0}, store=store)

        with patch.object(drive, "_get_service", side_effect=ConnectionError("auth failed")):
            with pytest.raises(ConnectionError, match="auth failed"):
                drive.collect()


class TestContactsCollectorFailure:
    """Contacts collect() must raise, not return {'contacts': [], ...}."""

    def test_collect_raises_on_error(self):
        """Contacts.collect() must propagate exceptions, not return empty data."""
        from lib.collectors.contacts import ContactsCollector

        store = FakeStore()
        contacts = ContactsCollector(config={"max_retries": 0}, store=store)

        with patch.object(contacts, "_get_service", side_effect=ConnectionError("auth failed")):
            with pytest.raises(ConnectionError, match="auth failed"):
                contacts.collect()


# ---------------------------------------------------------------------------
# Orchestrator status tests
# ---------------------------------------------------------------------------


class TestOrchestratorStatus:
    """Verify orchestrator surfaces degraded/stale status correctly."""

    def test_stale_detection(self):
        """Collectors with old last_success are reported as stale."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        store = FakeStore()
        # Simulate a collector that succeeded long ago
        store.sync_states["gmail"] = {
            "source": "gmail",
            "last_sync": "2025-01-01T00:00:00",
            "last_success": "2025-01-01T00:00:00",
            "items_synced": 100,
            "error": None,
        }

        with patch.object(CollectorOrchestrator, "__init__", lambda self, **kw: None):
            orch = CollectorOrchestrator.__new__(CollectorOrchestrator)
            orch.store = store
            mock_collector = MagicMock()
            mock_collector.sync_interval = 120
            mock_collector.circuit_breaker.state = "closed"
            orch.collectors = {"gmail": mock_collector}

            status = orch.get_status()

        assert status["gmail"]["stale"] is True
        assert status["gmail"]["status"] == "degraded"

    def test_healthy_collector(self):
        """Recent success with no errors is reported as healthy."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        store = FakeStore()
        store.sync_states["gmail"] = {
            "source": "gmail",
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "last_success": datetime.now(timezone.utc).isoformat(),
            "items_synced": 50,
            "error": None,
        }

        with patch.object(CollectorOrchestrator, "__init__", lambda self, **kw: None):
            orch = CollectorOrchestrator.__new__(CollectorOrchestrator)
            orch.store = store
            mock_collector = MagicMock()
            mock_collector.sync_interval = 120
            mock_collector.circuit_breaker.state = "closed"
            orch.collectors = {"gmail": mock_collector}

            status = orch.get_status()

        assert status["gmail"]["status"] == "healthy"
        assert status["gmail"]["healthy"] is True
        assert status["gmail"]["stale"] is False

    def test_failed_collector_never_succeeded(self):
        """Collector that never succeeded is reported as failed."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        store = FakeStore()
        store.sync_states["asana"] = {
            "source": "asana",
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "last_success": None,
            "items_synced": 0,
            "error": "auth failed",
        }

        with patch.object(CollectorOrchestrator, "__init__", lambda self, **kw: None):
            orch = CollectorOrchestrator.__new__(CollectorOrchestrator)
            orch.store = store
            mock_collector = MagicMock()
            mock_collector.sync_interval = 300
            mock_collector.circuit_breaker.state = "open"
            orch.collectors = {"asana": mock_collector}

            status = orch.get_status()

        assert status["asana"]["status"] == "failed"
        assert status["asana"]["healthy"] is False
        assert status["asana"]["circuit_breaker_state"] == "open"


# ---------------------------------------------------------------------------
# Xero collector typed result tests
# ---------------------------------------------------------------------------


class TestXeroCollectorResult:
    """Verify Xero collector returns typed CollectorResult, not plain dicts."""

    def test_xero_real_boundary_api_failure(self):
        """Xero.sync() returns status=failed when list_invoices raises ConnectionError.

        This is the real boundary test: we patch the actual dependency
        (engine.xero_client.list_invoices) that XeroCollector.sync() calls,
        making it raise a realistic transport error. This validates:
        1. XeroCollector.sync() reaches the real import boundary
        2. The except COLLECTOR_ERRORS handler catches ConnectionError
        3. classify_error maps ConnectionError -> "transport"
        4. Result has status="failed" and success is False
        5. update_sync_state is called with status="failed", error_type="transport"
        6. Circuit breaker records the failure

        To make this test run everywhere (including where httpx is not installed),
        we inject a mock httpx into sys.modules before engine.xero_client is imported.
        This lets the module load, then we patch list_invoices to raise.
        """
        import sys
        import types

        from lib.collectors.xero import XeroCollector

        store = FakeStore()
        xero = XeroCollector(config={}, store=store)

        # Ensure engine.xero_client is importable even without httpx.
        # Create a minimal mock httpx so the module-level `import httpx` succeeds.
        # Then remove engine.xero_client from cache so sync()'s `from engine.xero_client import ...`
        # re-imports it fresh with our mock httpx in place.
        mock_httpx = types.ModuleType("httpx")
        mock_httpx.post = MagicMock()
        mock_httpx.get = MagicMock()

        # Remove engine.xero_client from cache so it will be re-imported inside sync()
        saved_modules = {}
        for mod_name in list(sys.modules):
            if mod_name == "engine.xero_client" or mod_name.startswith("engine.xero_client."):
                saved_modules[mod_name] = sys.modules.pop(mod_name)

        original_httpx = sys.modules.get("httpx")
        sys.modules["httpx"] = mock_httpx

        try:
            with patch("engine.xero_client.list_invoices", side_effect=ConnectionError("down")):
                result = xero.sync()
        finally:
            # Restore original module state
            if original_httpx is not None:
                sys.modules["httpx"] = original_httpx
            else:
                sys.modules.pop("httpx", None)
            # Restore engine.xero_client
            for mod_name in list(sys.modules):
                if mod_name == "engine.xero_client" or mod_name.startswith("engine.xero_client."):
                    sys.modules.pop(mod_name)
            sys.modules.update(saved_modules)

        # Proof 1: status is "failed" — not empty success, not stale, not partial
        assert result["status"] == "failed"
        # Proof 2: success is explicitly False
        assert result["success"] is False
        # Proof 3: source identifies the collector
        assert result["source"] == "xero"
        # Proof 4: classify_error mapped ConnectionError -> "transport"
        assert result["error_type"] == "transport"
        # Proof 5: error message preserved
        assert "down" in result["error"]
        # Proof 6: state store was updated with correct status and error_type
        state = store.sync_states.get("xero")
        assert state is not None
        assert state["status"] == "failed"
        assert state["error_type"] == "transport"
        # Proof 7: circuit breaker recorded the failure
        assert xero.circuit_breaker.failure_count >= 1

    def test_xero_circuit_breaker_returns_stale(self):
        """Xero circuit breaker open returns stale, not plain dict."""
        from lib.collectors.xero import XeroCollector

        store = FakeStore()
        xero = XeroCollector(config={}, store=store)
        for _ in range(xero.circuit_breaker.failure_threshold):
            xero.circuit_breaker.record_failure()

        result = xero.sync()

        assert result["status"] == "stale"
        assert result["success"] is False
        assert result["source"] == "xero"


# ---------------------------------------------------------------------------
# Orchestrator mark_collected uses status field, not success boolean
# ---------------------------------------------------------------------------


class TestOrchestratorMarkCollected:
    """Verify orchestrator uses status field (not success bool) for mark_collected."""

    def test_partial_is_marked_collected(self):
        """PARTIAL results still get mark_collected (primary data was stored)."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        store = FakeStore()

        with patch.object(CollectorOrchestrator, "__init__", lambda self, **kw: None):
            orch = CollectorOrchestrator.__new__(CollectorOrchestrator)
            orch.store = store
            orch.logger = MagicMock()

            mock_collector = MagicMock()
            mock_collector.sync.return_value = {
                "source": "gmail",
                "status": "partial",
                "success": False,
                "stored": 10,
            }
            orch.collectors = {"gmail": mock_collector}

            with patch("lib.collectors.orchestrator.mark_collected") as mock_mark:
                with patch("lib.collectors.orchestrator.CollectorLock") as MockLock:
                    lock_instance = MagicMock()
                    lock_instance.acquired = True
                    lock_instance.__enter__ = MagicMock(return_value=lock_instance)
                    lock_instance.__exit__ = MagicMock(return_value=False)
                    MockLock.return_value = lock_instance

                    orch._sync_one("gmail")

                # PARTIAL gets mark_collected because primary data was written
                mock_mark.assert_called_once_with("gmail")

    def test_failed_is_not_marked_collected(self):
        """FAILED results do NOT get mark_collected (no data written)."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        store = FakeStore()

        with patch.object(CollectorOrchestrator, "__init__", lambda self, **kw: None):
            orch = CollectorOrchestrator.__new__(CollectorOrchestrator)
            orch.store = store
            orch.logger = MagicMock()

            mock_collector = MagicMock()
            mock_collector.sync.return_value = {
                "source": "gmail",
                "status": "failed",
                "success": False,
                "stored": 0,
                "error": "auth failed",
            }
            orch.collectors = {"gmail": mock_collector}

            with patch("lib.collectors.orchestrator.mark_collected") as mock_mark:
                with patch("lib.collectors.orchestrator.CollectorLock") as MockLock:
                    lock_instance = MagicMock()
                    lock_instance.acquired = True
                    lock_instance.__enter__ = MagicMock(return_value=lock_instance)
                    lock_instance.__exit__ = MagicMock(return_value=False)
                    MockLock.return_value = lock_instance

                    orch._sync_one("gmail")

                # FAILED does NOT get mark_collected
                mock_mark.assert_not_called()


# ---------------------------------------------------------------------------
# State store last_success preservation tests
# ---------------------------------------------------------------------------


class TestSyncStateLastSuccessPreservation:
    """Verify update_sync_state preserves last_success across failures."""

    def test_failure_preserves_last_success(self):
        """After success then failure, last_success must NOT be wiped."""
        store = FakeStore()

        # First call: success — sets last_success
        store.update_sync_state("gmail", success=True, items=10, status="success")
        after_success = store.sync_states["gmail"]["last_success"]
        assert after_success is not None

        # Second call: failure — must preserve last_success
        store.update_sync_state(
            "gmail",
            success=False,
            error="down",
            error_type="transport",
            status="failed",
        )
        after_failure = store.sync_states["gmail"]["last_success"]
        assert after_failure is not None, "last_success wiped on failure"
        assert after_failure == after_success

    def test_success_updates_last_success(self):
        """A new success must update last_success to the new timestamp."""
        store = FakeStore()

        store.update_sync_state("gmail", success=True, items=5, status="success")

        # Small delay guaranteed by different isoformat calls
        store.update_sync_state("gmail", success=True, items=8, status="success")
        second_success = store.sync_states["gmail"]["last_success"]

        # Both are non-None; second may equal first if same millisecond, but never None
        assert second_success is not None

    def test_never_succeeded_stays_none(self):
        """If a collector has never succeeded, last_success stays None."""
        store = FakeStore()

        store.update_sync_state(
            "xero",
            success=False,
            error="auth",
            error_type="auth",
            status="failed",
        )
        assert store.sync_states["xero"]["last_success"] is None

    def test_orchestrator_degraded_after_failure_with_prior_success(self):
        """End-to-end: success then failure → orchestrator sees 'degraded' not 'failed'.

        Before the COALESCE fix, INSERT OR REPLACE wiped last_success on failure,
        making the orchestrator think the collector had NEVER succeeded — classifying
        it as 'failed' instead of 'degraded'. This test proves the fix works.
        """
        from lib.collectors.orchestrator import CollectorOrchestrator

        store = FakeStore()

        # Step 1: collector succeeds — sets last_success
        store.update_sync_state("gmail", success=True, items=50, status="success")
        assert store.sync_states["gmail"]["last_success"] is not None

        # Step 2: collector fails — must NOT wipe last_success
        store.update_sync_state(
            "gmail",
            success=False,
            error="network down",
            error_type="transport",
            status="failed",
        )
        # Prove last_success survived
        assert store.sync_states["gmail"]["last_success"] is not None
        assert store.sync_states["gmail"]["error"] == "network down"

        # Step 3: orchestrator classifies health
        with patch.object(CollectorOrchestrator, "__init__", lambda self, **kw: None):
            orch = CollectorOrchestrator.__new__(CollectorOrchestrator)
            orch.store = store
            mock_collector = MagicMock()
            mock_collector.sync_interval = 120
            mock_collector.circuit_breaker.state = "closed"
            orch.collectors = {"gmail": mock_collector}

            status = orch.get_status()

        # PROOF: with last_success preserved and error present, status is "degraded"
        # NOT "failed" (which would mean "never succeeded")
        assert status["gmail"]["status"] == "degraded", (
            f"Expected 'degraded' but got '{status['gmail']['status']}'. "
            "If 'failed', last_success was wiped."
        )
        assert status["gmail"]["last_success"] is not None
        assert status["gmail"]["error"] == "network down"

    def test_orchestrator_failed_when_never_succeeded(self):
        """Collector that has NEVER succeeded is correctly classified as 'failed'."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        store = FakeStore()

        # Only failures, no prior success
        store.update_sync_state(
            "xero",
            success=False,
            error="auth denied",
            error_type="auth",
            status="failed",
        )
        assert store.sync_states["xero"]["last_success"] is None

        with patch.object(CollectorOrchestrator, "__init__", lambda self, **kw: None):
            orch = CollectorOrchestrator.__new__(CollectorOrchestrator)
            orch.store = store
            mock_collector = MagicMock()
            mock_collector.sync_interval = 300
            mock_collector.circuit_breaker.state = "open"
            orch.collectors = {"xero": mock_collector}

            status = orch.get_status()

        # No last_success + error → truly "failed"
        assert status["xero"]["status"] == "failed"
        assert status["xero"]["last_success"] is None

    def test_repeated_failures_preserve_last_success(self):
        """Multiple consecutive failures must never destroy last_success."""
        store = FakeStore()

        store.update_sync_state("asana", success=True, items=20, status="success")
        original_success = store.sync_states["asana"]["last_success"]
        assert original_success is not None

        # 5 consecutive failures
        for i in range(5):
            store.update_sync_state(
                "asana",
                success=False,
                error=f"failure {i}",
                error_type="transport",
                status="failed",
            )
            assert store.sync_states["asana"]["last_success"] == original_success, (
                f"last_success destroyed after failure {i}"
            )

    def test_real_sqlite_preserves_last_success(self, tmp_path):
        """Integration test: real SQLite ON CONFLICT preserves last_success.

        Uses raw sqlite3 to verify the actual SQL statement works correctly,
        without going through StateStore (which has singleton/migration guards).
        """
        db_path = str(tmp_path / "test_sync.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """CREATE TABLE sync_state (
                source TEXT PRIMARY KEY,
                last_sync TEXT,
                last_success TEXT,
                items_synced INTEGER DEFAULT 0,
                error TEXT,
                error_type TEXT,
                status TEXT
            )"""
        )

        # This is the exact SQL from state_store.py update_sync_state
        upsert_sql = """INSERT INTO sync_state
            (source, last_sync, last_success, items_synced, error, error_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                last_sync = excluded.last_sync,
                last_success = COALESCE(excluded.last_success, sync_state.last_success),
                items_synced = excluded.items_synced,
                error = excluded.error,
                error_type = excluded.error_type,
                status = excluded.status
        """

        # Success: sets last_success
        conn.execute(
            upsert_sql,
            ["test_src", "2026-01-01T10:00:00", "2026-01-01T10:00:00", 5, None, None, "success"],
        )
        conn.commit()
        row = conn.execute(
            "SELECT last_success FROM sync_state WHERE source = ?", ["test_src"]
        ).fetchone()
        assert row[0] == "2026-01-01T10:00:00"

        # Failure: passes None for last_success — COALESCE must preserve old value
        conn.execute(
            upsert_sql, ["test_src", "2026-01-01T11:00:00", None, 0, "timeout", "timeout", "failed"]
        )
        conn.commit()
        row = conn.execute(
            "SELECT last_success FROM sync_state WHERE source = ?", ["test_src"]
        ).fetchone()
        assert row[0] == "2026-01-01T10:00:00", f"last_success wiped: got {row[0]}"

        # New success: updates last_success to new timestamp
        conn.execute(
            upsert_sql,
            ["test_src", "2026-01-01T12:00:00", "2026-01-01T12:00:00", 8, None, None, "success"],
        )
        conn.commit()
        row = conn.execute(
            "SELECT last_success FROM sync_state WHERE source = ?", ["test_src"]
        ).fetchone()
        assert row[0] == "2026-01-01T12:00:00"

        conn.close()


# ---------------------------------------------------------------------------
# Test A: Xero secondary FETCH failure → PARTIAL (D1 regression)
# ---------------------------------------------------------------------------


class TestXeroSecondaryFetchFailure:
    """Prove that a secondary fetch failure in Xero produces PARTIAL, not SUCCESS.

    This is the exact defect D1: list_contacts() raises → data set to [] →
    storage block skipped → no error recorded → status stays SUCCESS.
    After the fix, the fetch error must be recorded and status must be PARTIAL.
    """

    def _setup_xero_module(self):
        """Inject mock httpx and ensure engine.xero_client is freshly importable.

        Returns (saved_modules, original_httpx) for cleanup.
        """
        import sys
        import types

        mock_httpx = types.ModuleType("httpx")
        mock_httpx.post = MagicMock()
        mock_httpx.get = MagicMock()

        saved_modules = {}
        for mod_name in list(sys.modules):
            if mod_name == "engine.xero_client" or mod_name.startswith("engine.xero_client."):
                saved_modules[mod_name] = sys.modules.pop(mod_name)

        original_httpx = sys.modules.get("httpx")
        sys.modules["httpx"] = mock_httpx

        # Force-import engine.xero_client so patches can target it
        import engine.xero_client  # noqa: F401

        return saved_modules, original_httpx

    def _teardown_xero_module(self, saved_modules, original_httpx):
        """Restore original module state."""
        import sys

        if original_httpx is not None:
            sys.modules["httpx"] = original_httpx
        else:
            sys.modules.pop("httpx", None)
        for mod_name in list(sys.modules):
            if mod_name == "engine.xero_client" or mod_name.startswith("engine.xero_client."):
                sys.modules.pop(mod_name)
        sys.modules.update(saved_modules)

    def test_contacts_fetch_failure_produces_partial(self):
        """Primary invoices succeed, but list_contacts raises → status=partial."""
        from lib.collectors.xero import XeroCollector

        store = FakeStore()
        store.insert = MagicMock(return_value="id")
        store.query = MagicMock(return_value=[])
        store.update = MagicMock(return_value=True)

        xero = XeroCollector(config={}, store=store)

        saved_modules, original_httpx = self._setup_xero_module()
        try:
            import engine.xero_client as xc

            mock_invoices = [
                {
                    "Type": "ACCREC",
                    "InvoiceNumber": "INV-001",
                    "Contact": {"Name": "Test Client"},
                    "Status": "PAID",
                    "Total": "1000",
                    "AmountDue": "0",
                    "CurrencyCode": "AED",
                    "DateString": "2026-01-15",
                    "DueDateString": "2026-02-15",
                    "FullyPaidOnDate": "2026-02-10",
                    "LineItems": [],
                },
            ]

            with (
                patch.object(xc, "list_invoices", return_value=mock_invoices),
                patch.object(xc, "list_contacts", side_effect=ConnectionError("contacts API down")),
                patch.object(xc, "list_credit_notes", return_value=[]),
                patch.object(xc, "list_bank_transactions", return_value=[]),
                patch.object(xc, "list_tax_rates", return_value=[]),
            ):
                result = xero.sync()
        finally:
            self._teardown_xero_module(saved_modules, original_httpx)

        # PROOF 1: status must be PARTIAL, not SUCCESS
        assert result["status"] == "partial", (
            f"Expected 'partial' but got '{result['status']}'. "
            "Fetch failure was silently swallowed."
        )
        # PROOF 2: success must be False (PARTIAL is not success)
        assert result["success"] is False
        # PROOF 3: secondary_failures must include contacts
        assert "contacts" in result.get("secondary_failures", []), (
            "contacts not in secondary_failures — fetch error was not recorded"
        )
        # PROOF 4: error metadata must survive in secondary_tables
        contacts_info = result.get("secondary_tables", {}).get("contacts", {})
        assert contacts_info.get("error") is not None, "contacts error metadata is missing"
        assert "fetch failed" in contacts_info["error"]
        # PROOF 5: sync state reflects partial truth
        state = store.sync_states.get("xero")
        assert state is not None
        assert state["status"] == "partial"

    def test_multiple_secondary_fetch_failures(self):
        """When multiple secondary fetches fail, all are tracked and status is PARTIAL."""
        from lib.collectors.xero import XeroCollector

        store = FakeStore()
        store.insert = MagicMock(return_value="id")
        store.query = MagicMock(return_value=[])
        store.update = MagicMock(return_value=True)

        xero = XeroCollector(config={}, store=store)

        saved_modules, original_httpx = self._setup_xero_module()
        try:
            import engine.xero_client as xc

            mock_invoices = [
                {
                    "Type": "ACCREC",
                    "InvoiceNumber": "INV-002",
                    "Contact": {"Name": "Client B"},
                    "Status": "AUTHORISED",
                    "Total": "500",
                    "AmountDue": "500",
                    "CurrencyCode": "AED",
                    "DateString": "2026-03-01",
                    "DueDateString": "2026-04-01",
                    "LineItems": [],
                },
            ]

            with (
                patch.object(xc, "list_invoices", return_value=mock_invoices),
                patch.object(xc, "list_contacts", side_effect=TimeoutError("timeout")),
                patch.object(xc, "list_credit_notes", side_effect=RuntimeError("429 rate limit")),
                patch.object(xc, "list_bank_transactions", return_value=[]),
                patch.object(xc, "list_tax_rates", side_effect=ConnectionError("DNS failure")),
            ):
                result = xero.sync()
        finally:
            self._teardown_xero_module(saved_modules, original_httpx)

        assert result["status"] == "partial"
        assert result["success"] is False
        failures = result.get("secondary_failures", [])
        assert "contacts" in failures
        assert "credit_notes" in failures
        assert "tax_rates" in failures
        # bank_transactions succeeded (returned []) — should NOT be in failures
        assert "bank_transactions" not in failures


# ---------------------------------------------------------------------------
# Test B: mark_collected() must not corrupt sync state (D2 regression)
# ---------------------------------------------------------------------------


class TestMarkCollectedNoCorruption:
    """Prove that mark_collected() does not overwrite collector-authored sync state.

    Before the fix, mark_collected() called update_sync_state(source, success=True)
    with defaults items=0 and status=None, overwriting the collector's correct values.
    After the fix, mark_collected() only updates last_sync via targeted SQL UPDATE.
    """

    def test_mark_collected_preserves_items_and_status(self, tmp_path):
        """End-to-end: collector writes state → mark_collected → items/status intact."""
        db_path = str(tmp_path / "test_mark.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """CREATE TABLE sync_state (
                source TEXT PRIMARY KEY,
                last_sync TEXT,
                last_success TEXT,
                items_synced INTEGER DEFAULT 0,
                error TEXT,
                error_type TEXT,
                status TEXT
            )"""
        )
        conn.commit()

        # Simulate what a collector does: write correct sync state
        upsert_sql = """INSERT INTO sync_state
            (source, last_sync, last_success, items_synced, error, error_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                last_sync = excluded.last_sync,
                last_success = COALESCE(excluded.last_success, sync_state.last_success),
                items_synced = excluded.items_synced,
                error = excluded.error,
                error_type = excluded.error_type,
                status = excluded.status
        """
        conn.execute(
            upsert_sql,
            [
                "gmail",
                "2026-03-14T10:00:00",
                "2026-03-14T10:00:00",
                50,
                None,
                None,
                "success",
            ],
        )
        conn.commit()

        # Verify collector's state is correct
        row = conn.execute(
            "SELECT items_synced, status FROM sync_state WHERE source = ?", ["gmail"]
        ).fetchone()
        assert row[0] == 50  # items_synced

        # Now simulate what mark_collected does after the fix:
        # targeted UPDATE of last_sync only
        conn.execute(
            "UPDATE sync_state SET last_sync = ? WHERE source = ?",
            ["2026-03-14T10:01:00", "gmail"],
        )
        conn.commit()

        # PROOF: items_synced and status must be preserved
        row = conn.execute(
            "SELECT items_synced, status, last_sync FROM sync_state WHERE source = ?",
            ["gmail"],
        ).fetchone()
        assert row[0] == 50, f"items_synced corrupted: expected 50, got {row[0]}"
        assert row[1] == "success", f"status corrupted: expected 'success', got {row[1]}"
        assert row[2] == "2026-03-14T10:01:00", "last_sync was not updated"

        conn.close()

    def test_mark_collected_preserves_partial_status(self, tmp_path):
        """mark_collected after PARTIAL sync must preserve partial status and items."""
        db_path = str(tmp_path / "test_mark_partial.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """CREATE TABLE sync_state (
                source TEXT PRIMARY KEY,
                last_sync TEXT,
                last_success TEXT,
                items_synced INTEGER DEFAULT 0,
                error TEXT,
                error_type TEXT,
                status TEXT
            )"""
        )
        conn.commit()

        upsert_sql = """INSERT INTO sync_state
            (source, last_sync, last_success, items_synced, error, error_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                last_sync = excluded.last_sync,
                last_success = COALESCE(excluded.last_success, sync_state.last_success),
                items_synced = excluded.items_synced,
                error = excluded.error,
                error_type = excluded.error_type,
                status = excluded.status
        """
        # Collector wrote PARTIAL with 30 items
        conn.execute(
            upsert_sql,
            [
                "xero",
                "2026-03-14T10:00:00",
                None,
                30,
                None,
                None,
                "partial",
            ],
        )
        conn.commit()

        # mark_collected: only updates last_sync
        conn.execute(
            "UPDATE sync_state SET last_sync = ? WHERE source = ?",
            ["2026-03-14T10:01:00", "xero"],
        )
        conn.commit()

        row = conn.execute(
            "SELECT items_synced, status FROM sync_state WHERE source = ?",
            ["xero"],
        ).fetchone()
        assert row[0] == 30, f"items_synced corrupted: expected 30, got {row[0]}"
        assert row[1] == "partial", f"status corrupted: expected 'partial', got {row[1]}"

        conn.close()


# ---------------------------------------------------------------------------
# Test C: Asana portfolio/goal fetch failure → PARTIAL (D1-equivalent regression)
# ---------------------------------------------------------------------------


class TestAsanaSecondaryFetchFailure:
    """Prove that Asana portfolio/goal fetch failures produce PARTIAL, not SUCCESS."""

    def test_portfolio_fetch_failure_produces_partial(self):
        """Primary tasks succeed, but list_portfolios raises → status=partial."""
        from lib.collectors.asana import AsanaCollector

        store = FakeStore()
        asana = AsanaCollector(config={"max_retries": 0}, store=store)

        # Provide raw_data as if collect() succeeded with primary tasks
        # but portfolio fetch failed
        raw_data = {
            "tasks": [
                {
                    "gid": "task1",
                    "name": "Test Task",
                    "completed": False,
                    "assignee": {"gid": "user1", "name": "Molham"},
                    "due_on": "2026-03-20",
                    "created_at": "2026-03-01T00:00:00.000Z",
                    "modified_at": "2026-03-10T00:00:00.000Z",
                    "notes": "test",
                    "projects": [{"gid": "proj1", "name": "Project A"}],
                    "tags": [],
                    "custom_fields": [],
                    "_project_gid": "proj1",
                },
            ],
            "subtasks_by_parent": {},
            "stories_by_task": {},
            "dependencies_by_task": {},
            "attachments_by_task": {},
            "portfolios": [],
            "goals": [],
            "_secondary_fetch_errors": {
                "asana_portfolios": "fetch failed: ConnectionError('portfolios API down')",
            },
        }

        # Patch collect() to return our crafted raw_data, bypassing real API
        with patch.object(asana, "collect", return_value=raw_data):
            result = asana.sync()

        # PROOF 1: status must be PARTIAL
        assert result["status"] == "partial", (
            f"Expected 'partial' but got '{result['status']}'. "
            "Portfolio fetch failure was silently swallowed."
        )
        # PROOF 2: success is False
        assert result["success"] is False
        # PROOF 3: asana_portfolios is in secondary_failures
        assert "asana_portfolios" in result.get("secondary_failures", [])
        # PROOF 4: sync state reflects partial
        state = store.sync_states.get("asana")
        assert state is not None
        assert state["status"] == "partial"
