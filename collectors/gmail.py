#!/usr/bin/env python3
"""Collect unread Gmail threads."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "out"


def collect_gmail(max_threads: int = 50) -> dict:
    """Fetch unread inbox threads."""
    now = datetime.now(timezone.utc)
    
    cmd = [
        "gog", "gmail", "search", "is:unread in:inbox",
        "--max", str(max_threads),
        "--json"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"error": result.stderr, "threads": []}
    
    data = json.loads(result.stdout)
    return {
        "collected_at": now.isoformat(),
        "threads": data.get("threads", [])
    }


def save(data: dict, filename: str = "gmail-unread.json"):
    """Save to output directory."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


if __name__ == "__main__":
    data = collect_gmail()
    path = save(data)
    print(f"Saved {len(data.get('threads', []))} threads to {path}")
