"""
Pattern Analyzer - Detects recurring patterns in work, communications, and scheduling.

Identifies:
- Recurring tasks and their frequencies
- Communication patterns (response times, peak hours)
- Work rhythm patterns (productive hours, meeting-heavy days)
- Stale/stuck items
"""

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PatternAnalyzer:
    """Detects and tracks patterns in work and communications."""

    def __init__(self, store, config: dict = None):
        """
        Args:
            store: StateStore instance
            config: Pattern detection config
        """
        self.store = store
        self.config = config or {}

    def analyze_task_patterns(self, days: int = 30) -> dict:
        """
        Analyze task completion patterns.

        Returns:
            {
                'completion_rate': float,
                'avg_completion_days': float,
                'by_day_of_week': {day: count},
                'by_lane': {lane: {created, completed, rate}},
                'recurring_titles': [{title, count, frequency}],
                'stale_tasks': [{id, title, days_stale}]
            }
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        # Get tasks from period
        tasks = self.store.query(
            """
            SELECT id, title, status, lane, created_at, updated_at, context
            FROM tasks
            WHERE created_at >= ?
        """,
            [cutoff],
        )

        total = len(tasks)
        completed = sum(1 for t in tasks if t["status"] in ("completed", "done"))

        # By day of week
        by_dow = defaultdict(int)
        for task in tasks:
            if task["status"] in ("completed", "done"):
                try:
                    dt = datetime.fromisoformat(
                        task["updated_at"].replace("Z", "+00:00")
                    )
                    by_dow[dt.strftime("%A")] += 1
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(
                        f"Could not parse updated_at for task {task.get('id', 'unknown')}: {e}"
                    )

        # By lane
        by_lane = defaultdict(lambda: {"created": 0, "completed": 0})
        for task in tasks:
            lane = task.get("lane") or "ops"
            by_lane[lane]["created"] += 1
            if task["status"] in ("completed", "done"):
                by_lane[lane]["completed"] += 1

        for lane in by_lane:
            created = by_lane[lane]["created"]
            completed = by_lane[lane]["completed"]
            by_lane[lane]["rate"] = (
                round(completed / created * 100, 1) if created > 0 else 0
            )

        # Find recurring title patterns
        title_counts = defaultdict(int)
        for task in tasks:
            # Normalize title (remove dates, numbers)
            normalized = re.sub(r"\d{4}-\d{2}-\d{2}", "", task["title"])
            normalized = re.sub(r"\d+", "#", normalized)
            normalized = normalized.strip()
            if len(normalized) > 10:
                title_counts[normalized] += 1

        recurring = [
            {"title": title, "count": count}
            for title, count in title_counts.items()
            if count >= 3
        ]
        recurring.sort(key=lambda x: x["count"], reverse=True)

        # Find stale tasks
        now = datetime.now()
        stale = []
        for task in tasks:
            if task["status"] not in ("completed", "done", "cancelled"):
                try:
                    updated = datetime.fromisoformat(
                        task["updated_at"].replace("Z", "+00:00")
                    )
                    days_stale = (now - updated).days
                    if days_stale >= 7:
                        stale.append(
                            {
                                "id": task["id"],
                                "title": task["title"],
                                "days_stale": days_stale,
                            }
                        )
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(
                        f"Could not parse updated_at for stale check on task {task.get('id', 'unknown')}: {e}"
                    )

        stale.sort(key=lambda x: x["days_stale"], reverse=True)

        # Feedback summary (last 7 days)
        fb_rows = self.store.query(
            "SELECT feedback_type, COUNT(*) as cnt FROM feedback WHERE created_at >= date('now','-7 days') GROUP BY feedback_type"
        )
        feedback_summary = {r["feedback_type"]: r["cnt"] for r in fb_rows}

        # Adjust detection sensitivity based on feedback
        try:
            self.adjust_scoring_weights(feedback_summary)
        except Exception as e:
            self.logger.error(f"Failed to adjust scoring weights: {e}")

        return {
            "period_days": days,
            "total_tasks": total,
            "completed": completed,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "by_day_of_week": dict(by_dow),
            "by_lane": dict(by_lane),
            "recurring_titles": recurring[:10],
            "stale_tasks": stale[:20],
            "recent_feedback": feedback_summary,
        }

    def analyze_communication_patterns(self, days: int = 14) -> dict:
        """
        Analyze communication patterns.

        Returns:
            {
                'avg_response_time_hours': float,
                'peak_hours': [hour],
                'top_senders': [{email, count}],
                'pending_responses': [{id, from, subject, age_hours}]
            }
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        comms = self.store.query(
            """
            SELECT id, from_email, subject, requires_response, response_deadline,
                   created_at, processed
            FROM communications
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """,
            [cutoff],
        )

        # Peak hours
        hour_counts = defaultdict(int)
        for comm in comms:
            try:
                dt = datetime.fromisoformat(comm["created_at"].replace("Z", "+00:00"))
                hour_counts[dt.hour] += 1
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(
                    f"Could not parse created_at for communication analysis: {e}"
                )

        peak_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]

        # Top senders
        sender_counts = defaultdict(int)
        for comm in comms:
            sender = comm.get("from_email", "unknown")
            sender_counts[sender] += 1

        top_senders = [
            {"email": email, "count": count}
            for email, count in sorted(
                sender_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]
        ]

        # Pending responses
        now = datetime.now()
        pending = []
        for comm in comms:
            if comm.get("requires_response") and not comm.get("processed"):
                try:
                    created = datetime.fromisoformat(
                        comm["created_at"].replace("Z", "+00:00")
                    )
                    age_hours = (now - created).total_seconds() / 3600
                    pending.append(
                        {
                            "id": comm["id"],
                            "from": comm.get("from_email"),
                            "subject": comm.get("subject"),
                            "age_hours": round(age_hours, 1),
                        }
                    )
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(
                        f"Could not parse created_at for pending response: {e}"
                    )

        pending.sort(key=lambda x: x["age_hours"], reverse=True)

        return {
            "period_days": days,
            "total_communications": len(comms),
            "peak_hours": [h[0] for h in peak_hours],
            "top_senders": top_senders,
            "pending_responses": pending[:20],
            "pending_count": len(pending),
        }

    def analyze_meeting_patterns(self, days: int = 30) -> dict:
        """
        Analyze meeting patterns.

        Returns:
            {
                'avg_meetings_per_day': float,
                'avg_meeting_duration_min': float,
                'meeting_heavy_days': [day_of_week],
                'total_meeting_hours': float
            }
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        events = self.store.query(
            """
            SELECT id, title, start_time, end_time
            FROM events
            WHERE start_time >= ?
        """,
            [cutoff],
        )

        total_minutes = 0
        by_dow = defaultdict(int)

        for event in events:
            try:
                start = datetime.fromisoformat(
                    event["start_time"].replace("Z", "+00:00")
                )
                end_str = event.get("end_time")
                end = (
                    datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    if end_str
                    else start + timedelta(hours=1)
                )

                duration = (end - start).total_seconds() / 60
                total_minutes += duration
                by_dow[start.strftime("%A")] += 1
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(
                    f"Could not parse event times for event {event.get('id', 'unknown')}: {e}"
                )

        meeting_count = len(events)
        avg_per_day = meeting_count / days if days > 0 else 0
        avg_duration = total_minutes / meeting_count if meeting_count > 0 else 0

        # Find heavy days
        heavy_days = sorted(by_dow.items(), key=lambda x: x[1], reverse=True)

        return {
            "period_days": days,
            "total_meetings": meeting_count,
            "avg_meetings_per_day": round(avg_per_day, 1),
            "avg_meeting_duration_min": round(avg_duration, 0),
            "total_meeting_hours": round(total_minutes / 60, 1),
            "by_day_of_week": dict(by_dow),
            "meeting_heavy_days": [d[0] for d in heavy_days[:2]],
        }

    def detect_anomalies(self) -> list[dict]:
        """
        Detect anomalies in recent patterns.

        Returns list of anomaly alerts.
        """
        anomalies = []

        # Check for unusual task staleness
        task_patterns = self.analyze_task_patterns(7)
        if task_patterns["completion_rate"] < 20:
            anomalies.append(
                {
                    "type": "low_completion_rate",
                    "severity": "warning",
                    "message": f"Task completion rate is only {task_patterns['completion_rate']}% this week",
                    "data": {"rate": task_patterns["completion_rate"]},
                }
            )

        if len(task_patterns["stale_tasks"]) > 10:
            anomalies.append(
                {
                    "type": "many_stale_tasks",
                    "severity": "warning",
                    "message": f"{len(task_patterns['stale_tasks'])} tasks are stale (7+ days without update)",
                    "data": {"count": len(task_patterns["stale_tasks"])},
                }
            )

        # Check for pending responses
        comm_patterns = self.analyze_communication_patterns(7)
        urgent_pending = [
            p for p in comm_patterns["pending_responses"] if p["age_hours"] > 48
        ]
        if urgent_pending:
            anomalies.append(
                {
                    "type": "overdue_responses",
                    "severity": "high",
                    "message": f"{len(urgent_pending)} emails need response (48+ hours old)",
                    "data": {"count": len(urgent_pending), "items": urgent_pending[:5]},
                }
            )

        return anomalies

    def save_pattern(self, pattern_type: str, data: dict):
        """Save detected pattern to database."""
        self.store.insert(
            "patterns",
            {
                "id": f"{pattern_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "type": pattern_type,
                "data": json.dumps(data),
                "detected_at": datetime.now().isoformat(),
            },
        )

    def adjust_scoring_weights(self, feedback_summary: dict[str, int]):
        """
        Adjust pattern detection confidence threshold based on aggregated feedback.
        Positive feedback increases threshold, negative decreases it.
        """
        pos = feedback_summary.get("positive", 0)
        neg = feedback_summary.get("negative", 0)
        threshold = self.config.get("confidence_threshold", 0.7)
        if pos > neg:
            threshold = min(0.99, threshold + 0.01 * (pos - neg))
        elif neg > pos:
            threshold = max(0.1, threshold - 0.01 * (neg - pos))
        self.config["confidence_threshold"] = threshold
        self.logger.info(f"Adjusted confidence_threshold to {threshold:.2f}")
