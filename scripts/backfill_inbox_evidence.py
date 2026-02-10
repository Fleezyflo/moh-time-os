#!/usr/bin/env python3
"""
Backfill inbox_items_v29 evidence payload fields.

Scans rows where evidence.payload is missing core fields and reconstructs
from communications via underlying_signal_id.

Usage:
    python scripts/backfill_inbox_evidence.py [--dry-run] [--limit N]
"""

import argparse
import json
import logging
import re
import sqlite3

from lib import paths
from lib.ui_spec_v21.time_utils import now_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def derive_snippet(
    body_text: str | None, snippet_raw: str | None, subject: str | None
) -> str:
    """Derive best snippet from available data."""
    if body_text and len(body_text.strip()) >= 20:
        clean_body = re.sub(r"<[^>]*>", "", body_text, flags=re.DOTALL)
        clean_body = re.sub(r"\s+", " ", clean_body).strip()
        return clean_body[:500]
    elif snippet_raw and snippet_raw != subject:
        return snippet_raw[:500]
    elif subject:
        return f"Re: {subject}"[:500]
    return ""


def build_url(source: str | None, source_id: str | None) -> str | None:
    """Build URL for source."""
    if source == "gmail" and source_id:
        return f"https://mail.google.com/mail/u/0/#inbox/{source_id}"
    return None


def backfill_inbox_items(
    conn: sqlite3.Connection,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """
    Backfill inbox_items_v29 rows with missing payload fields.

    Returns stats dict.
    """
    stats = {"scanned": 0, "updated": 0, "skipped": 0, "failed": 0}

    # Find items with missing payload fields
    query = """
        SELECT i.id, i.evidence, i.underlying_signal_id
        FROM inbox_items_v29 i
        WHERE i.type = 'flagged_signal'
        AND (
            json_extract(i.evidence, '$.payload.sender') IS NULL
            OR json_extract(i.evidence, '$.payload.subject') IS NULL
            OR json_extract(i.evidence, '$.url') IS NULL
        )
    """
    if limit:
        query += f" LIMIT {limit}"

    cursor = conn.execute(query)
    rows = cursor.fetchall()

    for row in rows:
        stats["scanned"] += 1
        inbox_id, evidence_raw, signal_id = row

        if not signal_id:
            logger.warning(f"No underlying_signal_id for {inbox_id}")
            stats["skipped"] += 1
            continue

        # Get communication data
        comm_cursor = conn.execute(
            """
            SELECT from_email, subject, snippet, body_text, thread_id,
                   source_id, source, created_at, priority
            FROM communications WHERE id = ?
        """,
            (signal_id,),
        )
        comm = comm_cursor.fetchone()

        if not comm:
            logger.warning(
                f"No communication found for {inbox_id} (signal_id={signal_id})"
            )
            stats["skipped"] += 1
            continue

        (
            sender,
            subject,
            snippet_raw,
            body_text,
            thread_id,
            source_id,
            source,
            received_at,
            priority,
        ) = comm

        # Parse existing evidence
        try:
            evidence = json.loads(evidence_raw) if evidence_raw else {}
        except json.JSONDecodeError:
            evidence = {}

        # Ensure payload exists
        if "payload" not in evidence:
            evidence["payload"] = {}

        # Derive snippet
        derived_snippet = derive_snippet(body_text, snippet_raw, subject)

        # Update fields (only if missing)
        evidence["payload"]["sender"] = evidence["payload"].get("sender") or sender
        evidence["payload"]["subject"] = evidence["payload"].get("subject") or subject
        evidence["payload"]["snippet"] = (
            evidence["payload"].get("snippet") or derived_snippet
        )
        evidence["payload"]["thread_id"] = (
            evidence["payload"].get("thread_id") or thread_id
        )
        evidence["payload"]["received_at"] = (
            evidence["payload"].get("received_at") or received_at
        )
        evidence["payload"]["flagged_reason"] = (
            evidence["payload"].get("flagged_reason")
            or f"Priority {priority} communication"
        )
        evidence["url"] = evidence.get("url") or build_url(source, source_id)

        # Mark as backfilled
        evidence["meta"] = evidence.get("meta", {})
        evidence["meta"]["backfilled_at"] = now_iso()

        if dry_run:
            logger.info(
                f"[DRY-RUN] Would update {inbox_id}: sender={sender}, subject={subject[:50] if subject else None}..."
            )
            stats["updated"] += 1
        else:
            try:
                conn.execute(
                    "UPDATE inbox_items_v29 SET evidence = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(evidence), now_iso(), inbox_id),
                )
                stats["updated"] += 1
                logger.info(f"Updated {inbox_id}")
            except Exception as e:
                logger.error(f"Failed to update {inbox_id}: {e}")
                stats["failed"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Backfill inbox evidence payload fields"
    )
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--limit", type=int, help="Limit number of items to process")
    args = parser.parse_args()

    conn = sqlite3.connect(str(paths.db_path()))
    conn.row_factory = sqlite3.Row

    try:
        stats = backfill_inbox_items(conn, dry_run=args.dry_run, limit=args.limit)
        if not args.dry_run:
            conn.commit()

        logger.info(f"Backfill complete: {stats}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
