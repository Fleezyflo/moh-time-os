"""
Time OS V5 — Asana Task Detector

Detects signals from Asana task data (collected JSON).
"""

import logging
from datetime import datetime

from ..data_loader import get_data_loader
from ..database import Database
from ..models import Signal, SignalSource
from .base import SignalDetector

logger = logging.getLogger(__name__)


class AsanaTaskDetector(SignalDetector):
    """
    Detects signals from Asana task data.

    Reads from out/asana-ops.json (collector output).

    Signal Types:
    - task_overdue: Task past due date
    - task_stale: Task not updated in 14+ days
    """

    detector_id = "asana_task"
    detector_version = "5.0.0"
    signal_types = ["task_overdue", "task_stale"]

    def __init__(self, db: Database):
        super().__init__(db)
        self.loader = get_data_loader()

    def detect(self) -> list[Signal]:
        """Run detection and return signals."""
        self.log_detection_start()
        self.load_existing_signals()

        signals = []
        signals.extend(self._detect_overdue())
        signals.extend(self._detect_stale())

        self.log_detection_end(len(signals))
        return signals

    def _detect_overdue(self) -> list[Signal]:
        """Detect overdue tasks from collected data."""
        signals = []
        tasks = self.loader.get_overdue_tasks()

        for task in tasks:
            gid = task.get("gid")
            if not gid:
                continue

            # Skip if signal exists
            if self.signal_exists("task_overdue", gid):
                continue

            days_overdue = task.get("days_overdue", 0)

            # Get scope IDs
            scope = self.loader.get_scope_for_task(task)

            signal = self.create_signal(
                signal_type="task_overdue",
                valence=-1,
                magnitude=self.overdue_magnitude(days_overdue),
                entity_type="task",
                entity_id=gid,
                source_type=SignalSource.ASANA,
                source_id=gid,
                value={
                    "gid": gid,
                    "name": task.get("name"),
                    "project": task.get("project"),
                    "assignee": task.get("assignee"),
                    "due_date": task.get("due"),
                    "days_overdue": days_overdue,
                },
                occurred_at=datetime.fromisoformat(task["due"])
                if task.get("due")
                else datetime.now(),
                scope_client_id=scope.get("client_id"),
                scope_brand_id=scope.get("brand_id"),
                scope_project_id=scope.get("project_id"),
                detection_confidence=1.0,
                attribution_confidence=0.9 if scope.get("client_id") else 0.5,
            )

            signals.append(signal)
            self.log_signal(signal)

        logger.info(f"[{self.detector_id}] Detected {len(signals)} overdue tasks")
        return signals

    def _detect_stale(self) -> list[Signal]:
        """Detect stale tasks from collected data."""
        signals = []
        tasks = self.loader.get_stale_tasks()

        for task in tasks:
            gid = task.get("gid")
            if not gid:
                continue

            # Skip if signal exists
            if self.signal_exists("task_stale", gid):
                continue

            days_stale = task.get("days_since_update", 14)

            # Get scope IDs
            scope = self.loader.get_scope_for_task(task)

            signal = self.create_signal(
                signal_type="task_stale",
                valence=-1,
                magnitude=min(0.3 + (days_stale * 0.02), 0.8),
                entity_type="task",
                entity_id=gid,
                source_type=SignalSource.ASANA,
                source_id=gid,
                value={
                    "gid": gid,
                    "name": task.get("name"),
                    "project": task.get("project"),
                    "assignee": task.get("assignee"),
                    "days_stale": days_stale,
                },
                occurred_at=datetime.now(),
                scope_client_id=scope.get("client_id"),
                scope_brand_id=scope.get("brand_id"),
                scope_project_id=scope.get("project_id"),
                detection_confidence=1.0,
                attribution_confidence=0.9 if scope.get("client_id") else 0.5,
            )

            signals.append(signal)
            self.log_signal(signal)

        logger.info(f"[{self.detector_id}] Detected {len(signals)} stale tasks")
        return signals
