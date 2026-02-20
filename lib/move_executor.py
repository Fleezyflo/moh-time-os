"""
Move Executor - Execute approved moves per MASTER_SPEC.md §18.6

Handles the approval flow:
- execute: Perform suggested action
- create_task: Convert to tracked task
- copy: Export move details
- dismiss: Mark as declined
- snooze: Defer to next cycle
"""

import json
import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from lib import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.db_path()
LOG_PATH = paths.out_dir() / "move_log.json"


class MoveExecutor:
    """Execute moves from dashboard approval."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _log_decision(self, move_id: str, decision: str, result: dict):
        """Log move decision for audit trail."""
        log = []
        if LOG_PATH.exists():
            try:
                with open(LOG_PATH) as f:
                    log = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Could not load move log: {e}")

        log.append(
            {
                "move_id": move_id,
                "decision": decision,
                "decided_at": datetime.now().isoformat(),
                "result": result,
            }
        )

        # Keep last 100 entries
        log = log[-100:]

        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "w") as f:
            json.dump(log, f, indent=2)

    def execute(self, move: dict) -> dict:
        """Execute the suggested action for a move."""
        action_type = move.get("action_type")
        suggested = move.get("suggested_action", {})

        result = {"success": False, "action_taken": None}

        try:
            if action_type == "communication":
                result = self._execute_communication(move, suggested)
            elif action_type == "task":
                result = self._execute_create_task(move, suggested)
            elif action_type == "data_fix":
                result = self._execute_data_fix(move, suggested)
            elif action_type == "review":
                result = self._execute_review(move, suggested)
            elif action_type == "outreach":
                result = self._execute_outreach(move, suggested)
            elif action_type == "decision":
                result = self._execute_decision(move, suggested)
            else:
                result = {
                    "success": False,
                    "error": f"Unknown action type: {action_type}",
                }
        except sqlite3.Error as e:
            logger.error(f"Database error executing move {move.get('id')}: {e}", exc_info=True)
            result = {"success": False, "error": f"Database error: {e}"}
        except Exception as e:
            logger.error(f"Unexpected error executing move {move.get('id')}: {e}", exc_info=True)
            result = {"success": False, "error": str(e)}

        self._log_decision(move.get("id", "unknown"), "execute", result)
        return result

    def create_task(self, move: dict) -> dict:
        """Convert move to a tracked task."""
        conn = self._get_conn()

        try:
            task_id = f"move_{uuid4().hex[:8]}"

            # Determine due date
            due_date = None
            if move.get("suggested_action", {}).get("due_date"):
                due_date = move["suggested_action"]["due_date"]
            else:
                # Default: 3 days from now
                due_date = (date.today() + timedelta(days=3)).isoformat()

            conn.execute(
                """
                INSERT INTO tasks (id, title, status, due_date, priority, source, created_at)
                VALUES (?, ?, 'todo', ?, 'high', 'time_os_move', datetime('now'))
            """,
                (task_id, move["title"], due_date),
            )

            conn.commit()

            result = {
                "success": True,
                "action_taken": "task_created",
                "task_id": task_id,
                "title": move["title"],
                "due_date": due_date,
            }
        except sqlite3.Error as e:
            logger.error(
                f"Database error creating task for move {move.get('id')}: {e}",
                exc_info=True,
            )
            result = {"success": False, "error": f"Database error: {e}"}
        except (KeyError, TypeError) as e:
            logger.warning(f"Invalid move data for task creation: {e}")
            result = {"success": False, "error": f"Invalid move data: {e}"}
        except Exception as e:
            logger.error(f"Unexpected error creating task: {e}", exc_info=True)
            result = {"success": False, "error": str(e)}
        finally:
            conn.close()

        self._log_decision(move.get("id", "unknown"), "create_task", result)
        return result

    def copy_to_clipboard(self, move: dict) -> dict:
        """Format move for clipboard (returns text, JS handles clipboard)."""
        text = f"""=== TIME OS MOVE ===
Title: {move["title"]}
Rationale: {move["rationale"]}
Domain: {move.get("domain", "unknown")}
Confidence: {move.get("data_confidence", "unknown")}
Score: {move.get("score", 0):.0f}

