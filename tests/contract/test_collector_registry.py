"""
Contract Tests — Collector Registry Enforcement

These tests FAIL if:
1. There is more than one active collector registry/mapping
2. Orchestrator doesn't use class-based collectors
3. Legacy collectors directory exists
4. API doesn't read from v29 tables
"""

import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestSingleRegistry:
    """Ensure there is only ONE collector registry."""

    def test_collector_registry_exists(self):
        """lib/collector_registry.py must exist and define COLLECTOR_REGISTRY."""
        registry_path = PROJECT_ROOT / "lib" / "collector_registry.py"
        assert registry_path.exists(), "lib/collector_registry.py must exist"

        spec = importlib.util.spec_from_file_location("collector_registry", registry_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "COLLECTOR_REGISTRY"), "COLLECTOR_REGISTRY must be defined"
        assert len(module.COLLECTOR_REGISTRY) == 8, (
            f"Expected 8 collectors, got {len(module.COLLECTOR_REGISTRY)}"
        )

    def test_registry_points_to_lib_collectors(self):
        """All registry entries must point to lib.collectors modules."""
        registry_path = PROJECT_ROOT / "lib" / "collector_registry.py"

        spec = importlib.util.spec_from_file_location("collector_registry", registry_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for name, entry in module.COLLECTOR_REGISTRY.items():
            assert entry.module.startswith("lib.collectors."), (
                f"Collector '{name}' must point to lib.collectors, got '{entry.module}'"
            )


class TestLegacyRemoved:
    """Ensure legacy collectors directory is gone."""

    def test_no_legacy_collectors_directory(self):
        """Top-level collectors/ directory must not exist."""
        legacy_dir = PROJECT_ROOT / "collectors"
        assert not legacy_dir.exists(), (
            "Legacy collectors/ directory still exists. "
            "All collection goes through lib/collectors/ now."
        )

    def test_no_scheduled_collect_imports(self):
        """No Python files should import from collectors.scheduled_collect."""
        for py_file in PROJECT_ROOT.rglob("*.py"):
            # Skip archived files and this test file itself
            if "_archive" in str(py_file) or py_file == Path(__file__):
                continue
            content = py_file.read_text()
            assert "from collectors.scheduled_collect" not in content, (
                f"{py_file.relative_to(PROJECT_ROOT)} still imports from "
                "collectors.scheduled_collect"
            )
            assert "from collectors.xero_ops" not in content, (
                f"{py_file.relative_to(PROJECT_ROOT)} still imports from collectors.xero_ops"
            )


class TestOrchestratorUsesClassCollectors:
    """Ensure CollectorOrchestrator uses class-based collectors directly."""

    def test_orchestrator_has_all_collectors(self):
        """Orchestrator must initialize all 8 collector types."""
        orch_path = PROJECT_ROOT / "lib" / "collectors" / "orchestrator.py"
        content = orch_path.read_text()

        expected = [
            "TasksCollector",
            "CalendarCollector",
            "ChatCollector",
            "GmailCollector",
            "AsanaCollector",
            "XeroCollector",
            "DriveCollector",
            "ContactsCollector",
        ]
        for collector in expected:
            assert collector in content, f"Orchestrator must use {collector}"

    def test_orchestrator_no_legacy_delegation(self):
        """Orchestrator must NOT delegate to scheduled_collect."""
        orch_path = PROJECT_ROOT / "lib" / "collectors" / "orchestrator.py"
        content = orch_path.read_text()

        assert "scheduled_collect" not in content, (
            "Orchestrator must not reference scheduled_collect"
        )

    def test_sync_all_delegates_to_force_sync(self):
        """CollectorOrchestrator.sync_all must call force_sync."""
        orch_path = PROJECT_ROOT / "lib" / "collectors" / "orchestrator.py"
        content = orch_path.read_text()
        assert "force_sync" in content, "sync_all must delegate to force_sync"

    def test_orchestrator_uses_lock(self):
        """Orchestrator must use CollectorLock."""
        orch_path = PROJECT_ROOT / "lib" / "collectors" / "orchestrator.py"
        content = orch_path.read_text()

        assert "CollectorLock" in content, "Orchestrator must use CollectorLock"
        assert "CollectorLock(name)" in content, "Orchestrator must acquire per-collector locks"


class TestAPIUsesV29:
    """Ensure API reads from v29 tables."""

    def test_endpoints_query_v29_tables(self):
        """API endpoints must query v29 tables."""
        endpoints_path = PROJECT_ROOT / "lib" / "ui_spec_v21" / "endpoints.py"
        content = endpoints_path.read_text()

        # Must query inbox_items_v29
        assert "inbox_items_v29" in content, "API must query inbox_items_v29"
        # Must query issues_v29
        assert "issues_v29" in content, "API must query issues_v29"


class TestLockfileExists:
    """Ensure lockfile mechanism works."""

    def test_collector_lock_class_exists(self):
        """CollectorLock must be defined in registry."""
        registry_path = PROJECT_ROOT / "lib" / "collector_registry.py"

        spec = importlib.util.spec_from_file_location("collector_registry", registry_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "CollectorLock"), "CollectorLock must be defined"

    def test_lock_is_context_manager(self):
        """CollectorLock must be a context manager."""
        registry_path = PROJECT_ROOT / "lib" / "collector_registry.py"

        spec = importlib.util.spec_from_file_location("collector_registry", registry_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        lock = module.CollectorLock()
        assert hasattr(lock, "__enter__"), "CollectorLock must have __enter__"
        assert hasattr(lock, "__exit__"), "CollectorLock must have __exit__"


class TestAllCollectorsUseSAAuth:
    """Ensure all collectors use service account auth, not gog CLI."""

    def test_no_gog_cli_in_collectors(self):
        """No collector in lib/collectors/ should shell out to gog CLI."""
        collectors_dir = PROJECT_ROOT / "lib" / "collectors"
        for py_file in collectors_dir.glob("*.py"):
            if py_file.name in (
                "base.py",
                "__init__.py",
                "resilience.py",
                "recorder.py",
                "watchdog.py",
                "orchestrator.py",
            ):
                continue
            content = py_file.read_text()
            # tasks.py legitimately uses gog CLI for Google Tasks (no Python API)
            if py_file.name == "tasks.py":
                continue
            assert '"gog"' not in content and "'gog'" not in content, (
                f"{py_file.name} shells out to gog CLI instead of using SA auth"
            )
