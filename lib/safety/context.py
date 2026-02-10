"""
Write Context Management

Ensures every DB write is attributable to an actor, request, and source.
Triggers will ABORT if context is not set.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass

from .utils import generate_request_id, get_cached_git_sha, now_utc_iso


@dataclass
class WriteContextData:
    """Data for a write context."""

    request_id: str
    actor: str
    source: str
    git_sha: str
    set_at: str


def set_write_context(
    conn: sqlite3.Connection,
    actor: str,
    source: str,
    request_id: str | None = None,
    git_sha: str | None = None,
) -> WriteContextData:
    """
    Set write context for a connection.

    This MUST be called before any writes to protected tables.
    Triggers will ABORT if context is not set.

    Args:
        conn: SQLite connection
        actor: Who is making the change (user ID, system, etc.)
        source: Where the change originated (api, migration, tooling, etc.)
        request_id: Unique ID for this request (auto-generated if None)
        git_sha: Git commit SHA (auto-detected if None)

    Returns:
        WriteContextData with the values that were set
    """
    if not actor:
        raise ValueError("actor is required for write context")
    if not source:
        raise ValueError("source is required for write context")

    request_id = request_id or generate_request_id()
    git_sha = git_sha or get_cached_git_sha()
    set_at = now_utc_iso()

    # Ensure table exists (idempotent)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS write_context_v1 (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            request_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            source TEXT NOT NULL,
            git_sha TEXT NOT NULL,
            set_at TEXT NOT NULL
        )
    """)

    # Upsert the single row
    conn.execute(
        """
        INSERT INTO write_context_v1 (id, request_id, actor, source, git_sha, set_at)
        VALUES (1, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            request_id = excluded.request_id,
            actor = excluded.actor,
            source = excluded.source,
            git_sha = excluded.git_sha,
            set_at = excluded.set_at
    """,
        (request_id, actor, source, git_sha, set_at),
    )

    return WriteContextData(
        request_id=request_id,
        actor=actor,
        source=source,
        git_sha=git_sha,
        set_at=set_at,
    )


def clear_write_context(conn: sqlite3.Connection) -> None:
    """
    Clear write context after a request completes.

    This prevents stale context from being used by subsequent operations.
    """
    conn.execute("""
        DELETE FROM write_context_v1 WHERE id = 1
    """)


def get_write_context(conn: sqlite3.Connection) -> WriteContextData | None:
    """
    Get current write context if set.

    Returns None if no context is set.
    """
    try:
        cursor = conn.execute("""
            SELECT request_id, actor, source, git_sha, set_at
            FROM write_context_v1
            WHERE id = 1
        """)
        row = cursor.fetchone()
        if row:
            return WriteContextData(
                request_id=row[0],
                actor=row[1],
                source=row[2],
                git_sha=row[3],
                set_at=row[4],
            )
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        pass
    return None


@contextmanager
def WriteContext(
    conn: sqlite3.Connection,
    actor: str,
    source: str,
    request_id: str | None = None,
    git_sha: str | None = None,
    auto_commit: bool = False,
):
    """
    Context manager for attributed DB writes.

    Usage:
        with WriteContext(conn, actor="user123", source="api"):
            conn.execute("UPDATE ...")

    Args:
        conn: SQLite connection
        actor: Who is making the change
        source: Where the change originated
        request_id: Unique ID for this request (auto-generated if None)
        git_sha: Git commit SHA (auto-detected if None)
        auto_commit: Whether to commit on successful exit

    Yields:
        WriteContextData with the context that was set
    """
    ctx = set_write_context(conn, actor, source, request_id, git_sha)
    try:
        yield ctx
        if auto_commit:
            conn.commit()
    finally:
        clear_write_context(conn)
