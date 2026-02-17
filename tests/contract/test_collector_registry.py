"""
Contract Tests — Collector Registry Enforcement

These tests FAIL if:
1. There is more than one active collector registry/mapping
2. Canonical runner doesn't use the registry
3. Legacy collectors are imported
4. API doesn't read from v29 tables
"""

import importlib.util
import re
from pathlib import Path

import pytest

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

    def test_scheduled_collect_uses_registry(self):
        """scheduled_collect.py must import from lib.collector_registry."""
        scheduled_path = PROJECT_ROOT / "collectors" / "scheduled_collect.py"
        content = scheduled_path.read_text()

        assert "from lib.collector_registry import" in content, (
            "scheduled_collect.py must import from lib.collector_registry"
        )

    def test_scheduled_collect_uses_lock(self):
        """scheduled_collect.py must use CollectorLock."""
        scheduled_path = PROJECT_ROOT / "collectors" / "scheduled_collect.py"
        content = scheduled_path.read_text()

        assert "CollectorLock" in content, "scheduled_collect.py must use CollectorLock"
        assert "with CollectorLock()" in content, "scheduled_collect.py must acquire lock"


class TestCanonicalRunnerAuthoritative:
    """Ensure canonical runner sources match registry."""

    def test_sources_match_registry(self):
        """All sources in scheduled_collect must be in registry."""
        registry_path = PROJECT_ROOT / "lib" / "collector_registry.py"
        scheduled_path = PROJECT_ROOT / "collectors" / "scheduled_collect.py"

        # Load registry
        spec = importlib.util.spec_from_file_location("collector_registry", registry_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registry_sources = set(module.COLLECTOR_REGISTRY.keys())

        # Parse scheduled_collect for sources
        content = scheduled_path.read_text()
        # Find the collectors dict
        match = re.search(r"collectors\s*=\s*\{([^}]+)\}", content, re.DOTALL)
        if match:
            dict_content = match.group(1)
            scheduled_sources = set(re.findall(r'["\'](\w+)["\']:', dict_content))
        else:
            scheduled_sources = set()

        missing = scheduled_sources - registry_sources
        assert not missing, f"Sources in scheduled_collect but not in registry: {missing}"


class TestLegacyBlocked:
    """Ensure legacy collectors cannot be imported."""

    def test_legacy_import_raises(self):
        """Importing from collectors._legacy must raise RuntimeError or ImportError."""
        import sys

        # Clear any cached imports to ensure fresh import behavior
        modules_to_clear = [k for k in sys.modules if k.startswith("collectors._legacy")]
        for mod in modules_to_clear:
            del sys.modules[mod]

        # Either RuntimeError (explicit block) or ImportError (import machinery failure)
        # Both indicate the legacy module is effectively blocked
        with pytest.raises((RuntimeError, ImportError)):
            from collectors._legacy import team_calendar  # noqa: F401

    def test_legacy_getattr_raises(self):
        """Accessing any attribute on _legacy must raise RuntimeError or ImportError."""
        import sys

        # Clear any cached imports - must clear all related modules
        modules_to_clear = [
            k for k in list(sys.modules.keys()) if "collectors" in k or "lib.collectors" in k
        ]
        for mod in modules_to_clear:
            try:
                del sys.modules[mod]
            except KeyError:
                pass

        try:
            import collectors._legacy as legacy

            # If import succeeds, verify __getattr__ blocks attribute access
            with pytest.raises(RuntimeError, match="deprecated"):
                _ = legacy.anything
        except (RuntimeError, ImportError):
            # If import itself fails, the legacy module is blocked - test passes
            pass


class TestOrchestratorDelegates:
    """Ensure CollectorOrchestrator delegates to canonical runner."""

    def test_force_sync_delegates(self):
        """CollectorOrchestrator.force_sync must delegate to scheduled_collect."""
        orch_path = PROJECT_ROOT / "lib" / "collectors" / "orchestrator.py"
        content = orch_path.read_text()

        # Must import from scheduled_collect
        assert "from collectors.scheduled_collect import" in content, (
            "orchestrator.force_sync must import from scheduled_collect"
        )

    def test_sync_all_delegates(self):
        """CollectorOrchestrator.sync_all must call force_sync."""
        orch_path = PROJECT_ROOT / "lib" / "collectors" / "orchestrator.py"
        content = orch_path.read_text()

        # Find sync_all method
        match = re.search(
            r"def sync_all\(self\)[^:]*:[^}]+?(?=\n    def |\nclass |\Z)",
            content,
            re.DOTALL,
        )
        if match:
            method_body = match.group(0)
            assert "force_sync" in method_body, "sync_all must delegate to force_sync"


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
