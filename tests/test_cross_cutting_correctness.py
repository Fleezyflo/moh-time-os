"""
Regression tests for cross-cutting correctness issues.

Tests that:
1. Time handling is consistent and explicit
2. Config/path behavior is environment-safe
3. Mutable shared state is thread-safe
4. Runtime behavior is deterministic across startups and environments
5. No deprecated time patterns remain in critical modules
"""

import os
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).parent.parent


# ===========================================================================
# 1. TIME POLICY TESTS — format, roundtrip, boundary conditions
# ===========================================================================


class TestCanonicalTimestamp:
    """Verify the canonical timestamp format (24-char, 3-digit ms, Z suffix)."""

    def test_now_iso_format(self):
        """now_iso() produces exactly 24-char ISO with Z suffix."""
        from lib.clock import now_iso

        ts = now_iso()
        assert len(ts) == 24, f"Expected 24 chars, got {len(ts)}: {ts}"
        assert ts.endswith("Z")
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", ts)

    def test_now_utc_is_aware(self):
        """now_utc() always returns timezone-aware UTC."""
        from lib.clock import now_utc

        dt = now_utc()
        assert dt.tzinfo is not None, "now_utc() must return aware datetime"
        assert dt.utcoffset().total_seconds() == 0

    def test_now_iso_is_consistent_with_now_utc(self):
        """now_iso() and now_utc() produce the same time (within 100ms)."""
        from lib.clock import from_iso, now_iso, now_utc

        dt = now_utc()
        ts = now_iso()
        parsed = from_iso(ts)
        # They should be within 100ms of each other
        delta = abs((parsed - dt).total_seconds())
        assert delta < 0.1, f"now_iso() and now_utc() differ by {delta}s"

    def test_to_iso_from_naive(self):
        """to_iso() treats naive datetimes as UTC (migration helper)."""
        from lib.clock import to_iso

        naive = datetime(2026, 3, 14, 12, 0, 0, 123000)
        result = to_iso(naive)
        assert result == "2026-03-14T12:00:00.123Z"

    def test_to_iso_from_aware_dubai(self):
        """to_iso() converts aware datetimes to UTC."""
        from lib.clock import to_iso

        dubai = ZoneInfo("Asia/Dubai")
        aware = datetime(2026, 3, 14, 16, 0, 0, 456000, tzinfo=dubai)
        result = to_iso(aware)
        assert result == "2026-03-14T12:00:00.456Z"

    def test_from_iso_roundtrip(self):
        """from_iso(to_iso(dt)) preserves the datetime to millisecond precision."""
        from lib.clock import from_iso, to_iso

        original = datetime(2026, 6, 15, 23, 59, 59, 999000, tzinfo=timezone.utc)
        roundtripped = from_iso(to_iso(original))
        assert roundtripped.year == original.year
        assert roundtripped.month == original.month
        assert roundtripped.day == original.day
        assert roundtripped.hour == original.hour
        assert roundtripped.minute == original.minute
        assert roundtripped.second == original.second
        # Microsecond truncated to millisecond
        assert roundtripped.microsecond == 999000

    def test_from_iso_to_iso_idempotent(self):
        """to_iso(from_iso(s)) == s for any canonical string."""
        from lib.clock import from_iso, to_iso

        canonical = "2026-02-08T14:30:00.123Z"
        assert to_iso(from_iso(canonical)) == canonical

    def test_ensure_aware_naive_input(self):
        """ensure_aware() tags naive datetime as UTC."""
        from lib.clock import ensure_aware

        naive = datetime(2026, 1, 1, 0, 0, 0)
        aware = ensure_aware(naive)
        assert aware.tzinfo is not None
        assert aware.utcoffset().total_seconds() == 0

    def test_ensure_aware_converts_to_utc(self):
        """ensure_aware() converts non-UTC aware datetime to UTC."""
        from lib.clock import ensure_aware

        dubai = ZoneInfo("Asia/Dubai")
        aware_dubai = datetime(2026, 3, 14, 16, 0, 0, tzinfo=dubai)
        result = ensure_aware(aware_dubai)
        assert result.utcoffset().total_seconds() == 0
        assert result.hour == 12  # Dubai +4 → UTC -4

    def test_store_now_iso_produces_canonical_format(self):
        """lib.store.now_iso() produces canonical 24-char format."""
        from lib.store import now_iso

        ts = now_iso()
        assert len(ts) == 24
        assert ts.endswith("Z")
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", ts)

    def test_normalize_microseconds_truncated(self):
        from lib.clock import normalize_timestamp

        result = normalize_timestamp("2026-02-08T14:30:00.123456Z")
        assert result == "2026-02-08T14:30:00.123Z"

    def test_normalize_offset_converted_to_utc(self):
        from lib.clock import normalize_timestamp

        result = normalize_timestamp("2026-02-08T18:30:00+04:00")
        assert result == "2026-02-08T14:30:00.000Z"

    def test_normalize_missing_ms_padded(self):
        from lib.clock import normalize_timestamp

        result = normalize_timestamp("2026-02-08T14:30:00Z")
        assert result == "2026-02-08T14:30:00.000Z"

    def test_midnight_boundary_dubai(self):
        """Org-local midnight in Dubai is 20:00 UTC previous day."""
        from datetime import date

        from lib.ui_spec_v21.time_utils import local_midnight_utc

        midnight = local_midnight_utc("Asia/Dubai", date(2026, 3, 15))
        assert midnight.day == 14
        assert midnight.hour == 20
        assert midnight.minute == 0
        assert midnight.tzinfo is not None

    def test_timestamp_lexicographic_ordering_matches_chronological(self):
        """Canonical ISO timestamps sort lexicographically = chronologically."""
        from lib.clock import to_iso

        t1 = datetime(2026, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 0, 0, 0, 1000, tzinfo=timezone.utc)
        t3 = datetime(2026, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc)

        s1, s2, s3 = to_iso(t1), to_iso(t2), to_iso(t3)
        assert s1 < s2 < s3, f"Lex order broken: {s1}, {s2}, {s3}"


