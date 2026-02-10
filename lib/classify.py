"""
Client tier classification and data quality tools.

Auto-suggests tiers based on AR/value, helps improve data quality.
"""

import logging
from dataclasses import dataclass

from .entities import (
    Client,
    find_client,
    list_clients,
    update_client,
    update_project,
)
from .store import get_connection

logger = logging.getLogger(__name__)


@dataclass
class TierSuggestion:
    client_id: str
    client_name: str
    current_tier: str | None
    suggested_tier: str
    reason: str
    ar_total: float
    confidence: str  # high, medium, low


def suggest_tier(client: Client) -> tuple[str, str, str]:
    """
    Suggest tier for a client based on objective data.

    Returns (tier, reason, confidence)

    Rules:
    - Tier A: AR > 200K or annual_value > 500K
    - Tier B: AR > 50K or annual_value > 100K
    - Tier C: Everything else
    """
    ar = client.ar_total or 0
    annual = client.annual_value or 0

    # Tier A
    if ar >= 200000:
        return "A", f"AR {ar:,.0f} AED (>200K)", "high"
    if annual >= 500000:
        return "A", f"Annual value {annual:,.0f} AED (>500K)", "high"

    # Tier B
    if ar >= 50000:
        return "B", f"AR {ar:,.0f} AED (>50K)", "high"
    if annual >= 100000:
        return "B", f"Annual value {annual:,.0f} AED (>100K)", "high"
    if ar >= 20000:
        return "B", f"AR {ar:,.0f} AED (>20K)", "medium"

    # Tier C
    if ar > 0:
        return "C", f"AR {ar:,.0f} AED (<20K)", "medium"

    return "C", "No AR or value data", "low"


def get_tier_suggestions(include_tiered: bool = False) -> list[TierSuggestion]:
    """Get tier suggestions for clients."""
    clients = list_clients(limit=500)
    suggestions = []

    for client in clients:
        if client.tier and not include_tiered:
            continue

        suggested, reason, confidence = suggest_tier(client)

        # Skip if already correctly tiered
        if client.tier == suggested:
            continue

        suggestions.append(
            TierSuggestion(
                client_id=client.id,
                client_name=client.name,
                current_tier=client.tier,
                suggested_tier=suggested,
                reason=reason,
                ar_total=client.ar_total or 0,
                confidence=confidence,
            )
        )

    # Sort by AR descending
    suggestions.sort(key=lambda s: s.ar_total, reverse=True)
    return suggestions


def apply_tier_suggestions(
    suggestions: list[TierSuggestion], confidence_threshold: str = "medium"
) -> int:
    """
    Apply tier suggestions.

    Args:
        suggestions: List of suggestions
        confidence_threshold: Minimum confidence to apply ('high', 'medium', 'low')

    Returns number applied.
    """
    confidence_order = {"high": 3, "medium": 2, "low": 1}
    threshold = confidence_order.get(confidence_threshold, 2)

    applied = 0
    for s in suggestions:
        if confidence_order.get(s.confidence, 0) >= threshold:
            update_client(s.client_id, tier=s.suggested_tier)
            applied += 1

    return applied


def get_unlinked_projects(limit: int = 50) -> list[dict]:
    """Get projects not linked to a client."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, asana_project_id
            FROM projects
            WHERE client_id IS NULL
            ORDER BY name
            LIMIT ?
        """,
            (limit,),
        ).fetchall()

    return [{"id": r[0], "name": r[1], "asana_id": r[2]} for r in rows]


def suggest_project_client_links() -> list[dict]:
    """Suggest client links for unlinked projects."""
    unlinked = get_unlinked_projects(limit=200)
    suggestions = []

    for proj in unlinked:
        name = proj["name"]

        # Try various matching strategies
        client = None
        strategy = None

        # 1. Extract client name from project name patterns
        for sep in [" - ", ": ", " | ", " – "]:
            if sep in name:
                potential = name.split(sep)[0].strip()
                client = find_client(potential)
                if client:
                    strategy = f'prefix before "{sep}"'
                    break

        # 2. Try first word
        if not client:
            first_word = name.split()[0] if name else None
            if first_word and len(first_word) >= 3:
                client = find_client(first_word)
                if client:
                    strategy = "first word match"

        # 3. Try full name fuzzy match
        if not client:
            client = find_client(name)
            if client:
                strategy = "fuzzy name match"

        if client:
            suggestions.append(
                {
                    "project_id": proj["id"],
                    "project_name": name,
                    "client_id": client.id,
                    "client_name": client.name,
                    "strategy": strategy,
                }
            )

    return suggestions


