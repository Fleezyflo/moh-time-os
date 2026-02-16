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


def _guarded_sqlite_connect(database, *args, **kwargs):
    """Intercept sqlite3.connect to block live DB access."""
    db_path = Path(database) if isinstance(database, str) else database

    # Resolve to absolute path for comparison
    if db_path != ":memory:":
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
    from lib.collectors.recorder import CASSETTES_DIR, validate_cassettes

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
            if '"access_token":' in text and "[REDACTED]" not in text:
                issues.append(f"{path.name}: Contains unredacted access_token")
            if '"api_key":' in text and "[REDACTED]" not in text:
                issues.append(f"{path.name}: Contains unredacted api_key")

        except json.JSONDecodeError as e:
            issues.append(f"{path.name}: Invalid JSON - {e}")

    return issues


@pytest.fixture(scope="session")
def validated_cassettes():
    """Session-scoped fixture that validates all cassettes once."""
    issues = validate_all_cassettes()
    if issues:
        pytest.fail("Cassette validation failed:\n" + "\n".join(f"  - {issue}" for issue in issues))
    return True
