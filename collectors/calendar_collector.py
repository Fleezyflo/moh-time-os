#!/usr/bin/env python3
"""Collect calendar events for next 24-48h."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "out"


def collect_calendar(hours_ahead: int = 48) -> dict:
    """Fetch calendar events for the next N hours."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours_ahead)
    
    cmd = [
        "gog", "calendar", "events", "primary",
        "--from", now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--to", end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--json"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"error": result.stderr, "events": []}
    
    data = json.loads(result.stdout)
    return {
        "collected_at": now.isoformat(),
        "range_hours": hours_ahead,
        "events": data.get("events", [])
    }


def save(data: dict, filename: str = "calendar-next.json"):
    """Save to output directory."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


if __name__ == "__main__":
    data = collect_calendar()
    path = save(data)
    print(f"Saved {len(data.get('events', []))} events to {path}")
