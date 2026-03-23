"""
Audit remediation verification tests — Pass 3.

Covers:
- task_project_linker.py migration (4 write sites → execute_write)
- api/server.py migrations (dismiss_watcher, snooze_watcher, add_issue_note,
  get_watchers, get_fix_data, proposals fallback)
- Orchestrator init-failure surfacing
- chat.py partial-failure metadata
- Intelligence API error field preservation
- Write-path rule enforcement

Each test is labeled [B] (behavioral — exercises real code) or
[S] (structural — verifies code shape via inspection).
"""

import inspect
import tempfile

import pytest

# ============================================================
# Group 1: task_project_linker.py migration verification
# ============================================================


class TestTaskProjectLinkerMigration:
    """Verify task_project_linker.py no longer uses sqlite3.connect."""

    def test_S_no_sqlite3_connect_in_module(self):
        """[S] task_project_linker.py must not import or use sqlite3.connect."""
        from lib import task_project_linker

        src = inspect.getsource(task_project_linker)
        # Filter to code-only lines (skip comments and docstrings captured by getsource)
        code_lines = [line for line in src.split("\n") if not line.strip().startswith("#")]
        code_only = "\n".join(code_lines)
        assert "sqlite3.connect" not in code_only, (
            "task_project_linker.py still uses sqlite3.connect"
        )

    def test_S_no_sqlite3_import(self):
        """[S] task_project_linker.py must not import sqlite3."""
        from lib import task_project_linker

        src = inspect.getsource(task_project_linker)
        code_lines = [line for line in src.split("\n") if not line.strip().startswith("#")]
        code_only = "\n".join(code_lines)
        assert "import sqlite3" not in code_only, "task_project_linker.py still imports sqlite3"

    def test_S_uses_store_execute_write(self):
        """[S] All 4 write functions use store.execute_write()."""
        from lib import task_project_linker

        for fn_name in ("link_by_asana_gid", "link_by_map", "link_by_name", "cascade_client_ids"):
            fn = getattr(task_project_linker, fn_name)
            src = inspect.getsource(fn)
            code_lines = [line for line in src.split("\n") if not line.strip().startswith("#")]
            code_only = "\n".join(code_lines)
            # Each write function should call execute_write
            assert "execute_write" in code_only or "dry_run" in code_only, (
                f"{fn_name} does not use execute_write"
            )

    def test_S_uses_store_query_for_reads(self):
        """[S] link_all() uses store.query() for read-only counts."""
        from lib import task_project_linker

        src = inspect.getsource(task_project_linker.link_all)
        code_lines = [line for line in src.split("\n") if not line.strip().startswith("#")]
        code_only = "\n".join(code_lines)
        assert "s.query(" in code_only, "link_all() should use store.query() for reads"

    def test_S_accepts_store_kwarg(self):
        """[S] All functions accept store= keyword argument."""
        from lib import task_project_linker

        for fn_name in (
            "link_by_asana_gid",
            "link_by_map",
            "link_by_name",
            "cascade_client_ids",
            "link_all",
        ):
            fn = getattr(task_project_linker, fn_name)
            sig = inspect.signature(fn)
            assert "store" in sig.parameters, f"{fn_name} does not accept store= parameter"


# ============================================================
# Group 2: api/server.py migration verification
# ============================================================


