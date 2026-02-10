"""
Morning brief generation for MOH Time OS.

Generates a formatted daily brief with:
- Overdue items with context
- Due today
- Client attention (AR issues, health)
- Summary stats
"""

import logging
from datetime import date

from .entities import list_clients
from .queries import due_today, due_tomorrow, overdue, summary_stats, waiting_long

logger = logging.getLogger(__name__)


def generate_morning_brief(
    max_overdue: int = 5,
    max_due_today: int = 10,
    include_waiting: bool = True,
    include_ar_alerts: bool = True,
) -> str:
    """
    Generate morning brief.

    Returns formatted markdown string.
    """
    lines = []
    today = date.today()

    lines.append(f"## Morning Brief — {today.strftime('%B %d, %Y')}")
    lines.append("")

    # ─────────────────────────────────────────────────────────────────
    # OVERDUE
    # ─────────────────────────────────────────────────────────────────
    overdue_items = overdue(limit=50)

    # Filter to recent overdue (not ancient Asana cruft)
    recent_overdue = [i for i in overdue_items if i.days_overdue() <= 30]

    if recent_overdue:
        lines.append(f"### 🔴 Overdue ({len(recent_overdue)})")
        lines.append("")

        for item in recent_overdue[:max_overdue]:
            lines.append(
                f"- **{item.what}** — due {item.due} ({item.days_overdue()}d ago)"
            )

            # Context line
            context_parts = []
            if item.counterparty:
                ctx = item.counterparty
                if item.snapshot and item.snapshot.person_role:
                    ctx += f" ({item.snapshot.person_role})"
                context_parts.append(ctx)
            if item.context_client_name:
                ctx = item.context_client_name
                if item.snapshot and item.snapshot.client_tier:
                    ctx += f" (Tier {item.snapshot.client_tier})"
                context_parts.append(ctx)

            if context_parts:
                lines.append(f"  {' @ '.join(context_parts)}")

            if item.context_stakes:
                lines.append(f"  Stakes: {item.context_stakes}")

            lines.append("")

        if len(recent_overdue) > max_overdue:
            lines.append(f"*+ {len(recent_overdue) - max_overdue} more overdue items*")
            lines.append("")

    # ─────────────────────────────────────────────────────────────────
    # DUE TODAY
    # ─────────────────────────────────────────────────────────────────
    today_items = due_today()

    if today_items:
        lines.append(f"### 📅 Due Today ({len(today_items)})")
        lines.append("")

        for item in today_items[:max_due_today]:
            line = f"- **{item.what}**"
            if item.context_client_name:
                line += f" | {item.context_client_name}"
            lines.append(line)

        if len(today_items) > max_due_today:
            lines.append(f"*+ {len(today_items) - max_due_today} more*")

        lines.append("")

    # ─────────────────────────────────────────────────────────────────
    # DUE TOMORROW
    # ─────────────────────────────────────────────────────────────────
    tomorrow_items = due_tomorrow()

    if tomorrow_items:
        lines.append(f"### 📆 Due Tomorrow ({len(tomorrow_items)})")
        lines.append("")

        for item in tomorrow_items[:5]:
            line = f"- {item.what}"
            if item.context_client_name:
                line += f" | {item.context_client_name}"
            lines.append(line)

        if len(tomorrow_items) > 5:
            lines.append(f"*+ {len(tomorrow_items) - 5} more*")

        lines.append("")

    # ─────────────────────────────────────────────────────────────────
    # ATTENTION (AR, Waiting)
    # ─────────────────────────────────────────────────────────────────
    attention_items = []

    # AR alerts
    if include_ar_alerts:
        clients_ar = list_clients(has_ar_overdue=True, limit=10)
        for client in clients_ar:
            if client.ar_overdue > 50000:  # Only significant amounts
                attention_items.append(
                    f"**{client.name}** AR {client.ar_overdue:,.0f} AED overdue ({client.ar_aging_bucket})"
                )

    # Long waiting items
    if include_waiting:
        long_waiting = waiting_long(days=7, limit=5)
        if long_waiting:
            attention_items.append(
                f"{len(long_waiting)} items waiting 7+ days on others"
            )

    if attention_items:
        lines.append("### ⚠️ Attention")
        lines.append("")
        for item in attention_items:
            lines.append(f"- {item}")
        lines.append("")

    # ─────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────
    stats = summary_stats()

    lines.append("### 📊 Summary")
    lines.append("")
    lines.append(
        f"**{stats['open']}** open | **{stats['waiting']}** waiting | **{stats['due_this_week']}** due this week"
    )

    if stats["high_priority"] > 0:
        lines.append(f"🔴 **{stats['high_priority']}** high priority items")

    lines.append("")

    return "\n".join(lines)


def generate_status_summary() -> str:
    """Generate quick status summary (shorter than full brief)."""
    stats = summary_stats()
    overdue_items = overdue(limit=100)
    recent_overdue = [i for i in overdue_items if i.days_overdue() <= 30]

    lines = [
        f"**Status**: {stats['open']} open, {stats['waiting']} waiting",
        f"**Overdue**: {len(recent_overdue)} items",
        f"**Due this week**: {stats['due_this_week']}",
    ]

    if stats["clients_ar_overdue"] > 0:
        lines.append(
            f"**AR attention**: {stats['clients_ar_overdue']} clients with overdue AR"
        )

    return "\n".join(lines)


def generate_client_status(client_name: str) -> str:
    """Generate status for a specific client."""
    from .entities import find_client
    from .queries import for_client

    client = find_client(client_name)
    if not client:
        return f"Client '{client_name}' not found"

    lines = [f"## {client.name}"]
    lines.append("")

    # Client info
    info_parts = []
    if client.tier:
        info_parts.append(f"Tier {client.tier}")
    if client.health:
        info_parts.append(f"Health: {client.health}")
    if client.ar_total > 0:
        info_parts.append(f"AR: {client.ar_total:,.0f} AED")
        if client.ar_aging_bucket and client.ar_aging_bucket != "current":
            info_parts[-1] += f" ({client.ar_aging_bucket} overdue)"

    if info_parts:
        lines.append(" | ".join(info_parts))
        lines.append("")

    if client.notes:
        lines.append(f"*{client.notes}*")
        lines.append("")

    # Open items
    items = for_client(client.id, status="open")
    if items:
        lines.append(f"### Open Items ({len(items)})")
        lines.append("")
        for item in items[:10]:
            line = f"- **{item.what}**"
            if item.due:
                if item.is_overdue():
                    line += f" — ⚠️ {item.days_overdue()}d overdue"
                else:
                    line += f" — due {item.due}"
            lines.append(line)

        if len(items) > 10:
            lines.append(f"*+ {len(items) - 10} more*")
    else:
        lines.append("*No open items*")

    return "\n".join(lines)


if __name__ == "__main__":
    logger.info(generate_morning_brief())
