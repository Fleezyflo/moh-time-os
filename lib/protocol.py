"""A Protocol — How I (A) use MOH Time OS.

This module provides the high-level functions for:
- Session start (health check)
- Heartbeat (check for urgent items)
- Surfacing (items with full context)
- Query handling (natural language queries)
"""

from typing import Optional, List, Tuple, Dict, Any
from datetime import date

from .health import startup_check, HealthStatus, status_report
from .queries import (
    overdue, due_today, due_soon, waiting, waiting_too_long,
    needs_attention, generate_brief, summary_stats,
    for_client_by_name, client_summary_by_name,
)
from .items import Item, list_items, get_item
from .resolve import resolve_client, resolve_person, resolve_project
from .capture import capture_item, quick_capture


def on_session_start() -> Tuple[bool, str]:
    """
    Run on session start.
    Returns (healthy, message).
    
    If healthy: proceed silently or with brief status
    If degraded: announce issue
    If failed: announce failure, guide recovery
    """
    status, msg = startup_check()
    
    if status == HealthStatus.HEALTHY:
        return True, msg
    elif status == HealthStatus.DEGRADED:
        return True, f"⚠️ {msg}"
    else:
        return False, f"🔴 {msg}"


def on_heartbeat() -> Tuple[bool, str]:
    """
    Run during heartbeat.
    Returns (needs_attention, message).
    
    If needs_attention=True: message contains what to surface
    If needs_attention=False: return HEARTBEAT_OK
    """
    attention = needs_attention()
    
    if not attention['needs_attention']:
        return False, "HEARTBEAT_OK"
    
    # Build alert message
    lines = []
    counts = attention['counts']
    
    # Summary line
    alerts = []
    if counts['overdue']:
        alerts.append(f"{counts['overdue']} overdue")
    if counts['due_today']:
        alerts.append(f"{counts['due_today']} due today")
    if counts['waiting_too_long']:
        alerts.append(f"{counts['waiting_too_long']} waiting >3d")
    if counts['clients_at_risk']:
        alerts.append(f"{counts['clients_at_risk']} clients at risk")
    
    lines.append(f"🔔 **MOH Time OS Alert:** {', '.join(alerts)}")
    lines.append("")
    
    # Overdue items (most urgent) - synthesize top 2, list rest
    if attention['overdue']:
        lines.append("**Overdue:**")
        for item in attention['overdue'][:2]:
            lines.append(f"• {item.synthesize(refresh_context=True)}")
            lines.append("")
        if len(attention['overdue']) > 2:
            lines.append(f"Plus {len(attention['overdue']) - 2} more overdue items.")
        lines.append("")
    
    # Due today - synthesize all
    if attention['due_today']:
        lines.append("**Due Today:**")
        for item in attention['due_today'][:3]:
            lines.append(f"• {item.synthesize(refresh_context=True)}")
            lines.append("")
    
    # Waiting too long
    if attention['waiting_too_long']:
        lines.append("**Waiting >3 days:**")
        for item in attention['waiting_too_long'][:2]:
            lines.append(f"• {item.synthesize(refresh_context=True)}")
        lines.append("")
    
    return True, "\n".join(lines)