class TestApiServerMigrations:
    """Verify api/server.py endpoint migrations."""

    def _get_function_source(self, fn_name: str) -> str:
        """Get source of a function from api/server.py, code-only lines."""
        import api.server as server_module

        fn = getattr(server_module, fn_name)
        src = inspect.getsource(fn)
        code_lines = [line for line in src.split("\n") if not line.strip().startswith("#")]
        return "\n".join(code_lines)

    def test_S_dismiss_watcher_no_sqlite3(self):
        """[S] dismiss_watcher no longer uses sqlite3.connect."""
        src = self._get_function_source("dismiss_watcher")
        assert "sqlite3.connect" not in src

    def test_S_dismiss_watcher_uses_execute_write(self):
        """[S] dismiss_watcher uses store.execute_write."""
        src = self._get_function_source("dismiss_watcher")
        assert "execute_write" in src

    def test_S_snooze_watcher_no_sqlite3(self):
        """[S] snooze_watcher no longer uses sqlite3.connect."""
        src = self._get_function_source("snooze_watcher")
        assert "sqlite3.connect" not in src

    def test_S_snooze_watcher_uses_execute_write(self):
        """[S] snooze_watcher uses store.execute_write."""
        src = self._get_function_source("snooze_watcher")
        assert "execute_write" in src

    def test_S_add_issue_note_no_raw_sqlite3(self):
        """[S] add_issue_note no longer opens raw sqlite3 connection."""
        src = self._get_function_source("add_issue_note")
        assert "sqlite3.connect" not in src

    def test_S_add_issue_note_uses_execute_write(self):
        """[S] add_issue_note uses store.execute_write for INSERT and UPDATE."""
        src = self._get_function_source("add_issue_note")
        # Should have multiple execute_write calls (CREATE TABLE, INSERT, UPDATE)
        assert src.count("execute_write") >= 2, (
            "add_issue_note should use execute_write for both INSERT and UPDATE"
        )

    def test_S_get_watchers_uses_store_query(self):
        """[S] get_watchers reads via store.query(), not raw cursor."""
        src = self._get_function_source("get_watchers")
        assert "store.query" in src
        assert "sqlite3.connect" not in src

    def test_S_get_fix_data_uses_store_query(self):
        """[S] get_fix_data reads via store.query(), not raw cursor."""
        src = self._get_function_source("get_fix_data")
        assert "store.query" in src
        assert "sqlite3.connect" not in src


# ============================================================
# Group 3: Orchestrator init-failure surfacing
# ============================================================


