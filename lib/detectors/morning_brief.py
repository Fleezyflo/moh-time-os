"""
Morning Brief -- daily digest of detection findings via Google Chat.

Sends exactly one brief per day when:
1. current_hour >= morning_brief_hour (from governance.yaml)
2. No brief has been sent today yet

Brief contents:
- New findings (with client tier, revenue if available)
- Worsened findings (acknowledged that got worse -> un-acknowledged)
- Resolved findings
- Weight review prompt (if pending)
- Suppressed findings are excluded entirely
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _format_finding_line(finding: dict) -> str:
    """Format a single finding into a brief line."""
    detector = finding.get("detector", "unknown")
    entity_name = finding.get("entity_name") or finding.get("entity_id", "unknown")
    severity = finding.get("severity", "medium")

    # Extract tier from severity_data if available
    severity_data_raw = finding.get("severity_data", "{}")
    try:
        severity_data = (
            json.loads(severity_data_raw)
            if isinstance(severity_data_raw, str)
            else severity_data_raw
        )
    except (json.JSONDecodeError, TypeError):
        severity_data = {}

    tier = severity_data.get("client_tier", "")
    tier_label = f" ({tier})" if tier else ""

    # Gracefully include revenue only when available
    revenue = severity_data.get("revenue")
    revenue_label = f" -- ${revenue:,.0f}" if revenue else ""

    if detector == "collision":
        ratio = severity_data.get("weighted_ratio", "?")
        return (
            f"  [{severity}] Collision: {entity_name} -- ratio {ratio}{tier_label}{revenue_label}"
        )
    elif detector == "drift":
        overdue = severity_data.get("overdue_count", "?")
        return (
            f"  [{severity}] Drift: {entity_name} -- {overdue} overdue{tier_label}{revenue_label}"
        )
    elif detector == "bottleneck":
        active = severity_data.get("active_tasks", "?")
        return f"  [{severity}] Bottleneck: {entity_name} -- {active} active tasks{tier_label}{revenue_label}"
    return f"  [{severity}] {detector}: {entity_name}{tier_label}{revenue_label}"


# Pre-built SQL -- no f-strings (S608).
_SQL_NEW_FINDINGS = (
    "SELECT id, detector, entity_name, entity_id, severity, severity_data "
    "FROM detection_findings "
    "WHERE notified_at IS NULL "
    "AND suppressed_until IS NULL "
    "AND resolved_at IS NULL "
    "ORDER BY severity, detector"
)

_SQL_WORSENED_FINDINGS = (
    "SELECT id, detector, entity_name, entity_id, severity, severity_data, "
    "acknowledged_at "
    "FROM detection_findings "
    "WHERE notified_at IS NOT NULL "
    "AND last_detected_at > notified_at "
    "AND suppressed_until IS NULL "
    "AND resolved_at IS NULL "
    "ORDER BY severity, detector"
)

_SQL_RESOLVED_FINDINGS = (
    "SELECT id, detector, entity_name, entity_id, severity, severity_data "
    "FROM detection_findings "
    "WHERE resolved_at IS NOT NULL "
    "AND notified_at IS NOT NULL "
    "AND resolved_at > notified_at "
    "AND suppressed_until IS NULL "
    "ORDER BY detector"
)

_SQL_UPDATE_NOTIFIED = "UPDATE detection_findings SET notified_at = ? WHERE id = ?"

_SQL_UNACKNOWLEDGE = "UPDATE detection_findings SET acknowledged_at = NULL WHERE id = ?"

_SQL_LAST_BRIEF = "SELECT last_sync FROM sync_state WHERE source = 'morning_brief_last_sent'"

_SQL_UPSERT_BRIEF_TIME = (
    "INSERT INTO sync_state (source, last_sync, last_success, items_synced) "
    "VALUES ('morning_brief_last_sent', ?, ?, ?) "
    "ON CONFLICT(source) DO UPDATE SET "
    "last_sync = excluded.last_sync, "
    "last_success = excluded.last_success, "
    "items_synced = excluded.items_synced"
)

_SQL_PENDING_WEIGHT_REVIEWS = (
    "SELECT COUNT(*) as cnt FROM detection_findings "
    "WHERE detector = 'collision' "
    "AND resolved_at IS NULL "
    "AND suppressed_until IS NULL"
)


def send_if_changed(
    db_path: str,
    notifier: object,
    morning_brief_hour: int = 8,
) -> dict:
    """
    Send morning brief if there are new/changed findings and timing gate passes.

    Args:
        db_path: Path to the SQLite database
        notifier: NotificationEngine instance (has channels["google_chat"])
        morning_brief_hour: Hour (0-23) after which the brief can fire

    Returns:
        Dict with status and details
    """
    now = datetime.now(timezone.utc)

    # Timing gate: only send after configured hour
    if now.hour < morning_brief_hour:
        return {"status": "skipped", "reason": "before_morning_brief_hour"}

    # Check if brief already sent today
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(_SQL_LAST_BRIEF)
            row = cursor.fetchone()
            if row and row["last_sync"]:
                last_sent_str = row["last_sync"]
                try:
                    last_sent = datetime.fromisoformat(last_sent_str)
                    if last_sent.date() == now.date():
                        return {"status": "skipped", "reason": "already_sent_today"}
                except ValueError as e:
                    logger.warning("Could not parse last brief time: %s", e)
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error("Failed to check last brief time: %s", e)
        return {"status": "error", "error": str(e)}

    # Gather findings
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            new_findings = [dict(r) for r in conn.execute(_SQL_NEW_FINDINGS).fetchall()]
            worsened_findings = [dict(r) for r in conn.execute(_SQL_WORSENED_FINDINGS).fetchall()]
            resolved_findings = [dict(r) for r in conn.execute(_SQL_RESOLVED_FINDINGS).fetchall()]

            # Check pending weight reviews
            weight_row = conn.execute(_SQL_PENDING_WEIGHT_REVIEWS).fetchone()
            pending_weights = weight_row["cnt"] if weight_row else 0
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error("Failed to gather findings for brief: %s", e)
        return {"status": "error", "error": str(e)}

    # Nothing to report?
    if not new_findings and not worsened_findings and not resolved_findings:
        return {"status": "skipped", "reason": "no_changes"}

    # Build message
    sections = []

    if new_findings:
        sections.append(f"*New findings ({len(new_findings)}):*")
        for f in new_findings:
            sections.append(_format_finding_line(f))

    if worsened_findings:
        sections.append(f"\n*Worsened findings ({len(worsened_findings)}):*")
        for f in worsened_findings:
            sections.append(_format_finding_line(f))

    if resolved_findings:
        sections.append(f"\n*Resolved ({len(resolved_findings)}):*")
        for f in resolved_findings:
            entity_name = f.get("entity_name") or f.get("entity_id", "unknown")
            sections.append(f"  Resolved: {f.get('detector', '?')} -- {entity_name}")

    if pending_weights > 0:
        sections.append(
            f"\n*Weight check:* {pending_weights} collision findings "
            'with auto-classified weights. Reply "weights" to review.'
        )

    message = "\n".join(sections)
    title = f"Morning Brief -- {now.strftime('%A %b %d')}"

    # Send via Google Chat channel (outbox-safe path)
    channel = getattr(notifier, "channels", {}).get("google_chat")
    if not channel:
        logger.warning("No Google Chat channel configured -- brief not sent")
        return {"status": "error", "error": "no_google_chat_channel"}

    try:
        from lib.notifier.channels.safe_send import safe_send_sync

        result = safe_send_sync(
            channel=channel,
            message=message,
            title=title,
            caller="morning_brief",
        )
    except (ValueError, OSError) as e:
        logger.error("Failed to send morning brief: %s", e)
        return {"status": "error", "error": str(e)}

    if not result.get("success"):
        return {"status": "error", "error": result.get("error", "send failed")}

    # Mark findings as notified + un-acknowledge worsened findings
    try:
        conn = sqlite3.connect(db_path)
        try:
            now_iso = now.isoformat()
            total_notified = 0

            for f in new_findings:
                conn.execute(_SQL_UPDATE_NOTIFIED, (now_iso, f["id"]))
                total_notified += 1

            for f in worsened_findings:
                conn.execute(_SQL_UPDATE_NOTIFIED, (now_iso, f["id"]))
                # Un-acknowledge worsened findings so they require re-acknowledgment
                if f.get("acknowledged_at"):
                    conn.execute(_SQL_UNACKNOWLEDGE, (f["id"],))
                total_notified += 1

            for f in resolved_findings:
                conn.execute(_SQL_UPDATE_NOTIFIED, (now_iso, f["id"]))
                total_notified += 1

            # Record brief sent time
            conn.execute(_SQL_UPSERT_BRIEF_TIME, (now_iso, now_iso, total_notified))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error("Failed to update notified_at after brief: %s", e)
        return {"status": "partial", "error": f"sent but update failed: {e}"}

    logger.info(
        "Morning brief sent: %d new, %d worsened, %d resolved",
        len(new_findings),
        len(worsened_findings),
        len(resolved_findings),
    )

    return {
        "status": "sent",
        "new": len(new_findings),
        "worsened": len(worsened_findings),
        "resolved": len(resolved_findings),
        "pending_weights": pending_weights,
    }
