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
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from lib import paths
from datetime import UTC
from enum import StrEnum
import sqlite3

logger = logging.getLogger(__name__)

BUNDLES_DIR = paths.data_dir() / "bundles"
BUNDLES_DIR.mkdir(parents=True, exist_ok=True)


class ChangeType(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    STATUS_CHANGE = "status_change"


class BundleStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


def create_bundle(
    domain: str,
    description: str,
    changes: list[dict],
    pre_images: dict[str, Any] = None,
) -> dict:
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
    timestamp = datetime.now(UTC).isoformat()

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


def _generate_rollback_steps(changes: list[dict], pre_images: dict) -> list[dict]:
    """Generate rollback steps from changes and pre-images."""
    rollback_steps = []

    for change in reversed(changes):  # Reverse order for rollback
        change_type = change.get("type")
        item_id = change.get("id")

        if change_type == ChangeType.CREATE.value:
            # Rollback: delete the created item
            rollback_steps.append(
                {
                    "type": ChangeType.DELETE.value,
                    "id": item_id,
                    "target": change.get("target"),
                }
            )

        elif change_type == ChangeType.UPDATE.value:
            # Rollback: restore pre-image
            pre_image = pre_images.get(item_id)
            if pre_image:
                rollback_steps.append(
                    {
                        "type": ChangeType.UPDATE.value,
                        "id": item_id,
                        "target": change.get("target"),
                        "data": pre_image,
                    }
                )

        elif change_type == ChangeType.DELETE.value:
            # Rollback: recreate from pre-image
            pre_image = pre_images.get(item_id)
            if pre_image:
                rollback_steps.append(
                    {
                        "type": ChangeType.CREATE.value,
                        "id": item_id,
                        "target": change.get("target"),
                        "data": pre_image,
                    }
                )

        elif change_type == ChangeType.STATUS_CHANGE.value:
            # Rollback: restore previous status
            pre_image = pre_images.get(item_id)
            if pre_image and "status" in pre_image:
                rollback_steps.append(
                    {
                        "type": ChangeType.STATUS_CHANGE.value,
                        "id": item_id,
                        "target": change.get("target"),
                        "data": {"status": pre_image["status"]},
                    }
                )

    return rollback_steps


def get_bundle(bundle_id: str) -> dict | None:
    """Load a bundle by ID."""
    bundle_file = BUNDLES_DIR / f"{bundle_id}.json"
    if bundle_file.exists():
        try:
            return json.loads(bundle_file.read_text())
        except json.JSONDecodeError as e:
            logger.error(f"Corrupt bundle file {bundle_id}: {e}")
            return None
    return None


def mark_applied(bundle_id: str) -> dict:
    """Mark a bundle as successfully applied."""
    bundle = get_bundle(bundle_id)
    if not bundle:
        raise ValueError(f"Bundle not found: {bundle_id}")

    bundle["status"] = BundleStatus.APPLIED.value
    bundle["applied_at"] = datetime.now(UTC).isoformat()

    bundle_file = BUNDLES_DIR / f"{bundle_id}.json"
    bundle_file.write_text(json.dumps(bundle, indent=2))

    return bundle


def mark_failed(bundle_id: str, error: str) -> dict:
    """Mark a bundle as failed."""
    bundle = get_bundle(bundle_id)
    if not bundle:
        raise ValueError(f"Bundle not found: {bundle_id}")

    bundle["status"] = BundleStatus.FAILED.value
    bundle["error"] = error

    bundle_file = BUNDLES_DIR / f"{bundle_id}.json"
    bundle_file.write_text(json.dumps(bundle, indent=2))

    return bundle


def rollback_bundle(bundle_id: str) -> dict:
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
        try:
            step_type = step.get("type", "unknown")
            step.get("target", "")

            if step_type == "restore_value":
                # Restore a configuration or field value
                from lib.store import Store

                store = Store()
                collection = step.get("collection", "")
                record_id = step.get("record_id", "")
                field_name = step.get("field", "")
                old_value = step.get("old_value")
                if collection and record_id and field_name:
                    store.update(collection, record_id, {field_name: old_value})
                    rollback_results.append({"step": step, "executed": True, "result": "restored"})
                else:
                    rollback_results.append(
                        {"step": step, "executed": False, "result": "missing_params"}
                    )

            elif step_type == "delete_record":
                from lib.store import Store

                store = Store()
                collection = step.get("collection", "")
                record_id = step.get("record_id", "")
                if collection and record_id:
                    store.delete(collection, record_id)
                    rollback_results.append({"step": step, "executed": True, "result": "deleted"})
                else:
                    rollback_results.append(
                        {"step": step, "executed": False, "result": "missing_params"}
                    )

            else:
                # Unknown step type — record but don't execute
                logger.warning(f"Unknown rollback step type: {step_type}")
                rollback_results.append(
                    {"step": step, "executed": False, "result": f"unknown_type:{step_type}"}
                )

        except (sqlite3.Error, ValueError, OSError) as step_err:
            logger.error(f"Rollback step failed: {step_err}", exc_info=True)
            rollback_results.append(
                {"step": step, "executed": False, "result": f"error:{str(step_err)[:80]}"}
            )

    bundle["status"] = BundleStatus.ROLLED_BACK.value
    bundle["rolled_back_at"] = datetime.now(UTC).isoformat()
    bundle["rollback_results"] = rollback_results

    bundle_file = BUNDLES_DIR / f"{bundle_id}.json"
    bundle_file.write_text(json.dumps(bundle, indent=2))

    return bundle


def list_bundles(
    domain: str = None,
    status: str = None,
    limit: int = 50,
) -> list[dict]:
    """List bundles with optional filters."""
    bundles = []

    for bundle_file in sorted(BUNDLES_DIR.glob("*.json"), reverse=True):
        try:
            bundle = json.loads(bundle_file.read_text())
        except json.JSONDecodeError as e:
            logger.warning(f"Skipping corrupt bundle {bundle_file.name}: {e}")
            continue

        if domain and bundle.get("domain") != domain:
            continue
        if status and bundle.get("status") != status:
            continue

        bundles.append(bundle)

        if len(bundles) >= limit:
            break

    return bundles


def list_pending_bundles() -> list[dict]:
    """List all pending (unapplied) bundles."""
    return list_bundles(status=BundleStatus.PENDING.value)


def list_rollbackable_bundles() -> list[dict]:
    """List all bundles that can be rolled back."""
    return list_bundles(status=BundleStatus.APPLIED.value)


def cleanup_old_bundles(days: int = 30) -> int:
    """Remove bundles older than N days. Returns count removed."""
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(days=days)
    removed = 0

    for bundle_file in BUNDLES_DIR.glob("*.json"):
        try:
            bundle = json.loads(bundle_file.read_text())
            created = datetime.fromisoformat(bundle["created_at"].replace("Z", "+00:00"))
            if created < cutoff:
                bundle_file.unlink()
                removed += 1
        except (json.JSONDecodeError, KeyError, ValueError, OSError) as e:
            logger.debug(f"Could not process bundle {bundle_file}: {e}")

    return removed


# Convenience functions for creating specific change types


def create_task_bundle(
    description: str,
    creates: list[dict] = None,
    updates: list[dict] = None,
    deletes: list[str] = None,
    pre_images: dict = None,
) -> dict:
    """Create a bundle for task changes."""
    changes = []

    for task in creates or []:
        changes.append(
            {
                "type": ChangeType.CREATE.value,
                "id": task.get("id", str(uuid.uuid4())[:8]),
                "target": "tasks",
                "data": task,
            }
        )

    for task in updates or []:
        changes.append(
            {
                "type": ChangeType.UPDATE.value,
                "id": task["id"],
                "target": "tasks",
                "data": task,
            }
        )

    for task_id in deletes or []:
        changes.append(
            {
                "type": ChangeType.DELETE.value,
                "id": task_id,
                "target": "tasks",
            }
        )

    return create_bundle("tasks", description, changes, pre_images)


def create_calendar_bundle(
    description: str,
    creates: list[dict] = None,
    updates: list[dict] = None,
    deletes: list[str] = None,
    pre_images: dict = None,
) -> dict:
    """Create a bundle for calendar changes."""
    changes = []

    for event in creates or []:
        changes.append(
            {
                "type": ChangeType.CREATE.value,
                "id": event.get("id", str(uuid.uuid4())[:8]),
                "target": "calendar",
                "data": event,
            }
        )

    for event in updates or []:
        changes.append(
            {
                "type": ChangeType.UPDATE.value,
                "id": event["id"],
                "target": "calendar",
                "data": event,
            }
        )

    for event_id in deletes or []:
        changes.append(
            {
                "type": ChangeType.DELETE.value,
                "id": event_id,
                "target": "calendar",
            }
        )

    return create_bundle("calendar", description, changes, pre_images)


def create_status_change_bundle(
    item_id: str,
    old_status: str,
    new_status: str,
    reason: str = None,
) -> dict:
    """Create a bundle for a status transition."""
    changes = [
        {
            "type": ChangeType.STATUS_CHANGE.value,
            "id": item_id,
            "target": "items",
            "data": {"status": new_status, "reason": reason},
        }
    ]

    pre_images = {item_id: {"status": old_status}}

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
        logger.info("Usage: change_bundles.py <command> [args]")
        logger.info("Commands: list, pending, get <id>, rollback <id>, cleanup [days]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        bundles = list_bundles()
        for b in bundles:
            logger.info(f"{b['id']} | {b['domain']} | {b['status']} | {b['description'][:40]}")
    elif cmd == "pending":
        bundles = list_pending_bundles()
        for b in bundles:
            logger.info(f"{b['id']} | {b['domain']} | {b['description'][:40]}")
    elif cmd == "get" and len(sys.argv) >= 3:
        bundle = get_bundle(sys.argv[2])
        if bundle:
            logger.info(json.dumps(bundle, indent=2))
        else:
            logger.info("Bundle not found")
    elif cmd == "rollback" and len(sys.argv) >= 3:
        bundle = rollback_bundle(sys.argv[2])
        logger.info(f"Rolled back bundle {bundle['id']}")
    elif cmd == "cleanup":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        removed = cleanup_old_bundles(days)
        logger.info(f"Removed {removed} bundles older than {days} days")
    else:
        logger.info(f"Unknown command: {cmd}")
        sys.exit(1)


class BundleManager:
    """
    Manages change bundles for a cycle.

    Tracks active bundles, provides rollback capabilities, and cleanup.
    This is the high-level API for bundle operations.
    """

    def __init__(self):
        """Initialize the bundle manager."""
        self.active_bundles: dict[str, str] = {}  # cycle_id -> [bundle_ids]

    def start_bundle(
        self,
        cycle_id: str,
        domain: str,
        description: str,
        changes: list[dict],
        pre_images: dict[str, Any] = None,
    ) -> str:
        """
        Create and track a new bundle for a cycle.

        Returns the bundle ID.
        """
        bundle = create_bundle(domain, description, changes, pre_images)
        bundle_id = bundle["id"]

        # Track this bundle for the cycle
        if cycle_id not in self.active_bundles:
            self.active_bundles[cycle_id] = []
        self.active_bundles[cycle_id].append(bundle_id)

        logger.info(f"Started bundle {bundle_id} for cycle {cycle_id}")
        return bundle_id

    def apply_bundle(self, bundle_id: str) -> dict:
        """Mark a bundle as applied."""
        bundle = mark_applied(bundle_id)
        logger.info(f"Applied bundle {bundle_id}")
        return bundle

    def fail_bundle(self, bundle_id: str, error: str) -> dict:
        """Mark a bundle as failed."""
        bundle = mark_failed(bundle_id, error)
        logger.error(f"Failed bundle {bundle_id}: {error}")
        return bundle

    def rollback_cycle(self, cycle_id: str) -> dict:
        """
        Rollback all bundles from a failed cycle.

        Returns summary of rollback operations.
        """
        bundle_ids = self.active_bundles.get(cycle_id, [])
        if not bundle_ids:
            logger.warning(f"No bundles to rollback for cycle {cycle_id}")
            return {
                "cycle_id": cycle_id,
                "bundles_processed": 0,
                "bundles_rolled_back": 0,
                "errors": [],
            }

        rolled_back = 0
        errors = []

        for bundle_id in bundle_ids:
            try:
                bundle = get_bundle(bundle_id)
                if bundle and bundle["status"] == BundleStatus.APPLIED.value:
                    rollback_bundle(bundle_id)
                    rolled_back += 1
                    logger.info(f"Rolled back bundle {bundle_id}")
            except (sqlite3.Error, ValueError, OSError) as e:
                error_msg = f"Failed to rollback {bundle_id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return {
            "cycle_id": cycle_id,
            "bundles_processed": len(bundle_ids),
            "bundles_rolled_back": rolled_back,
            "errors": errors,
        }

    def list_bundles_for_status(
        self, status: str = None, since: str = None, limit: int = 50
    ) -> list[dict]:
        """
        List bundles with optional filters.

        Args:
            status: Filter by bundle status (pending, applied, failed, rolled_back)
            since: ISO timestamp to filter bundles created after this time
            limit: Maximum number of bundles to return

        Returns:
            List of bundle dicts
        """
        bundles = list_bundles(status=status, limit=limit * 2)

        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
                bundles = [
                    b
                    for b in bundles
                    if datetime.fromisoformat(b["created_at"].replace("Z", "+00:00")) >= since_dt
                ]
            except ValueError as e:
                logger.warning(f"Invalid since timestamp {since}: {e}")

        return bundles[:limit]

    def prune_bundles(self, keep_days: int = 30) -> int:
        """
        Remove bundles older than keep_days.

        Returns the count of bundles removed.
        """
        removed = cleanup_old_bundles(keep_days)
        logger.info(f"Pruned {removed} bundles older than {keep_days} days")
        return removed

    def get_cycle_summary(self, cycle_id: str) -> dict:
        """Get summary of bundles for a cycle."""
        bundle_ids = self.active_bundles.get(cycle_id, [])

        bundles = [get_bundle(bid) for bid in bundle_ids]
        bundles = [b for b in bundles if b is not None]

        created = len(bundles)
        applied = len([b for b in bundles if b["status"] == BundleStatus.APPLIED.value])
        failed = len([b for b in bundles if b["status"] == BundleStatus.FAILED.value])
        rolled_back = len([b for b in bundles if b["status"] == BundleStatus.ROLLED_BACK.value])

        return {
            "cycle_id": cycle_id,
            "bundles_created": created,
            "bundles_applied": applied,
            "bundles_failed": failed,
            "bundles_rolled_back": rolled_back,
        }