def apply_project_links(suggestions: list[dict]) -> int:
    """Apply suggested project-client links."""
    applied = 0
    for s in suggestions:
        update_project(s["project_id"], client_id=s["client_id"])
        applied += 1
    return applied


def get_data_quality_report() -> dict:
    """Get data quality metrics."""
    with get_connection() as conn:
        total_clients = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        tiered_clients = conn.execute(
            "SELECT COUNT(*) FROM clients WHERE tier IS NOT NULL"
        ).fetchone()[0]
        clients_with_health = conn.execute(
            "SELECT COUNT(*) FROM clients WHERE relationship_health IS NOT NULL"
        ).fetchone()[0]

        total_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        linked_projects = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE client_id IS NOT NULL"
        ).fetchone()[0]

        total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        items_with_client = conn.execute(
            "SELECT COUNT(*) FROM items WHERE client_id IS NOT NULL"
        ).fetchone()[0]
        items_with_due = conn.execute(
            "SELECT COUNT(*) FROM items WHERE due IS NOT NULL AND status = 'open'"
        ).fetchone()[0]
        open_items = conn.execute(
            "SELECT COUNT(*) FROM items WHERE status = 'open'"
        ).fetchone()[0]

    return {
        "clients": {
            "total": total_clients,
            "tiered": tiered_clients,
            "tiered_pct": round(100 * tiered_clients / total_clients, 1)
            if total_clients
            else 0,
            "with_health": clients_with_health,
        },
        "projects": {
            "total": total_projects,
            "linked": linked_projects,
            "linked_pct": round(100 * linked_projects / total_projects, 1)
            if total_projects
            else 0,
        },
        "items": {
            "total": total_items,
            "open": open_items,
            "with_client": items_with_client,
            "with_client_pct": round(100 * items_with_client / total_items, 1)
            if total_items
            else 0,
            "with_due_date": items_with_due,
            "due_date_pct": round(100 * items_with_due / open_items, 1)
            if open_items
            else 0,
        },
    }


def run_auto_classification() -> dict:
    """Run automatic tier classification and project linking."""
    results = {}

    # 1. Tier suggestions
    suggestions = get_tier_suggestions()
    high_conf = [s for s in suggestions if s.confidence == "high"]
    applied_tiers = apply_tier_suggestions(high_conf, confidence_threshold="high")
    results["tiers"] = {
        "suggestions": len(suggestions),
        "high_confidence": len(high_conf),
        "applied": applied_tiers,
    }

    # 2. Project links
    link_suggestions = suggest_project_client_links()
    applied_links = apply_project_links(link_suggestions)
    results["project_links"] = {
        "suggestions": len(link_suggestions),
        "applied": applied_links,
    }

    # 3. Data quality after
    results["quality"] = get_data_quality_report()

    return results


if __name__ == "__main__":
    logger.info("=== Auto-Classification ===\n")
    results = run_auto_classification()

    logger.info("Tier Classification:")
    t = results["tiers"]
    logger.info(f"  Suggestions: {t['suggestions']}")
    logger.info(f"  High confidence: {t['high_confidence']}")
    logger.info(f"  Applied: {t['applied']}")
    logger.info("\nProject Linking:")
    p = results["project_links"]
    logger.info(f"  Suggestions: {p['suggestions']}")
    logger.info(f"  Applied: {p['applied']}")
    logger.info("\nData Quality:")
    q = results["quality"]
    logger.info(f"  Clients tiered: {q['clients']['tiered_pct']}%")
    logger.info(f"  Projects linked: {q['projects']['linked_pct']}%")
    logger.info(f"  Items with client: {q['items']['with_client_pct']}%")
