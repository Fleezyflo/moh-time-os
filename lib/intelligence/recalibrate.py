"""
Signal recalibration module.

Re-scores existing signals in the `signals` table using graduated severity rules,
and updates `signal_definitions.priority_weight` by category.

Severity rules:
  - deadline_overdue: critical only if days_overdue > 14 AND has client_id; high if 7-14 with client; medium if 1-7; low if no client (stale)
  - ar_aging_risk: critical if aging_bucket='90+'; high if '60'; medium if '30'; low if 'current'
  - data_quality_issue: max severity = medium
  - hierarchy_violation: max severity = low
  - deadline_at_risk: high (was critical in some cases)
  - deadline_approaching: medium (informational)
  - commitment_overdue: high (not critical unless compound)

Priority weight by category:
  - deadline/commitment signals: 0.8
  - client health signals: 1.0
  - anomaly signals: 0.6
  - protocol/data quality: 0.3
"""

import json
import logging
import sqlite3
from pathlib import Path

from lib.paths import db_path as canonical_db_path

logger = logging.getLogger(__name__)

# Weight map by signal category
PRIORITY_WEIGHTS = {
    "deadline": 0.8,
    "commitment": 0.8,
    "health": 1.0,
    "anomaly": 0.6,
    "protocol": 0.3,
}


def _get_db_path(db_path: str | None = None) -> str:
    """Resolve database path."""
    if db_path:
        return str(db_path)
    return str(canonical_db_path())


def signal_distribution_report(db_path: str | None = None) -> dict:
    """
    Report severity distribution of active signals.

    Returns:
        {
            "total_active": int,
            "by_severity": {"critical": N, "high": N, "medium": N, "low": N},
            "by_type": {"deadline_overdue": {"critical": N, ...}, ...},
            "critical_pct": float
        }
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_type: dict[str, dict[str, int]] = {}

    rows = conn.execute(
        "SELECT signal_type, severity, COUNT(*) as cnt "
        "FROM signals WHERE status = 'active' "
        "GROUP BY signal_type, severity"
    ).fetchall()

    total = 0
    for row in rows:
        stype = row["signal_type"]
        sev = row["severity"]
        cnt = row["cnt"]
        total += cnt

        if sev in by_severity:
            by_severity[sev] += cnt

        if stype not in by_type:
            by_type[stype] = {}
        by_type[stype][sev] = cnt

    conn.close()

    critical_pct = (by_severity["critical"] / total * 100) if total > 0 else 0.0

    return {
        "total_active": total,
        "by_severity": by_severity,
        "by_type": by_type,
        "critical_pct": round(critical_pct, 1),
    }


def _recalibrate_deadline_overdue(value_json: str) -> str:
    """Determine new severity for deadline_overdue signals.

    Rules:
      - No client_id → stale/orphan data → low regardless of days
      - days_overdue > 14 with client → critical
      - days_overdue 7-14 with client → high
      - days_overdue 1-7 → medium
      - days_overdue 0 → low
    """
    try:
        data = json.loads(value_json)
        days = data.get("days_overdue", 0)
        has_client = bool(data.get("client_id"))
    except (json.JSONDecodeError, TypeError):
        return "medium"

    if not has_client:
        # Orphaned task with no client linkage — stale data, not an emergency
        return "low"

    if days > 14:
        return "critical"
    elif days > 7:
        return "high"
    elif days > 0:
        return "medium"
    return "low"


def _recalibrate_ar_aging(value_json: str) -> str:
    """Determine new severity for ar_aging_risk signals."""
    try:
        data = json.loads(value_json)
        bucket = data.get("aging_bucket", "current")
    except (json.JSONDecodeError, TypeError):
        return "medium"

    bucket_map = {
        "90+": "critical",
        "90": "critical",
        "60": "high",
        "30": "medium",
        "current": "low",
    }
    return bucket_map.get(str(bucket), "medium")


def recalibrate_active_signals(
    db_path: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Re-score all active signals with graduated severity rules.

    Args:
        db_path: Database path (uses default if None).
        dry_run: If True, compute changes without writing.

    Returns:
        {
            "before": distribution report,
            "after": distribution report (or projected if dry_run),
            "changes": {"upgraded": N, "downgraded": N, "unchanged": N},
            "dry_run": bool
        }
    """
    db = _get_db_path(db_path)
    before = signal_distribution_report(db)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT signal_id, signal_type, severity, value FROM signals WHERE status = 'active'"
    ).fetchall()

    upgraded = 0
    downgraded = 0
    unchanged = 0
    severity_order = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    updates: list[tuple[str, str]] = []  # (new_severity, signal_id)

    for row in rows:
        signal_type = row["signal_type"]
        old_severity = row["severity"]
        value_json = row["value"]
        new_severity = old_severity

        if signal_type == "deadline_overdue":
            new_severity = _recalibrate_deadline_overdue(value_json)
        elif signal_type == "ar_aging_risk":
            new_severity = _recalibrate_ar_aging(value_json)
        elif signal_type == "data_quality_issue":
            # Cap at medium
            if severity_order.get(old_severity, 0) > severity_order["medium"]:
                new_severity = "medium"
        elif signal_type == "hierarchy_violation":
            # Cap at low
            new_severity = "low"
        elif signal_type == "deadline_approaching":
            # Informational — cap at medium
            if severity_order.get(old_severity, 0) > severity_order["medium"]:
                new_severity = "medium"
        elif signal_type == "deadline_at_risk":
            # Cap at high
            if severity_order.get(old_severity, 0) > severity_order["high"]:
                new_severity = "high"

        old_rank = severity_order.get(old_severity, 0)
        new_rank = severity_order.get(new_severity, 0)

        if new_rank < old_rank:
            downgraded += 1
        elif new_rank > old_rank:
            upgraded += 1
        else:
            unchanged += 1

        if new_severity != old_severity:
            updates.append((new_severity, row["signal_id"]))

    if not dry_run and updates:
        conn.executemany(
            "UPDATE signals SET severity = ? WHERE signal_id = ?",
            updates,
        )
        conn.commit()

    conn.close()

    after = signal_distribution_report(db) if not dry_run else before

    return {
        "before": before,
        "after": after,
        "changes": {
            "upgraded": upgraded,
            "downgraded": downgraded,
            "unchanged": unchanged,
            "total_updated": len(updates),
        },
        "dry_run": dry_run,
    }


