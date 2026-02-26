#!/usr/bin/env python3
"""
Entity Linker — Links projects to clients, brands, and sets engagement types.

Hierarchy:
  Client → Brand → Project (with engagement_type: retainer | project | campaign)

Examples:
  - Gargash → SIXT → SIXT Monthly (retainer)
  - GMG → Aswaaq → Aswaaq Monthly (retainer)
  - SSS → SSS → SSS Ramadan Campaign (campaign)
"""

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone

from lib import paths
from datetime import UTC

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()


# =============================================================================
# Configuration: Client → Brand mappings
# =============================================================================

# Client name → client_id (will be populated from DB)
CLIENT_IDS: dict[str, str] = {}

# Brand definitions: brand_name → client_name
BRAND_TO_CLIENT = {
    # Gargash brands
    "SIXT": "Gargash Enterprises L.L.C",
    "Daimler": "Gargash Enterprises L.L.C",
    "Mercedes-Benz": "Gargash Enterprises L.L.C",
    "MB": "Gargash Enterprises L.L.C",  # Mercedes-Benz shorthand
    "Alfa Romeo": "Gargash Enterprises L.L.C",
    "GAC": "Gargash Enterprises L.L.C",
    # GMG brands
    "Aswaaq": "GMG Consumer LLC",
    "Geant": "GMG Consumer LLC",
    "Monoprix": "GMG Consumer LLC",
    # SSS (Sun Sand Sports)
    "SSS": "Sun Sand Sports LLC",
    "Sun Sand Sports": "Sun Sand Sports LLC",
    # SuperCare
    "SuperCare": "Super Care Pharmacy L.L.C",
    "Supercare": "Super Care Pharmacy L.L.C",
    # Five Guys
    "Five Guys": "Five Guys",
    # BinSina
    "BinSina": "BinSina",
    # Other clients (1:1 brand:client)
    "Ankai": "Ankai",
    "BEFIT": "BEFIT",
    "Maesto": "Maesto",
    "Purple": "Purple",
    # ASICS
    "ASICS": "ASICS ARABIA FZE",
}

# Internal project patterns (link to hrmny)
INTERNAL_PATTERNS = [
    r"^hrmny",
    r"^HRMNY",
    r"^HR\s",
    r"^Admin",
    r"^Employee",
    r"^Candidates",
    r"^Talents",
    r"^Templates",
    r"^Workflows",
    r"^CRM$",
    r"^CS\s",
    r"^Sales Pipeline",
    r"^Proposal pipeline",
    r"Board$",
    r"assigned tasks$",
    r"^System\s",
    r"^00\.\s",  # 00. System Intake Ledger
    r"^Traffic:",
    r"^Active Production",
    r"^Post Production",
    r"^Master Production",
    r"^Creative\s",
    r"^Onboarding",
    r"^Performance Review",
    r"^Recruitment",
    r"^Office\s",
    r"^Equipment",
    r"^Price per unit",
    r"^Quantity of deliverables",
    r"^Total \(excluding VAT\)",
    r"^Unit Description",
    r"^Percent increase",
    r"Focus Points$",
    r"^\[",  # [Creative], [Onboarding Template]
    r"^Receivables",
    r"^Outgoing Invoice",
    r"^Company Docs",
    r"TIMESHEETS",
    r"Payroll",
    r"Procurement",
    r"^Leadership",
    r"^Managerial",
    r"^INCOMING PROJECTS",
    r"^Social Media Strategy Template",
    r"^Sonic Unit",  # Internal music unit
    r"^Ramy \|",  # Personal task boards
    r"^Muhannad",  # Personal task boards
    r"^Jessica$",  # Personal task boards
    r"^Feb$",  # Temp project
    r"^Back To Roots",  # Internal initiative
]


# Engagement type detection
def detect_engagement_type(project_name: str) -> str:
    """Detect engagement type from project name."""
    name_lower = project_name.lower()

    if "monthly" in name_lower or "retainer" in name_lower:
        return "retainer"
    if "campaign" in name_lower or "activation" in name_lower:
        return "campaign"
    return "project"


# =============================================================================
# Database Operations
# =============================================================================


