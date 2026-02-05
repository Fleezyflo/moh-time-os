#!/usr/bin/env python3
"""Collect Google Chat mentions and unread messages."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "out"
GOG_ACCOUNT = "molham@hrmny.co"


def get_spaces(max_spaces: int = 20) -> list:
    """Get chat spaces (limited to most recent)."""
    cmd = ["gog", "chat", "spaces", "list", "--account", GOG_ACCOUNT, "--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        spaces = data.get("spaces", [])
        # Limit to avoid timeout - prioritize DMs and recent spaces
        return spaces[:max_spaces]
    except subprocess.TimeoutExpired:
        print("  Chat spaces list timed out")
        return []
    except Exception as e:
        print(f"  Chat spaces error: {e}")
        return []


def get_messages(space_id: str, max_messages: int = 10) -> list:
    """Get recent messages from a space."""
    cmd = ["gog", "chat", "messages", "list", space_id, "--account", GOG_ACCOUNT, "--max", str(max_messages), "--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        return data.get("messages", [])
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


def collect_chat() -> dict:
    """Fetch spaces and recent messages with mentions (parallel)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    now = datetime.now(timezone.utc)
    spaces = get_spaces()
    mentions = []
    
    def fetch_space_messages(space):
        space_id = space.get("resource", "").replace("spaces/", "")
        space_name = space.get("name", "Unknown")
        space_uri = space.get("uri", "")
        
        if not space_id:
            return []
        
        messages = get_messages(space_id, max_messages=10)
        space_mentions = []
        
        for msg in messages:
            text = msg.get("text", "")
            if "@Molham" in text or "molham" in text.lower():
                msg["_space_id"] = space_id
                msg["_space_name"] = space_name
                msg["_space_uri"] = space_uri
                space_mentions.append(msg)
        
        return space_mentions
    
    # Fetch all spaces in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_space_messages, s) for s in spaces]
        for future in as_completed(futures):
            try:
                mentions.extend(future.result())
            except Exception:
                pass
    
    return {
        "collected_at": now.isoformat(),
        "spaces": spaces,
        "mentions": mentions
    }


def save(data: dict, filename: str = "chat-mentions.json"):
    """Save to output directory."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


if __name__ == "__main__":
    data = collect_chat()
    path = save(data)
    print(f"Saved {len(data.get('mentions', []))} mentions from {len(data.get('spaces', []))} spaces to {path}")
