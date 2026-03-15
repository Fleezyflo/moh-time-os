"""
Task Weight System -- derives task effort classification from patterns.

Weight classes:
- quick (0.5): review, approve, reply, update, confirm, forward
- standard (1.0): default for unmatched tasks
- heavy (4.0): proposal, report, strategy, audit, presentation, campaign

Stored rules in task_weight_rules table learn from user corrections.
Per-task overrides in task_weight_overrides take precedence.
"""

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Default patterns -- seeded into task_weight_rules on first run
DEFAULT_RULES: list[dict[str, Any]] = [
    {"pattern": r"\breview\b", "field": "title", "assigned_weight": "quick", "weight_value": 0.5},
    {"pattern": r"\bapprove\b", "field": "title", "assigned_weight": "quick", "weight_value": 0.5},
    {"pattern": r"\breply\b", "field": "title", "assigned_weight": "quick", "weight_value": 0.5},
    {"pattern": r"\bupdate\b", "field": "title", "assigned_weight": "quick", "weight_value": 0.5},
    {"pattern": r"\bconfirm\b", "field": "title", "assigned_weight": "quick", "weight_value": 0.5},
    {"pattern": r"\bforward\b", "field": "title", "assigned_weight": "quick", "weight_value": 0.5},
    {"pattern": r"\bproposal\b", "field": "title", "assigned_weight": "heavy", "weight_value": 4.0},
    {"pattern": r"\breport\b", "field": "title", "assigned_weight": "heavy", "weight_value": 4.0},
    {"pattern": r"\bstrategy\b", "field": "title", "assigned_weight": "heavy", "weight_value": 4.0},
    {"pattern": r"\baudit\b", "field": "title", "assigned_weight": "heavy", "weight_value": 4.0},
    {
        "pattern": r"\bpresentation\b",
        "field": "title",
        "assigned_weight": "heavy",
        "weight_value": 4.0,
    },
    {"pattern": r"\bcampaign\b", "field": "title", "assigned_weight": "heavy", "weight_value": 4.0},
]


@dataclass
class TaskWeight:
    """Resolved weight for a single task."""

    task_id: str
    weight_class: str  # quick, standard, heavy
    weight_value: float  # 0.5, 1.0, 4.0
    source: str  # "override", "rule", "default"
    matched_pattern: str | None = None


