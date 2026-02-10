"""
Time OS V4 - Deadline Detector

Detects deadline-related signals:
- Approaching deadlines
- Overdue tasks
- Deadline clusters (multiple things due at once)
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from ..artifact_service import get_artifact_service
from .base import BaseDetector

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "moh_time_os.db"
)

# Legacy filter: tasks overdue more than this many days are considered archived/legacy noise
# and excluded from signal generation to keep proposals clean
LEGACY_OVERDUE_THRESHOLD_DAYS = 365


class DeadlineDetector(BaseDetector):
    """
    Detects deadline-related risks and alerts.

    Signal types produced:
    - deadline_approaching: Task/deliverable due soon
    - deadline_overdue: Task/deliverable past due
    - deadline_cluster: Multiple items due in same window
    - deadline_at_risk: High-priority item with tight deadline
    """

    detector_id = "deadline_detector"
    version = "1.0.0"
    description = "Detects deadline-related signals from tasks and projects"
    signal_types = [
        "deadline_approaching",
        "deadline_overdue",
        "deadline_cluster",
        "deadline_at_risk",
    ]

    # Thresholds
    APPROACHING_DAYS = 3  # Alert if due within N days
    CLUSTER_WINDOW_DAYS = 2  # Items due within N days of each other
    CLUSTER_MIN_COUNT = 3  # Min items to trigger cluster signal

    def get_parameters(self) -> dict[str, Any]:
        return {
            "approaching_days": self.APPROACHING_DAYS,
            "cluster_window_days": self.CLUSTER_WINDOW_DAYS,
            "cluster_min_count": self.CLUSTER_MIN_COUNT,
        }

    def detect(self, scope: dict) -> list[dict[str, Any]]:
        """Run deadline detection."""
        signals = []
        artifact_svc = get_artifact_service()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            today = datetime.now().date()
            approaching_cutoff = (
                today + timedelta(days=self.APPROACHING_DAYS)
            ).isoformat()

            # Find overdue tasks (excluding legacy tasks > LEGACY_OVERDUE_THRESHOLD_DAYS old)
            legacy_cutoff = (
                today - timedelta(days=LEGACY_OVERDUE_THRESHOLD_DAYS)
            ).isoformat()
            cursor.execute(
                """
                SELECT t.id, t.title, t.source, t.due_date, t.assignee, t.project,
                       t.project as project_name, NULL
                FROM tasks t
                WHERE t.due_date < ? AND t.due_date IS NOT NULL
                AND t.due_date >= ?  -- Exclude legacy tasks (older than threshold)
                AND t.status NOT IN ('done', 'cancelled', 'closed', 'archived')
                ORDER BY t.due_date
            """,
                (today.isoformat(), legacy_cutoff),
            )

            for row in cursor.fetchall():
                (
                    task_id,
                    title,
                    source,
                    due_date,
                    assignee,
                    project_id,
                    project_name,
                    client_id,
                ) = row
                item_id = task_id  # Use task_id as entity reference
                owner = assignee

                try:
                    days_overdue = (
                        today - datetime.fromisoformat(due_date[:10]).date()
                    ).days
                except (ValueError, TypeError):
                    # Can't parse due_date - may miss overdue detection
                    logger.warning(
                        f"Skipping task {task_id} '{title}': invalid due_date '{due_date}'"
                    )
                    continue
                severity = (
                    "critical"
                    if days_overdue > 7
                    else "high"
                    if days_overdue > 3
                    else "medium"
                )

                # Create evidence excerpts
                evidence_excerpts = []
                evidence_artifacts = []

                # Find artifact for this task
                cursor.execute(
                    "SELECT artifact_id FROM artifacts WHERE source_id = ? AND source = 'asana'",
                    (item_id,),
                )
                art_row = cursor.fetchone()
                if art_row:
                    artifact_id = art_row[0]
                    evidence_artifacts.append(artifact_id)

                    # Create excerpt with proof text
                    proof_text = f"Task '{title or 'Unknown'}' was due {due_date}, now {days_overdue} days overdue"
                    excerpt = artifact_svc.create_excerpt(
                        artifact_id,
                        proof_text,
                        anchor_type="computed",
                        anchor_start="due",
                        anchor_end="due",
                    )
                    evidence_excerpts.append(excerpt["excerpt_id"])

                    # Add owner excerpt if available
                    if owner:
                        owner_excerpt = artifact_svc.create_excerpt(
                            artifact_id,
                            f"Assigned to: {owner}",
                            anchor_type="computed",
                            anchor_start="owner",
                            anchor_end="owner",
                        )
                        evidence_excerpts.append(owner_excerpt["excerpt_id"])

                    # Add project excerpt if available
                    if project_name:
                        proj_excerpt = artifact_svc.create_excerpt(
                            artifact_id,
                            f"Project: {project_name}",
                            anchor_type="computed",
                            anchor_start="project",
                            anchor_end="project",
                        )
                        evidence_excerpts.append(proj_excerpt["excerpt_id"])

                # Pull in evidence from linked artifacts (emails mentioning this task)
                cursor.execute(
                    """
                    SELECT ae.excerpt_id, a.artifact_id, a.source
                    FROM entity_links el
                    JOIN artifacts a ON el.from_artifact_id = a.artifact_id
                    JOIN artifact_excerpts ae ON a.artifact_id = ae.artifact_id
                    WHERE el.to_entity_type = 'task'
                      AND el.to_entity_id = ?
                      AND el.confidence >= 0.7
                      AND a.source IN ('gmail', 'gchat')
                    ORDER BY a.occurred_at DESC
                    LIMIT 3
                """,
                    (item_id,),
                )

                for linked_row in cursor.fetchall():
                    excerpt_id, linked_artifact_id, source = linked_row
                    if excerpt_id not in evidence_excerpts:
                        evidence_excerpts.append(excerpt_id)
                        if linked_artifact_id not in evidence_artifacts:
                            evidence_artifacts.append(linked_artifact_id)

                signal = self.create_signal(
                    signal_type="deadline_overdue",
                    entity_ref_type="task",
                    entity_ref_id=item_id,
                    value={
                        "title": title,
                        "due_date": due_date,
                        "days_overdue": days_overdue,
                        "owner": owner,
                        "project_id": project_id,
                        "project_name": project_name,
                        "client_id": client_id,
                    },
                    severity=severity,
                    interpretation_confidence=0.95,
                    linkage_confidence_floor=0.9,
                    evidence_excerpt_ids=evidence_excerpts,
                    evidence_artifact_ids=evidence_artifacts,
                )
                signals.append(signal)

            # Find approaching deadlines
            cursor.execute(
                """
                SELECT t.id, t.title, t.source, t.due_date, t.assignee, t.project,
                       t.project as project_name, NULL
                FROM tasks t
                WHERE t.due_date >= ? AND t.due_date <= ? AND t.due_date IS NOT NULL
                AND t.status NOT IN ('done', 'cancelled', 'closed', 'archived')
                ORDER BY t.due_date
            """,
                (today.isoformat(), approaching_cutoff),
            )

            for row in cursor.fetchall():
                (
                    task_id,
                    title,
                    source,
                    due_date,
                    assignee,
                    project_id,
                    project_name,
                    client_id,
                ) = row
                item_id = task_id
                owner = assignee

                try:
                    days_until = (
                        datetime.fromisoformat(due_date[:10]).date() - today
                    ).days
                except (ValueError, TypeError):
                    # Can't parse due_date - may miss approaching deadline
                    logger.warning(
                        f"Skipping task {task_id} '{title}': invalid due_date '{due_date}'"
                    )
                    continue
                severity = "high" if days_until <= 1 else "medium"

                # Create evidence
                evidence_excerpts = []
                evidence_artifacts = []

                cursor.execute(
                    "SELECT artifact_id FROM artifacts WHERE source_id = ? AND source = 'asana'",
                    (item_id,),
                )
                art_row = cursor.fetchone()
                if art_row:
                    artifact_id = art_row[0]
                    evidence_artifacts.append(artifact_id)

                    proof_text = f"Task '{title or 'Unknown'}' due in {days_until} day(s) on {due_date}"
                    excerpt = artifact_svc.create_excerpt(
                        artifact_id,
                        proof_text,
                        anchor_type="computed",
                        anchor_start="due",
                        anchor_end="due",
                    )
                    evidence_excerpts.append(excerpt["excerpt_id"])

                    if owner:
                        owner_excerpt = artifact_svc.create_excerpt(
                            artifact_id,
                            f"Assigned to: {owner}",
                            anchor_type="computed",
                            anchor_start="owner",
                            anchor_end="owner",
                        )
                        evidence_excerpts.append(owner_excerpt["excerpt_id"])

                    if project_name:
                        proj_excerpt = artifact_svc.create_excerpt(
                            artifact_id,
                            f"Project: {project_name}",
                            anchor_type="computed",
                            anchor_start="project",
                            anchor_end="project",
                        )
                        evidence_excerpts.append(proj_excerpt["excerpt_id"])

                # Pull in evidence from linked artifacts (emails mentioning this task)
                cursor.execute(
                    """
                    SELECT ae.excerpt_id, a.artifact_id, a.source
                    FROM entity_links el
                    JOIN artifacts a ON el.from_artifact_id = a.artifact_id
                    JOIN artifact_excerpts ae ON a.artifact_id = ae.artifact_id
                    WHERE el.to_entity_type = 'task'
                      AND el.to_entity_id = ?
                      AND el.confidence >= 0.7
                      AND a.source IN ('gmail', 'gchat')
                    ORDER BY a.occurred_at DESC
                    LIMIT 3
                """,
                    (item_id,),
                )

                for linked_row in cursor.fetchall():
                    excerpt_id, linked_artifact_id, source = linked_row
                    if excerpt_id not in evidence_excerpts:
                        evidence_excerpts.append(excerpt_id)
                        if linked_artifact_id not in evidence_artifacts:
                            evidence_artifacts.append(linked_artifact_id)

                signal = self.create_signal(
                    signal_type="deadline_approaching",
                    entity_ref_type="task",
                    entity_ref_id=item_id,
                    value={
                        "title": title,
                        "due_date": due_date,
                        "days_until": days_until,
                        "owner": owner,
                        "project_id": project_id,
                        "project_name": project_name,
                        "client_id": client_id,
                    },
                    severity=severity,
                    interpretation_confidence=0.95,
                    linkage_confidence_floor=0.9,
                    evidence_excerpt_ids=evidence_excerpts,
                    evidence_artifact_ids=evidence_artifacts,
                )
                signals.append(signal)

            # Find deadline clusters by project/client
            cursor.execute(
                """
                SELECT p.id, p.name, p.client_id, c.name as client_name,
                       COUNT(*) as due_count, MIN(t.due_date) as earliest_due
                FROM tasks t
                JOIN projects p ON t.project = p.id
                LEFT JOIN clients c ON p.client_id = c.id
                WHERE t.due_date >= ? AND t.due_date <= date(?, '+' || ? || ' days')
                AND t.due_date IS NOT NULL
                AND t.status NOT IN ('done', 'cancelled', 'closed', 'archived')
                GROUP BY p.id
                HAVING COUNT(*) >= ?
            """,
                (
                    today.isoformat(),
                    today.isoformat(),
                    self.CLUSTER_WINDOW_DAYS,
                    self.CLUSTER_MIN_COUNT,
                ),
            )

            for row in cursor.fetchall():
                (
                    project_id,
                    project_name,
                    client_id,
                    client_name,
                    due_count,
                    earliest_due,
                ) = row

                signal = self.create_signal(
                    signal_type="deadline_cluster",
                    entity_ref_type="project",
                    entity_ref_id=project_id,
                    value={
                        "project_name": project_name,
                        "client_id": client_id,
                        "client_name": client_name,
                        "items_due": due_count,
                        "window_days": self.CLUSTER_WINDOW_DAYS,
                        "earliest_due": earliest_due,
                    },
                    severity="high",
                    interpretation_confidence=0.9,
                    linkage_confidence_floor=0.9,
                )
                signals.append(signal)

            return signals

        finally:
            conn.close()