def get_connection():
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def load_client_ids(conn) -> dict[str, str]:
    """Load client name → id mapping."""
    rows = conn.execute("SELECT id, name FROM clients").fetchall()
    return {r["name"]: r["id"] for r in rows}


def ensure_hrmny_client(conn) -> str:
    """Ensure hrmny internal client exists, return its ID."""
    row = conn.execute("SELECT id FROM clients WHERE name = 'hrmny (Internal)'").fetchone()

    if row:
        return row["id"]

    # Create hrmny internal client
    import uuid

    client_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO clients (id, name, name_normalized, type, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            client_id,
            "hrmny (Internal)",
            "hrmny internal",
            "internal",
            now,
            now,
        ),
    )
    conn.commit()
    logger.info(f"Created hrmny (Internal) client: {client_id}")
    return client_id


def ensure_brands(conn, client_ids: dict[str, str]) -> dict[str, str]:
    """Ensure all brands exist, return brand_name → brand_id mapping."""
    brand_ids = {}

    # Load existing brands
    existing = conn.execute("SELECT id, name FROM brands").fetchall()
    for row in existing:
        brand_ids[row["name"]] = row["id"]

    # Create missing brands
    import uuid

    for brand_name, client_name in BRAND_TO_CLIENT.items():
        if brand_name in brand_ids:
            continue

        client_id = client_ids.get(client_name)
        if not client_id:
            logger.info(f"  Warning: Client '{client_name}' not found for brand '{brand_name}'")
            continue

        brand_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO brands (id, name, client_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                brand_id,
                brand_name,
                client_id,
                now,
                now,
            ),
        )
        brand_ids[brand_name] = brand_id
        logger.info(f"  Created brand: {brand_name} → {client_name}")
    conn.commit()
    return brand_ids


def is_internal_project(name: str) -> bool:
    """Check if project is internal."""
    return any(re.search(pattern, name, re.IGNORECASE) for pattern in INTERNAL_PATTERNS)


def extract_brand_from_name(name: str) -> str | None:
    """Extract brand name from project name."""
    # Pattern: "GMG: Aswaaq" or "GMG: Geant"
    match = re.match(r"^GMG:\s*(\w+)", name, re.IGNORECASE)
    if match:
        return match.group(1)

    # Pattern: "SIXT Monthly" or "SIXT | Something"
    for brand in BRAND_TO_CLIENT:
        if name.startswith(brand) or name.startswith(brand.upper()):
            return brand
        # Also check for brand in the name for patterns like "SSS Ramadan"
        if brand in name or brand.upper() in name.upper():
            return brand

    return None


