"""
Integration Tests — Full Lifecycle Flows

Tests end-to-end flows through the spec modules.
"""

import contextlib
import json
import sqlite3
from datetime import timedelta
from uuid import uuid4

from lib.ui_spec_v21.inbox_lifecycle import InboxLifecycleManager
from lib.ui_spec_v21.issue_lifecycle import IssueLifecycleManager
from lib.ui_spec_v21.migrations import run_migrations
from lib.ui_spec_v21.time_utils import from_iso, now_iso, to_iso


def create_test_db():
    """Create in-memory test database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    run_migrations(conn, verbose=False)

    # Create supporting tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS brands (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS engagements (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            brand_id TEXT,
            name TEXT NOT NULL,
            type TEXT,
            state TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            number TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'AED',
            issue_date TEXT,
            due_date TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS team_members (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
    """)

    # Add v2.9 columns to issues table if not present
    try:
        conn.execute("ALTER TABLE issues ADD COLUMN regression_watch_until TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("ALTER TABLE issues ADD COLUMN suppressed INTEGER DEFAULT 0")

    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("ALTER TABLE issues ADD COLUMN tagged_by_user_id TEXT")

    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("ALTER TABLE issues ADD COLUMN tagged_at TEXT")

    return conn


def seed_test_data(conn):
    """Seed basic test data."""
    now = now_iso()

    # Client
    conn.execute(
        """
        INSERT INTO clients (id, name, tier, created_at, updated_at)
        VALUES ('client_1', 'Acme Corp', 'gold', ?, ?)
    """,
        (now, now),
    )

    # Team member
    conn.execute("""
        INSERT INTO team_members (id, name) VALUES ('user_1', 'Test User')
    """)

    conn.commit()


# ==============================================================================
# Integration Test: Inbox → Issue → Resolve Flow
# ==============================================================================


def test_integration_inbox_to_issue_resolve():
    """
    Full flow:
    1. Create issue
    2. Create inbox item for issue
    3. User tags the inbox item (links to issue)
    4. User resolves the issue
    5. Verify: issue in regression_watch, inbox item archived
    """
    conn = create_test_db()
    seed_test_data(conn)

    now = now_iso()
    issue_id = str(uuid4())
    inbox_id = str(uuid4())

    # Step 1: Create issue in surfaced state
    evidence = json.dumps(
        {
            "version": "v1",
            "kind": "invoice",
            "url": None,
            "display_text": "INV-001 overdue",
            "source_system": "xero",
            "source_id": "inv_123",
            "payload": {
                "number": "INV-001",
                "amount": 10000,
                "currency": "AED",
                "status": "overdue",
            },
        }
    )

    conn.execute(
        """
        INSERT INTO issues (
            id, type, state, severity, client_id, title, evidence,
            evidence_version, created_at, updated_at
        ) VALUES (?, 'financial', 'surfaced', 'high', 'client_1',
                  'Invoice overdue', ?, 'v1', ?, ?)
    """,
        (issue_id, evidence, now, now),
    )

    # Step 2: Create inbox item pointing to issue
    conn.execute(
        """
        INSERT INTO inbox_items (
            id, type, state, severity, proposed_at, title, evidence,
            evidence_version, underlying_issue_id, client_id, created_at, updated_at
        ) VALUES (?, 'issue', 'proposed', 'high', ?, 'Invoice overdue', ?,
                  'v1', ?, 'client_1', ?, ?)
    """,
        (inbox_id, now, evidence, issue_id, now, now),
    )
    conn.commit()

    # Step 3: User tags the inbox item
    inbox_lifecycle = InboxLifecycleManager(conn)
    result = inbox_lifecycle.execute_action(inbox_id, "tag", {}, "user_1")
    conn.commit()

    assert result.success, f"Tag action failed: {result.error}"
    assert result.inbox_item_state == "linked_to_issue"

    # Verify inbox item is now terminal
    cursor = conn.execute("SELECT state FROM inbox_items WHERE id = ?", (inbox_id,))
    row = cursor.fetchone()
    assert row["state"] == "linked_to_issue"

    # Verify issue was tagged
    cursor = conn.execute(
        "SELECT tagged_by_user_id, tagged_at FROM issues WHERE id = ?", (issue_id,)
    )
    row = cursor.fetchone()
    assert row["tagged_by_user_id"] == "user_1"
    assert row["tagged_at"] is not None

    # Step 4: User resolves the issue
    issue_lifecycle = IssueLifecycleManager(conn)
    success, error = issue_lifecycle.transition(
        issue_id, "resolve", "user_1", {"note": "Payment received"}
    )
    conn.commit()

    assert success, f"Resolve failed: {error}"

    # Step 5: Verify issue is in regression_watch (NOT resolved)
    cursor = conn.execute(
        "SELECT state, regression_watch_until FROM issues WHERE id = ?", (issue_id,)
    )
    row = cursor.fetchone()
    assert (
        row["state"] == "regression_watch"
    ), f"Expected regression_watch, got {row['state']}"
    assert row["regression_watch_until"] is not None

    # Verify regression_watch_until is ~90 days in future
    watch_until = from_iso(row["regression_watch_until"])
    expected = from_iso(now) + timedelta(days=90)
    delta = abs((watch_until - expected).total_seconds())
    assert delta < 60, f"regression_watch_until off by {delta} seconds"

    # Verify transition audit trail
    cursor = conn.execute(
        """
        SELECT previous_state, new_state, transition_reason
        FROM issue_transitions
        WHERE issue_id = ?
        ORDER BY transitioned_at
    """,
        (issue_id,),
    )
    transitions = cursor.fetchall()

    # Should have: surfaced→resolved (user), resolved→regression_watch (system)
    assert len(transitions) >= 2

    print("✓ Integration test: inbox → issue → resolve PASSED")
    conn.close()


# ==============================================================================
# Integration Test: Snooze Expiry Flow
# ==============================================================================


def test_integration_snooze_expiry():
    """
    Flow:
    1. Create inbox item
    2. Snooze it for 1 day
    3. Advance time past snooze_until
    4. Run snooze expiry job
    5. Verify: item back to proposed, resurfaced_at set
    """
    conn = create_test_db()
    seed_test_data(conn)

    # Create inbox item
    inbox_id = str(uuid4())
    now = now_iso()
    evidence = json.dumps(
        {
            "version": "v1",
            "kind": "invoice",
            "url": None,
            "display_text": "Test",
            "source_system": "xero",
            "source_id": "test",
            "payload": {
                "number": "1",
                "amount": 100,
                "currency": "AED",
                "status": "sent",
            },
        }
    )

    # Insert as proposed
    conn.execute(
        """
        INSERT INTO inbox_items (
            id, type, state, severity, proposed_at, title, evidence,
            evidence_version, underlying_signal_id, client_id, created_at, updated_at
        ) VALUES (?, 'flagged_signal', 'proposed', 'medium', ?, 'Test signal', ?,
                  'v1', 'signal_1', 'client_1', ?, ?)
    """,
        (inbox_id, now, evidence, now, now),
    )
    conn.commit()

    # Snooze for 1 day
    inbox_lifecycle = InboxLifecycleManager(conn)
    result = inbox_lifecycle.execute_action(
        inbox_id, "snooze", {"snooze_days": 1}, "user_1"
    )
    conn.commit()

    assert result.success
    assert result.inbox_item_state == "snoozed"

    # Manually set snooze_until to past
    past_time = to_iso(from_iso(now) - timedelta(hours=1))
    conn.execute(
        "UPDATE inbox_items SET snooze_until = ? WHERE id = ?", (past_time, inbox_id)
    )
    conn.commit()

    # Run snooze expiry
    count = inbox_lifecycle.process_snooze_expiry()
    conn.commit()

    assert count == 1, f"Expected 1 item to resurface, got {count}"

    # Verify state and resurfaced_at
    cursor = conn.execute(
        "SELECT state, resurfaced_at FROM inbox_items WHERE id = ?", (inbox_id,)
    )
    row = cursor.fetchone()
    assert row["state"] == "proposed"
    assert row["resurfaced_at"] is not None

    print("✓ Integration test: snooze expiry PASSED")
    conn.close()


# ==============================================================================
# Integration Test: Dismiss Creates Suppression
# ==============================================================================


def test_integration_dismiss_suppression():
    """
    Flow:
    1. Create issue and inbox item
    2. Dismiss inbox item
    3. Verify: suppression rule created, issue suppressed
    4. Create new inbox item for same issue
    5. Verify: should be blocked by suppression
    """
    conn = create_test_db()
    seed_test_data(conn)

    now = now_iso()
    issue_id = str(uuid4())
    inbox_id = str(uuid4())

    evidence = json.dumps(
        {
            "version": "v1",
            "kind": "invoice",
            "url": None,
            "display_text": "Test",
            "source_system": "xero",
            "source_id": "inv_456",
            "payload": {
                "number": "INV-002",
                "amount": 5000,
                "currency": "AED",
                "status": "overdue",
            },
        }
    )

    # Create issue
    conn.execute(
        """
        INSERT INTO issues (
            id, type, state, severity, client_id, title, evidence,
            evidence_version, created_at, updated_at
        ) VALUES (?, 'financial', 'surfaced', 'medium', 'client_1',
                  'Invoice overdue', ?, 'v1', ?, ?)
    """,
        (issue_id, evidence, now, now),
    )

    # Create inbox item
    conn.execute(
        """
        INSERT INTO inbox_items (
            id, type, state, severity, proposed_at, title, evidence,
            evidence_version, underlying_issue_id, client_id, created_at, updated_at
        ) VALUES (?, 'issue', 'proposed', 'medium', ?, 'Invoice overdue', ?,
                  'v1', ?, 'client_1', ?, ?)
    """,
        (inbox_id, now, evidence, issue_id, now, now),
    )
    conn.commit()

    # Dismiss
    inbox_lifecycle = InboxLifecycleManager(conn)
    result = inbox_lifecycle.execute_action(
        inbox_id, "dismiss", {"note": "Known issue, will address next month"}, "user_1"
    )
    conn.commit()

    assert result.success, f"Dismiss failed: {result.error}"
    assert result.inbox_item_state == "dismissed"
    assert result.suppression_key is not None

    # Verify suppression rule exists
    cursor = conn.execute(
        """
        SELECT * FROM inbox_suppression_rules WHERE suppression_key = ?
    """,
        (result.suppression_key,),
    )
    rule = cursor.fetchone()
    assert rule is not None

    # Verify issue is suppressed
    cursor = conn.execute("SELECT suppressed FROM issues WHERE id = ?", (issue_id,))
    row = cursor.fetchone()
    assert row["suppressed"] == 1

    print("✓ Integration test: dismiss suppression PASSED")
    conn.close()


# ==============================================================================
# Integration Test: Regression Detection
# ==============================================================================


def test_integration_regression_watch_expiry():
    """
    Flow:
    1. Create issue in regression_watch with expired watch period
    2. Run regression watch job
    3. Verify: issue transitions to closed
    """
    conn = create_test_db()
    seed_test_data(conn)

    now = now_iso()
    issue_id = str(uuid4())

    # Create issue already in regression_watch with expired watch
    past_watch = to_iso(from_iso(now) - timedelta(days=1))
    evidence = json.dumps(
        {
            "version": "v1",
            "kind": "invoice",
            "url": None,
            "display_text": "Test",
            "source_system": "xero",
            "source_id": "test",
            "payload": {
                "number": "1",
                "amount": 100,
                "currency": "AED",
                "status": "paid",
            },
        }
    )

    conn.execute(
        """
        INSERT INTO issues (
            id, type, state, severity, client_id, title, evidence,
            evidence_version, regression_watch_until, created_at, updated_at
        ) VALUES (?, 'financial', 'regression_watch', 'medium', 'client_1',
                  'Test issue', ?, 'v1', ?, ?, ?)
    """,
        (issue_id, evidence, past_watch, now, now),
    )
    conn.commit()

    # Run regression watch job
    issue_lifecycle = IssueLifecycleManager(conn)
    closed_count, regressed_count = issue_lifecycle.process_regression_watch()
    conn.commit()

    assert closed_count == 1, f"Expected 1 closed, got {closed_count}"

    # Verify state is closed
    cursor = conn.execute("SELECT state FROM issues WHERE id = ?", (issue_id,))
    row = cursor.fetchone()
    assert row["state"] == "closed"

    print("✓ Integration test: regression watch expiry PASSED")
    conn.close()


# ==============================================================================
# Run all integration tests
# ==============================================================================


def run_all():
    """Run all integration tests."""
    print("\n=== Running Integration Tests ===\n")

    test_integration_inbox_to_issue_resolve()
    test_integration_snooze_expiry()
    test_integration_dismiss_suppression()
    test_integration_regression_watch_expiry()

    print("\n=== All Integration Tests PASSED ===\n")


if __name__ == "__main__":
    run_all()
