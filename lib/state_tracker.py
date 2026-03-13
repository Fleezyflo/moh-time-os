#!/usr/bin/env python3
"""
State Tracker — Tracks what's been surfaced to avoid duplicate alerts.

Maintains:
- Last collection timestamps per source
- Hashes of surfaced items (to detect new vs seen)
- Surfaced item IDs with timestamps
- Change detection for intelligent filtering
"""

import fcntl
import hashlib
import json
import logging
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from lib import paths
from lib.compat import UTC
from lib.state_store import get_store

logger = logging.getLogger(__name__)

STATE_FILE = paths.data_dir() / "state.json"
_STATE_LOCK = STATE_FILE.parent / ".state.lock"


@contextmanager
def _file_lock():
    """Acquire exclusive lock for state file read-modify-write cycles.

    Without this, concurrent threads/processes could both read stale
    state, both write back, and one thread's changes would be lost
    (audit finding: state tracker lost updates).
    """
    _STATE_LOCK.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(_STATE_LOCK, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def load_state() -> dict:
    """Load current state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return _default_state()
    return _default_state()


def _default_state() -> dict:
    return {
        "version": 1,
        "last_collection": {},  # source -> ISO timestamp
        "last_surface": None,  # ISO timestamp of last heartbeat surface
        "surfaced_hashes": {},  # source -> {hash: timestamp}
        "pending_items": [],  # Items identified but not yet surfaced
        "acked_items": [],  # Items user acknowledged
    }


def save_state(state: dict) -> None:
    """Save state to disk atomically via temp file + rename.

    Previous version used write_text() directly, which could leave
    truncated/corrupt state files on crash (audit fix).
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(state, indent=2, default=str)
    # Atomic write: write to temp then rename
    fd = tempfile.NamedTemporaryFile(mode="w", dir=STATE_FILE.parent, suffix=".tmp", delete=False)
    try:
        fd.write(content)
        fd.flush()
        fd.close()
        Path(fd.name).rename(STATE_FILE)
    except BaseException:
        Path(fd.name).unlink(missing_ok=True)
        raise


def hash_item(item: dict, keys: list[str] = None) -> str:
    """Generate stable hash for an item."""
    subset = {k: item.get(k) for k in keys if k in item} if keys else item
    content = json.dumps(subset, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def mark_collected(source: str) -> None:
    """Mark a source as collected now.

    Delegates to StateStore.update_sync_state() for thread-safe, DB-backed
    tracking. The JSON state file is no longer updated for collection timestamps
    — use get_sync_states() on the store instead.
    """
    get_store().update_sync_state(source, success=True)


def get_last_collection(source: str) -> datetime | None:
    """Get when a source was last collected.

    Reads from StateStore (DB-backed) instead of JSON state file.
    """
    states = get_store().get_sync_states()
    info = states.get(source)
    if info is None:
        return None
    last_sync = info["last_sync"]
    if last_sync:
        return datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
    return None


def mark_surfaced(source: str, items: list[dict], hash_keys: list[str] = None) -> None:
    """Mark items as surfaced (won't alert again unless changed).

    Uses file lock to prevent lost updates from concurrent writes
    (audit finding: state tracker race condition).
    """
    with _file_lock():
        state = load_state()
        now = datetime.now(UTC).isoformat()

        if source not in state["surfaced_hashes"]:
            state["surfaced_hashes"][source] = {}

        for item in items:
            h = hash_item(item, hash_keys)
            state["surfaced_hashes"][source][h] = now

        state["last_surface"] = now
        save_state(state)


def filter_new_items(source: str, items: list[dict], hash_keys: list[str] = None) -> list[dict]:
    """Filter to only items not previously surfaced."""
    state = load_state()
    seen = set(state.get("surfaced_hashes", {}).get(source, {}).keys())

    new_items = []
    for item in items:
        h = hash_item(item, hash_keys)
        if h not in seen:
            new_items.append(item)

    return new_items


def get_new_count(source: str, items: list[dict], hash_keys: list[str] = None) -> int:
    """Count how many items are new (not seen before)."""
    return len(filter_new_items(source, items, hash_keys))


def cleanup_old_hashes(max_age_days: int = 7) -> int:
    """Remove hashes older than max_age_days to prevent unbounded growth."""
    with _file_lock():
        state = load_state()
        cutoff = datetime.now(UTC).timestamp() - (max_age_days * 86400)
        removed = 0

        for source in state.get("surfaced_hashes", {}):
            hashes = state["surfaced_hashes"][source]
            to_remove = []
            for h, ts in hashes.items():
                try:
                    item_ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                    if item_ts < cutoff:
                        to_remove.append(h)
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse timestamp '{ts}': {e}")
            for h in to_remove:
                del hashes[h]
                removed += 1

        save_state(state)
        return removed


def get_state_summary() -> dict:
    """Get summary of current state for debugging."""
    state = load_state()
    return {
        "last_collection": state.get("last_collection", {}),
        "last_surface": state.get("last_surface"),
        "surfaced_counts": {
            source: len(hashes) for source, hashes in state.get("surfaced_hashes", {}).items()
        },
        "pending_count": len(state.get("pending_items", [])),
        "acked_count": len(state.get("acked_items", [])),
    }


if __name__ == "__main__":
    logger.info(json.dumps(get_state_summary(), indent=2))