def link_project(
    conn,
    project: dict,
    client_ids: dict[str, str],
    brand_ids: dict[str, str],
    hrmny_id: str,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """
    Link a single project to client/brand.
    Returns (changed, reason).
    """
    name = project["name"]
    current_client_id = project["client_id"]
    current_brand_id = project["brand_id"]
    current_engagement = project["engagement_type"]

    new_client_id = current_client_id
    new_brand_id = current_brand_id
    new_engagement = detect_engagement_type(name)

    # 1. Check if internal
    if is_internal_project(name):
        new_client_id = hrmny_id
        reason = "internal"
    else:
        # 2. Try to extract brand
        brand_name = extract_brand_from_name(name)
        if brand_name:
            new_brand_id = brand_ids.get(brand_name)
            client_name = BRAND_TO_CLIENT.get(brand_name)
            if client_name:
                new_client_id = client_ids.get(client_name)
            reason = f"brand:{brand_name}"
        else:
            # 3. Try direct client name match
            for client_name, client_id in client_ids.items():
                if client_name.lower() in name.lower() or name.lower() in client_name.lower():
                    new_client_id = client_id
                    reason = f"client:{client_name}"
                    break
            else:
                reason = "no-match"

    # Check if anything changed
    changed = (
        new_client_id != current_client_id
        or new_brand_id != current_brand_id
        or new_engagement != current_engagement
    )

    if changed and not dry_run:
        now = datetime.now(UTC).isoformat()
        conn.execute(
            """
            UPDATE projects
            SET client_id = ?, brand_id = ?, engagement_type = ?, updated_at = ?
            WHERE id = ?
        """,
            (
                new_client_id,
                new_brand_id,
                new_engagement,
                now,
                project["id"],
            ),
        )

    return changed, reason


# =============================================================================
# Main Entry Points
# =============================================================================


def run_linking(dry_run: bool = False) -> dict:
    """Run the entity linking process."""
    conn = get_connection()

    logger.info("=== Entity Linker ===")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    # (newline for readability)

    # 1. Load client IDs
    logger.info("Loading clients...")
    client_ids = load_client_ids(conn)
    logger.info(f"  Found {len(client_ids)} clients")
    # 2. Ensure hrmny internal client
    logger.info("Ensuring hrmny (Internal) client...")
    hrmny_id = ensure_hrmny_client(conn)
    client_ids["hrmny (Internal)"] = hrmny_id

    # 3. Ensure brands
    logger.info("Ensuring brands...")
    brand_ids = ensure_brands(conn, client_ids)
    logger.info(f"  {len(brand_ids)} brands ready")
    # 4. Process all projects
    logger.info("\nProcessing projects...")
    projects = conn.execute("""
        SELECT id, name, client_id, brand_id, engagement_type
        FROM projects
    """).fetchall()

    stats = {
        "total": len(projects),
        "changed": 0,
        "internal": 0,
        "brand_linked": 0,
        "client_linked": 0,
        "no_match": 0,
    }

    changes = []

    for project in projects:
        changed, reason = link_project(
            conn, dict(project), client_ids, brand_ids, hrmny_id, dry_run
        )

        if changed:
            stats["changed"] += 1
            changes.append({"name": project["name"], "reason": reason})

        if reason == "internal":
            stats["internal"] += 1
        elif reason.startswith("brand:"):
            stats["brand_linked"] += 1
        elif reason.startswith("client:"):
            stats["client_linked"] += 1
        else:
            stats["no_match"] += 1

    if not dry_run:
        conn.commit()

    conn.close()

    logger.info("\nResults:")
    logger.info(f"  Total projects: {stats['total']}")
    logger.info(f"  Changed: {stats['changed']}")
    logger.info(f"  Internal: {stats['internal']}")
    logger.info(f"  Brand-linked: {stats['brand_linked']}")
    logger.info(f"  Client-linked: {stats['client_linked']}")
    logger.info(f"  No match: {stats['no_match']}")
    return {
        "stats": stats,
        "changes": changes[:50],  # First 50 changes
    }


def get_unlinked_projects() -> list[dict]:
    """Get projects that couldn't be linked."""
    conn = get_connection()

    rows = conn.execute("""
        SELECT id, name, client_id, brand_id, engagement_type
        FROM projects
        WHERE client_id IS NULL
        ORDER BY name
    """).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def get_coverage_stats() -> dict:
    """Get current linking coverage statistics."""
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    with_client = conn.execute(
        "SELECT COUNT(*) FROM projects WHERE client_id IS NOT NULL"
    ).fetchone()[0]
    with_brand = conn.execute(
        "SELECT COUNT(*) FROM projects WHERE brand_id IS NOT NULL"
    ).fetchone()[0]

    # By engagement type
    by_engagement = conn.execute("""
        SELECT engagement_type, COUNT(*) as cnt
        FROM projects
        GROUP BY engagement_type
    """).fetchall()

    conn.close()

    return {
        "total": total,
        "with_client": with_client,
        "with_brand": with_brand,
        "client_coverage": round(100 * with_client / total, 1) if total else 0,
        "brand_coverage": round(100 * with_brand / total, 1) if total else 0,
        "by_engagement": {r["engagement_type"]: r["cnt"] for r in by_engagement},
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        run_linking(dry_run=True)
    elif len(sys.argv) > 1 and sys.argv[1] == "--stats":
        stats = get_coverage_stats()
        logger.info(json.dumps(stats, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--unlinked":
        unlinked = get_unlinked_projects()
        for p in unlinked:
            logger.info(p["name"])
    else:
        run_linking(dry_run=False)
