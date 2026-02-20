#!/usr/bin/env python3
"""
Initialize/migrate the V5 database schema.

Usage:
    .venv/bin/python scripts/init_v5_db.py [--status] [--force]

This ensures all V5 tables (signals_v5, issues_v5, etc.) exist.
Safe to run multiple times - only creates tables that don't exist.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def check_status():
    """Check if V5 tables exist."""
    from lib.v5 import get_db

    db = get_db()

    tables_to_check = [
        "signals_v5",
        "issues_v5",
        "clients",
        "projects_v5",
        "people",
    ]

    logger.info("V5 Database Status")
    logger.info("=" * 50)
    logger.info(f"Database: {db.db_path}")
    logger.info("")

    all_exist = True
    for table in tables_to_check:
        exists = db.fetch_value(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        status = "✓" if exists else "✗"
        if not exists:
            all_exist = False
        logger.info(f"  {status} {table}")

    logger.info("")
    if all_exist:
        logger.info("All V5 tables exist. Schema is ready.")
        return 0
    else:
        logger.info("Some tables missing. Run without --status to create them.")
        return 1


def init_schema(force: bool = False):
    """Initialize V5 schema."""
    from lib.v5 import TimeOSOrchestrator, get_db

    db = get_db()

    # Check if already initialized
    exists = db.fetch_value(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='signals_v5'"
    )

    if exists and not force:
        logger.info("V5 schema already exists. Use --force to reinitialize.")
        logger.info(f"Database: {db.db_path}")
        return 0

    logger.info("Initializing V5 database schema...")
    logger.info(f"Database: {db.db_path}")
    logger.info("")

    # Use the orchestrator's auto_migrate which handles schema creation
    try:
        # auto_migrate=True will create schema if missing
        orch = TimeOSOrchestrator(db, auto_migrate=True)
        logger.info("✓ V5 schema initialized successfully")

        # Verify by checking key tables
        for table in ["signals_v5", "issues_v5"]:
            exists = db.fetch_value(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if exists:
                logger.info(f"  ✓ {table} created")
            else:
                logger.warning(f"  ✗ {table} not created (check migration)")

        return 0

    except Exception as e:
        logger.error(f"✗ Schema initialization failed: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Initialize/migrate the V5 database schema"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check if V5 tables exist (no changes made)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reinitialization even if tables exist",
    )

    args = parser.parse_args()

    if args.status:
        return check_status()
    else:
        return init_schema(force=args.force)


if __name__ == "__main__":
    sys.exit(main())