class TaskWeightEngine:
    """Derives task weights from patterns and overrides."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_default_rules()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_default_rules(self) -> None:
        """Seed default rules if task_weight_rules is empty."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM task_weight_rules")
            row = cursor.fetchone()
            if row and row["cnt"] > 0:
                return

            now = datetime.now(timezone.utc).isoformat()
            for i, rule in enumerate(DEFAULT_RULES):
                rule_id = f"default_{i:03d}"
                conn.execute(
                    """INSERT OR IGNORE INTO task_weight_rules
                       (id, pattern, field, assigned_weight, weight_value,
                        confidence, corrections_count, confirmations_count,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 0.5, 0, 0, ?, ?)""",
                    (
                        rule_id,
                        rule["pattern"],
                        rule["field"],
                        rule["assigned_weight"],
                        rule["weight_value"],
                        now,
                        now,
                    ),
                )
            conn.commit()
            logger.info("Seeded %d default task weight rules", len(DEFAULT_RULES))
        except sqlite3.OperationalError as e:
            logger.warning("Could not seed task weight rules: %s", e)
        finally:
            conn.close()

    def get_weight(self, task_id: str, title: str) -> TaskWeight:
        """
        Resolve weight for a task. Priority:
        1. Per-task override (task_weight_overrides)
        2. Pattern match (task_weight_rules, highest confidence first)
        3. Default: standard / 1.0
        """
        conn = self._get_conn()
        try:
            # Check override first
            cursor = conn.execute(
                "SELECT weight_class, weight_value FROM task_weight_overrides WHERE task_id = ?",
                (task_id,),
            )
            override = cursor.fetchone()
            if override:
                return TaskWeight(
                    task_id=task_id,
                    weight_class=override["weight_class"],
                    weight_value=override["weight_value"],
                    source="override",
                )

            # Check rules (ordered by confidence descending)
            cursor = conn.execute(
                """SELECT pattern, field, assigned_weight, weight_value
                   FROM task_weight_rules
                   ORDER BY confidence DESC, weight_value DESC"""
            )
            for rule in cursor.fetchall():
                field_value = title if rule["field"] == "title" else title
                try:
                    if re.search(rule["pattern"], field_value, re.IGNORECASE):
                        return TaskWeight(
                            task_id=task_id,
                            weight_class=rule["assigned_weight"],
                            weight_value=rule["weight_value"],
                            source="rule",
                            matched_pattern=rule["pattern"],
                        )
                except re.error:
                    logger.warning(
                        "Invalid regex pattern in task_weight_rules: %s", rule["pattern"]
                    )
                    continue

            # Default
            return TaskWeight(
                task_id=task_id,
                weight_class="standard",
                weight_value=1.0,
                source="default",
            )
        finally:
            conn.close()

    def get_weights_bulk(self, tasks: list[dict[str, Any]]) -> dict[str, TaskWeight]:
        """Get weights for multiple tasks at once. Returns {task_id: TaskWeight}."""
        result: dict[str, TaskWeight] = {}
        for task in tasks:
            task_id = task.get("id", task.get("task_id", ""))
            title = task.get("title", "")
            result[task_id] = self.get_weight(task_id, title)
        return result

    def record_correction(self, task_id: str, title: str, new_weight_class: str) -> None:
        """Record a user correction -- updates override and adjusts rule confidence."""
        weight_values = {"quick": 0.5, "standard": 1.0, "heavy": 4.0}
        weight_value = weight_values.get(new_weight_class, 1.0)

        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()

            # Upsert override
            conn.execute(
                """INSERT INTO task_weight_overrides (id, task_id, weight_class, weight_value, set_by, created_at)
                   VALUES (?, ?, ?, ?, 'user', ?)
                   ON CONFLICT(id) DO UPDATE SET
                       weight_class = excluded.weight_class,
                       weight_value = excluded.weight_value""",
                (f"override_{task_id}", task_id, new_weight_class, weight_value, now),
            )

            # Find which rule matched and decrease its confidence
            cursor = conn.execute(
                "SELECT id, pattern FROM task_weight_rules ORDER BY confidence DESC"
            )
            for rule in cursor.fetchall():
                try:
                    if re.search(rule["pattern"], title, re.IGNORECASE):
                        conn.execute(
                            """UPDATE task_weight_rules
                               SET corrections_count = corrections_count + 1,
                                   confidence = MAX(0.1, confidence - 0.05),
                                   updated_at = ?
                               WHERE id = ?""",
                            (now, rule["id"]),
                        )
                        break
                except re.error:
                    continue

            conn.commit()
            logger.info(
                "Recorded weight correction for task %s: %s -> %s",
                task_id,
                title[:40],
                new_weight_class,
            )
        finally:
            conn.close()

    def record_confirmation(self, task_id: str, title: str) -> None:
        """Record a user confirmation -- increases matched rule confidence."""
        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            cursor = conn.execute(
                "SELECT id, pattern FROM task_weight_rules ORDER BY confidence DESC"
            )
            for rule in cursor.fetchall():
                try:
                    if re.search(rule["pattern"], title, re.IGNORECASE):
                        conn.execute(
                            """UPDATE task_weight_rules
                               SET confirmations_count = confirmations_count + 1,
                                   confidence = MIN(1.0, confidence + 0.05),
                                   updated_at = ?
                               WHERE id = ?""",
                            (now, rule["id"]),
                        )
                        conn.commit()
                        break
                except re.error:
                    continue
        finally:
            conn.close()

    def to_dict(self, weight: TaskWeight) -> dict[str, Any]:
        """Serialize a TaskWeight for JSON storage."""
        return {
            "task_id": weight.task_id,
            "weight_class": weight.weight_class,
            "weight_value": weight.weight_value,
            "source": weight.source,
            "matched_pattern": weight.matched_pattern,
        }
