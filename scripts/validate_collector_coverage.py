#!/usr/bin/env python3
"""
Collector Coverage Audit & Validation Script (CS-6.1)

Validates that all collector expansions are properly implemented:
- All 21 new tables exist
- All new columns exist on existing tables
- Resilience module is wired into base collector
- All 5 collectors have expanded capabilities

Exit code: 0 if all checks pass, 1 if any fail
"""

import sqlite3
import sys
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.db import get_connection, run_startup_migrations, table_exists


def check_tables_exist() -> bool:
    """Verify all 21 new tables exist in the database."""
    print("\n1. Checking new tables exist...")

    new_tables = [
        "asana_custom_fields",
        "asana_subtasks",
        "asana_sections",
        "asana_stories",
        "asana_task_dependencies",
        "asana_portfolios",
        "asana_goals",
        "asana_attachments",
        "gmail_participants",
        "gmail_attachments",
        "gmail_labels",
        "calendar_attendees",
        "calendar_recurrence_rules",
        "chat_reactions",
        "chat_attachments",
        "chat_space_metadata",
        "chat_space_members",
        "xero_line_items",
        "xero_contacts",
        "xero_credit_notes",
        "xero_bank_transactions",
        "xero_tax_rates",
    ]

    run_startup_migrations()
    all_exist = True

    with get_connection() as conn:
        for table in new_tables:
            exists = table_exists(conn, table)
            status = "✅" if exists else "❌"
            print(f"   {status} {table}")
            if not exists:
                all_exist = False

    return all_exist


def check_new_columns() -> bool:
    """Verify new columns exist on expanded tables."""
    print("\n2. Checking new columns on expanded tables...")

    table_columns = {
        "communications": [
            "is_read",
            "is_starred",
            "importance",
            "has_attachments",
            "attachment_count",
            "label_ids",
        ],
        "tasks": [
            "section_id",
            "section_name",
            "subtask_count",
            "has_dependencies",
            "attachment_count",
            "story_count",
            "custom_fields_json",
        ],
        "chat_messages": [
            "thread_id",
            "thread_reply_count",
            "reaction_count",
            "has_attachment",
            "attachment_count",
        ],
    }

    all_exist = True
    sqlite3.connect(":memory:")

    # Get real connection
    with get_connection() as real_conn:
        for table, expected_cols in table_columns.items():
            actual = [r[1] for r in real_conn.execute(f"PRAGMA table_info({table})").fetchall()]
            print(f"   {table}:")
            for col in expected_cols:
                status = "✅" if col in actual else "❌"
                print(f"      {status} {col}")
                if col not in actual:
                    all_exist = False

    return all_exist


def check_resilience_infrastructure() -> bool:
    """Verify resilience module exists and is imported in base."""
    print("\n3. Checking resilience infrastructure...")

    resilience_path = REPO_ROOT / "lib" / "collectors" / "resilience.py"
    base_path = REPO_ROOT / "lib" / "collectors" / "base.py"

    # Check resilience.py exists
    if not resilience_path.exists():
        print(f"   ❌ {resilience_path} does not exist")
        return False
    print("   ✅ resilience.py exists")

    # Check base.py imports from resilience
    base_content = base_path.read_text()
    if (
        "from .resilience import" not in base_content
        and "from lib.collectors.resilience import" not in base_content
    ):
        print("   ❌ base.py does not import from resilience")
        return False
    print("   ✅ base.py imports resilience module")

    # Check for required classes in resilience.py
    resilience_content = resilience_path.read_text()
    required_classes = ["CircuitBreaker", "RetryConfig", "RateLimiter", "retry_with_backoff"]
    all_found = True
    for cls in required_classes:
        if cls in resilience_content:
            print(f"   ✅ {cls} defined in resilience.py")
        else:
            print(f"   ❌ {cls} not found in resilience.py")
            all_found = False

    return all_found


def check_collector_expansions() -> bool:
    """Verify all 5 collectors have expanded sync methods."""
    print("\n4. Checking collector expansions...")

    collectors = {
        "asana": "lib/collectors/asana.py",
        "gmail": "lib/collectors/gmail.py",
        "calendar": "lib/collectors/calendar.py",
        "chat": "lib/collectors/chat.py",
        "xero": "lib/collectors/xero.py",
    }

    all_expanded = True
    for name, path in collectors.items():
        collector_path = REPO_ROOT / path
        if not collector_path.exists():
            print(f"   ❌ {name}: {path} does not exist")
            all_expanded = False
            continue

        content = collector_path.read_text()

        # Check for sync method override
        if "def sync(self)" in content:
            print(f"   ✅ {name}: has sync() override")
        else:
            print(f"   ❌ {name}: missing sync() override")
            all_expanded = False

    return all_expanded


def main():
    """Run all validation checks."""
    print("=" * 70)
    print("Collector Coverage Audit & Validation (CS-6.1)")
    print("=" * 70)

    checks = [
        ("New tables exist", check_tables_exist),
        ("New columns exist", check_new_columns),
        ("Resilience infrastructure", check_resilience_infrastructure),
        ("Collector expansions", check_collector_expansions),
    ]

    results = []
    for name, check_fn in checks:
        try:
            passed = check_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ {name}: FAILED with exception: {e}")
            results.append((name, False))

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n🎉 All checks passed!")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please review above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
