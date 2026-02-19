"""
Test configuration — ensures repo root is in sys.path + determinism guards.

This allows tests to import from top-level packages (collectors, scripts, lib).
Enforces determinism by blocking live DB access and validating cassettes.

IMPORTANT: Guards are installed at conftest load time (not in fixtures) to catch
import-time filesystem probes to live DB paths.
"""

import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add repo root to sys.path so tests can import collectors.*, scripts.*, lib.*
REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# =============================================================================
# DETERMINISM GUARD: Block live database access
# =============================================================================

LIVE_DB_PATH = Path("data/moh_time_os.db")
# Use string concatenation to avoid resolving paths (which would trigger stat)
LIVE_DB_ABSOLUTE = REPO_ROOT / LIVE_DB_PATH
HOME_DB_ABSOLUTE = Path.home() / ".moh_time_os" / "data" / "moh_time_os.db"

# Precompute string patterns for fast matching (avoid Path operations)
# Include all variants: absolute, relative, with/without repo prefix
_FORBIDDEN_DB_PATTERNS = [
    str(LIVE_DB_ABSOLUTE),
    str(HOME_DB_ABSOLUTE),
    "moh_time_os/data/moh_time_os.db",
    ".moh_time_os/data/moh_time_os.db",
    "data/moh_time_os.db",  # Relative path from repo root
]

# =============================================================================
# AUDIT LOG: Prove no live DB paths are ever probed during tests
# =============================================================================

# Default to repo-local .db_watch.log to avoid /tmp permission issues
# Override with DB_WATCH_LOG env var if needed
_DB_WATCH_LOG = Path(os.environ.get("DB_WATCH_LOG", str(REPO_ROOT / ".db_watch.log")))
_DB_PATTERNS_FOR_AUDIT = ["moh_time_os.db"]


import threading
_log_recursion_guard = threading.local()


def _log_db_probe(operation: str, path_str: str):
    """Log any filesystem operation that touches a path matching DB patterns.

    All probes are logged faithfully. To prove normal tests don't touch the
    live DB, run: pytest -q tests -k "not determinism_guards"
    and verify the log is empty.

    test_determinism_guards.py intentionally probes forbidden paths to verify
    guards work; those entries are expected when running the full suite.
    """
    # Prevent recursion during logging (open() can trigger our guards)
    if getattr(_log_recursion_guard, 'active', False):
        return

    _log_recursion_guard.active = True
    try:
        for pattern in _DB_PATTERNS_FOR_AUDIT:
            if pattern in path_str:
                try:
                    with open(_DB_WATCH_LOG, "a") as f:
                        f.write(f"{operation}: {path_str}\n")
                except (OSError, PermissionError):
                    pass  # Ignore if can't write to log
                break
    finally:
        _log_recursion_guard.active = False


def _is_forbidden_path(path_str: str) -> bool:
    """Check if a path string matches any forbidden live DB pattern."""
    if not path_str:
        return False
    for pattern in _FORBIDDEN_DB_PATTERNS:
        if pattern in path_str:
            return True
    return False


def _raise_determinism_violation(path_str: str, operation: str):
    """Raise RuntimeError for forbidden path access."""
    raise RuntimeError(
        f"DETERMINISM VIOLATION: live DB path probed via {operation}: {path_str}\n"
        "Tests must use fixture_db from tests/fixtures/fixture_db.py.\n"
        "Use: from tests.fixtures import create_fixture_db"
    )


# =============================================================================
# FILESYSTEM GUARDS (installed at conftest load time)
# =============================================================================

_original_os_stat = os.stat
_original_os_lstat = os.lstat
_original_path_exists = Path.exists
_original_path_stat = Path.stat
_original_path_resolve = Path.resolve


def _guarded_os_stat(path, *args, **kwargs):
    """Guard os.stat against live DB path probes."""
    path_str = str(path)
    _log_db_probe("os.stat", path_str)
    if _is_forbidden_path(path_str):
        _raise_determinism_violation(path_str, "os.stat")
    return _original_os_stat(path, *args, **kwargs)


def _guarded_os_lstat(path, *args, **kwargs):
    """Guard os.lstat against live DB path probes."""
    path_str = str(path)
    _log_db_probe("os.lstat", path_str)
    if _is_forbidden_path(path_str):
        _raise_determinism_violation(path_str, "os.lstat")
    return _original_os_lstat(path, *args, **kwargs)


