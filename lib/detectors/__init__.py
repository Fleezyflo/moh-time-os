"""
Detection System Orchestrator -- runs all detectors, correlates, and stores findings.

Entry point: run_all_detectors(db_path, dry_run=True)

Handles:
- Running CollisionDetector, DriftDetector, BottleneckDetector
- Passing results through the correlator
- Deduplication: existing findings get last_detected updated, new ones inserted
- Writing to detection_findings or detection_findings_preview (dry-run mode)
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

from .bottleneck import BottleneckDetector
from .collision import CollisionDetector
from .correlator import FindingGroup, correlate
from .drift import DriftDetector

logger = logging.getLogger(__name__)

__all__ = [
    "run_all_detectors",
    "CollisionDetector",
    "DriftDetector",
    "BottleneckDetector",
    "FindingGroup",
]


def _finding_dedup_key(detector: str, finding_type: str, entity_type: str, entity_id: str) -> str:
    """Compute a deduplication key for a finding."""
    content = f"{detector}:{finding_type}:{entity_type}:{entity_id}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# Pre-built SQL per table -- avoids f-string SQL (S608).
# Table names are hardcoded here; callers select by key.
_SQL = {
    "detection_findings": {
        "select": "SELECT id FROM detection_findings WHERE id = ? AND resolved_at IS NULL",
        "update": (
            "UPDATE detection_findings SET last_detected_at = ?, severity = ?, "
            "severity_data = ?, adjacent_data = ?, related_findings = ?, "
            "cycle_id = ?, updated_at = ? WHERE id = ?"
        ),
        "insert": (
            "INSERT INTO detection_findings "
            "(id, detector, finding_type, entity_type, entity_id, entity_name, "
            "severity, severity_data, adjacent_data, related_findings, "
            "first_detected_at, last_detected_at, cycle_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
    },
    "detection_findings_preview": {
        "select": "SELECT id FROM detection_findings_preview WHERE id = ? AND resolved_at IS NULL",
        "update": (
            "UPDATE detection_findings_preview SET last_detected_at = ?, severity = ?, "
            "severity_data = ?, adjacent_data = ?, related_findings = ?, "
            "cycle_id = ?, updated_at = ? WHERE id = ?"
        ),
        "insert": (
            "INSERT INTO detection_findings_preview "
            "(id, detector, finding_type, entity_type, entity_id, entity_name, "
            "severity, severity_data, adjacent_data, related_findings, "
            "first_detected_at, last_detected_at, cycle_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
    },
}


def _store_findings(
    conn: sqlite3.Connection,
    table: str,
    groups: list[FindingGroup],
    cycle_id: str,
) -> dict[str, int]:
    """
    Store correlated findings. Deduplication:
    - Existing active finding with same dedup key -> update last_detected_at
    - New finding -> insert
    """
    if table not in _SQL:
        msg = f"Invalid table name: {table}"
        raise ValueError(msg)

    sql = _SQL[table]
    inserted = 0
    updated = 0
    now = datetime.now().isoformat()

    for group in groups:
        primary = group.primary_finding
        detector = group.primary_type

        # Determine entity info based on finding type
        entity_type, entity_id, entity_name = _extract_entity(detector, primary)
        finding_type = _extract_finding_type(detector, primary)

        dedup_key = _finding_dedup_key(detector, finding_type, entity_type, entity_id)

        # Determine severity
        severity = _extract_severity(detector, primary)

        # Check for existing active finding
        cursor = conn.execute(sql["select"], (dedup_key,))
        existing = cursor.fetchone()

        severity_data = json.dumps(_extract_severity_data(detector, primary))
        adjacent_data = json.dumps(primary)
        related_data = json.dumps(
            [
                {"type": s.get("type"), "relationship": s.get("relationship")}
                for s in group.subordinates
            ]
        )

        if existing:
            conn.execute(
                sql["update"],
                (
                    now,
                    severity,
                    severity_data,
                    adjacent_data,
                    related_data,
                    cycle_id,
                    now,
                    dedup_key,
                ),
            )
            updated += 1
        else:
            conn.execute(
                sql["insert"],
                (
                    dedup_key,
                    detector,
                    finding_type,
                    entity_type,
                    entity_id,
                    entity_name,
                    severity,
                    severity_data,
                    adjacent_data,
                    related_data,
                    now,
                    now,
                    cycle_id,
                    now,
                    now,
                ),
            )
            inserted += 1

    conn.commit()
    return {"inserted": inserted, "updated": updated}


def _extract_entity(detector: str, finding: dict[str, Any]) -> tuple[str, str, str | None]:
    """Extract entity info from a finding based on detector type."""
    if detector == "collision":
        person = finding.get("person", "unknown")
        day = finding.get("date", "")
        return ("person_day", f"{person}_{day}", person)
    elif detector == "drift":
        return ("client", finding.get("client_id", "unknown"), finding.get("client_name"))
    elif detector == "bottleneck":
        return ("person", finding.get("member_name", "unknown"), finding.get("member_name"))
    return ("unknown", "unknown", None)


def _extract_finding_type(detector: str, finding: dict[str, Any]) -> str:
    """Extract finding type from detector and finding data."""
    if detector == "collision":
        return "collision"
    elif detector == "drift":
        return "drift"
    elif detector == "bottleneck":
        return finding.get("trigger", "bottleneck")
    return detector


def _extract_severity(detector: str, finding: dict[str, Any]) -> str:
    """Derive severity from finding data."""
    if detector == "collision":
        ratio = finding.get("weighted_ratio", 0)
        if ratio >= 4.0 or ratio == 999.0:
            return "critical"
        elif ratio >= 3.0:
            return "high"
        return "medium"
    elif detector == "drift":
        overdue = finding.get("overdue_count", 0)
        tier = finding.get("client_tier", "").lower()
        if tier in ("platinum", "gold") and overdue >= 3:
            return "critical"
        elif overdue >= 5:
            return "critical"
        elif overdue >= 3:
            return "high"
        return "medium"
    elif detector == "bottleneck":
        active = finding.get("active_tasks", 0)
        median = finding.get("median_active", 1)
        if median > 0 and active > 3 * median:
            return "critical"
        elif finding.get("overdue_tasks", 0) > 5:
            return "high"
        return "medium"
    return "medium"


def _extract_severity_data(detector: str, finding: dict[str, Any]) -> dict[str, Any]:
    """Extract key severity metrics from a finding."""
    if detector == "collision":
        return {
            "weighted_ratio": finding.get("weighted_ratio"),
            "available_minutes": finding.get("available_minutes"),
            "tasks_due": finding.get("tasks_due"),
        }
    elif detector == "drift":
        return {
            "overdue_count": finding.get("overdue_count"),
            "completions_5d": finding.get("completions_5d"),
            "client_tier": finding.get("client_tier"),
            "days_since_last_meeting": finding.get("days_since_last_meeting"),
        }
    elif detector == "bottleneck":
        return {
            "active_tasks": finding.get("active_tasks"),
            "completed_5d": finding.get("completed_5d"),
            "overdue_tasks": finding.get("overdue_tasks"),
            "median_active": finding.get("median_active"),
            "trigger": finding.get("trigger"),
        }
    return {}


def run_all_detectors(
    db_path: str,
    dry_run: bool = True,
    cycle_id: str | None = None,
) -> dict[str, Any]:
    """
    Run all detectors, correlate findings, store results.

    Args:
        db_path: Path to the SQLite database
        dry_run: If True, write to detection_findings_preview instead of detection_findings
        cycle_id: Optional cycle identifier for tracing

    Returns:
        Summary of detection run
    """
    import time

    start = time.time()
    cycle_id = cycle_id or datetime.now().strftime("cycle_%Y%m%d_%H%M%S")
    table = "detection_findings_preview" if dry_run else "detection_findings"

    results: dict[str, Any] = {
        "cycle_id": cycle_id,
        "dry_run": dry_run,
        "table": table,
        "detectors": {},
    }

    # Run all three detectors
    try:
        collision_detector = CollisionDetector(db_path)
        collisions = collision_detector.detect()
        results["detectors"]["collision"] = {
            "findings": len(collisions),
            "status": "ok",
        }
        logger.info("CollisionDetector: %d findings", len(collisions))
    except (sqlite3.Error, ValueError, OSError) as e:
        collisions = []
        results["detectors"]["collision"] = {"findings": 0, "status": "error", "error": str(e)}
        logger.warning("CollisionDetector failed: %s", e)

    try:
        drift_detector = DriftDetector(db_path)
        drifts = drift_detector.detect()
        results["detectors"]["drift"] = {
            "findings": len(drifts),
            "status": "ok",
        }
        logger.info("DriftDetector: %d findings", len(drifts))
    except (sqlite3.Error, ValueError, OSError) as e:
        drifts = []
        results["detectors"]["drift"] = {"findings": 0, "status": "error", "error": str(e)}
        logger.warning("DriftDetector failed: %s", e)

    try:
        bottleneck_detector = BottleneckDetector(db_path)
        bottlenecks = bottleneck_detector.detect()
        results["detectors"]["bottleneck"] = {
            "findings": len(bottlenecks),
            "status": "ok",
        }
        logger.info("BottleneckDetector: %d findings", len(bottlenecks))
    except (sqlite3.Error, ValueError, OSError) as e:
        bottlenecks = []
        results["detectors"]["bottleneck"] = {"findings": 0, "status": "error", "error": str(e)}
        logger.warning("BottleneckDetector failed: %s", e)

    # Correlate findings
    try:
        groups = correlate(collisions, drifts, bottlenecks)
        results["correlation"] = {
            "groups": len(groups),
            "status": "ok",
        }
        logger.info(
            "Correlator: %d groups from %d total findings",
            len(groups),
            len(collisions) + len(drifts) + len(bottlenecks),
        )
    except (ValueError, TypeError) as e:
        groups = []
        results["correlation"] = {"groups": 0, "status": "error", "error": str(e)}
        logger.warning("Correlator failed: %s", e)

    # Store findings
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            store_result = _store_findings(conn, table, groups, cycle_id)
            results["storage"] = {**store_result, "status": "ok"}
            logger.info(
                "Stored findings: %d inserted, %d updated in %s",
                store_result["inserted"],
                store_result["updated"],
                table,
            )
        finally:
            conn.close()
    except sqlite3.Error as e:
        results["storage"] = {"status": "error", "error": str(e)}
        logger.warning("Finding storage failed: %s", e)

    # Update sync_state
    try:
        conn = sqlite3.connect(db_path)
        try:
            now = datetime.now().isoformat()
            conn.execute(
                """INSERT INTO sync_state (source, last_sync, last_success, items_synced)
                   VALUES ('detection_last_run', ?, ?, ?)
                   ON CONFLICT(source) DO UPDATE SET
                       last_sync = excluded.last_sync,
                       last_success = excluded.last_success,
                       items_synced = excluded.items_synced""",
                (now, now, len(groups)),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning("Could not update sync_state: %s", e)

    duration_ms = int((time.time() - start) * 1000)
    results["duration_ms"] = duration_ms
    logger.info("Detection run complete in %dms", duration_ms)

    return results
