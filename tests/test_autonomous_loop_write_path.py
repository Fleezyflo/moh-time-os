"""Write-path migration tests for lib/autonomous_loop.py.

The daemon's _process_commitment_truth marks processed emails with an UPDATE.
That write was routed through store.query() (a read-only method once the
StateStore guard lands). These tests pin the migration to store.execute_write():

- Structural: the module marks emails processed via execute_write, not query().
- Behavioral: the UPDATE actually persists (email flips processed 0 -> 1) using a
  real temp-DB StateStore, so the test goes red if the write path ever breaks.
"""

import inspect
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from lib.autonomous_loop import AutonomousLoop
from lib.state_store import StateStore


def test_S_mark_processed_uses_execute_write():
    """[S] _process_commitment_truth marks emails processed via execute_write()."""
    source = inspect.getsource(AutonomousLoop._process_commitment_truth)
    assert "execute_write" in source, (
        "_process_commitment_truth must mark emails processed via store.execute_write()"
    )
    assert "UPDATE communications" in source, "expected the processed-email UPDATE to remain"
    # The UPDATE must not be routed through the read-only query() method.
    assert ".query(\n" not in source and 'query("UPDATE' not in source, (
        "the processed-email UPDATE must not run through store.query()"
    )


@pytest.fixture
def real_store_loop():
    """AutonomousLoop with heavy deps mocked but a REAL temp-DB StateStore."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_file = f.name

    StateStore._instance = None
    store = StateStore(db_file)
    store.execute_write(
        """CREATE TABLE communications (
            id TEXT PRIMARY KEY,
            source TEXT,
            subject TEXT,
            snippet TEXT,
            from_email TEXT,
            processed INTEGER DEFAULT 0,
            created_at TEXT
        )"""
    )

    with (
        patch("lib.autonomous_loop.get_store", return_value=store),
        patch("lib.autonomous_loop.CollectorOrchestrator"),
        patch("lib.autonomous_loop.AnalyzerOrchestrator"),
        patch("lib.autonomous_loop.get_governance"),
        patch("lib.autonomous_loop.ReasonerEngine"),
        patch("lib.autonomous_loop.ExecutorEngine"),
        patch("lib.autonomous_loop.NotificationEngine"),
        patch.object(AutonomousLoop, "_load_notification_config", return_value={}),
    ):
        loop = AutonomousLoop(config_path=f"{tempfile.gettempdir()}/test_config")
        loop.store = store
        yield loop, store

    StateStore._instance = None
    Path(db_file).unlink(missing_ok=True)


def test_B_mark_processed_persists_update(real_store_loop):
    """[B] _process_commitment_truth flips a recent unprocessed email to processed=1."""
    loop, store = real_store_loop
    store.execute_write(
        "INSERT INTO communications (id, source, subject, snippet, from_email, processed, created_at) "
        "VALUES (?, 'email', 'hi', 'no commitments here', 'a@b.com', 0, datetime('now'))",
        ["email-1"],
    )

    # CommitmentManager extraction is irrelevant to the write under test; stub it to
    # return no commitments so the only DB mutation is the processed-flag UPDATE.
    fake_manager = Mock()
    fake_manager.extract_commitments_from_email.return_value = []
    fake_manager.get_untracked_commitments.return_value = []
    with patch("lib.commitment_truth.CommitmentManager", return_value=fake_manager):
        result = loop._process_commitment_truth()

    assert "error" not in result, f"unexpected error: {result.get('error')}"
    assert result["emails_processed"] == 1
    rows = store.query("SELECT processed FROM communications WHERE id = 'email-1'")
    assert rows[0]["processed"] == 1, "email was not marked processed (write path broken)"


def test_B_mark_processed_skips_already_processed(real_store_loop):
    """[B] An already-processed email is not re-selected (processed=0 filter holds)."""
    loop, store = real_store_loop
    store.execute_write(
        "INSERT INTO communications (id, source, subject, snippet, from_email, processed, created_at) "
        "VALUES (?, 'email', 'done', '', 'a@b.com', 1, datetime('now'))",
        ["email-done"],
    )

    fake_manager = Mock()
    fake_manager.extract_commitments_from_email.return_value = []
    fake_manager.get_untracked_commitments.return_value = []
    with patch("lib.commitment_truth.CommitmentManager", return_value=fake_manager):
        result = loop._process_commitment_truth()

    assert result["emails_processed"] == 0
    # raw read just to prove nothing flipped it back
    conn = sqlite3.connect(store.db_path)
    try:
        val = conn.execute(
            "SELECT processed FROM communications WHERE id = 'email-done'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert val == 1