Suggested Action:
{json.dumps(move.get("suggested_action", {}), indent=2)}

Drill URL: {move.get("drill_url", "")}
"""

        result = {"success": True, "action_taken": "copied", "text": text}

        self._log_decision(move.get("id", "unknown"), "copy", result)
        return result

    def dismiss(self, move: dict) -> dict:
        """Mark move as dismissed (won't resurface)."""
        # Store dismissal to prevent regenerating same move
        conn = self._get_conn()

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO dismissed_moves (move_key, dismissed_at)
                VALUES (?, datetime('now'))
            """,
                (f"{move.get('entity_type')}:{move.get('entity_id')}",),
            )
            conn.commit()
            result = {"success": True, "action_taken": "dismissed"}
        except sqlite3.OperationalError as e:
            logger.debug(f"Could not persist dismissal (table may not exist): {e}")
            result = {
                "success": True,
                "action_taken": "dismissed",
                "note": "dismissal not persisted",
            }
        finally:
            conn.close()

        self._log_decision(move.get("id", "unknown"), "dismiss", result)
        return result

    def snooze(self, move: dict, hours: int = 24) -> dict:
        """Defer move to next cycle."""
        result = {
            "success": True,
            "action_taken": "snoozed",
            "until": (datetime.now() + timedelta(hours=hours)).isoformat(),
        }

        self._log_decision(move.get("id", "unknown"), "snooze", result)
        return result

    # --- Action executors ---

    def _execute_communication(self, move: dict, suggested: dict) -> dict:
        """Execute communication action (email draft, etc.)."""
        template = suggested.get("template", "generic")
        subject = suggested.get("subject", move["title"])

        # For now, generate email draft text
        draft = f"""Subject: {subject}

[Generated by Time OS - Review before sending]

---
Move: {move["title"]}
Rationale: {move["rationale"]}
---

[Your message here]
"""

        return {
            "success": True,
            "action_taken": "email_draft_generated",
            "draft": draft,
            "template": template,
        }

    def _execute_create_task(self, move: dict, suggested: dict) -> dict:
        """Execute task creation action."""
        return self.create_task(move)

    def _execute_data_fix(self, move: dict, suggested: dict) -> dict:
        """Execute data fix action (opens queue with filter)."""
        return {
            "success": True,
            "action_taken": "queue_filter_applied",
            "url": move.get("drill_url", "#queue"),
        }

    def _execute_review(self, move: dict, suggested: dict) -> dict:
        """Execute review action."""
        return {
            "success": True,
            "action_taken": "review_initiated",
            "url": move.get("drill_url", "#"),
        }

    def _execute_outreach(self, move: dict, suggested: dict) -> dict:
        """Execute outreach action."""
        return {
            "success": True,
            "action_taken": "outreach_draft_generated",
            "subject": suggested.get("subject", move["title"]),
            "type": suggested.get("type", "email"),
        }

    def _execute_decision(self, move: dict, suggested: dict) -> dict:
        """Execute decision action."""
        return {
            "success": True,
            "action_taken": "decision_logged",
            "title": move["title"],
        }


# API endpoint handler for dashboard
def handle_move_action(action: str, move_data: dict) -> dict:
    """Handle move action from dashboard API."""
    executor = MoveExecutor()

    if action == "execute":
        return executor.execute(move_data)
    if action == "task":
        return executor.create_task(move_data)
    if action == "copy":
        return executor.copy_to_clipboard(move_data)
    if action == "dismiss":
        return executor.dismiss(move_data)
    if action == "snooze":
        return executor.snooze(move_data)
    return {"success": False, "error": f"Unknown action: {action}"}


if __name__ == "__main__":
    import sys

    # Test with sample move
    test_move = {
        "id": "m-001",
        "title": "Test move",
        "rationale": "Testing move executor",
        "action_type": "task",
        "entity_type": "task",
        "entity_id": "test-123",
        "drill_url": "#test",
    }

    action = sys.argv[1] if len(sys.argv) > 1 else "copy"
    result = handle_move_action(action, test_move)
    logger.info(json.dumps(result, indent=2))
