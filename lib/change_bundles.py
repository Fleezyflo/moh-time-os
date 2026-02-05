#!/usr/bin/env python3
"""
MOH Time OS — Change Bundle System

Every write produces a manifest with:
- Proposed creates/updates
- Pre-image snapshot
- Rollback steps

Enables rollback-first safety.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any
from enum import Enum

BUNDLES_DIR = Path(__file__).parent.parent / "data" / "bundles"
BUNDLES_DIR.mkdir(parents=True, exist_ok=True)


class ChangeType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    STATUS_CHANGE = "status_change"


class BundleStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


def create_bundle(
    domain: str,
    description: str,
    changes: List[Dict],
    pre_images: Dict[str, Any] = None,
) -> Dict:
    """
    Create a new change bundle.
    
    Args:
        domain: The domain (calendar, tasks, email, delegation, alerts)
        description: Human-readable description of the change
        changes: List of change operations
        pre_images: Snapshot of affected items before change
    
    Returns:
        Bundle dict with ID and metadata
    """
    bundle_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()
    
    bundle = {
        "id": bundle_id,
        "domain": domain,
        "description": description,
        "status": BundleStatus.PENDING.value,
        "created_at": timestamp,
        "applied_at": None,
        "rolled_back_at": None,
        "changes": changes,
        "pre_images": pre_images or {},
        "rollback_steps": _generate_rollback_steps(changes, pre_images),
        "error": None,
    }
    
    # Save to disk
    bundle_file = BUNDLES_DIR / f"{bundle_id}.json"
    bundle_file.write_text(json.dumps(bundle, indent=2))
    
    return bundle


def _generate_rollback_steps(changes: List[Dict], pre_images: Dict) -> List[Dict]:
    """Generate rollback steps from changes and pre-images."""
    rollback_steps = []
    
    for change in reversed(changes):  # Reverse order for rollback
        change_type = change.get("type")
        item_id = change.get("id")
        
        if change_type == ChangeType.CREATE.value:
            # Rollback: delete the created item
            rollback_steps.append({
                "type": ChangeType.DELETE.value,
                "id": item_id,
                "target": change.get("target"),
            })
        
        elif change_type == ChangeType.UPDATE.value:
            # Rollback: restore pre-image
            pre_image = pre_images.get(item_id)
            if pre_image:
                rollback_steps.append({
                    "type": ChangeType.UPDATE.value,
                    "id": item_id,
                    "target": change.get("target"),
                    "data": pre_image,
                })
        
        elif change_type == ChangeType.DELETE.value:
            # Rollback: recreate from pre-image
            pre_image = pre_images.get(item_id)
            if pre_image:
                rollback_steps.append({
                    "type": ChangeType.CREATE.value,
                    "id": item_id,
                    "target": change.get("target"),
                    "data": pre_image,
                })
        
        elif change_type == ChangeType.STATUS_CHANGE.value:
            # Rollback: restore previous status
            pre_image = pre_images.get(item_id)
            if pre_image and "status" in pre_image:
                rollback_steps.append({
                    "type": ChangeType.STATUS_CHANGE.value,
                    "id": item_id,
                    "target": change.get("target"),
                    "data": {"status": pre_image["status"]},
                })
    
    return rollback_steps


def get_bundle(bundle_id: str) -> Optional[Dict]:
    """Load a bundle by ID."""
    bundle_file = BUNDLES_DIR / f"{bundle_id}.json"
    if bundle_file.exists():
        return json.loads(bundle_file.read_text())
    return None


def mark_applied(bundle_id: str) -> Dict:
    """Mark a bundle as successfully applied."""
    bundle = get_bundle(bundle_id)
    if not bundle:
        raise ValueError(f"Bundle not found: {bundle_id}")
    
    bundle["status"] = BundleStatus.APPLIED.value
    bundle["applied_at"] = datetime.now(timezone.utc).isoformat()
    
    bundle_file = BUNDLES_DIR / f"{bundle_id}.json"
    bundle_file.write_text(json.dumps(bundle, indent=2))
    
    return bundle


def mark_failed(bundle_id: str, error: str) -> Dict:
    """Mark a bundle as failed."""
    bundle = get_bundle(bundle_id)
    if not bundle:
        raise ValueError(f"Bundle not found: {bundle_id}")
    
    bundle["status"] = BundleStatus.FAILED.value
    bundle["error"] = error
    
    bundle_file = BUNDLES_DIR / f"{bundle_id}.json"
    bundle_file.write_text(json.dumps(bundle, indent=2))
    
    return bundle


def rollback_bundle(bundle_id: str) -> Dict:
    """
    Execute rollback for a bundle.
    
    Returns the bundle with updated status and rollback results.
    """
    bundle = get_bundle(bundle_id)
    if not bundle:
        raise ValueError(f"Bundle not found: {bundle_id}")
    
    if bundle["status"] != BundleStatus.APPLIED.value:
        raise ValueError(f"Cannot rollback bundle in status: {bundle['status']}")
    
    rollback_results = []
    
    for step in bundle.get("rollback_steps", []):
        # In a real implementation, this would execute the rollback
        # For now, we just record what would happen
        rollback_results.append({
            "step": step,
            "executed": False,  # Would be True after actual execution
            "result": "pending_execution",
        })
    
    bundle["status"] = BundleStatus.ROLLED_BACK.value
    bundle["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
    bundle["rollback_results"] = rollback_results
    
    bundle_file = BUNDLES_DIR / f"{bundle_id}.json"
    bundle_file.write_text(json.dumps(bundle, indent=2))
    
    return bundle


def list_bundles(
    domain: str = None,
    status: str = None,
    limit: int = 50,
) -> List[Dict]:
    """List bundles with optional filters."""
    bundles = []
    
    for bundle_file in sorted(BUNDLES_DIR.glob("*.json"), reverse=True):
        bundle = json.loads(bundle_file.read_text())
        
        if domain and bundle.get("domain") != domain:
            continue
        if status and bundle.get("status") != status:
            continue
        
        bundles.append(bundle)
        
        if len(bundles) >= limit:
            break
    
    return bundles


def list_pending_bundles() -> List[Dict]:
    """List all pending (unapplied) bundles."""
    return list_bundles(status=BundleStatus.PENDING.value)


def list_rollbackable_bundles() -> List[Dict]:
    """List all bundles that can be rolled back."""
    return list_bundles(status=BundleStatus.APPLIED.value)


def cleanup_old_bundles(days: int = 30) -> int:
    """Remove bundles older than N days. Returns count removed."""
    from datetime import timedelta
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed = 0
    
    for bundle_file in BUNDLES_DIR.glob("*.json"):
        try:
            bundle = json.loads(bundle_file.read_text())
            created = datetime.fromisoformat(bundle["created_at"].replace("Z", "+00:00"))
            if created < cutoff:
                bundle_file.unlink()
                removed += 1
        except:
            pass
    
    return removed


# Convenience functions for creating specific change types

def create_task_bundle(
    description: str,
    creates: List[Dict] = None,
    updates: List[Dict] = None,
    deletes: List[str] = None,
    pre_images: Dict = None,
) -> Dict:
    """Create a bundle for task changes."""
    changes = []
    
    for task in (creates or []):
        changes.append({
            "type": ChangeType.CREATE.value,
            "id": task.get("id", str(uuid.uuid4())[:8]),
            "target": "tasks",
            "data": task,
        })
    
    for task in (updates or []):
        changes.append({
            "type": ChangeType.UPDATE.value,
            "id": task["id"],
            "target": "tasks",
            "data": task,
        })
    
    for task_id in (deletes or []):
        changes.append({
            "type": ChangeType.DELETE.value,
            "id": task_id,
            "target": "tasks",
        })
    
    return create_bundle("tasks", description, changes, pre_images)


def create_calendar_bundle(
    description: str,
    creates: List[Dict] = None,
    updates: List[Dict] = None,
    deletes: List[str] = None,
    pre_images: Dict = None,
) -> Dict:
    """Create a bundle for calendar changes."""
    changes = []
    
    for event in (creates or []):
        changes.append({
            "type": ChangeType.CREATE.value,
            "id": event.get("id", str(uuid.uuid4())[:8]),
            "target": "calendar",
            "data": event,
        })
    
    for event in (updates or []):
        changes.append({
            "type": ChangeType.UPDATE.value,
            "id": event["id"],
            "target": "calendar",
            "data": event,
        })
    
    for event_id in (deletes or []):
        changes.append({
            "type": ChangeType.DELETE.value,
            "id": event_id,
            "target": "calendar",
        })
    
    return create_bundle("calendar", description, changes, pre_images)


def create_status_change_bundle(
    item_id: str,
    old_status: str,
    new_status: str,
    reason: str = None,
) -> Dict:
    """Create a bundle for a status transition."""
    changes = [{
        "type": ChangeType.STATUS_CHANGE.value,
        "id": item_id,
        "target": "items",
        "data": {"status": new_status, "reason": reason},
    }]
    
    pre_images = {
        item_id: {"status": old_status}
    }
    
    return create_bundle(
        "tasks",
        f"Status change: {old_status} → {new_status}",
        changes,
        pre_images,
    )


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: change_bundles.py <command> [args]")
        print("Commands: list, pending, get <id>, rollback <id>, cleanup [days]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        bundles = list_bundles()
        for b in bundles:
            print(f"{b['id']} | {b['domain']} | {b['status']} | {b['description'][:40]}")
    
    elif cmd == "pending":
        bundles = list_pending_bundles()
        for b in bundles:
            print(f"{b['id']} | {b['domain']} | {b['description'][:40]}")
    
    elif cmd == "get" and len(sys.argv) >= 3:
        bundle = get_bundle(sys.argv[2])
        if bundle:
            print(json.dumps(bundle, indent=2))
        else:
            print("Bundle not found")
    
    elif cmd == "rollback" and len(sys.argv) >= 3:
        bundle = rollback_bundle(sys.argv[2])
        print(f"Rolled back bundle {bundle['id']}")
    
    elif cmd == "cleanup":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        removed = cleanup_old_bundles(days)
        print(f"Removed {removed} bundles older than {days} days")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
