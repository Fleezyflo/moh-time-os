"""Query helpers for common access patterns."""

from datetime import date, timedelta
from typing import Any

from .entities import Project, find_client, get_client, list_clients, list_projects
from .items import Item, list_items
from .store import db_exists, get_connection


def open_items() -> list[Item]:
    """All open items, ordered by due date."""
    return list_items(status="open")


def overdue() -> list[Item]:
    """Open items past due."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    items = list_items(status="open", due_before=yesterday)
    return [i for i in items if i.is_overdue()]


def due_today() -> list[Item]:
    """Items due today."""
    today = date.today().isoformat()
    items = list_items(status="open", due_before=today, due_after=today)
    return [i for i in items if i.due == today]


def due_this_week() -> list[Item]:
    """Open items due within 7 days."""
    today = date.today().isoformat()
    end = (date.today() + timedelta(days=7)).isoformat()
    return list_items(status="open", due_before=end, due_after=today)


def due_soon(days: int = 3) -> list[Item]:
    """Open items due within N days."""
    today = date.today().isoformat()
    end = (date.today() + timedelta(days=days)).isoformat()
    return list_items(status="open", due_before=end, due_after=today)


def waiting() -> list[Item]:
    """Items in waiting status."""
    return list_items(status="waiting")


def waiting_too_long(days: int = 3) -> list[Item]:
    """Items waiting longer than N days."""
    items = waiting()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return [i for i in items if i.waiting_since and i.waiting_since < cutoff]


def for_client(client_id: str) -> list[Item]:
    """All open items for a client."""
    return list_items(status="open", client_id=client_id)


def for_client_by_name(name: str) -> list[Item]:
    """All open items for a client (by name lookup)."""
    client = find_client(name=name)
    if not client:
        return []
    return for_client(client.id)


def for_project(project_id: str) -> list[Item]:
    """All open items for a project."""
    return list_items(status="open", project_id=project_id)


def summary_stats() -> dict[str, Any]:
    """Get summary statistics."""
    if not db_exists():
        return {"error": "Database not initialized"}

    with get_connection() as conn:
        stats = {}

        stats["total_items"] = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

        stats["open"] = conn.execute("SELECT COUNT(*) FROM items WHERE status = 'open'").fetchone()[
            0
        ]

        stats["waiting"] = conn.execute(
            "SELECT COUNT(*) FROM items WHERE status = 'waiting'"
        ).fetchone()[0]

        stats["done"] = conn.execute("SELECT COUNT(*) FROM items WHERE status = 'done'").fetchone()[
            0
        ]

        stats["overdue"] = conn.execute(
            "SELECT COUNT(*) FROM items WHERE status = 'open' AND due IS NOT NULL AND due < date('now')"
        ).fetchone()[0]

        stats["due_this_week"] = conn.execute("""
            SELECT COUNT(*) FROM items
            WHERE status = 'open'
            AND due IS NOT NULL
            AND due >= date('now')
            AND due <= date('now', '+7 days')
        """).fetchone()[0]

        stats["clients"] = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]

        stats["people"] = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]

        stats["projects"] = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

        return stats


def client_summary(client_id: str) -> dict[str, Any]:
    """Get full summary for a client."""
    client = get_client(client_id)
    if not client:
        return {"error": "Client not found"}

    items = for_client(client_id)
    overdue_items = [i for i in items if i.is_overdue()]

    return {
        "client": client.full_context(),
        "tier": client.tier,
        "health": client.health,
        "ar_outstanding": client.ar_outstanding,
        "ar_aging": client.ar_aging,
        "open_items": len(items),
        "overdue_items": len(overdue_items),
        "items": items,
    }


def client_summary_by_name(name: str) -> dict[str, Any]:
    """Get full summary for a client by name."""
    client = find_client(name=name)
    if not client:
        return {"error": f'Client "{name}" not found'}
    return client_summary(client.id)


def at_risk_projects() -> list[Project]:
    """Projects with health != on_track."""
    return (
        list_projects(health="at_risk")
        + list_projects(health="blocked")
        + list_projects(health="late")
    )


def needs_attention() -> dict[str, Any]:
    """Get everything that needs attention right now."""
    result = {
        "overdue": overdue(),
        "due_today": due_today(),
        "due_this_week": due_this_week(),
        "waiting_too_long": waiting_too_long(3),
        "critical_clients": list_clients(health="critical"),
        "poor_clients": list_clients(health="poor"),
        "fair_clients": list_clients(health="fair"),
        "at_risk_projects": at_risk_projects(),
    }

    # Add counts
    result["counts"] = {
        "overdue": len(result["overdue"]),
        "due_today": len(result["due_today"]),
        "due_this_week": len(result["due_this_week"]),
        "waiting_too_long": len(result["waiting_too_long"]),
        "clients_at_risk": len(result["critical_clients"]) + len(result["poor_clients"]),
        "projects_at_risk": len(result["at_risk_projects"]),
    }

    result["needs_attention"] = any(
        [
            result["overdue"],
            result["due_today"],
            result["waiting_too_long"],
            result["critical_clients"],
            result["poor_clients"],
            result["at_risk_projects"],
        ]
    )

    return result


def generate_brief() -> str:
    """Generate a daily brief summary."""
    stats = summary_stats()
    attention = needs_attention()

    lines = ["## Daily Brief\n"]

    # Stats summary
    lines.append(
        f"**Items:** {stats['open']} open, {stats['waiting']} waiting, {stats['overdue']} overdue"
    )
    lines.append(
        f"**Entities:** {stats['clients']} clients, {stats['projects']} projects, {stats['people']} people\n"
    )

    if not attention["needs_attention"]:
        lines.append("✅ **All clear.** Nothing urgent needs attention.\n")
        return "\n".join(lines)

    # Overdue
    if attention["overdue"]:
        lines.append(f"### ⚠️ Overdue ({len(attention['overdue'])})")
        for item in attention["overdue"][:5]:
            lines.append(f"- {item.short_display()}")
        if len(attention["overdue"]) > 5:
            lines.append(f"  ... and {len(attention['overdue']) - 5} more")
        lines.append("")

    # Due today
    if attention["due_today"]:
        lines.append(f"### 📅 Due Today ({len(attention['due_today'])})")
        for item in attention["due_today"][:5]:
            lines.append(f"- {item.short_display()}")
        lines.append("")

    # Due this week (excluding today)
    due_week = [i for i in attention["due_this_week"] if i not in attention["due_today"]]
    if due_week:
        lines.append(f"### 📆 Due This Week ({len(due_week)})")
        for item in due_week[:5]:
            lines.append(f"- {item.short_display()}")
        if len(due_week) > 5:
            lines.append(f"  ... and {len(due_week) - 5} more")
        lines.append("")

    # Waiting too long
    if attention["waiting_too_long"]:
        lines.append(f"### ⏳ Waiting >3 days ({len(attention['waiting_too_long'])})")
        for item in attention["waiting_too_long"][:3]:
            lines.append(f"- {item.short_display()}")
        lines.append("")

    # At-risk clients
    at_risk = attention["critical_clients"] + attention["poor_clients"]
    if at_risk:
        lines.append(f"### 🔴 Clients at Risk ({len(at_risk)})")
        for client in at_risk:
            lines.append(
                f"- {client.name} (Tier {client.tier}): {client.health} — AR {client.ar_outstanding:,.0f} AED ({client.ar_aging})"
            )
        lines.append("")

    # Fair clients (warning)
    if attention["fair_clients"]:
        lines.append(f"### 🟡 Clients to Watch ({len(attention['fair_clients'])})")
        for client in attention["fair_clients"][:3]:
            lines.append(
                f"- {client.name}: AR {client.ar_outstanding:,.0f} AED ({client.ar_aging})"
            )
        lines.append("")

    # At-risk projects
    if attention["at_risk_projects"]:
        lines.append(f"### 🔴 Projects at Risk ({len(attention['at_risk_projects'])})")
        for project in attention["at_risk_projects"][:3]:
            lines.append(f"- {project.name}: {project.health}")
        lines.append("")

    return "\n".join(lines)
