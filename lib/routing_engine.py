#!/usr/bin/env python3
"""
MOH Time OS — Routing Engine

Deterministic projection from canonical objects → Google Tasks.
Per MOH_TIME_OS_ROUTING.md spec.
"""

import json
import logging
from datetime import datetime

from .config_store import get_lane
from .status_engine import Status, get_status_prefix

logger = logging.getLogger(__name__)


# MOHOS/v1 template
MOHOS_HEADER_TEMPLATE = """MOHOS/v1
lane: {lane}
project: {project}
status: {status}
urgency: {urgency}
impact: {impact}
deadline: {deadline_type}:{deadline}
effort: {effort_min}-{effort_max}
waiting_for: {waiting_for}
sensitivity: {sensitivity}
source: {source}
dedupe_key: {dedupe_key}
---
{context}"""


def generate_dedupe_key(item: dict) -> str:
    """Generate a stable dedupe key for an item."""
    import hashlib

    # Use source reference if available
    source_ref = item.get("source_ref")
    if source_ref:
        return hashlib.sha256(source_ref.encode()).hexdigest()[:24]

    # Fallback to item ID
    item_id = item.get("id")
    if item_id:
        return hashlib.sha256(item_id.encode()).hexdigest()[:24]

    # Last resort: hash the title
    title = item.get("what") or item.get("title") or ""
    return hashlib.sha256(title.encode()).hexdigest()[:24]


def determine_destination_list(item: dict) -> tuple[str, str]:
    """
    Determine the destination Google Tasks list for an item.

    Returns: (list_name, reason)
    """
    lane = item.get("lane")
    status = item.get("status")

    # Rule 1: If lane is unknown → Unknowns
    if not lane or lane == "unknown":
        return "Unknowns", "Lane unknown or uncertain"

    # Rule 2: New captures → Inbox until normalized
    if status == Status.NEW.value:
        return "Inbox", "New item awaiting normalization"

    # Rule 3: Get lane display name
    lane_config = get_lane(lane)
    list_name = lane_config.get("display_name", lane.title()) if lane_config else lane.title()

    return list_name, f"Routed to lane: {lane}"


def should_mirror_to_waiting(item: dict) -> bool:
    """Check if item should be mirrored to Waiting-for list."""
    status = item.get("status")
    return status in [Status.DELEGATED.value, Status.WAITING_FOR.value]


def format_task_notes(item: dict) -> str:
    """Format item as MOHOS/v1 task notes."""
    # Extract or default values
    lane = item.get("lane", "unknown")
    project = item.get("project_id") or "(unenrolled)"
    status = item.get("status", Status.NEW.value)
    urgency = item.get("urgency", "medium")
    impact = item.get("impact", "medium")
    deadline_type = item.get("deadline_type", "soft")
    deadline = item.get("due", "")
    effort_min = item.get("effort_min", "")
    effort_max = item.get("effort_max", "")
    waiting_for = item.get("waiting_for", "")

    # Sensitivity flags
    sensitivity_flags = item.get("sensitivity_flags")
    if isinstance(sensitivity_flags, list):
        sensitivity = ",".join(sensitivity_flags) if sensitivity_flags else ""
    else:
        sensitivity = sensitivity_flags or ""

    # Source reference
    source_type = item.get("source_type", "manual")
    source_ref = item.get("source_ref", "")
    source = f"{source_type}:{source_ref}" if source_ref else source_type

    # Dedupe key
    dedupe_key = item.get("dedupe_key") or generate_dedupe_key(item)

    # Context
    context = item.get("context_summary") or item.get("notes") or ""

    return MOHOS_HEADER_TEMPLATE.format(
        lane=lane,
        project=project,
        status=status,
        urgency=urgency,
        impact=impact,
        deadline_type=deadline_type,
        deadline=deadline,
        effort_min=effort_min or "",
        effort_max=effort_max or "",
        waiting_for=waiting_for,
        sensitivity=sensitivity,
        source=source,
        dedupe_key=dedupe_key,
        context=context,
    )