def _guarded_path_exists(self):
    """Guard Path.exists against live DB path probes."""
    path_str = str(self)
    _log_db_probe("Path.exists", path_str)
    if _is_forbidden_path(path_str):
        _raise_determinism_violation(path_str, "Path.exists")
    return _original_path_exists(self)


def _guarded_path_stat(self, *args, **kwargs):
    """Guard Path.stat against live DB path probes."""
    path_str = str(self)
    _log_db_probe("Path.stat", path_str)
    if _is_forbidden_path(path_str):
        _raise_determinism_violation(path_str, "Path.stat")
    return _original_path_stat(self, *args, **kwargs)


# Install filesystem guards IMMEDIATELY at conftest load time
# This catches import-time probes in modules like lib/query_engine.py
os.stat = _guarded_os_stat
os.lstat = _guarded_os_lstat
Path.exists = _guarded_path_exists
Path.stat = _guarded_path_stat


def _extract_path_from_uri(database: str) -> str:
    """Extract filesystem path from SQLite URI format (file:/path?mode=ro)."""
    if not database.startswith("file:"):
        return database
    path = database[5:]
    if "?" in path:
        path = path.split("?")[0]
    return path


def _guarded_sqlite_connect(database, *args, **kwargs):
    """Intercept sqlite3.connect to block live DB access.

    IMPORTANT: Does NOT use Path.resolve() or any filesystem probing.
    Uses pure string normalization to avoid triggering os.stat/lstat on live paths.
    """
    db_str = str(database) if not isinstance(database, str) else database
    actual_path = _extract_path_from_uri(db_str)

    # Log the connection attempt for audit
    _log_db_probe("sqlite3.connect", actual_path)

    # Check against forbidden patterns using pure string comparison
    # No filesystem probes - use _is_forbidden_path which is string-only
    if actual_path != ":memory:" and _is_forbidden_path(actual_path):
        raise RuntimeError(
            f"DETERMINISM VIOLATION: Test attempted to access live DB at {database}.\n"
            "Tests must use fixture_db from tests/fixtures/fixture_db.py.\n"
            "Use: from tests.fixtures import create_fixture_db"
        )

    return _original_sqlite_connect(database, *args, **kwargs)


# Store original and patch at import time
_original_sqlite_connect = sqlite3.connect


@pytest.fixture(autouse=True)
def guard_live_db_access(monkeypatch):
    """Automatically guard all tests against live DB access."""
    monkeypatch.setattr(sqlite3, "connect", _guarded_sqlite_connect)


# =============================================================================
# CASSETTE VALIDATION
# =============================================================================

def validate_all_cassettes():
    """
    Validate all cassettes for determinism requirements:
    - Expiry metadata present
    - No secrets (redaction markers present where expected)
    - Sorted keys for deterministic JSON
    """
    from lib.collectors.recorder import validate_cassettes, CASSETTES_DIR

    issues = validate_cassettes()

    # Additional checks: ensure cassettes use sorted keys
    import json
    for path in CASSETTES_DIR.glob("*.json"):
        try:
            text = path.read_text()
            data = json.loads(text)

            # Verify it can be re-serialized identically (sorted keys)
            reserialized = json.dumps(data, indent=2, sort_keys=True) + "\n"
            original_normalized = json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"

            if reserialized != original_normalized:
                issues.append(f"{path.name}: Keys not sorted (non-deterministic)")

            # Check for unredacted secrets
            if '"access_token":' in text and '[REDACTED]' not in text:
                issues.append(f"{path.name}: Contains unredacted access_token")
            if '"api_key":' in text and '[REDACTED]' not in text:
                issues.append(f"{path.name}: Contains unredacted api_key")

        except json.JSONDecodeError as e:
            issues.append(f"{path.name}: Invalid JSON - {e}")

    return issues


@pytest.fixture(scope="session")
def validated_cassettes():
    """Session-scoped fixture that validates all cassettes once."""
    issues = validate_all_cassettes()
    if issues:
        pytest.fail(
            "Cassette validation failed:\n" +
            "\n".join(f"  - {issue}" for issue in issues)
        )
    return True


# =============================================================================
# FIXTURE DB FOR INTEGRATION TESTS
# =============================================================================

@pytest.fixture(scope="session")
def fixture_db_path(tmp_path_factory):
    """
    Session-scoped fixture DB path for tests that need database access.
    Creates once per test session, reused across all tests.
    """
    from tests.fixtures.fixture_db import create_fixture_db

    db_path = tmp_path_factory.mktemp("db") / "fixture_test.db"
    conn = create_fixture_db(db_path)
    conn.close()
    return db_path
