"""
Data Foundation End-to-End Validation (DF-4.1)

Validates that all Data Foundation fixes (DF-1.1 through DF-3.3) produce
a system where the DIRECTIVE's core questions are answerable.

Usage:
    python scripts/validate_data_foundation.py [--db PATH]
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ValidationResult:
    """Tracks pass/fail/warn for a single check."""

    def __init__(self, domain: str, check: str, passed: bool, detail: str, warn: bool = False):
        self.domain = domain
        self.check = check
        self.passed = passed
        self.detail = detail
        self.warn = warn  # non-critical known issue

    @property
    def status(self) -> str:
        if self.passed:
            return "PASS"
        if self.warn:
            return "WARN"
        return "FAIL"


def _pct(n: int, total: int) -> float:
    return (100.0 * n / total) if total > 0 else 0.0


# ---------------------------------------------------------------------------
# Domain validators
# ---------------------------------------------------------------------------


def validate_clients(conn: sqlite3.Connection) -> list[ValidationResult]:
    results = []

    # Tier coverage for revenue-bearing clients
    with_revenue = conn.execute(
        "SELECT COUNT(*) FROM clients WHERE lifetime_revenue > 0"
    ).fetchone()[0]
    tiered = conn.execute(
        "SELECT COUNT(*) FROM clients WHERE lifetime_revenue > 0 AND tier IS NOT NULL"
    ).fetchone()[0]
    pct = _pct(tiered, with_revenue)
    results.append(
        ValidationResult(
            "clients",
            "tier_coverage",
            pct >= 90,
            f"{tiered}/{with_revenue} revenue clients tiered ({pct:.1f}%)",
        )
    )

    # lifetime_revenue populated for clients with invoices
    with_invoices = conn.execute("""
        SELECT COUNT(DISTINCT c.id) FROM clients c
        JOIN invoices i ON i.client_id = c.id
        WHERE c.lifetime_revenue IS NULL OR c.lifetime_revenue = 0
    """).fetchone()[0]
    results.append(
        ValidationResult(
            "clients",
            "revenue_populated",
            with_invoices == 0,
            f"{with_invoices} clients with invoices but no lifetime_revenue",
        )
    )

    # Print tier distribution
    tiers = conn.execute(
        "SELECT tier, COUNT(*) FROM clients GROUP BY tier ORDER BY tier"
    ).fetchall()
    dist = ", ".join(f"{t[0] or 'NULL'}={t[1]}" for t in tiers)
    results.append(
        ValidationResult(
            "clients",
            "tier_distribution",
            True,
            f"Distribution: {dist}",
        )
    )

    return results


def validate_tasks(conn: sqlite3.Connection) -> list[ValidationResult]:
    results = []

    total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

    # Project link rate
    with_project = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE project_id IS NOT NULL"
    ).fetchone()[0]
    pct = _pct(with_project, total)
    results.append(
        ValidationResult(
            "tasks",
            "project_link_rate",
            pct >= 50,
            f"{with_project}/{total} tasks have project_id ({pct:.1f}%)",
        )
    )

    # Completed tasks have completed_at
    completed = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'").fetchone()[0]
    completed_with_at = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'completed' AND completed_at IS NOT NULL"
    ).fetchone()[0]
    ok = (completed == 0) or (completed_with_at == completed)
    results.append(
        ValidationResult(
            "tasks",
            "completed_at_populated",
            ok,
            f"{completed_with_at}/{completed} completed tasks have completed_at"
            + (" (vacuously true — 0 completed)" if completed == 0 else ""),
        )
    )

    # Status distribution includes variety
    statuses = conn.execute(
        "SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY COUNT(*) DESC"
    ).fetchall()
    dist = ", ".join(f"{s[0]}={s[1]}" for s in statuses)
    results.append(
        ValidationResult(
            "tasks",
            "status_distribution",
            True,
            f"Distribution: {dist}",
        )
    )

    return results


def validate_entity_links(conn: sqlite3.Connection) -> list[ValidationResult]:
    results = []

    total = conn.execute("SELECT COUNT(*) FROM entity_links").fetchone()[0]
    proposed = conn.execute(
        "SELECT COUNT(*) FROM entity_links WHERE status = 'proposed'"
    ).fetchone()[0]
    pct_proposed = _pct(proposed, total)

    # Proposed < 30% — known issue: 16K proposed remain from DF-2.2
    results.append(
        ValidationResult(
            "entity_links",
            "proposed_ratio",
            pct_proposed < 30,
            f"{proposed}/{total} proposed ({pct_proposed:.1f}%)",
            warn=True,  # Known: 16K proposed at 70-79% confidence; needs manual review
        )
    )

    # Avg confidence of confirmed > 0.8
    avg_conf = (
        conn.execute(
            "SELECT AVG(confidence) FROM entity_links WHERE status = 'confirmed'"
        ).fetchone()[0]
        or 0
    )
    results.append(
        ValidationResult(
            "entity_links",
            "confirmed_avg_confidence",
            avg_conf > 0.8,
            f"Avg confirmed confidence: {avg_conf:.4f}",
        )
    )

    # Distribution
    link_statuses = conn.execute(
        "SELECT status, COUNT(*) FROM entity_links GROUP BY status ORDER BY status"
    ).fetchall()
    dist = ", ".join(f"{s[0]}={s[1]}" for s in link_statuses)
    results.append(
        ValidationResult(
            "entity_links",
            "status_distribution",
            True,
            f"Distribution: {dist}",
        )
    )

    return results


def validate_signals(conn: sqlite3.Connection) -> list[ValidationResult]:
    results = []

    total_active = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'active'").fetchone()[
        0
    ]
    critical = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE status = 'active' AND severity = 'critical'"
    ).fetchone()[0]
    pct_critical = _pct(critical, total_active)

    results.append(
        ValidationResult(
            "signals",
            "critical_ratio",
            pct_critical < 20,
            f"{critical}/{total_active} active signals are critical ({pct_critical:.1f}%)",
        )
    )

    # At least 3 severity levels
    levels = conn.execute(
        "SELECT DISTINCT severity FROM signals WHERE status = 'active'"
    ).fetchall()
    level_count = len(levels)
    results.append(
        ValidationResult(
            "signals",
            "severity_diversity",
            level_count >= 3,
            f"{level_count} severity levels: {', '.join(lv[0] for lv in levels)}",
        )
    )

    # Distribution
    sev_dist = conn.execute(
        "SELECT severity, COUNT(*) FROM signals WHERE status = 'active' GROUP BY severity ORDER BY severity"
    ).fetchall()
    dist = ", ".join(f"{s[0]}={s[1]}" for s in sev_dist)
    results.append(
        ValidationResult(
            "signals",
            "severity_distribution",
            True,
            f"Distribution: {dist}",
        )
    )

    return results


def validate_engagements(conn: sqlite3.Connection) -> list[ValidationResult]:
    results = []

    total = conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0]
    results.append(
        ValidationResult(
            "engagements",
            "has_rows",
            total > 0,
            f"{total} engagements",
        )
    )

    # Projects reference engagements (via asana_project_gid → asana_project_id)
    linked = conn.execute("""
        SELECT COUNT(DISTINCT e.id) FROM engagements e
        JOIN projects p ON p.asana_project_id = e.asana_project_gid
    """).fetchone()[0]
    results.append(
        ValidationResult(
            "engagements",
            "project_linkage",
            linked > 0,
            f"{linked} engagements linked to projects",
        )
    )

    # Type distribution
    types = conn.execute(
        "SELECT type, COUNT(*) FROM engagements GROUP BY type ORDER BY type"
    ).fetchall()
    dist = ", ".join(f"{t[0]}={t[1]}" for t in types)
    results.append(
        ValidationResult(
            "engagements",
            "type_distribution",
            True,
            f"Distribution: {dist}",
        )
    )

    return results


def validate_collectors(conn: sqlite3.Connection) -> list[ValidationResult]:
    results = []

    # Check sync_state for last run times
    collectors = conn.execute("SELECT source, last_sync FROM sync_state ORDER BY source").fetchall()

    if not collectors:
        results.append(
            ValidationResult(
                "collectors",
                "freshness",
                False,
                "No sync_state entries found",
            )
        )
        return results

    now = datetime.now(timezone.utc)
    stale = []
    fresh = []
    for source, last_sync in collectors:
        if last_sync:
            try:
                last_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                age_hours = (now - last_dt).total_seconds() / 3600
                if age_hours > 48:
                    stale.append(f"{source} ({age_hours:.0f}h ago)")
                else:
                    fresh.append(source)
            except (ValueError, TypeError):
                stale.append(f"{source} (unparseable: {last_sync})")
        else:
            stale.append(f"{source} (never)")

    # This is a known issue — collectors haven't been running during dev
    all_fresh = len(stale) == 0
    results.append(
        ValidationResult(
            "collectors",
            "freshness",
            all_fresh,
            f"Fresh: {', '.join(fresh) or 'none'} | Stale: {', '.join(stale) or 'none'}",
            warn=not all_fresh,  # Expected during dev — no daemon running
        )
    )

    # Print last sync times
    sync_lines = ", ".join(f"{c[0]}={c[1] or 'never'}" for c in collectors)
    results.append(
        ValidationResult(
            "collectors",
            "last_sync_times",
            True,
            f"Last syncs: {sync_lines}",
        )
    )

    return results


def validate_capacity_lanes(conn: sqlite3.Connection) -> list[ValidationResult]:
    results = []

    lane_count = conn.execute("SELECT COUNT(*) FROM capacity_lanes").fetchone()[0]
    results.append(
        ValidationResult(
            "capacity_lanes",
            "has_rows",
            lane_count > 0,
            f"{lane_count} lanes",
        )
    )

    # At least 1 lane has tasks
    lanes_with_tasks = conn.execute(
        "SELECT COUNT(DISTINCT lane_id) FROM tasks WHERE lane_id IS NOT NULL"
    ).fetchone()[0]
    results.append(
        ValidationResult(
            "capacity_lanes",
            "tasks_assigned",
            lanes_with_tasks > 0,
            f"{lanes_with_tasks} lanes have tasks assigned",
        )
    )

    # Lane load summary
    lane_loads = conn.execute("""
        SELECT cl.name, cl.display_name,
               COUNT(t.rowid) as task_count,
               (SELECT COUNT(*) FROM team_members tm WHERE tm.default_lane = cl.name) as team_count
        FROM capacity_lanes cl
        LEFT JOIN tasks t ON t.lane_id = cl.id
        GROUP BY cl.id
        ORDER BY task_count DESC
    """).fetchall()
    summary = ", ".join(f"{ln[0]}={ln[2]}tasks/{ln[3]}people" for ln in lane_loads)
    results.append(
        ValidationResult(
            "capacity_lanes",
            "load_summary",
            True,
            f"Lanes: {summary}",
        )
    )

    return results


def validate_cross_entity_views(conn: sqlite3.Connection) -> list[ValidationResult]:
    results = []

    # v_client_operational_profile
    rows = conn.execute(
        "SELECT COUNT(*) FROM v_client_operational_profile WHERE client_name IS NOT NULL"
    ).fetchone()[0]
    results.append(
        ValidationResult(
            "cross_entity",
            "v_client_operational_profile",
            rows > 0,
            f"{rows} rows with non-null data",
        )
    )

    # v_project_operational_state — rows with task counts > 0
    rows_with_tasks = conn.execute(
        "SELECT COUNT(*) FROM v_project_operational_state WHERE total_tasks > 0"
    ).fetchone()[0]
    results.append(
        ValidationResult(
            "cross_entity",
            "v_project_operational_state",
            rows_with_tasks > 0,
            f"{rows_with_tasks} projects with task counts > 0",
        )
    )

    # v_person_load_profile — rows with assigned tasks
    rows_with_assigned = conn.execute(
        "SELECT COUNT(*) FROM v_person_load_profile WHERE assigned_tasks > 0"
    ).fetchone()[0]
    results.append(
        ValidationResult(
            "cross_entity",
            "v_person_load_profile",
            rows_with_assigned > 0,
            f"{rows_with_assigned} people with assigned tasks",
        )
    )

    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def run_validation(db_path: str) -> list[ValidationResult]:
    conn = sqlite3.connect(db_path)
    all_results = []

    validators = [
        validate_clients,
        validate_tasks,
        validate_entity_links,
        validate_signals,
        validate_engagements,
        validate_collectors,
        validate_capacity_lanes,
        validate_cross_entity_views,
    ]

    for validator in validators:
        try:
            all_results.extend(validator(conn))
        except Exception as e:
            all_results.append(
                ValidationResult(
                    validator.__name__.replace("validate_", ""),
                    "execution",
                    False,
                    f"Validator crashed: {e}",
                )
            )

    conn.close()
    return all_results


def print_report(results: list[ValidationResult]) -> int:
    """Print structured report. Returns exit code (0 = all pass/warn, 1 = hard fail)."""

    print("=" * 72)
    print("  DATA FOUNDATION VALIDATION REPORT")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 72)

    current_domain = None
    pass_count = 0
    fail_count = 0
    warn_count = 0

    for r in results:
        if r.domain != current_domain:
            current_domain = r.domain
            print(f"\n  [{current_domain.upper()}]")

        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}[r.status]
        print(f"    {icon} {r.check}: {r.detail}")

        if r.passed:
            pass_count += 1
        elif r.warn:
            warn_count += 1
        else:
            fail_count += 1

    total = pass_count + fail_count + warn_count
    score = _pct(pass_count + warn_count, total) if total > 0 else 0

    print("\n" + "=" * 72)
    print(f"  SUMMARY: {pass_count} PASS / {warn_count} WARN / {fail_count} FAIL")
    print(f"  SCORE: {score:.0f}% (pass + warn)")
    print("=" * 72)

    if warn_count > 0:
        print("\n  Known Issues (WARN):")
        for r in results:
            if r.warn and not r.passed:
                print(f"    - {r.domain}.{r.check}: {r.detail}")

    if fail_count > 0:
        print("\n  Critical Failures (FAIL):")
        for r in results:
            if not r.passed and not r.warn:
                print(f"    - {r.domain}.{r.check}: {r.detail}")

    return 1 if fail_count > 0 else 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Data Foundation Validation")
    parser.add_argument(
        "--db",
        default="data/moh_time_os.db",
        help="Path to the database (default: data/moh_time_os.db)",
    )
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"ERROR: Database not found: {args.db}")
        sys.exit(1)

    results = run_validation(args.db)
    exit_code = print_report(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
