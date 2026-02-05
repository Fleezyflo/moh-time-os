#!/usr/bin/env python3
"""
MOH Time OS — Calendar Integration

Read/write Google Calendar with change bundles and MOHOS_BLOCK/v1 tagging.
"""

import json
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from ..change_bundles import create_calendar_bundle
from ..governance import get_domain_mode, can_write, DomainMode
from ..routing_engine import format_calendar_block


def fetch_events(hours: int = 48) -> List[Dict]:
    """Fetch calendar events for the next N hours."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)
    
    cmd = [
        "gog", "calendar", "events", "primary",
        "--from", now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--to", end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--json"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("events", [])
    except Exception as e:
        print(f"Calendar fetch error: {e}")
    
    return []


def is_system_owned(event: Dict) -> bool:
    """Check if event is system-owned (created by Time OS)."""
    description = event.get("description", "")
    return "MOHOS_BLOCK/v1" in description


def extract_dedupe_key(event: Dict) -> Optional[str]:
    """Extract dedupe key from a system-owned event."""
    description = event.get("description", "")
    for line in description.split("\n"):
        if line.startswith("task_dedupe_key:"):
            return line.split(":", 1)[1].strip()
    return None


def create_block(
    item: Dict,
    start_time: str,
    duration_minutes: int,
) -> Tuple[bool, str]:
    """
    Create a calendar block for an item.
    
    Returns: (success, message)
    """
    # Check domain mode
    if not can_write("calendar"):
        mode = get_domain_mode("calendar")
        return False, f"Calendar domain is in {mode.value} mode. Cannot create blocks."
    
    # Format block
    block = format_calendar_block(item, start_time, duration_minutes)
    
    # Create change bundle
    bundle = create_calendar_bundle(
        description=f"Create block: {block['summary']}",
        creates=[block],
    )
    
    # Execute via gog CLI
    cmd = [
        "gog", "calendar", "events", "add", "primary",
        "--title", block["summary"],
        "--start", block["start"]["dateTime"],
        "--end", block["end"]["dateTime"],
        "--description", block["description"],
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            from ..change_bundles import mark_applied
            mark_applied(bundle["id"])
            return True, f"Block created: {block['summary']}"
        else:
            from ..change_bundles import mark_failed
            mark_failed(bundle["id"], result.stderr)
            return False, f"Failed: {result.stderr}"
    except Exception as e:
        return False, f"Error: {e}"


def update_block(
    event_id: str,
    updates: Dict,
) -> Tuple[bool, str]:
    """Update a system-owned calendar block."""
    # Fetch current event for pre-image
    events = fetch_events(hours=168)  # Week
    event = next((e for e in events if e.get("id") == event_id), None)
    
    if not event:
        return False, "Event not found"
    
    if not is_system_owned(event):
        return False, "Cannot edit non-system-owned events"
    
    if not can_write("calendar"):
        return False, "Calendar domain not in Execute mode"
    
    # Create bundle with pre-image
    bundle = create_calendar_bundle(
        description=f"Update block: {event.get('summary')}",
        updates=[{"id": event_id, **updates}],
        pre_images={event_id: event},
    )
    
    # Execute update via gog CLI
    # Note: Actual gog update command would go here
    
    return True, "Update prepared (execution pending)"


def delete_block(event_id: str) -> Tuple[bool, str]:
    """Delete a system-owned calendar block."""
    events = fetch_events(hours=168)
    event = next((e for e in events if e.get("id") == event_id), None)
    
    if not event:
        return False, "Event not found"
    
    if not is_system_owned(event):
        return False, "Cannot delete non-system-owned events"
    
    if not can_write("calendar"):
        return False, "Calendar domain not in Execute mode"
    
    # Create bundle with pre-image for rollback
    bundle = create_calendar_bundle(
        description=f"Delete block: {event.get('summary')}",
        deletes=[event_id],
        pre_images={event_id: event},
    )
    
    # Execute via gog CLI
    cmd = ["gog", "calendar", "events", "delete", "primary", event_id, "--force"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            from ..change_bundles import mark_applied
            mark_applied(bundle["id"])
            return True, "Block deleted"
        else:
            return False, f"Failed: {result.stderr}"
    except Exception as e:
        return False, f"Error: {e}"


def find_linked_items(events: List[Dict]) -> Dict[str, List[Dict]]:
    """Find items linked to calendar events via dedupe keys."""
    linked = {}
    
    for event in events:
        if is_system_owned(event):
            dedupe_key = extract_dedupe_key(event)
            if dedupe_key:
                if dedupe_key not in linked:
                    linked[dedupe_key] = []
                linked[dedupe_key].append(event)
    
    return linked
