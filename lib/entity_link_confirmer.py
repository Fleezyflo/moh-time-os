"""
Entity link auto-confirmer — batch confirm high-confidence proposed links.

Confirms links above a confidence threshold and flags low-confidence ones for review.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIRM_THRESHOLD = 0.85
DEFAULT_FLAG_THRESHOLD = 0.50


def auto_confirm_links(
    db_path: str,
    confidence_threshold: float = DEFAULT_CONFIRM_THRESHOLD,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Auto-confirm proposed entity links above confidence threshold.

    Args:
        db_path: Path to SQLite database.
        confidence_threshold: Minimum confidence to auto-confirm.
        dry_run: If True, report what would be confirmed without changing data.

    Returns:
        Summary dict with counts.
    """
    conn = sqlite3.connect(db_path)
    now = datetime.now().isoformat()

    try:
        # Count how many would be confirmed
        count_row = conn.execute(
            """SELECT COUNT(*) FROM entity_links
               WHERE status = 'proposed' AND confidence >= ?""",
            (confidence_threshold,),
        ).fetchone()
        to_confirm = count_row[0]

        if dry_run:
            # Get breakdown by method
            method_dist = conn.execute(
                """SELECT method, COUNT(*) FROM entity_links
                   WHERE status = 'proposed' AND confidence >= ?
                   GROUP BY method""",
                (confidence_threshold,),
            ).fetchall()

            logger.info(
                f"[DRY RUN] Would confirm {to_confirm} links (threshold={confidence_threshold})"
            )
            return {
                "confirmed": 0,
                "would_confirm": to_confirm,
                "dry_run": True,
                "by_method": dict(method_dist),
            }

        # Perform the confirmation
        conn.execute(
            """UPDATE entity_links
               SET status = 'confirmed',
                   confirmed_by = 'auto_confirmer',
                   confirmed_at = ?,
                   updated_at = ?
               WHERE status = 'proposed' AND confidence >= ?""",
            (now, now, confidence_threshold),
        )
        conn.commit()

        logger.info(f"Auto-confirmed {to_confirm} links (threshold={confidence_threshold})")
        return {
            "confirmed": to_confirm,
            "dry_run": False,
            "threshold": confidence_threshold,
        }

    finally:
        conn.close()


def flag_low_confidence_links(
    db_path: str,
    threshold: float = DEFAULT_FLAG_THRESHOLD,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Identify low-confidence proposed links for manual review.

    Returns list of questionable links with context.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """SELECT link_id, from_artifact_id, to_entity_type, to_entity_id,
                      method, confidence, confidence_reasons
               FROM entity_links
               WHERE status = 'proposed' AND confidence < ?
               ORDER BY confidence ASC
               LIMIT ?""",
            (threshold, limit),
        ).fetchall()

        flagged = [dict(row) for row in rows]
        logger.info(f"Flagged {len(flagged)} low-confidence links (< {threshold})")
        return flagged

    finally:
        conn.close()


def link_confirmation_report(db_path: str) -> dict[str, Any]:
    """Generate a report on entity link status distribution.

    Returns summary with counts and averages.
    """
    conn = sqlite3.connect(db_path)

    try:
        # Status distribution
        status_dist = dict(
            conn.execute("SELECT status, COUNT(*) FROM entity_links GROUP BY status").fetchall()
        )

        # Average confidence by method
        method_stats = conn.execute(
            """SELECT method, COUNT(*), AVG(confidence), MIN(confidence), MAX(confidence)
               FROM entity_links GROUP BY method ORDER BY COUNT(*) DESC"""
        ).fetchall()

        # Proposed by confidence bucket
        buckets = conn.execute(
            """SELECT
                CASE WHEN confidence >= 0.9 THEN '90-100'
                     WHEN confidence >= 0.8 THEN '80-89'
                     WHEN confidence >= 0.7 THEN '70-79'
                     WHEN confidence >= 0.5 THEN '50-69'
                     ELSE '<50' END as bucket,
                COUNT(*)
               FROM entity_links WHERE status = 'proposed'
               GROUP BY bucket ORDER BY bucket"""
        ).fetchall()

        total = sum(status_dist.values())

        return {
            "total_links": total,
            "status_distribution": status_dist,
            "proposed_by_confidence": dict(buckets),
            "method_stats": [
                {
                    "method": row[0],
                    "count": row[1],
                    "avg_confidence": round(row[2], 3),
                    "min_confidence": round(row[3], 3),
                    "max_confidence": round(row[4], 3),
                }
                for row in method_stats
            ],
        }

    finally:
        conn.close()