def update_priority_weights(
    db_path: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Update signal_definitions.priority_weight by category.

    Returns:
        {"updates": [{"signal_type": ..., "old_weight": ..., "new_weight": ...}], "dry_run": bool}
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT signal_type, category, priority_weight FROM signal_definitions"
    ).fetchall()

    updates = []
    for row in rows:
        old_weight = row["priority_weight"]
        category = row["category"]
        new_weight = PRIORITY_WEIGHTS.get(category, old_weight)

        updates.append(
            {
                "signal_type": row["signal_type"],
                "category": category,
                "old_weight": old_weight,
                "new_weight": new_weight,
            }
        )

    if not dry_run:
        for u in updates:
            conn.execute(
                "UPDATE signal_definitions SET priority_weight = ? WHERE signal_type = ?",
                (u["new_weight"], u["signal_type"]),
            )
        conn.commit()

    conn.close()

    return {"updates": updates, "dry_run": dry_run}


def full_recalibration(
    db_path: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Run complete recalibration: severity re-scoring + priority weight update.

    Returns combined results.
    """
    severity_result = recalibrate_active_signals(db_path, dry_run=dry_run)
    weight_result = update_priority_weights(db_path, dry_run=dry_run)

    return {
        "severity_recalibration": severity_result,
        "priority_weights": weight_result,
        "dry_run": dry_run,
    }


if __name__ == "__main__":
    import sys

    dry = "--dry-run" in sys.argv

    print("=" * 60)
    print("MOH TIME OS — Signal Recalibration")
    print("=" * 60)

    result = full_recalibration(dry_run=dry)

    sr = result["severity_recalibration"]
    print(f"\nMode: {'DRY RUN' if dry else 'LIVE'}")

    print("\n--- Before ---")
    for sev, cnt in sr["before"]["by_severity"].items():
        print(f"  {sev}: {cnt}")
    print(f"  Critical %: {sr['before']['critical_pct']}%")

    if not dry:
        print("\n--- After ---")
        for sev, cnt in sr["after"]["by_severity"].items():
            print(f"  {sev}: {cnt}")
        print(f"  Critical %: {sr['after']['critical_pct']}%")

    print("\n--- Changes ---")
    for k, v in sr["changes"].items():
        print(f"  {k}: {v}")

    print("\n--- Priority Weight Updates ---")
    for u in result["priority_weights"]["updates"]:
        changed = " ← changed" if u["old_weight"] != u["new_weight"] else ""
        print(f"  {u['signal_type']}: {u['old_weight']} → {u['new_weight']}{changed}")
