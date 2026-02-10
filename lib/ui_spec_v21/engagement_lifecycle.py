"""
Engagement Lifecycle — Spec Section 6.7

Implements the 7-state engagement lifecycle with transitions and audit trail.
"""

import sqlite3
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .time_utils import now_iso


class EngagementState(Enum):
    """
    Engagement states per spec §6.7.

    7 states total.
    """

    PLANNED = "planned"
    ACTIVE = "active"
    BLOCKED = "blocked"
    PAUSED = "paused"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    COMPLETED = "completed"


class EngagementType(Enum):
    """Engagement types per spec §6.7."""

    PROJECT = "project"
    RETAINER = "retainer"


# Valid state transitions per spec §6.7
VALID_TRANSITIONS: dict[EngagementState, list[EngagementState]] = {
    EngagementState.PLANNED: [
        EngagementState.ACTIVE,  # First task started OR kickoff meeting
    ],
    EngagementState.ACTIVE: [
        EngagementState.BLOCKED,  # External dependency
        EngagementState.PAUSED,  # Client request
        EngagementState.DELIVERING,  # 80%+ tasks complete
    ],
    EngagementState.BLOCKED: [
        EngagementState.ACTIVE,  # Unblocked
    ],
    EngagementState.PAUSED: [
        EngagementState.ACTIVE,  # Resumed
    ],
    EngagementState.DELIVERING: [
        EngagementState.DELIVERED,  # All tasks complete
        EngagementState.BLOCKED,  # External dependency
        EngagementState.PAUSED,  # Client request
    ],
    EngagementState.DELIVERED: [
        EngagementState.COMPLETED,  # Invoice paid / sign-off / 30d timeout
        EngagementState.DELIVERING,  # Additional work requested
    ],
    EngagementState.COMPLETED: [
        # Terminal state - no outgoing transitions
    ],
}

# Trigger → Transition mapping per spec §6.7
HEURISTIC_TRIGGERS: dict[str, tuple[EngagementState, EngagementState]] = {
    "task_started": (EngagementState.PLANNED, EngagementState.ACTIVE),
    "kickoff_meeting": (EngagementState.PLANNED, EngagementState.ACTIVE),
    "blocked_keyword": (EngagementState.ACTIVE, EngagementState.BLOCKED),
    "paused_keyword": (EngagementState.ACTIVE, EngagementState.PAUSED),
    "eighty_percent_complete": (EngagementState.ACTIVE, EngagementState.DELIVERING),
    "all_tasks_complete": (EngagementState.DELIVERING, EngagementState.DELIVERED),
    "delivery_email": (EngagementState.DELIVERING, EngagementState.DELIVERED),
    "approved_in_minutes": (EngagementState.DELIVERING, EngagementState.DELIVERED),
    "invoice_paid": (EngagementState.DELIVERED, EngagementState.COMPLETED),
    "thirty_day_timeout": (EngagementState.DELIVERED, EngagementState.COMPLETED),
    "unblocked": (EngagementState.BLOCKED, EngagementState.ACTIVE),
    "resumed": (EngagementState.PAUSED, EngagementState.ACTIVE),
}

# Actions available per state
AVAILABLE_ACTIONS: dict[EngagementState, list[str]] = {
    EngagementState.PLANNED: ["activate"],
    EngagementState.ACTIVE: ["block", "pause", "mark_delivering"],
    EngagementState.BLOCKED: ["unblock"],
    EngagementState.PAUSED: ["resume"],
    EngagementState.DELIVERING: ["mark_delivered", "block", "pause"],
    EngagementState.DELIVERED: ["complete", "reopen"],
    EngagementState.COMPLETED: [],  # Terminal
}


@dataclass
class TransitionResult:
    """Result of a state transition attempt."""

    success: bool
    error: str | None = None
    previous_state: str | None = None
    new_state: str | None = None
    transition_id: str | None = None


