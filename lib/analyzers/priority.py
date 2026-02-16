"""
Priority Analyzer - Computes unified priority queue across all items.
THIS IS THE CORE INTELLIGENCE - what matters most right now.

Implements DESIGN_V4_SURGICAL.md scoring algorithm.
"""

import json
import logging
from datetime import datetime

import yaml

from lib import paths

from ..state_store import StateStore, get_store

logger = logging.getLogger(__name__)


def days_until_date(date_str: str) -> int:
    """Calculate days until a date string (YYYY-MM-DD)."""
    try:
        due = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        return (due - datetime.now().date()).days
    except (ValueError, TypeError):
        return 999  # Far future if can't parse


class PriorityAnalyzer:
    """
    Computes and maintains priority rankings across all actionable items.

    Scoring algorithm per DESIGN_V4_SURGICAL.md:
    - Due date factor: 0-40 points
    - Explicit priority factor: 0-25 points
    - Sender/VIP factor: 0-25 points
    - Project criticality: 0-10 points
    - Blocker factor: 0-10 points
    """

    def __init__(self, config: dict = None, store: StateStore = None):
        self.store = store or get_store()
        self.config = config or self._load_config()

    def _load_config(self) -> dict:
        """Load intelligence configuration."""
        config_file = paths.config_dir() / "intelligence.yaml"
        if config_file.exists():
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        return {}

    def analyze(self) -> list[dict]:
        """
        Compute priority queue across all actionable items.
        Returns sorted list of items with scores and reasons.
        """
        items = []

        # Get all pending tasks
        tasks = self.store.query(
            "SELECT * FROM tasks WHERE status NOT IN ('completed', 'done', 'cancelled')"
        )

        for task in tasks:
            score, reasons = self._score_task(dict(task))
            items.append(
                {
                    "type": "task",
                    "id": task["id"],
                    "source_id": task.get("source_id"),
                    "title": task["title"],
                    "score": score,
                    "due": task.get("due_date"),
                    "project": task.get("project"),
                    "assignee": task.get("assignee"),
                    "source": task["source"],
                    "status": task["status"],
                    "reasons": reasons,
                }
            )

        # Get emails needing response
        emails = self.store.query(
            "SELECT * FROM communications WHERE requires_response = 1 AND processed = 0"
        )

        for email in emails:
            score, reasons = self._score_email(dict(email))
            items.append(
                {
                    "type": "email",
                    "id": email["id"],
                    "source_id": email.get("source_id"),
                    "title": email.get("subject", "(no subject)"),
                    "score": score,
                    "due": email.get("response_deadline"),
                    "from": email.get("from_email"),
                    "source": "email",
                    "sentiment": email.get("sentiment"),
                    "reasons": reasons,
                }
            )

        # Sort by score descending
        items.sort(key=lambda x: x["score"], reverse=True)

        # Update priority scores in DB
        self._update_stored_scores(items)

        # Store in cache for quick access
        self.store.set_cache("priority_queue", items)

        return items

    def _score_task(self, task: dict) -> tuple[float, list[str]]:
        """
        Score a task with DIMINISHING RETURNS for very overdue items.
        Key insight: Tasks overdue 2+ weeks are probably stale, not critical.
        Returns (score 0-100, list of reasons).
        """
        score = 40  # Lower base score
        reasons = []

        # === DUE DATE FACTOR (with diminishing returns) ===
        due_date = task.get("due_date")
        if due_date:
            days_until = days_until_date(due_date)

            if days_until < 0:
                # Overdue - use diminishing returns
                overdue_days = abs(days_until)
                if overdue_days <= 3:
                    # Recent overdue - high priority
                    score += 30 + min(10, overdue_days * 3)
                    reasons.append(
                        f"Overdue by {overdue_days} day{'s' if overdue_days > 1 else ''}"
                    )
                elif overdue_days <= 7:
                    # 1 week overdue - still important
                    score += 25
                    reasons.append(f"Overdue {overdue_days} days")
                elif overdue_days <= 14:
                    # 2 weeks overdue - needs attention but not critical
                    score += 15
                    reasons.append("Overdue 2 weeks")
                elif overdue_days <= 30:
                    # Stale (2-4 weeks) - probably needs review
                    score += 5
                    reasons.append(f"Stale ({overdue_days}d overdue)")
                else:
                    # Ancient (30+ days) - likely needs cleanup
                    score -= 10
                    reasons.append(f"Ancient ({overdue_days}d overdue)")
            elif days_until == 0:
                score += 35
                reasons.append("Due today")
            elif days_until == 1:
                score += 30
                reasons.append("Due tomorrow")
            elif days_until <= 3:
                score += 20
                reasons.append(f"Due in {days_until} days")
            elif days_until <= 7:
                score += 10
                reasons.append("Due this week")
        else:
            # No due date - lower priority
            score -= 5
            reasons.append("No due date")

        # === EXPLICIT PRIORITY FACTOR (reduced impact) ===
        tags = task.get("tags", "[]")
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Could not parse tags JSON for task {task.get('id', 'unknown')}: {e}")
                tags = []

        tags_lower = [t.lower() for t in tags] if tags else []

        if "urgent" in tags_lower or "critical" in tags_lower:
            score += 15  # Reduced from 25
            reasons.append("Marked urgent")
        elif "high" in tags_lower or "important" in tags_lower:
            score += 10  # Reduced from 15
            reasons.append("High priority")

        # Stored priority field (minimal impact to prevent source inflation)
        # Convert string priorities to numeric
        stored_priority_raw = task.get("priority", 50)
        if isinstance(stored_priority_raw, str):
            priority_map = {"critical": 100, "high": 80, "normal": 50, "low": 20}
            stored_priority = priority_map.get(stored_priority_raw.lower(), 50)
        else:
            stored_priority = int(stored_priority_raw or 50)

        if stored_priority >= 85:
            score += 10
            if "High priority" not in reasons and "Marked urgent" not in reasons:
                reasons.append("Source priority high")
        elif stored_priority >= 70:
            score += 5

        # === PROJECT CRITICALITY (0-10 points) ===
        project_id = task.get("project_id") or task.get("project")
        if project_id:
            project = self.store.query(
                "SELECT health FROM projects WHERE id = ? OR name = ?",
                [project_id, project_id],
            )
            if project:
                health = project[0].get("health", "green")
                if health == "red":
                    score += 10
                    reasons.append("Project at risk")
                elif health == "yellow":
                    score += 5

        # === BLOCKERS (affects others) ===
        blockers = task.get("blockers", "[]")
        if isinstance(blockers, str):
            try:
                blockers = json.loads(blockers)
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(
                    f"Could not parse blockers JSON for task {task.get('id', 'unknown')}: {e}"
                )
                blockers = []

        # Check if this task blocks others
        blocking_count = self.store.count("tasks", f"dependencies LIKE '%{task['id']}%'")
        if blocking_count > 0:
            score += 10
            reasons.append(f"Blocking {blocking_count} other task(s)")

        # === STATUS ADJUSTMENTS ===
        if task.get("status") == "blocked":
            score *= 0.7  # Reduce priority of blocked items
            reasons.append("Blocked")
        elif task.get("status") == "in_progress":
            score *= 1.05  # Slight boost to in-progress items

        return round(min(100, max(0, score)), 2), reasons

    def _score_email(self, email: dict) -> tuple[float, list[str]]:
        """
        Score an email per DESIGN_V4_SURGICAL.md algorithm.
        Returns (score 0-100, list of reasons).
        """
        score = 50  # Base score
        reasons = []

        # === SENDER/VIP FACTOR (0-25 points) ===
        sender_tier = email.get("stakeholder_tier") or email.get("sender_tier", "significant")

        if sender_tier == "always_urgent" or email.get("is_vip"):
            score += 25
            reasons.append("VIP sender")
        elif sender_tier == "important":
            score += 15
            reasons.append("Important sender")

        # === AGE FACTOR (emails get more urgent over time) ===
        age_hours = email.get("age_hours", 0)
        if not age_hours and email.get("created_at"):
            try:
                created = datetime.fromisoformat(email["created_at"].replace("Z", "+00:00"))
                age_hours = (datetime.now(created.tzinfo) - created).total_seconds() / 3600
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(
                    f"Could not parse created_at for email {email.get('id', 'unknown')}: {e}"
                )
                age_hours = 0

        if age_hours > 48:
            score += 20
            reasons.append(f"Awaiting response {int(age_hours)}h")
        elif age_hours > 24:
            score += 15
            reasons.append(f"Awaiting response {int(age_hours)}h")
        elif age_hours > 8:
            score += 10
            reasons.append(f"Received {int(age_hours)}h ago")

        # === RESPONSE DEADLINE ===
        deadline = email.get("response_deadline")
        if deadline:
            days_until = days_until_date(deadline)
            if days_until < 0:
                score += 30
                reasons.append("Response overdue")
            elif days_until == 0:
                score += 25
                reasons.append("Response due today")
            elif days_until == 1:
                score += 15
                reasons.append("Response due tomorrow")

        # === SENTIMENT/URGENCY ===
        sentiment = email.get("sentiment", "normal")
        if sentiment == "urgent":
            score += 15
            reasons.append("Urgent tone")
        elif sentiment == "negative":
            score += 10
            reasons.append("Needs attention")

        # === LABELS ===
        labels = email.get("labels", "[]")
        if isinstance(labels, str):
            try:
                labels = json.loads(labels)
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(
                    f"Could not parse labels JSON for email {email.get('id', 'unknown')}: {e}"
                )
                labels = []

        if "IMPORTANT" in labels:
            score += 10
            if "Important" not in " ".join(reasons):
                reasons.append("Marked important")

        if not reasons:
            reasons.append("Pending review")

        return round(min(100, max(0, score)), 2), reasons

    def _update_stored_scores(self, items: list[dict]):
        """Update priority scores in the database."""
        for item in items:
            if item["type"] == "task":
                self.store.update(
                    "tasks",
                    item["id"],
                    {
                        "priority": int(item["score"]),
                        "priority_reasons": json.dumps(item["reasons"]),
                    },
                )
            elif item["type"] == "email":
                self.store.update(
                    "communications",
                    item["id"],
                    {
                        "priority": int(item["score"]),
                        "priority_reasons": json.dumps(item["reasons"]),
                    },
                )

    def get_top_priorities(self, limit: int = 10, item_type: str = None) -> list[dict]:
        """Get top N priority items, optionally filtered by type."""
        queue = self.store.get_cache("priority_queue")
        if not queue:
            queue = self.analyze()

        if item_type:
            queue = [item for item in queue if item["type"] == item_type]

        return queue[:limit]
