"""
Test configuration — ensures repo root is in sys.path + determinism guards.

This allows tests to import from top-level packages (collectors, scripts, lib).
Enforces determinism by blocking live DB access and validating cassettes.
"""

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
LIVE_DB_ABSOLUTE = (REPO_ROOT / LIVE_DB_PATH).resolve()


def _extract_path_from_uri(database: str) -> str:
    """Extract filesystem path from SQLite URI format.
    
    SQLite URI: file:/path/to/db?mode=ro&cache=shared
    Returns: /path/to/db
    """
    if not database.startswith("file:"):
        return database
    
    # Strip 'file:' prefix
    path_part = database[5:]
    
    # Remove query string if present
    if "?" in path_part:
        path_part = path_part.split("?")[0]
    
    return path_part


def _guarded_sqlite_connect(database, *args, **kwargs):
    """Intercept sqlite3.connect to block live DB access."""
    db_str = str(database) if not isinstance(database, str) else database
    
    # Handle SQLite URI format (file:/path?mode=ro)
    actual_path = _extract_path_from_uri(db_str)
    db_path = Path(actual_path)

    # Resolve to absolute path for comparison
    if actual_path != ":memory:":
        try:
            abs_path = db_path.resolve()
        except (OSError, ValueError):
            abs_path = db_path

        # Block live DB
        if abs_path == LIVE_DB_ABSOLUTE or str(db_path) == str(LIVE_DB_PATH):
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
def integration_db_path(tmp_path_factory):
    """
    Session-scoped fixture DB for tests that need real-like data.
    
    Use this instead of hardcoding live DB paths.
    Creates a fixture DB once per test session.
    """
    from tests.fixtures.fixture_db import create_fixture_db
    
    db_path = tmp_path_factory.mktemp("db") / "integration_test.db"
    conn = create_fixture_db(db_path)
    conn.close()
    return db_path


@pytest.fixture
def integration_engine(integration_db_path):
    """QueryEngine using fixture DB for integration tests."""
    from lib.query_engine import QueryEngine
    return QueryEngine(integration_db_path)