def handle_query(query: str) -> str:
    """
    Handle a natural language query about the system.
    
    Examples:
        "what's open?" -> list open items
        "what's overdue?" -> list overdue items
        "status" -> system status
        "what about GMG?" -> client summary
        "brief" -> daily brief
    """
    query_lower = query.lower().strip()
    
    # Status queries
    if query_lower in ['status', 'health', 'system status']:
        return status_report()
    
    # Stats
    if query_lower in ['stats', 'statistics', 'numbers']:
        stats = summary_stats()
        return (
            f"**Items:** {stats['open']} open, {stats['waiting']} waiting, "
            f"{stats['overdue']} overdue\n"
            f"**Entities:** {stats['clients']} clients, {stats['projects']} projects, "
            f"{stats['people']} people"
        )
    
    # Brief
    if query_lower in ['brief', 'daily brief', 'summary']:
        return generate_brief()
    
    # Overdue
    if 'overdue' in query_lower:
        items = overdue()
        if not items:
            return "No overdue items 🎉"
        
        lines = [f"**{len(items)} Overdue Items:**\n"]
        # Synthesize top 5, list rest briefly
        for item in items[:5]:
            lines.append(f"• {item.synthesize(refresh_context=True)}")
            lines.append("")
        if len(items) > 5:
            lines.append(f"Plus {len(items) - 5} more:")
            for item in items[5:15]:
                lines.append(f"  - {item.short_display()}")
        if len(items) > 15:
            lines.append(f"  ... +{len(items) - 15} more")
        return "\n".join(lines)
    
    # Open items
    if "what's open" in query_lower or 'open items' in query_lower:
        items = list_items(status='open', limit=20)
        if not items:
            return "No open items"
        
        lines = [f"**{len(items)} Open Items:**\n"]
        for item in items[:15]:
            lines.append(f"• {item.short_display()}")
        return "\n".join(lines)
    
    # Due today
    if 'due today' in query_lower or 'today' in query_lower:
        items = due_today()
        if not items:
            return f"Nothing due today ({date.today().isoformat()})"
        
        lines = [f"**{len(items)} Due Today:**\n"]
        for item in items:
            lines.append(f"• {item.what}")
        return "\n".join(lines)
    
    # Due this week / due soon
    if 'this week' in query_lower or 'due soon' in query_lower:
        items = due_soon(7)
        if not items:
            return "Nothing due in the next 7 days"
        
        lines = [f"**{len(items)} Due This Week:**\n"]
        for item in items[:10]:
            lines.append(f"• {item.short_display()}")
        return "\n".join(lines)
    
    # Waiting
    if 'waiting' in query_lower:
        items = waiting()
        if not items:
            return "No items in waiting status"
        
        lines = [f"**{len(items)} Waiting:**\n"]
        for item in items[:10]:
            lines.append(f"• {item.what}")
            if item.waiting_since:
                lines.append(f"  ↳ since {item.waiting_since}")
        return "\n".join(lines)
    
    # Client query ("what about X", "how's X", "GMG status")
    client_patterns = [
        r"what about (.+?)(?:\?|$)",
        r"how'?s (.+?)(?:\?|$)",
        r"(.+?) status",
        r"status of (.+?)(?:\?|$)",
    ]
    
    import re
    for pattern in client_patterns:
        match = re.search(pattern, query_lower)
        if match:
            client_name = match.group(1).strip()
            result = resolve_client(client_name)
            if result and result.confidence > 0.5:
                summary = client_summary_by_name(result.entity.name)
                if 'error' not in summary:
                    lines = [
                        f"**{summary['client']}**",
                        f"Tier: {summary['tier']} | Health: {summary['health']}",
                        f"AR: {summary['ar_outstanding']:,.0f} AED ({summary['ar_aging']})",
                        f"Open items: {summary['open_items']} ({summary['overdue_items']} overdue)",
                    ]
                    if summary['items']:
                        lines.append("\n**Items:**")
                        for item in summary['items'][:5]:
                            lines.append(f"• {item.short_display()}")
                    return "\n".join(lines)
    
    # Relationship query
    relationship_patterns = [
        r"how'?s (?:the |our )?relationship with (.+?)(?:\?|$)",
        r"relationship with (.+?)(?:\?|$)",
        r"how are (?:we|things) with (.+?)(?:\?|$)",
    ]
    
    for pattern in relationship_patterns:
        match = re.search(pattern, query_lower)
        if match:
            client_name = match.group(1).strip()
            result = resolve_client(client_name)
            if result and result.confidence > 0.5:
                client = result.entity
                # Get client items and contacts
                from .contacts import list_client_contacts
                contacts = list_client_contacts(client.id)
                items = for_client_by_name(client.name)
                overdue_items = [i for i in items if i.is_overdue()]
                
                lines = [f"## Relationship with {client.name}\n"]
                
                # Health summary
                lines.append(f"**Status:** {client.health} (Tier {client.tier})")
                if client.ar_outstanding > 0:
                    lines.append(f"**AR:** {client.ar_outstanding:,.0f} AED ({client.ar_aging})")
                    if client.payment_pattern != 'Unknown':
                        lines.append(f"**Payment Pattern:** {client.payment_pattern}")
                
                # Contacts
                if contacts:
                    lines.append(f"\n**Contacts ({len(contacts)}):**")
                    for c in contacts[:5]:
                        role = f" ({c.role})" if c.role else ""
                        lines.append(f"  • {c.name}{role}")
                else:
                    lines.append(f"\n**Contacts:** None registered")
                
                # Items
                lines.append(f"\n**Open Items:** {len(items)}")
                if overdue_items:
                    lines.append(f"**Overdue:** {len(overdue_items)}")
                
                if items:
                    lines.append("\n**Recent items:**")
                    for item in items[:3]:
                        lines.append(f"  • {item.short_display()}")
                
                return "\n".join(lines)
            else:
                return f"Client '{client_name}' not found"
    
    # Fallback
    return (
        "I can answer:\n"
        "• `status` - system health\n"
        "• `stats` - summary numbers\n"
        "• `brief` - daily brief\n"
        "• `what's overdue?` - overdue items\n"
        "• `what's open?` - all open items\n"
        "• `due today` - items due today\n"
        "• `what about [client]?` - client summary\n"
        "• `how's our relationship with [client]?` - relationship details"
    )


def surface_item(item_id: str) -> str:
    """Surface an item with full context."""
    item = get_item(item_id, include_history=True)
    if not item:
        return f"Item not found: {item_id}"
    
    return item.full_context_display()


# Convenience re-exports for A to use
track = capture_item
quick_track = quick_capture
