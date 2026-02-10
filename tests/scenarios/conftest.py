"""
Golden Scenario Test Infrastructure.

Cross-layer behavioral contracts that verify:
- Seed inputs → collector normalization → DB roundtrip → API response → UI mapping
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden"


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for scenario tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Run safety migrations to set up schema
    from lib.safety import run_safety_migrations

    run_safety_migrations(conn)

    yield conn

    conn.close()
    Path(db_path).unlink(missing_ok=True)


def load_golden(name: str) -> dict[str, Any]:
    """Load a golden file by name."""
    path = GOLDEN_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Golden file not found: {path}")
    return json.loads(path.read_text())


def save_golden(name: str, data: dict[str, Any]) -> None:
    """Save data to a golden file."""
    path = GOLDEN_DIR / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")


def compare_golden(name: str, actual: dict[str, Any], update: bool = False) -> None:
    """
    Compare actual output against golden file.

    If update=True, overwrites the golden file instead of comparing.
    """
    if update:
        save_golden(name, actual)
        return

    expected = load_golden(name)

    # Deep comparison with helpful diff
    import difflib

    expected_str = json.dumps(expected, indent=2, sort_keys=True, default=str)
    actual_str = json.dumps(actual, indent=2, sort_keys=True, default=str)

    if expected_str != actual_str:
        diff = difflib.unified_diff(
            expected_str.splitlines(keepends=True),
            actual_str.splitlines(keepends=True),
            fromfile=f"golden/{name}.json",
            tofile="actual",
        )
        diff_str = "".join(diff)
        pytest.fail(
            f"Golden mismatch for {name}.\n"
            f"Update with: make scenarios-update\n"
            f"Or document in docs/scenarios/CHANGELOG.md\n\n"
            f"Diff:\n{diff_str}"
        )