def format_task_title(item: dict) -> str:
    """Format task title with optional status prefix."""
    title = item.get("what") or item.get("title") or "Untitled"
    status = item.get("status", "")

    prefix = get_status_prefix(status)
    if prefix:
        return f"{prefix} {title}"

    return title


def route_item(item: dict) -> dict:
    """
    Route an item to its destination.

    Returns routing decision with all details needed for projection.
    """
    # Determine destination
    dest_list, reason = determine_destination_list(item)

    # Check if mirroring needed
    mirror = should_mirror_to_waiting(item)

    # Format for projection
    title = format_task_title(item)
    notes = format_task_notes(item)
    dedupe_key = item.get("dedupe_key") or generate_dedupe_key(item)

    return {
        "item_id": item.get("id"),
        "destination_list": dest_list,
        "mirror_to_waiting": mirror,
        "reason": reason,
        "title": title,
        "notes": notes,
        "dedupe_key": dedupe_key,
        "due": item.get("due"),
    }


def batch_route(items: list[dict]) -> list[dict]:
    """Route multiple items."""
    return [route_item(item) for item in items]


def check_duplicates(items: list[dict]) -> list[dict]:
    """
    Check for duplicate dedupe keys.

    Returns list of conflicts if duplicates found.
    """
    seen = {}
    conflicts = []

    for item in items:
        dedupe_key = item.get("dedupe_key") or generate_dedupe_key(item)

        if dedupe_key in seen:
            conflicts.append(
                {
                    "type": "duplicate",
                    "dedupe_key": dedupe_key,
                    "items": [seen[dedupe_key], item],
                }
            )
        else:
            seen[dedupe_key] = item

    return conflicts


# Calendar block template
CALENDAR_BLOCK_TEMPLATE = """MOHOS_BLOCK/v1
lane: {lane}
project: {project}
task_dedupe_key: {dedupe_key}
status: planned
planned_minutes: {minutes}
source: system
---
{notes}"""


def format_calendar_block(item: dict, start_time: str, duration_minutes: int) -> dict:
    """
    Format a calendar block for an item.

    Returns event data for Google Calendar API.
    """
    lane = item.get("lane", "unknown")
    project = item.get("project_id") or "(unenrolled)"
    dedupe_key = item.get("dedupe_key") or generate_dedupe_key(item)
    title = item.get("what") or item.get("title") or "Work Block"

    description = CALENDAR_BLOCK_TEMPLATE.format(
        lane=lane,
        project=project,
        dedupe_key=dedupe_key,
        minutes=duration_minutes,
        notes=f"Task: {title}",
    )

    # Calculate end time
    from datetime import timedelta

    start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    end = start + timedelta(minutes=duration_minutes)

    return {
        "summary": f"[{lane.upper()}] {title}",
        "description": description,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "colorId": None,  # Could map lane to color
        "_mohos_dedupe_key": dedupe_key,
        "_mohos_item_id": item.get("id"),
    }


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        logger.info("Usage: routing_engine.py <command> [args]")
        logger.info("Commands: route <item_json>, demo")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "demo":
        # Demo routing
        demo_item = {
            "id": "item123",
            "what": "Review Five Guys proposal",
            "status": "planned",
            "lane": "client",
            "urgency": "high",
            "impact": "medium",
            "due": "2026-02-05",
            "source_type": "email",
            "source_ref": "msg123abc",
        }

        result = route_item(demo_item)
        logger.info(json.dumps(result, indent=2))
    elif cmd == "route" and len(sys.argv) >= 3:
        try:
            item = json.loads(sys.argv[2])
        except json.JSONDecodeError as e:
            logger.error(f"Error: Invalid JSON item: {e}")
            sys.exit(1)
        result = route_item(item)
        logger.info(json.dumps(result, indent=2))
    else:
        logger.info(f"Unknown command: {cmd}")