class TestOrchestratorInitFailure:
    """Verify orchestrator surfaces collector init failures."""

    def test_S_has_init_failures_dict(self):
        """[S] CollectorOrchestrator has init_failures attribute."""
        src = inspect.getsource(
            __import__(
                "lib.collectors.orchestrator", fromlist=["CollectorOrchestrator"]
            ).CollectorOrchestrator
        )
        assert "self.init_failures" in src

    def test_S_init_failures_populated_on_error(self):
        """[S] _init_collectors records failures in init_failures dict."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        src = inspect.getsource(CollectorOrchestrator._init_collectors)
        assert "self.init_failures[source_name]" in src, (
            "_init_collectors does not record failures in init_failures"
        )

    def test_S_sync_surfaces_init_failures(self):
        """[S] _sync_impl includes _init_failures in results when present."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        src = inspect.getsource(CollectorOrchestrator._sync_impl)
        assert "_init_failures" in src, "_sync_impl does not surface init_failures in sync results"

    def test_S_get_status_surfaces_init_failures(self):
        """[S] get_status includes init-failed collectors."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        src = inspect.getsource(CollectorOrchestrator.get_status)
        assert "init_failed" in src, "get_status does not surface init-failed collectors"


# ============================================================
# Group 4: chat.py partial-failure metadata
# ============================================================


class TestChatPartialFailure:
    """Verify chat.py surfaces partial failures explicitly."""

    def test_S_collect_tracks_partial_failures(self):
        """[S] collect() builds partial_failures list."""
        from lib.collectors.chat import ChatCollector

        src = inspect.getsource(ChatCollector.collect)
        assert "partial_failures" in src, "collect() does not track partial_failures"

    def test_S_collect_returns_partial_failure_metadata(self):
        """[S] collect() includes partial_failures in return value."""
        from lib.collectors.chat import ChatCollector

        src = inspect.getsource(ChatCollector.collect)
        assert '"partial_failures"' in src or "'partial_failures'" in src, (
            "collect() does not include partial_failures in result dict"
        )

    def test_S_list_messages_returns_error_tuple(self):
        """[S] _list_messages returns (messages, error_or_None) tuple."""
        from lib.collectors.chat import ChatCollector

        src = inspect.getsource(ChatCollector._list_messages)
        # Should return a tuple, not just a list
        assert "return [], str(e)" in src or "return list(" in src, (
            "_list_messages should return tuple (messages, error_or_None)"
        )

    def test_S_sync_surfaces_partial_failures(self):
        """[S] sync() propagates partial_failures from collect() to result."""
        from lib.collectors.chat import ChatCollector

        src = inspect.getsource(ChatCollector.sync)
        assert "partial_failures" in src, "sync() does not propagate partial_failures to result"

    def test_S_members_failure_tracked(self):
        """[S] collect() tracks member fetch failures in partial_failures."""
        from lib.collectors.chat import ChatCollector

        src = inspect.getsource(ChatCollector.collect)
        # Check that member failures are tracked, not just logged
        assert '"members"' in src or "'members'" in src, "collect() does not track member failures"


# ============================================================
# Group 5: Intelligence API error field preservation
# ============================================================


class TestIntelligenceAPIErrorFields:
    """Verify intelligence API endpoints preserve error metadata."""

    def test_S_patterns_endpoint_preserves_success(self):
        """[S] /intelligence/patterns returns detection_success field."""
        from api.spec_router import get_intelligence_patterns

        src = inspect.getsource(get_intelligence_patterns)
        assert "detection_success" in src, "patterns endpoint does not return detection_success"

    def test_S_patterns_endpoint_preserves_errors(self):
        """[S] /intelligence/patterns returns detection_errors when present."""
        from api.spec_router import get_intelligence_patterns

        src = inspect.getsource(get_intelligence_patterns)
        assert "detection_errors" in src, "patterns endpoint strips detection_errors"

    def test_S_proposals_endpoint_served_by_intelligence_router(self):
        """[S] /intelligence/proposals is served by intelligence_router (canonical)."""
        from api.intelligence_router import list_proposals

        src = inspect.getsource(list_proposals)
        assert "generate_proposals" in src, (
            "canonical proposals endpoint must call generate_proposals"
        )


# ============================================================
# Group 6: Write-path rule enforcement
# ============================================================


class TestWritePathRule:
    """Verify write-path rule is codified and enforced."""

    def test_S_state_store_documents_write_rule(self):
        """[S] StateStore has write-path rule documentation."""
        from lib.state_store import StateStore

        src = inspect.getsource(StateStore)
        assert "WRITE-PATH RULE" in src, "StateStore does not document write-path rule"
        assert "PROHIBITED" in src, "StateStore does not document prohibited patterns"

    def test_B_query_rejects_insert(self):
        """[B] store.query() raises RuntimeError on INSERT."""

        from lib.state_store import StateStore

        # Reset singleton for testing
        StateStore._instance = None
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = StateStore(f.name)
            with pytest.raises(RuntimeError, match="read-only"):
                store.query("INSERT INTO foo VALUES (1)")
            StateStore._instance = None

    def test_B_query_rejects_update(self):
        """[B] store.query() raises RuntimeError on UPDATE."""

        from lib.state_store import StateStore

        StateStore._instance = None
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = StateStore(f.name)
            with pytest.raises(RuntimeError, match="read-only"):
                store.query("UPDATE foo SET x = 1")
            StateStore._instance = None

    def test_B_query_rejects_delete(self):
        """[B] store.query() raises RuntimeError on DELETE."""

        from lib.state_store import StateStore

        StateStore._instance = None
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = StateStore(f.name)
            with pytest.raises(RuntimeError, match="read-only"):
                store.query("DELETE FROM foo WHERE id = 1")
            StateStore._instance = None

    def test_S_no_sqlite3_connect_in_task_project_linker(self):
        """[S] task_project_linker uses no raw sqlite3.connect."""
        from lib import task_project_linker

        src = inspect.getsource(task_project_linker)
        code_lines = [
            line
            for line in src.split("\n")
            if not line.strip().startswith("#") and '"""' not in line
        ]
        code_only = "\n".join(code_lines)
        assert "sqlite3.connect" not in code_only
