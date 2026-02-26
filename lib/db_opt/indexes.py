"""
Index Management — Create Performance-Critical Indexes

Provides:
- ensure_indexes(db_path): Creates all indexes idempotently
- IndexReport: Tracks created, existing, and failed indexes

All indexes use CREATE INDEX IF NOT EXISTS for idempotent operation.
Can be called multiple times without errors or duplicates.
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class IndexReport:
    """Report of index creation results."""

    created: list[str] = field(default_factory=list)
    already_existed: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    total_checked: int = 0

    def add_success(self, index_name: str, was_new: bool = True) -> None:
        """Record successful index creation or existing."""
        if was_new:
            self.created.append(index_name)
        else:
            self.already_existed.append(index_name)

    def add_error(self, index_name: str, error: str) -> None:
        """Record index creation error."""
        self.errors.append({"index": index_name, "error": error})

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "created": len(self.created),
            "already_existed": len(self.already_existed),
            "errors": len(self.errors),
            "total_checked": self.total_checked,
            "created_names": self.created,
            "error_details": self.errors,
        }


# Critical indexes for performance
PERFORMANCE_INDEXES = [
    # Projects table
    ("projects", ["client_id"]),
    ("projects", ["status"]),
    ("projects", ["brand_id"]),
    ("projects", ["client_id", "status"]),
    # Tasks table
    ("tasks", ["project_id"]),
    ("tasks", ["assignee_id"]),
    ("tasks", ["status"]),
    ("tasks", ["due_date"]),
    ("tasks", ["project_id", "status"]),
    ("tasks", ["assignee_id", "status"]),
    # Invoices table
    ("invoices", ["client_id"]),
    ("invoices", ["status"]),
    ("invoices", ["due_date"]),
    ("invoices", ["client_id", "status"]),
    # Communications table
    ("communications", ["client_id"]),
    ("communications", ["sent_at"]),
    ("communications", ["from_domain"]),
    ("communications", ["client_id", "sent_at"]),
    # Signals table
    ("signals", ["severity"]),
    ("signals", ["status"]),
    ("signals", ["created_at"]),
    ("signals", ["severity", "status"]),
    # Resolution queue
    ("resolution_queue", ["status"]),
    ("resolution_queue", ["created_at"]),
    ("resolution_queue", ["status", "created_at"]),
    # Time blocks
    ("time_blocks", ["date"]),
    ("time_blocks", ["person_id"]),
    ("time_blocks", ["date", "person_id"]),
    # Commitments
    ("commitments", ["due_at"]),
    ("commitments", ["status"]),
    ("commitments", ["due_at", "status"]),
    # Entity links (composite indexes for common joins)
    ("entity_links", ["source_type", "source_id"]),
    ("entity_links", ["target_type", "target_id"]),
    ("entity_links", ["source_type", "source_id", "target_type"]),
    # Issues/Engagements
    ("issues", ["client_id"]),
    ("issues", ["state"]),
    ("issues", ["severity"]),
    ("issues", ["client_id", "state"]),
    ("engagements", ["client_id"]),
    ("engagements", ["state"]),
    ("engagements", ["client_id", "state"]),
    # People table
    ("people", ["type"]),
    ("people", ["client_id"]),
    # Signals v29
    ("signals_v29", ["client_id"]),
    ("signals_v29", ["severity"]),
    ("signals_v29", ["observed_at"]),
    ("signals_v29", ["client_id", "observed_at"]),
    # Issues v29
    ("issues_v29", ["client_id"]),
    ("issues_v29", ["state"]),
    ("issues_v29", ["client_id", "state"]),
]


def _index_name(table: str, columns: list[str]) -> str:
    """Generate consistent index name from table and columns."""
    col_str = "_".join(columns)
    return f"idx_{table}_{col_str}"


def ensure_indexes(db_path: str | Path) -> IndexReport:
    """
    Create all performance-critical indexes idempotently.

    Args:
        db_path: Path to SQLite database

    Returns:
        IndexReport with creation status for each index

    Usage:
        report = ensure_indexes("data/moh_time_os.db")
        print(f"Created {len(report.created)} indexes")
        for error in report.errors:
            logger.warning(f"Index {error['index']} failed: {error['error']}")
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    report = IndexReport()
    conn = sqlite3.connect(str(db_path))

    try:
        # Get existing indexes
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        existing_indexes = {row[0] for row in cursor.fetchall()}

        # Get existing tables
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Create each index
        for table, columns in PERFORMANCE_INDEXES:
            report.total_checked += 1

            # Skip if table doesn't exist
            if table not in existing_tables:
                logger.debug(f"Skipping index for {table} (table does not exist)")
                continue

            index_name = _index_name(table, columns)
            column_list = ", ".join(columns)

            # Check if already exists
            if index_name in existing_indexes:
                report.add_success(index_name, was_new=False)
                logger.debug(f"Index {index_name} already exists")
                continue

            # Create the index
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column_list})"

            try:
                conn.execute(sql)
                report.add_success(index_name, was_new=True)
                logger.info(f"Created index {index_name} on {table}({column_list})")
            except sqlite3.Error as e:
                error_msg = str(e)
                report.add_error(index_name, error_msg)
                logger.warning(f"Failed to create index {index_name} on {table}: {error_msg}")

        conn.commit()

    except sqlite3.Error as e:
        logger.error(f"Database error during index creation: {e}")
        raise
    finally:
        conn.close()

    return report


def get_missing_indexes(db_path: str | Path) -> list[tuple[str, list[str]]]:
    """
    Check which recommended indexes are missing.

    Returns list of (table, [columns]) tuples that don't have indexes yet.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))

    try:
        # Get existing indexes
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        existing_indexes = {row[0] for row in cursor.fetchall()}

        # Get existing tables
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        missing = []
        for table, columns in PERFORMANCE_INDEXES:
            if table not in existing_tables:
                continue

            index_name = _index_name(table, columns)
            if index_name not in existing_indexes:
                missing.append((table, columns))

        return missing

    finally:
        conn.close()


def drop_index(db_path: str | Path, table: str, columns: list[str]) -> bool:
    """
    Drop an index by table and column list.

    Returns True if dropped, False if didn't exist.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return False

    conn = sqlite3.connect(str(db_path))

    try:
        index_name = _index_name(table, columns)
        conn.execute(f"DROP INDEX IF EXISTS {index_name}")
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Failed to drop index {index_name}: {e}")
        return False
    finally:
        conn.close()
