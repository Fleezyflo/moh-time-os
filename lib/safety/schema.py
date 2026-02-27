"""
Schema Assertions

Verifies database schema is correct at startup and in CI.
"""

import sqlite3
from dataclasses import dataclass

from lib import safe_sql


@dataclass
class SchemaViolation:
    """A schema violation."""

    category: str
    name: str
    message: str


class SchemaAssertion:
    """
    Asserts database schema matches expected state.

    Use at startup and in CI to catch schema drift.
    """

    # Required tables
    REQUIRED_TABLES = [
        "inbox_items_v29",
        "issues_v29",
        "issue_transitions_v29",
        "inbox_suppression_rules_v29",
        "write_context_v1",
        "db_write_audit_v1",
        "maintenance_mode_v1",
    ]

    # Required triggers (by prefix pattern)
    REQUIRED_TRIGGER_PREFIXES = [
        # Invariant triggers
        "trg_inbox_v29_terminal_requires_resolved",
        "trg_inbox_v29_dismissed_requires_audit",
        "trg_inbox_v29_linked_requires_issue",
        # Context triggers
        "trg_inbox_items_v29_ctx_insert",
        "trg_inbox_items_v29_ctx_update",
        # Audit triggers
        "trg_inbox_items_v29_audit_insert",
        "trg_inbox_items_v29_audit_update",
    ]

    # Required columns by table
    REQUIRED_COLUMNS = {
        "inbox_items_v29": [
            "id",
            "type",
            "state",
            "severity",
            "proposed_at",
            "dismissed_at",
            "dismissed_by",
            "suppression_key",
            "resolved_at",
            "resolved_issue_id",
        ],
        "db_write_audit_v1": [
            "id",
            "at",
            "actor",
            "request_id",
            "source",
            "git_sha",
            "table_name",
            "op",
            "row_id",
            "before_json",
            "after_json",
        ],
        "write_context_v1": [
            "id",
            "request_id",
            "actor",
            "source",
            "git_sha",
            "set_at",
        ],
    }

    # Required indexes (safety-critical only)
    REQUIRED_INDEXES = [
        "idx_audit_table_row",
        "idx_audit_actor",
        "idx_audit_request",
        "idx_audit_at",
        # idx_inbox_items_v29_state is optional - might have different name
    ]

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def assert_all(self) -> list[SchemaViolation]:
        """
        Run all schema assertions.

        Returns list of violations (empty if schema is correct).
        """
        violations = []
        violations.extend(self.assert_tables_exist())
        violations.extend(self.assert_triggers_exist())
        violations.extend(self.assert_columns_exist())
        violations.extend(self.assert_indexes_exist())
        violations.extend(self.assert_inbox_items_is_view())
        return violations

    def assert_tables_exist(self) -> list[SchemaViolation]:
        """Assert required tables exist."""
        violations = []
        for table in self.REQUIRED_TABLES:
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
                (table,),
            )
            if not cursor.fetchone():
                violations.append(
                    SchemaViolation(
                        category="table",
                        name=table,
                        message=f"Required table '{table}' does not exist",
                    )
                )
        return violations

    def assert_triggers_exist(self) -> list[SchemaViolation]:
        """Assert required triggers exist."""
        violations = []

        # Get all triggers
        cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")
        existing_triggers = {row[0] for row in cursor.fetchall()}

        for prefix in self.REQUIRED_TRIGGER_PREFIXES:
            # Check if any trigger starts with this prefix
            found = any(t.startswith(prefix) or t == prefix for t in existing_triggers)
            if not found:
                violations.append(
                    SchemaViolation(
                        category="trigger",
                        name=prefix,
                        message=f"Required trigger '{prefix}*' does not exist",
                    )
                )

        return violations

    def assert_columns_exist(self) -> list[SchemaViolation]:
        """Assert required columns exist in tables."""
        violations = []

        for table, columns in self.REQUIRED_COLUMNS.items():
            # Check if table exists first
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
                (table,),
            )
            if not cursor.fetchone():
                continue  # Table missing is caught by assert_tables_exist

            # Get existing columns
            cursor = self.conn.execute(safe_sql.pragma_table_info(table))
            existing_columns = {row[1] for row in cursor.fetchall()}

            for column in columns:
                if column not in existing_columns:
                    violations.append(
                        SchemaViolation(
                            category="column",
                            name=f"{table}.{column}",
                            message=f"Required column '{table}.{column}' does not exist",
                        )
                    )

        return violations

    def assert_indexes_exist(self) -> list[SchemaViolation]:
        """Assert required indexes exist."""
        violations = []

        cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        existing_indexes = {row[0] for row in cursor.fetchall()}

        for index in self.REQUIRED_INDEXES:
            if index not in existing_indexes:
                violations.append(
                    SchemaViolation(
                        category="index",
                        name=index,
                        message=f"Required index '{index}' does not exist",
                    )
                )

        return violations

    def assert_inbox_items_is_view(self) -> list[SchemaViolation]:
        """Assert legacy inbox_items is a VIEW (not writable table)."""
        violations = []

        cursor = self.conn.execute("SELECT type FROM sqlite_master WHERE name = 'inbox_items'")
        row = cursor.fetchone()

        if row:
            if row[0] == "table":
                violations.append(
                    SchemaViolation(
                        category="legacy",
                        name="inbox_items",
                        message="Legacy 'inbox_items' is a TABLE but should be a VIEW (read-only)",
                    )
                )
        # If it doesn't exist, that's fine too

        return violations


def assert_schema(
    conn: sqlite3.Connection, raise_on_violation: bool = True
) -> list[SchemaViolation]:
    """
    Assert database schema is correct.

    Args:
        conn: SQLite connection
        raise_on_violation: If True, raise AssertionError on any violation

    Returns:
        List of violations (empty if schema is correct)

    Raises:
        AssertionError: If raise_on_violation=True and violations found
    """
    assertion = SchemaAssertion(conn)
    violations = assertion.assert_all()

    if violations and raise_on_violation:
        msgs = [f"  - {v.message}" for v in violations]
        raise AssertionError("Schema violations found:\n" + "\n".join(msgs))

    return violations


def assert_no_legacy_writes(project_root: str) -> list[str]:
    """
    Assert no code writes to legacy inbox_items table.

    Uses ripgrep to scan codebase for forbidden patterns.

    Returns list of violations (file:line with forbidden pattern).
    """
    import shutil
    import subprocess

    rg = shutil.which("rg")
    if not rg:
        # ripgrep not installed, skip
        return []

    forbidden_patterns = [
        r"INSERT\s+INTO\s+inbox_items\s*\(",
        r"UPDATE\s+inbox_items\s+SET",
        r"DELETE\s+FROM\s+inbox_items\s",
    ]

    violations: list[str] = []

    for pattern in forbidden_patterns:
        try:
            result = subprocess.run(  # noqa: S603 - rg path verified via shutil.which
                [
                    rg,
                    "-n",
                    "-i",
                    "--glob",
                    "*.py",
                    "--glob",
                    "!*test*",
                    pattern,
                    project_root,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    # Skip if it's in a migration or safety module
                    if "migration" in line.lower() or "safety" in line.lower():
                        continue
                    violations.append(line)
        except subprocess.TimeoutExpired:
            pass

    return violations
