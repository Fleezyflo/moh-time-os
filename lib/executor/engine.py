"""
Executor Engine - Processes and executes approved actions.
"""

import json
import logging
from datetime import datetime

from lib import paths

from ..change_bundles import BundleManager
from ..governance import GovernanceEngine, get_governance
from ..notifier import NotificationEngine
from ..state_store import StateStore, get_store
from .handlers import CalendarHandler, EmailHandler, NotificationHandler, TaskHandler

logger = logging.getLogger(__name__)


class ExecutorEngine:
    """
    Executes approved actions across external systems.

    This is WIRING POINT #7:
    Approved Decisions → Executor → External Systems
    """

    def __init__(
        self,
        store: StateStore = None,
        governance: GovernanceEngine = None,
        config_path: str = None,
    ):
        self.store = store or get_store()
        self.governance = governance or get_governance()

        # Load notification config and create notifier
        self.config_path = config_path or str(paths.config_dir())
        notif_config = self._load_notification_config()
        self.notifier = NotificationEngine(self.store, notif_config)

        # Initialize handlers
        self.handlers = {
            "task": TaskHandler(self.store),
            "task_complete": TaskHandler(self.store),
            "task_create": TaskHandler(self.store),
            "task_update": TaskHandler(self.store),
            "calendar": CalendarHandler(self.store),
            "calendar_create": CalendarHandler(self.store),
            "calendar_update": CalendarHandler(self.store),
            "calendar_delete": CalendarHandler(self.store),
            "notification": NotificationHandler(self.store, notifier=self.notifier),
            "notify": NotificationHandler(self.store, notifier=self.notifier),
            "email": EmailHandler(self.store),
            "email_archive": EmailHandler(self.store),
            "email_label": EmailHandler(self.store),
        }

        self.bundle_manager = BundleManager()

    def _load_notification_config(self) -> dict:
        """Load notification config from governance.yaml."""
        from pathlib import Path

        import yaml

        config_file = Path(self.config_path) / "governance.yaml"
        if config_file.exists():
            with open(config_file) as f:
                config = yaml.safe_load(f)
                return config.get("notification_settings", {})
        return {}

    def process_pending_actions(self, cycle_id: str = None) -> list[dict]:
        """
        Process all pending approved actions.

        Args:
            cycle_id: Optional cycle ID to track bundles per cycle

        Returns:
            List of execution results (with bundle tracking if cycle_id provided)
        """
        results = []

        # Get approved actions
        actions = self.store.query(
            "SELECT * FROM actions WHERE status = 'approved' ORDER BY created_at"
        )

        for action in actions:
            result = self._execute_action(action, cycle_id=cycle_id)
            results.append(result)

        return results

    def _execute_action(self, action: dict, cycle_id: str = None) -> dict:
        """
        Execute a single action.

        Args:
            action: The action to execute
            cycle_id: Optional cycle ID for bundle tracking

        Returns:
            Execution result dict
        """
        action_id = action["id"]
        action_type = action["type"]
        bundle_id = None

        logger.info(f"Executing action {action_id}: {action_type}")

        # Get handler
        handler = self.handlers.get(action_type)
        if not handler:
            error = f"Unknown action type: {action_type}"
            self._update_action_status(action_id, "failed", error=error)
            return {"id": action_id, "status": "failed", "error": error}

        try:
            # Parse payload
            payload = (
                json.loads(action["payload"])
                if isinstance(action["payload"], str)
                else action["payload"]
            )

            # Create bundle for tracking if cycle_id provided
            if cycle_id:
                change_data = {
                    "type": action_type,
                    "id": action_id,
                    "target": action_type.split("_")[0],
                    "data": payload,
                }
                bundle_id = self.bundle_manager.start_bundle(
                    cycle_id=cycle_id,
                    domain=action_type.split("_")[0],
                    description=f"Action: {action_type}",
                    changes=[change_data],
                    pre_images={},
                )

            # Update status to executing
            self._update_action_status(action_id, "executing")

            # Execute
            result = handler.execute(payload)

            # Update with success
            self._update_action_status(action_id, "done", result=result)

            # Mark bundle as applied if created
            if bundle_id and cycle_id:
                self.bundle_manager.apply_bundle(bundle_id)

            logger.info(f"Action {action_id} completed successfully")
            return {
                "id": action_id,
                "status": "done",
                "result": result,
                "bundle_id": bundle_id,
            }

        except Exception as e:
            error = str(e)
            logger.error(f"Action {action_id} failed: {error}")

            # Mark bundle as failed if created
            if bundle_id and cycle_id:
                self.bundle_manager.fail_bundle(bundle_id, error)

            # Update with failure
            retry_count = action.get("retry_count", 0) + 1
            self._update_action_status(action_id, "failed", error=error, retry_count=retry_count)

            return {
                "id": action_id,
                "status": "failed",
                "error": error,
                "bundle_id": bundle_id,
            }

    def _update_action_status(
        self,
        action_id: str,
        status: str,
        result: dict = None,
        error: str = None,
        retry_count: int = None,
    ):
        """Update action status in database."""
        update = {
            "status": status,
        }

        if status == "done":
            update["executed_at"] = datetime.now().isoformat()
        if result:
            update["result"] = json.dumps(result)
        if error:
            update["error"] = error
        if retry_count is not None:
            update["retry_count"] = retry_count

        self.store.update("actions", action_id, update)

    def queue_action(self, action_type: str, payload: dict, requires_approval: bool = True) -> str:
        """Queue a new action for execution."""
        from uuid import uuid4

        action_id = f"action_{uuid4().hex[:8]}"

        # Check governance
        can_auto, reason = self.governance.can_execute(
            domain=action_type.split("_")[0], action=action_type, context=payload
        )

        status = "approved" if can_auto and not requires_approval else "pending"

        self.store.insert(
            "actions",
            {
                "id": action_id,
                "type": action_type,
                "target_system": action_type.split("_")[0],
                "payload": json.dumps(payload),
                "status": status,
                "requires_approval": 1 if requires_approval else 0,
                "created_at": datetime.now().isoformat(),
            },
        )

        logger.info(f"Queued action {action_id}: {action_type} (status={status})")

        return action_id

    def approve_action(self, action_id: str, approved_by: str = "user") -> bool:
        """Approve a pending action."""
        action = self.store.get("actions", action_id)
        if not action:
            return False

        self.store.update(
            "actions",
            action_id,
            {
                "status": "approved",
                "approved_by": approved_by,
                "approved_at": datetime.now().isoformat(),
            },
        )

        logger.info(f"Action {action_id} approved by {approved_by}")
        return True

    def reject_action(self, action_id: str, reason: str = None) -> bool:
        """Reject a pending action."""
        action = self.store.get("actions", action_id)
        if not action:
            return False

        self.store.update(
            "actions",
            action_id,
            {"status": "rejected", "error": reason or "Rejected by user"},
        )

        logger.info(f"Action {action_id} rejected")
        return True

    def get_pending_actions(self) -> list[dict]:
        """Get actions pending approval."""
        return self.store.query(
            "SELECT * FROM actions WHERE status = 'pending' ORDER BY created_at"
        )

    def get_action_history(self, limit: int = 50) -> list[dict]:
        """Get recent action history."""
        return self.store.query("SELECT * FROM actions ORDER BY created_at DESC LIMIT ?", [limit])
