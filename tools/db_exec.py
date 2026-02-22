#!/usr/bin/env python3
"""
Safe DB Execution Tool

Executes SQL against the database with proper attribution.
Requires --actor and --source flags.

Usage:
    python tools/db_exec.py --actor moh --source tooling "SELECT * FROM inbox_items_v29 LIMIT 5"
    python tools/db_exec.py --actor moh --source maintenance --maintenance "UPDATE inbox_items_v29 SET ..."

For maintenance mode (bypasses context checks for bulk operations):
    python tools/db_exec.py --actor moh --source maintenance --maintenance "UPDATE ..."
"""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib import paths
from lib.safety import WriteContext, generate_request_id, get_git_sha
from lib.safety.migrations import disable_maintenance_mode, enable_maintenance_mode

# Configure logging for stderr (metadata/debug output)
logging.basicConfig(
    level=logging.INFO,
    format="# %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


def write_stdout(text: str) -> None:
    """Write to stdout (for query results)."""
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        description="Execute SQL with proper attribution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Read query (no context needed)
    python tools/db_exec.py --actor moh --source tooling "SELECT COUNT(*) FROM inbox_items_v29"

    # Write query (context enforced)
    python tools/db_exec.py --actor moh --source tooling "UPDATE inbox_items_v29 SET read_at = datetime('now') WHERE id = 'xxx'"

    # Maintenance mode (for bulk operations)
    python tools/db_exec.py --actor moh --source maintenance --maintenance "UPDATE ..."
        """,
    )

    parser.add_argument("sql", help="SQL to execute")
    parser.add_argument("--actor", required=True, help="Who is running this (required)")
    parser.add_argument("--source", required=True, help="Source of this operation (required)")
    parser.add_argument("--request-id", help="Request ID (auto-generated if not provided)")
    parser.add_argument(
        "--maintenance",
        action="store_true",
        help="Enable maintenance mode for bulk operations",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--db", help="Database path (default: auto-detected)")

    args = parser.parse_args()

    # Validate inputs
    if not args.actor or args.actor.strip() == "":
        logger.error("ERROR: --actor is required and cannot be empty")
        sys.exit(1)

    if not args.source or args.source.strip() == "":
        logger.error("ERROR: --source is required and cannot be empty")
        sys.exit(1)

    # Get database path
    db_path = Path(args.db) if args.db else paths.db_path()
    if not db_path.exists():
        logger.error("ERROR: Database not found at %s", db_path)
        sys.exit(1)

    # Connect and execute
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    request_id = args.request_id or generate_request_id()
    git_sha = get_git_sha()

    logger.info("Database: %s", db_path)
    logger.info("Actor: %s", args.actor)
    logger.info("Source: %s", args.source)
    logger.info("Request ID: %s", request_id)
    logger.info("Git SHA: %s", git_sha)
    logger.info("Maintenance mode: %s", args.maintenance)
    logger.info("")

    try:
        if args.maintenance:
            # Enable maintenance mode
            enable_maintenance_mode(conn, reason=f"db_exec: {args.sql[:100]}", set_by=args.actor)
            logger.info("Maintenance mode ENABLED")

        # Set write context
        with WriteContext(
            conn,
            actor=args.actor,
            source=args.source,
            request_id=request_id,
            git_sha=git_sha,
        ):
            cursor = conn.execute(args.sql)

            # Check if this was a write
            is_write = (
                args.sql.strip()
                .upper()
                .startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"))
            )

            if is_write:
                rows_affected = cursor.rowcount
                conn.commit()
                logger.info("Rows affected: %d", rows_affected)

                # Show audit trail
                audit_cursor = conn.execute(
                    """
                    SELECT id, at, actor, request_id, table_name, op, row_id
                    FROM db_write_audit_v1
                    WHERE request_id = ?
                    ORDER BY at DESC
                    LIMIT 10
                """,
                    (request_id,),
                )
                audit_rows = audit_cursor.fetchall()
                if audit_rows:
                    logger.info("")
                    logger.info("Audit trail:")
                    for row in audit_rows:
                        logger.info(
                            "  %s | %s %s | row=%s...",
                            row["at"],
                            row["op"],
                            row["table_name"],
                            row["row_id"][:16],
                        )
            else:
                # Read query - display results
                rows = cursor.fetchall()
                if args.json:
                    result = [dict(row) for row in rows]
                    write_stdout(json.dumps(result, indent=2, default=str))
                else:
                    if rows:
                        # Print header
                        columns = rows[0].keys()
                        write_stdout(" | ".join(columns))
                        write_stdout("-" * 80)
                        for row in rows:
                            write_stdout(" | ".join(str(row[c]) for c in columns))
                        logger.info("")
                        logger.info("%d rows", len(rows))
                    else:
                        logger.info("No results")

    except sqlite3.Error as e:
        logger.error("ERROR: %s", e)
        sys.exit(1)
    finally:
        if args.maintenance:
            disable_maintenance_mode(conn)
            logger.info("Maintenance mode DISABLED")
        conn.close()


if __name__ == "__main__":
    main()
