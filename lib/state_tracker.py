#!/usr/bin/env python3
"""
State Tracker — Tracks what's been surfaced to avoid duplicate alerts.

Maintains:
- Last collection timestamps per source
- Hashes of surfaced items (to detect new vs seen)
- Surfaced item IDs with timestamps
- Change detection for intelligent filtering
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any, Set

STATE_FILE = Path(__file__).parent.parent / "data" / "state.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> Dict:
    """Load current state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return _default_state()
    return _default_state()


def _default_state() -> Dict:
    return {
        "version": 1,
        "last_collection": {},  # source -> ISO timestamp
        "last_surface": None,   # ISO timestamp of last heartbeat surface
        "surfaced_hashes": {},  # source -> {hash: timestamp}
        "pending_items": [],    # Items identified but not yet surfaced
        "acked_items": [],      # Items user acknowledged
    }


def save_state(state: Dict) -> None:
    """Save state to disk."""
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def hash_item(item: Dict, keys: List[str] = None) -> str:
    """Generate stable hash for an item."""
    if keys:
        subset = {k: item.get(k) for k in keys if k in item}
    else:
        subset = item
    content = json.dumps(subset, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def mark_collected(source: str) -> None:
    """Mark a source as collected now."""
    state = load_state()
    state["last_collection"][source] = datetime.now(timezone.utc).isoformat()
    save_state(state)


def get_last_collection(source: str) -> Optional[datetime]:
    """Get when a source was last collected."""
    state = load_state()
    ts = state.get("last_collection", {}).get(source)
    if ts:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return None


def mark_surfaced(source: str, items: List[Dict], hash_keys: List[str] = None) -> None:
    """Mark items as surfaced (won't alert again unless changed)."""
    state = load_state()
    now = datetime.now(timezone.utc).isoformat()
    
    if source not in state["surfaced_hashes"]:
        state["surfaced_hashes"][source] = {}
    
    for item in items:
        h = hash_item(item, hash_keys)
        state["surfaced_hashes"][source][h] = now
    
    state["last_surface"] = now
    save_state(state)


def filter_new_items(source: str, items: List[Dict], hash_keys: List[str] = None) -> List[Dict]:
    """Filter to only items not previously surfaced."""
    state = load_state()
    seen = set(state.get("surfaced_hashes", {}).get(source, {}).keys())
    
    new_items = []
    for item in items:
        h = hash_item(item, hash_keys)
        if h not in seen:
            new_items.append(item)
    
    return new_items


def get_new_count(source: str, items: List[Dict], hash_keys: List[str] = None) -> int:
    """Count how many items are new (not seen before)."""
    return len(filter_new_items(source, items, hash_keys))


def cleanup_old_hashes(max_age_days: int = 7) -> int:
    """Remove hashes older than max_age_days to prevent unbounded growth."""
    state = load_state()
    cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 86400)
    removed = 0
    
    for source in state.get("surfaced_hashes", {}):
        hashes = state["surfaced_hashes"][source]
        to_remove = []
        for h, ts in hashes.items():
            try:
                item_ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                if item_ts < cutoff:
                    to_remove.append(h)
            except:
                pass
        for h in to_remove:
            del hashes[h]
            removed += 1
    
    save_state(state)
    return removed


def get_state_summary() -> Dict:
    """Get summary of current state for debugging."""
    state = load_state()
    return {
        "last_collection": state.get("last_collection", {}),
        "last_surface": state.get("last_surface"),
        "surfaced_counts": {
            source: len(hashes) 
            for source, hashes in state.get("surfaced_hashes", {}).items()
        },
        "pending_count": len(state.get("pending_items", [])),
        "acked_count": len(state.get("acked_items", [])),
    }


if __name__ == "__main__":
    print(json.dumps(get_state_summary(), indent=2))