class EngagementLifecycleManager:
    """
    Manages engagement lifecycle transitions.

    Spec: 6.7 Engagement Lifecycle
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._ensure_tables()

    def _ensure_tables(self):
        """Create required tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS engagement_transitions (
                id TEXT PRIMARY KEY,
                engagement_id TEXT NOT NULL,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                trigger TEXT,
                actor TEXT,
                note TEXT,
                transitioned_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_engagement_transitions_engagement_id
            ON engagement_transitions(engagement_id);
        """)

    def get_engagement(self, engagement_id: str) -> dict[str, Any] | None:
        """Get engagement by ID."""
        cursor = self.conn.execute(
            """
            SELECT * FROM engagements WHERE id = ?
        """,
            (engagement_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)

    def validate_transition(self, current_state: str, target_state: str) -> tuple[bool, str | None]:
        """
        Validate if a state transition is allowed.

        Returns:
            Tuple of (valid, error_message)
        """
        try:
            current = EngagementState(current_state)
            target = EngagementState(target_state)
        except ValueError as e:
            return False, f"Invalid state: {e}"

        if target not in VALID_TRANSITIONS.get(current, []):
            return (
                False,
                f"Transition from {current_state} to {target_state} not allowed",
            )

        return True, None

    def transition(
        self,
        engagement_id: str,
        target_state: str,
        trigger: str | None = None,
        actor: str | None = None,
        note: str | None = None,
    ) -> TransitionResult:
        """
        Transition engagement to a new state.

        Args:
            engagement_id: Engagement ID
            target_state: Target state value
            trigger: What triggered this transition
            actor: user_id or 'system'
            note: Optional note

        Returns:
            TransitionResult
        """
        engagement = self.get_engagement(engagement_id)
        if not engagement:
            return TransitionResult(success=False, error="Engagement not found")

        current_state = engagement.get("state", "planned")

        # Validate transition
        valid, error = self.validate_transition(current_state, target_state)
        if not valid:
            return TransitionResult(success=False, error=error, previous_state=current_state)

        now = now_iso()
        transition_id = str(uuid.uuid4())

        # Update engagement state
        self.conn.execute(
            """
            UPDATE engagements
            SET state = ?, updated_at = ?
            WHERE id = ?
        """,
            (target_state, now, engagement_id),
        )

        # Log transition
        self._log_transition(
            transition_id=transition_id,
            engagement_id=engagement_id,
            from_state=current_state,
            to_state=target_state,
            trigger=trigger,
            actor=actor,
            note=note,
            transitioned_at=now,
        )

        self.conn.commit()

        return TransitionResult(
            success=True,
            previous_state=current_state,
            new_state=target_state,
            transition_id=transition_id,
        )

    def _log_transition(
        self,
        transition_id: str,
        engagement_id: str,
        from_state: str,
        to_state: str,
        trigger: str | None,
        actor: str | None,
        note: str | None,
        transitioned_at: str,
    ):
        """Log state transition for audit trail."""
        now = now_iso()
        self.conn.execute(
            """
            INSERT INTO engagement_transitions (
                id, engagement_id, from_state, to_state, trigger, actor, note,
                transitioned_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                transition_id,
                engagement_id,
                from_state,
                to_state,
                trigger,
                actor,
                note,
                transitioned_at,
                now,
            ),
        )

    def get_transition_history(self, engagement_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get transition history for an engagement."""
        cursor = self.conn.execute(
            """
            SELECT * FROM engagement_transitions
            WHERE engagement_id = ?
            ORDER BY transitioned_at DESC
            LIMIT ?
        """,
            (engagement_id, limit),
        )

        return [dict(row) for row in cursor.fetchall()]

    def execute_action(
        self, engagement_id: str, action: str, actor: str, note: str | None = None
    ) -> TransitionResult:
        """
        Execute a named action on an engagement.

        Args:
            engagement_id: Engagement ID
            action: Action name from AVAILABLE_ACTIONS
            actor: user_id performing the action
            note: Optional note

        Returns:
            TransitionResult
        """
        engagement = self.get_engagement(engagement_id)
        if not engagement:
            return TransitionResult(success=False, error="Engagement not found")

        current_state = engagement.get("state", "planned")

        # Check if action is available
        try:
            state_enum = EngagementState(current_state)
            available = AVAILABLE_ACTIONS.get(state_enum, [])
        except ValueError:
            available = []

        if action not in available:
            return TransitionResult(
                success=False,
                error=f"Action '{action}' not available in state '{current_state}'",
                previous_state=current_state,
            )

        # Map action to target state
        action_to_state = {
            "activate": EngagementState.ACTIVE,
            "block": EngagementState.BLOCKED,
            "pause": EngagementState.PAUSED,
            "unblock": EngagementState.ACTIVE,
            "resume": EngagementState.ACTIVE,
            "mark_delivering": EngagementState.DELIVERING,
            "mark_delivered": EngagementState.DELIVERED,
            "complete": EngagementState.COMPLETED,
            "reopen": EngagementState.DELIVERING,
        }

        target_state = action_to_state.get(action)
        if not target_state:
            return TransitionResult(
                success=False,
                error=f"Unknown action: {action}",
                previous_state=current_state,
            )

        return self.transition(
            engagement_id=engagement_id,
            target_state=target_state.value,
            trigger=f"action:{action}",
            actor=actor,
            note=note,
        )

    def get_available_actions(self, engagement_id: str) -> list[str]:
        """Get available actions for an engagement."""
        engagement = self.get_engagement(engagement_id)
        if not engagement:
            return []

        current_state = engagement.get("state", "planned")

        try:
            state_enum = EngagementState(current_state)
            return AVAILABLE_ACTIONS.get(state_enum, [])
        except ValueError:
            return []

    def process_heuristic_trigger(
        self, engagement_id: str, trigger: str
    ) -> TransitionResult | None:
        """
        Process a heuristic trigger from signals.

        Only transitions if the trigger matches the current state.

        Args:
            engagement_id: Engagement ID
            trigger: Trigger name from HEURISTIC_TRIGGERS

        Returns:
            TransitionResult if transition occurred, None otherwise
        """
        if trigger not in HEURISTIC_TRIGGERS:
            return None

        engagement = self.get_engagement(engagement_id)
        if not engagement:
            return None

        current_state = engagement.get("state", "planned")
        required_state, target_state = HEURISTIC_TRIGGERS[trigger]

        # Only trigger if in expected state
        if current_state != required_state.value:
            return None

        return self.transition(
            engagement_id=engagement_id,
            target_state=target_state.value,
            trigger=f"heuristic:{trigger}",
            actor="system",
        )

    def check_thirty_day_timeout(self) -> int:
        """
        Check for engagements in 'delivered' state for 30+ days.

        Automatically transitions them to 'completed'.

        Returns:
            Number of engagements transitioned
        """
        from datetime import timedelta

        from .time_utils import now_utc, to_iso

        cutoff = to_iso(now_utc() - timedelta(days=30))

        # Find delivered engagements older than 30 days
        cursor = self.conn.execute(
            """
            SELECT id FROM engagements
            WHERE state = 'delivered'
            AND updated_at <= ?
        """,
            (cutoff,),
        )

        count = 0
        for row in cursor.fetchall():
            result = self.transition(
                engagement_id=row[0],
                target_state=EngagementState.COMPLETED.value,
                trigger="thirty_day_timeout",
                actor="system",
            )
            if result.success:
                count += 1

        return count


# SQL migration for engagement tables
ENGAGEMENT_MIGRATION = """
-- Engagements table with lifecycle state
CREATE TABLE IF NOT EXISTS engagements (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('project', 'retainer')),
    state TEXT NOT NULL DEFAULT 'planned' CHECK (state IN (
        'planned', 'active', 'blocked', 'paused',
        'delivering', 'delivered', 'completed'
    )),
    -- Asana integration
    asana_project_gid TEXT,
    asana_url TEXT,
    -- Dates
    started_at TEXT,
    completed_at TEXT,
    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- Foreign keys
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (brand_id) REFERENCES brands(id)
);

CREATE INDEX IF NOT EXISTS idx_engagements_client_id ON engagements(client_id);
CREATE INDEX IF NOT EXISTS idx_engagements_state ON engagements(state);
CREATE INDEX IF NOT EXISTS idx_engagements_asana_gid ON engagements(asana_project_gid);

-- Engagement transitions audit table
CREATE TABLE IF NOT EXISTS engagement_transitions (
    id TEXT PRIMARY KEY,
    engagement_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger TEXT,
    actor TEXT,
    note TEXT,
    transitioned_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements(id)
);

CREATE INDEX IF NOT EXISTS idx_engagement_transitions_engagement_id
ON engagement_transitions(engagement_id);
"""