# ===========================================================================
# 2. CONFIG/PATH TESTS — environment-safe, no machine-specific assumptions
# ===========================================================================


class TestPathResolution:
    """Verify path resolution is environment-safe."""

    def test_db_path_respects_env_override(self):
        """DB path can be overridden via MOH_TIME_OS_DB."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = f.name

        try:
            with patch.dict(os.environ, {"MOH_TIME_OS_DB": tmp_path}):
                from lib import paths

                result = paths.db_path()
                assert str(result) == str(Path(tmp_path).resolve())
        finally:
            os.unlink(tmp_path)

    def test_store_get_connection_uses_runtime_db_path(self):
        """store.get_connection() resolves DB path at call time, not import time."""
        import inspect

        from lib import store

        source = inspect.getsource(store.get_connection)
        assert "_db_path()" in source, (
            "get_connection must call _db_path() for runtime resolution, "
            "not use the import-time-cached DB_PATH"
        )

    def test_store_init_db_uses_runtime_db_path(self):
        """store.init_db() resolves DB path at call time."""
        import inspect

        from lib import store

        source = inspect.getsource(store.init_db)
        assert "_db_path()" in source, "init_db must call _db_path() for runtime resolution"

    def test_credential_paths_respects_env_override(self):
        """Google SA file can be overridden via GOOGLE_SA_FILE."""
        with patch.dict(os.environ, {"GOOGLE_SA_FILE": "/custom/path/sa.json"}):
            from lib.credential_paths import google_sa_file

            result = google_sa_file()
            assert str(result) == "/custom/path/sa.json"

    def test_credential_paths_no_hardcoded_macos_on_linux(self):
        """On Linux, credential path doesn't use Library/Application Support."""
        os.environ.pop("GOOGLE_SA_FILE", None)
        from lib.credential_paths import google_sa_file

        with patch("lib.credential_paths.platform.system", return_value="Linux"):
            result = google_sa_file()
            assert "Library/Application Support" not in str(result)
            assert ".config/gogcli" in str(result)

    def test_no_hardcoded_sa_path_in_collectors(self):
        """No collector file still has a hardcoded macOS SA path."""
        collector_dir = REPO_ROOT / "lib" / "collectors"
        for py_file in collector_dir.glob("*.py"):
            content = py_file.read_text()
            assert 'Path.home() / "Library' not in content, (
                f"{py_file.name} still has hardcoded macOS Path.home() SA path"
            )

    def test_no_module_level_db_path_in_production(self):
        """No production file defines DB_PATH at module level.

        Module-level DB_PATH = paths.db_path() captures the path at import
        time, before env overrides (MOH_TIME_OS_DB) can take effect. All
        path resolution must happen at call time inside function bodies.
        """
        production_dirs = ["lib", "api", "cli", "engine", "scripts"]
        violations = []

        for dir_name in production_dirs:
            dir_path = REPO_ROOT / dir_name
            if not dir_path.exists():
                continue
            for py_file in dir_path.rglob("*.py"):
                rel = str(py_file.relative_to(REPO_ROOT))
                content = py_file.read_text()
                for i, line in enumerate(content.split("\n"), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if re.match(r"^DB_PATH\s*=", stripped):
                        violations.append(f"{rel}:{i}: {stripped}")

        assert not violations, (
            f"Found module-level DB_PATH in {len(violations)} locations. "
            f"Use paths.db_path() at call time instead.\n" + "\n".join(violations)
        )

    def test_no_hardcoded_os_path_join_db_in_production(self):
        """No production file uses os.path.join to construct a DB path."""
        production_dirs = ["lib", "api", "cli", "engine", "scripts"]
        violations = []

        for dir_name in production_dirs:
            dir_path = REPO_ROOT / dir_name
            if not dir_path.exists():
                continue
            for py_file in dir_path.rglob("*.py"):
                rel = str(py_file.relative_to(REPO_ROOT))
                content = py_file.read_text()
                for i, line in enumerate(content.split("\n"), 1):
                    if "os.path.join" in line and "moh_time_os.db" in line:
                        violations.append(f"{rel}:{i}: {line.strip()}")

        assert not violations, (
            f"Found hardcoded os.path.join DB path in {len(violations)} locations. "
            f"Use paths.db_path() instead.\n" + "\n".join(violations)
        )

    def test_config_store_uses_runtime_resolution(self):
        """config_store resolves paths at call time, not import time."""
        from lib import config_store

        # _config_dir must be a function, not a cached value
        assert callable(config_store._config_dir), (
            "config_store._config_dir must be a callable for runtime resolution"
        )
        assert callable(config_store._config_file), (
            "config_store._config_file must be a callable for runtime resolution"
        )

    def test_v4_services_use_runtime_db_path(self):
        """lib/v4 service __init__ methods resolve DB path at call time."""
        v4_dir = REPO_ROOT / "lib" / "v4"
        if not v4_dir.exists():
            pytest.skip("lib/v4 not found")

        violations = []
        for py_file in v4_dir.rglob("*.py"):
            content = py_file.read_text()
            if re.search(r"^DB_PATH\s*=", content, re.MULTILINE):
                rel = py_file.relative_to(REPO_ROOT)
                violations.append(str(rel))

        assert not violations, f"lib/v4 files still define module-level DB_PATH: {violations}"


# ===========================================================================
# 3. MUTABLE STATE THREAD-SAFETY TESTS — prove locks work under concurrency
# ===========================================================================


class TestCircuitBreakerThreadSafety:
    """Verify circuit breaker state is thread-safe."""

    def test_concurrent_failures_reach_threshold(self):
        """Multiple threads recording failures should eventually open the circuit."""
        from lib.collectors.resilience import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=10, cooldown_seconds=300)
        errors = []

        def record_failures():
            try:
                for _ in range(5):
                    cb.record_failure()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_failures) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert cb.state == "open", f"Expected OPEN after 20 failures, got {cb.state}"
        assert cb.failure_count == 20

    def test_concurrent_success_resets(self):
        """Concurrent success calls should safely reset state."""
        from lib.collectors.resilience import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.01)

        errors = []

        def record_success():
            try:
                cb.record_success()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_success) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_concurrent_can_execute_during_failures(self):
        """can_execute() is consistent even when failures are being recorded."""
        from lib.collectors.resilience import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=100, cooldown_seconds=300)
        results = []
        lock = threading.Lock()

        def check_and_fail():
            for _ in range(50):
                can = cb.can_execute()
                with lock:
                    results.append(can)
                cb.record_failure()

        threads = [threading.Thread(target=check_and_fail) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 200 results
        assert len(results) == 200


class TestRateLimiterThreadSafety:
    """Verify rate limiter token bucket is thread-safe."""

    def test_concurrent_requests_dont_exceed_limit(self):
        """Concurrent allow_request() calls don't overdraw tokens."""
        from lib.collectors.resilience import RateLimiter

        rl = RateLimiter(requests_per_minute=60)
        allowed = []
        lock = threading.Lock()

        def check_request():
            result = rl.allow_request()
            with lock:
                allowed.append(result)

        threads = [threading.Thread(target=check_request) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed_count = sum(1 for x in allowed if x)
        # Initial tokens = 60, plus a tiny refill window. Must not exceed ~62.
        assert allowed_count <= 65, f"Granted {allowed_count} tokens, expected ≤65"
        # Must have granted at least most of the initial tokens
        assert allowed_count >= 55, f"Only granted {allowed_count}, expected ≥55"


class TestCacheSingletonThreadSafety:
    """Verify global cache is initialized exactly once."""

    def test_get_cache_returns_same_instance(self):
        """Concurrent get_cache() calls return the same instance."""
        from lib.cache.decorators import get_cache

        instances = []
        lock = threading.Lock()

        def get_instance():
            cache = get_cache()
            with lock:
                instances.append(id(cache))

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        unique_ids = set(instances)
        assert len(unique_ids) == 1, f"Got {len(unique_ids)} different cache instances"


class TestFeatureFlagThreadSafety:
    """Verify feature flag registry is thread-safe with RLock."""

    def test_concurrent_read_write_no_crash(self):
        """Concurrent get() and set_override() don't crash or deadlock."""
        from lib.features import FlagDefinition, FlagRegistry, FlagType

        registry = FlagRegistry()
        registry.register(
            FlagDefinition(
                name="test_flag",
                description="Test",
                default=False,
                flag_type=FlagType.BOOLEAN,
            )
        )

        errors = []

        def read_flag():
            try:
                for _ in range(200):
                    registry.get("test_flag")
            except Exception as e:
                errors.append(e)

        def write_flag():
            try:
                for i in range(200):
                    registry.set_override("test_flag", i % 2 == 0)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=read_flag),
            threading.Thread(target=write_flag),
            threading.Thread(target=read_flag),
            threading.Thread(target=write_flag),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # No deadlock (all threads completed within 5s)
        alive = [t for t in threads if t.is_alive()]
        assert not alive, f"{len(alive)} threads still alive — likely deadlocked"
        assert not errors, f"Thread errors: {errors}"

    def test_get_all_doesnt_deadlock(self):
        """get_all() calls get() under lock — RLock must allow re-entrancy."""
        from lib.features import FlagDefinition, FlagRegistry, FlagType

        registry = FlagRegistry()
        registry.register(
            FlagDefinition(name="a", description="A", default=True, flag_type=FlagType.BOOLEAN)
        )
        registry.register(
            FlagDefinition(name="b", description="B", default=42, flag_type=FlagType.NUMBER)
        )

        # This would deadlock with threading.Lock (non-reentrant)
        result = registry.get_all()
        assert "a" in result
        assert "b" in result


# ===========================================================================
# 4. DETERMINISM TESTS — prove behavior is stable across environments
# ===========================================================================


class TestTimezoneConsistency:
    """Verify timestamps are consistent regardless of local timezone."""

    def test_now_iso_always_utc(self):
        """now_iso() always produces UTC (Z suffix) regardless of TZ env."""
        from lib.clock import from_iso, now_iso

        ts = now_iso()
        assert ts.endswith("Z")
        dt = from_iso(ts)
        assert dt.utcoffset().total_seconds() == 0

    def test_state_store_sync_state_uses_utc(self):
        """StateStore.update_sync_state stores UTC-aware timestamps."""
        import inspect

        from lib.state_store import StateStore

        source = inspect.getsource(StateStore.update_sync_state)
        assert "timezone.utc" in source, "update_sync_state must use datetime.now(timezone.utc)"

    def test_state_store_cache_uses_utc(self):
        """StateStore.set_cache stores UTC-aware timestamps."""
        import inspect

        from lib.state_store import StateStore

        source = inspect.getsource(StateStore.set_cache)
        assert "timezone.utc" in source, "set_cache must use datetime.now(timezone.utc)"


# ===========================================================================
# 5. STATIC ANALYSIS — enforce no deprecated patterns in critical modules
# ===========================================================================


class TestNoNaiveDatetimeInProductionCode:
    """Static analysis: ALL production code must use datetime.now(timezone.utc)."""

    # Directories that constitute production source code
    PRODUCTION_DIRS = ["lib", "api", "cli", "engine", "scripts"]

    # Excluded paths: clock.py is the canonical module
    EXCLUDED_PATTERNS = [
        "lib/clock.py",  # The canonical time module itself
    ]

    def _get_production_python_files(self):
        """Collect all .py files in production directories."""
        files = []
        for dir_name in self.PRODUCTION_DIRS:
            dir_path = REPO_ROOT / dir_name
            if dir_path.exists():
                files.extend(dir_path.rglob("*.py"))
        return files

    def _is_excluded(self, path: Path) -> bool:
        rel = str(path.relative_to(REPO_ROOT))
        return any(excl in rel for excl in self.EXCLUDED_PATTERNS)

    def test_no_bare_datetime_now_in_production(self):
        """No production Python file uses bare datetime.now() without timezone.

        This is a comprehensive sweep of all production directories:
        lib/, api/, cli/, engine/, scripts/.

        Only lib/clock.py (the canonical time module) is excluded.
        """
        violations = []
        for py_file in self._get_production_python_files():
            if self._is_excluded(py_file):
                continue
            content = py_file.read_text()
            bare_calls = re.findall(r"datetime\.now\(\s*\)", content)
            if bare_calls:
                rel = py_file.relative_to(REPO_ROOT)
                violations.append(f"{rel}: {len(bare_calls)} bare datetime.now() calls")

        assert not violations, (
            f"Found bare datetime.now() in {len(violations)} production files. "
            f"Use datetime.now(timezone.utc) instead.\n" + "\n".join(violations)
        )

    def test_no_utcnow_in_production(self):
        """No production Python file uses deprecated datetime.utcnow().

        datetime.utcnow() is deprecated since Python 3.12 and produces
        naive UTC datetimes (no timezone object).
        """
        violations = []
        for py_file in self._get_production_python_files():
            if self._is_excluded(py_file):
                continue
            content = py_file.read_text()
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.lstrip()
                if stripped.startswith("#") or stripped.startswith('"""'):
                    continue
                if "datetime.utcnow()" in stripped:
                    rel = py_file.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{i}")

        assert not violations, (
            f"Found datetime.utcnow() in {len(violations)} locations. "
            f"Use datetime.now(timezone.utc) instead.\n" + "\n".join(violations)
        )


class TestNoHardcodedMacOSPaths:
    """Static analysis: no hardcoded macOS paths in maintained scope."""

    def test_no_library_application_support_in_collectors(self):
        """No collector imports Path.home() for Library/Application Support."""
        for subdir in ["lib/collectors", "lib/integrations"]:
            dir_path = REPO_ROOT / subdir
            if not dir_path.exists():
                continue
            for py_file in dir_path.glob("*.py"):
                content = py_file.read_text()
                if "Library/Application Support" in content and "credential_paths" not in content:
                    pytest.fail(
                        f"{subdir}/{py_file.name} has hardcoded macOS path "
                        f"without using credential_paths module"
                    )


class TestLockCoverage:
    """Static analysis: verify locks are actually used, not just declared."""

    def test_export_router_uses_its_lock(self):
        """export_router actually acquires _exports_lock when accessing _exports."""
        full_path = REPO_ROOT / "api" / "export_router.py"
        if not full_path.exists():
            pytest.skip("export_router.py not found")

        content = full_path.read_text()
        assert "_exports_lock" in content, "export_router must declare _exports_lock"
        # Count uses — must appear more than just the declaration
        uses = content.count("_exports_lock")
        assert uses >= 3, (
            f"_exports_lock appears {uses} times — must be acquired (with _exports_lock:) "
            f"not just declared"
        )

    def test_migrations_lock_in_run_startup(self):
        """run_startup_migrations acquires _migrations_lock internally."""
        import inspect

        from lib import db

        source = inspect.getsource(db.run_startup_migrations)
        assert "_migrations_lock" in source, (
            "run_startup_migrations must acquire _migrations_lock internally"
        )

    def test_v4_singletons_have_locks(self):
        """All lib/v4 lazy singleton getters use threading.Lock for thread safety.

        Structural: scans every lib/v4/*.py file for 'global _X; if _X is None'
        patterns and verifies a corresponding lock exists.
        """
        v4_dir = REPO_ROOT / "lib" / "v4"
        if not v4_dir.exists():
            pytest.skip("lib/v4 not found")

        violations = []
        for py_file in v4_dir.glob("*.py"):
            content = py_file.read_text()
            # Find global singleton patterns
            global_matches = re.findall(r"global (_\w+)\b", content)
            for var_name in global_matches:
                # Check if this is a lazy init (has 'if _X is None:' pattern)
                if f"if {var_name} is None:" in content:
                    # Verify a corresponding lock exists
                    has_lock = "_lock" in content and "threading" in content
                    if not has_lock:
                        rel = py_file.relative_to(REPO_ROOT)
                        violations.append(f"{rel}: {var_name} has lazy init without threading.Lock")

        assert not violations, (
            f"Found {len(violations)} unprotected singleton initializers in lib/v4/. "
            f"All lazy singletons must use threading.Lock with double-checked locking.\n"
            + "\n".join(violations)
        )

    def test_flag_registry_uses_rlock(self):
        """FlagRegistry must use RLock (not Lock) to support get_all() re-entrancy."""
        import inspect

        from lib.features import FlagRegistry

        source = inspect.getsource(FlagRegistry)
        assert "RLock" in source, "FlagRegistry must use threading.RLock for re-entrancy"


# ===========================================================================
# 6. NO-DEFERRAL ENFORCEMENT — zero bare datetime or path captures in code
# ===========================================================================


def _ast_collect_datetime_aliases(tree) -> set[str]:
    """Collect all names that alias the datetime class in a module.

    Handles:
      - from datetime import datetime          -> {"datetime"}
      - from datetime import datetime as dt    -> {"dt"}
      - import datetime                        -> NOT included (datetime.datetime.now pattern)

    This is structural: it reads the AST import nodes, not a hardcoded list.
    """
    import ast

    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            for alias in node.names:
                if alias.name == "datetime":
                    aliases.add(alias.asname if alias.asname else "datetime")
    return aliases


def _ast_find_bare_datetime_calls(filepath: Path, method: str = "now") -> list:
    """Use AST to find actual datetime.now() or datetime.utcnow() calls.

    Returns list of "line_number: source_line" for calls with no arguments.

    Structural: collects ALL aliased names for the datetime class from
    import statements (e.g., `from datetime import datetime as dt`) and
    checks calls on any of those aliases. Not limited to the literal
    name "datetime".
    """
    import ast

    content = filepath.read_text()
    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError:
        return []

    aliases = _ast_collect_datetime_aliases(tree)
    if not aliases:
        return []

    lines = content.split("\n")
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != method:
            continue
        # Check the object is ANY alias of the datetime class
        if isinstance(func.value, ast.Name) and func.value.id in aliases:
            # bare call: no positional args AND no keyword args
            # datetime.now() is bare; datetime.now(tz=timezone.utc) is NOT bare
            if not node.args and not node.keywords:
                lineno = node.lineno
                source = lines[lineno - 1].strip() if lineno <= len(lines) else ""
                violations.append(f"{lineno}: {source[:100]}")
    return violations


def _ast_find_naive_fromtimestamp(filepath: Path) -> list:
    """Find datetime.fromtimestamp() calls without tz argument.

    datetime.fromtimestamp(ts) produces a naive datetime.
    datetime.fromtimestamp(ts, tz=timezone.utc) produces an aware datetime.

    This detects the naive form: exactly 1 positional arg and no 'tz' keyword.
    """
    import ast

    content = filepath.read_text()
    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError:
        return []

    aliases = _ast_collect_datetime_aliases(tree)
    if not aliases:
        return []

    lines = content.split("\n")
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "fromtimestamp":
            continue
        if isinstance(func.value, ast.Name) and func.value.id in aliases:
            # Check if tz argument is provided (either positional or keyword)
            has_tz_kwarg = any(kw.arg == "tz" for kw in node.keywords)
            # fromtimestamp(ts) = 1 positional, fromtimestamp(ts, tz) = 2 positional
            if len(node.args) < 2 and not has_tz_kwarg:
                lineno = node.lineno
                source = lines[lineno - 1].strip() if lineno <= len(lines) else ""
                violations.append(f"{lineno}: {source[:100]}")
    return violations


def _ast_find_module_level_path_calls(filepath: Path) -> list:
    """Find module-level assignments that call path-producing functions.

    Structural detector: instead of matching a closed list of variable names,
    this checks if any top-level assignment's RHS calls a function known to
    produce runtime-dependent paths. Catches patterns like:
      - DEFAULT_DB = paths.db_path()
      - SA_FILE = google_sa_file()
      - V5_DB_PATH = paths.v5_db_path()
      - KEY_PATH = os.path.join(os.path.dirname(__file__), ...)
      - SCHEDULE_PATH = project_root() / "config" / ...

    Only checks module-level (top-level) assignments, not assignments inside
    function bodies (which are fine).
    """
    import ast

    content = filepath.read_text()
    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError:
        return []

    # Functions that produce runtime-dependent paths
    PATH_PRODUCING_FUNCTIONS = {
        "db_path",
        "v5_db_path",
        "project_root",
        "google_sa_file",
        "config_dir",
        "config_file",
        "blob_key_path",
    }

    # os.path functions that construct paths
    OS_PATH_FUNCTIONS = {"join", "dirname", "expanduser", "abspath", "realpath"}

    lines = content.split("\n")
    violations = []

    def _calls_path_function(node) -> bool:
        """Recursively check if an AST node contains a call to a path-producing function."""
        if isinstance(node, ast.Call):
            func = node.func
            # Direct call: func_name()
            if isinstance(func, ast.Name) and func.id in PATH_PRODUCING_FUNCTIONS:
                return True
            # Attribute call: module.func_name()
            if isinstance(func, ast.Attribute):
                if func.attr in PATH_PRODUCING_FUNCTIONS:
                    return True
                # os.path.join(...) etc
                if func.attr in OS_PATH_FUNCTIONS and isinstance(func.value, ast.Attribute):
                    if isinstance(func.value.value, ast.Name) and func.value.value.id == "os":
                        return True
            # Check arguments recursively
            for arg in node.args:
                if _calls_path_function(arg):
                    return True
            for kw in node.keywords:
                if _calls_path_function(kw.value):
                    return True
        # BinOp: project_root() / "config"
        if isinstance(node, ast.BinOp):
            return _calls_path_function(node.left) or _calls_path_function(node.right)
        return False

    for stmt in tree.body:  # Only top-level statements
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    # UPPER_CASE module-level assignment
                    if _calls_path_function(stmt.value):
                        lineno = stmt.lineno
                        source = lines[lineno - 1].strip() if lineno <= len(lines) else ""
                        violations.append(f"{lineno}: {source[:100]}")

    return violations


class TestNoDeferralDatetime:
    """Enforce zero naive datetime calls in all Python code.

    Uses STRUCTURAL AST detection:
    - Collects all aliased names for the datetime class from import statements
    - Detects bare .now()/.utcnow() on ANY alias (not just literal "datetime")
    - Detects .fromtimestamp() without tz argument on any alias

    Scope: production, test, and archive .py files.
    Historical markdown/spec documents are excluded (pseudocode examples).
    """

    PRODUCTION_DIRS = ["lib", "api", "cli", "engine", "scripts"]
    EXCLUDED_PATTERNS = ["lib/clock.py"]

    def _get_all_python_files(self, dirs: list[str]) -> list[Path]:
        files = []
        for dir_name in dirs:
            dir_path = REPO_ROOT / dir_name
            if dir_path.exists():
                files.extend(dir_path.rglob("*.py"))
        return files

    def _is_excluded(self, path: Path) -> bool:
        rel = str(path.relative_to(REPO_ROOT))
        return any(excl in rel for excl in self.EXCLUDED_PATTERNS)

    def test_no_bare_datetime_now_in_tests(self):
        """No test file calls bare datetime.now() without timezone arg.
        Detects aliased imports like `from datetime import datetime as dt; dt.now()`.
        """
        test_dir = REPO_ROOT / "tests"
        violations = []
        for py_file in test_dir.rglob("*.py"):
            hits = _ast_find_bare_datetime_calls(py_file, "now")
            if hits:
                rel = py_file.relative_to(REPO_ROOT)
                violations.extend(f"{rel}:{h}" for h in hits)

        assert not violations, (
            f"Found {len(violations)} bare datetime.now() calls in test code. "
            f"Use datetime.now(timezone.utc) instead.\n" + "\n".join(violations)
        )

    def test_no_bare_datetime_now_in_archives(self):
        """No archive Python file calls bare datetime.now()."""
        archive_dirs = [
            REPO_ROOT / "docs" / "archive",
            REPO_ROOT / "_archive",
        ]
        violations = []
        for archive_dir in archive_dirs:
            if not archive_dir.exists():
                continue
            for py_file in archive_dir.rglob("*.py"):
                hits = _ast_find_bare_datetime_calls(py_file, "now")
                if hits:
                    rel = py_file.relative_to(REPO_ROOT)
                    violations.extend(f"{rel}:{h}" for h in hits)

        assert not violations, (
            f"Found {len(violations)} bare datetime.now() calls in archive code. "
            f"Use datetime.now(timezone.utc) instead.\n" + "\n".join(violations)
        )

    def test_no_utcnow_in_tests(self):
        """No test file calls deprecated datetime.utcnow()."""
        test_dir = REPO_ROOT / "tests"
        violations = []
        for py_file in test_dir.rglob("*.py"):
            hits = _ast_find_bare_datetime_calls(py_file, "utcnow")
            if hits:
                rel = py_file.relative_to(REPO_ROOT)
                violations.extend(f"{rel}:{h}" for h in hits)

        assert not violations, (
            f"Found {len(violations)} datetime.utcnow() calls in test code. "
            f"Use datetime.now(timezone.utc) instead.\n" + "\n".join(violations)
        )

    def test_no_naive_fromtimestamp_in_production(self):
        """No production file calls datetime.fromtimestamp() without tz arg.

        datetime.fromtimestamp(ts) produces a naive datetime.
        datetime.fromtimestamp(ts, tz=timezone.utc) produces an aware datetime.
        Mixing naive and aware causes TypeError at runtime.
        """
        violations = []
        for py_file in self._get_all_python_files(self.PRODUCTION_DIRS):
            if self._is_excluded(py_file):
                continue
            hits = _ast_find_naive_fromtimestamp(py_file)
            if hits:
                rel = py_file.relative_to(REPO_ROOT)
                violations.extend(f"{rel}:{h}" for h in hits)

        assert not violations, (
            f"Found {len(violations)} naive datetime.fromtimestamp() calls. "
            f"Use datetime.fromtimestamp(ts, tz=timezone.utc) instead.\n" + "\n".join(violations)
        )

    def test_no_aliased_bare_now_in_production(self):
        """No production file uses an aliased datetime.now() call.

        Catches `from datetime import datetime as dt; dt.now()` which
        earlier regex/name-based detectors missed.
        """
        violations = []
        for py_file in self._get_all_python_files(self.PRODUCTION_DIRS):
            if self._is_excluded(py_file):
                continue
            hits = _ast_find_bare_datetime_calls(py_file, "now")
            if hits:
                rel = py_file.relative_to(REPO_ROOT)
                violations.extend(f"{rel}:{h}" for h in hits)

        assert not violations, (
            f"Found {len(violations)} bare datetime.now() calls (including aliased). "
            f"Use datetime.now(timezone.utc) instead.\n" + "\n".join(violations)
        )


class TestNoDeferralPathCaptures:
    """Enforce zero module-level path captures across all production code.

    Uses STRUCTURAL AST detection: checks if any top-level UPPER_CASE
    assignment calls a path-producing function (paths.db_path(),
    google_sa_file(), os.path.join(), project_root(), etc.).

    Not limited to a closed list of variable names — catches any new
    module-level path capture regardless of what name it uses.
    """

    PRODUCTION_DIRS = ["lib", "api", "cli", "engine", "scripts"]

    def test_no_module_level_path_calls_in_production(self):
        """No production file captures a path-producing function at module level.

        Structural: uses AST to detect any top-level UPPER_CASE assignment
        whose RHS calls db_path(), v5_db_path(), google_sa_file(),
        project_root(), os.path.join(), etc.

        This catches patterns that name-based lists miss:
        - DEFAULT_DB = paths.db_path()
        - V5_DB_PATH = paths.v5_db_path()
        - KEY_PATH = os.path.join(os.path.dirname(__file__), ...)
        """
        violations = []

        for dir_name in self.PRODUCTION_DIRS:
            dir_path = REPO_ROOT / dir_name
            if not dir_path.exists():
                continue
            for py_file in dir_path.rglob("*.py"):
                hits = _ast_find_module_level_path_calls(py_file)
                if hits:
                    rel = py_file.relative_to(REPO_ROOT)
                    violations.extend(f"{rel}:{h}" for h in hits)

        assert not violations, (
            f"Found {len(violations)} module-level path captures in production code. "
            f"Use getter functions for runtime resolution.\n" + "\n".join(violations)
        )

    def test_no_module_level_sa_file_in_collectors(self):
        """No collector caches SA_FILE at module level (regex fallback)."""
        collector_dir = REPO_ROOT / "lib" / "collectors"
        violations = []
        for py_file in collector_dir.glob("*.py"):
            content = py_file.read_text()
            for i, line in enumerate(content.split("\n"), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if re.match(r"^SA_FILE\s*=", stripped):
                    rel = py_file.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{i}: {stripped}")

        assert not violations, (
            f"Found module-level SA_FILE in {len(violations)} collector files. "
            f"Use _sa_file() getter for runtime resolution.\n" + "\n".join(violations)
        )

    def test_no_module_level_db_path_in_archives(self):
        """No archive file caches DB_PATH at module level."""
        archive_dirs = [
            REPO_ROOT / "docs" / "archive",
            REPO_ROOT / "_archive",
        ]
        violations = []
        for archive_dir in archive_dirs:
            if not archive_dir.exists():
                continue
            for py_file in archive_dir.rglob("*.py"):
                content = py_file.read_text()
                for i, line in enumerate(content.split("\n"), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if re.match(r"^DB_PATH\s*=", stripped):
                        rel = py_file.relative_to(REPO_ROOT)
                        violations.append(f"{rel}:{i}: {stripped}")

        assert not violations, (
            f"Found module-level DB_PATH in {len(violations)} archive files.\n"
            + "\n".join(violations)
        )
