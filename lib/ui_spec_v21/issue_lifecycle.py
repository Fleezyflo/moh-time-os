"""
Issue Lifecycle Manager — Spec Section 6.5

Implements issue state machine and transitions.
"""

import json
import sqlite3
from typing import Any
from uuid import uuid4

from lib.compat import StrEnum

from .time_utils import from_iso, now_iso, to_iso


class IssueState(StrEnum):
    DETECTED = "detected"
    SURFACED = "surfaced"
    SNOOZED = "snoozed"
    ACKNOWLEDGED = "acknowledged"
    ADDRESSING = "addressing"
    AWAITING_RESOLUTION = "awaiting_resolution"
    RESOLVED = "resolved"
    REGRESSION_WATCH = "regression_watch"
    CLOSED = "closed"
    REGRESSED = "regressed"


class IssueType(StrEnum):
    FINANCIAL = "financial"
    SCHEDULE_DELIVERY = "schedule_delivery"
    COMMUNICATION = "communication"
    RISK = "risk"


class TransitionReason(StrEnum):
    USER = "user"
    SYSTEM_TIMER = "system_timer"
    SYSTEM_SIGNAL = "system_signal"
    SYSTEM_THRESHOLD = "system_threshold"
    SYSTEM_AGGREGATION = "system_aggregation"


# Open states (UI display)
OPEN_STATES = {
    IssueState.DETECTED,
    IssueState.SURFACED,
    IssueState.SNOOZED,
    IssueState.ACKNOWLEDGED,
    IssueState.ADDRESSING,
    IssueState.AWAITING_RESOLUTION,
    IssueState.REGRESSED,
}

# Closed states (UI display)
CLOSED_STATES = {
    IssueState.RESOLVED,
    IssueState.REGRESSION_WATCH,
    IssueState.CLOSED,
}

# Health-counted states (penalty calculation)
HEALTH_COUNTED_STATES = {
    IssueState.SURFACED,
    IssueState.ACKNOWLEDGED,
    IssueState.ADDRESSING,
    IssueState.AWAITING_RESOLUTION,
    IssueState.REGRESSED,
}

# Valid transitions per state
VALID_TRANSITIONS = {
    IssueState.DETECTED: {IssueState.SURFACED},
    IssueState.SURFACED: {
        IssueState.SNOOZED,
        IssueState.ACKNOWLEDGED,
        IssueState.ADDRESSING,
        IssueState.RESOLVED,
    },
    IssueState.SNOOZED: {IssueState.SURFACED},
    IssueState.ACKNOWLEDGED: {
        IssueState.SNOOZED,
        IssueState.ADDRESSING,
        IssueState.RESOLVED,
    },
    IssueState.ADDRESSING: {
        IssueState.SNOOZED,
        IssueState.AWAITING_RESOLUTION,
        IssueState.RESOLVED,
    },
    IssueState.AWAITING_RESOLUTION: {IssueState.RESOLVED},
    IssueState.RESOLVED: {IssueState.REGRESSION_WATCH},
    IssueState.REGRESSION_WATCH: {IssueState.CLOSED, IssueState.REGRESSED},
    IssueState.CLOSED: set(),
    IssueState.REGRESSED: {
        IssueState.SNOOZED,
        IssueState.ACKNOWLEDGED,
        IssueState.ADDRESSING,
        IssueState.RESOLVED,
    },
}

# Available actions by state (spec 7.6)
# v2.9: AVAILABLE_ACTIONS per §7.6 available_actions by state
AVAILABLE_ACTIONS = {
    IssueState.SURFACED: ["acknowledge", "assign", "snooze", "resolve"],
    IssueState.ACKNOWLEDGED: ["assign", "snooze", "resolve"],
    IssueState.ADDRESSING: ["snooze", "resolve", "escalate"],
    IssueState.AWAITING_RESOLUTION: ["resolve", "escalate"],
    IssueState.SNOOZED: ["unsnooze"],
    IssueState.RESOLVED: [],  # Never returned (resolve → regression_watch atomically)
    IssueState.REGRESSION_WATCH: [],
    IssueState.CLOSED: [],
    IssueState.REGRESSED: [
        "acknowledge",
        "assign",
        "snooze",
        "resolve",
    ],  # Same as surfaced
    IssueState.DETECTED: [],  # System-only, not visible to user
}


class IssueLifecycleManager:
    """
    Manages issue lifecycle and state transitions.

    Spec: 6.5 Issue Lifecycle
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_issue(self, issue_id: str) -> dict[str, Any] | None:
        """Fetch issue by ID."""
        cursor = self.conn.execute("SELECT * FROM issues_v29 WHERE id = ?", (issue_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)

    def create_issue(
        self,
        issue_type: str,
        severity: str,
        title: str,
        evidence: dict[str, Any],
        client_id: str,
        brand_id: str | None = None,
        engagement_id: str | None = None,
    ) -> str:
        """
        Create a new issue.

        Returns issue_id.
        """
        issue_id = str(uuid4())
        now = now_iso()

        self.conn.execute(
            """
            INSERT INTO issues_v29 (
                id, type, state, severity, client_id, brand_id, engagement_id,
                title, evidence, evidence_version, created_at, updated_at
            ) VALUES (?, ?, 'detected', ?, ?, ?, ?, ?, ?, 'v1', ?, ?)
        """,
            (
                issue_id,
                issue_type,
                severity,
                client_id,
                brand_id,
                engagement_id,
                title,
                json.dumps(evidence),
                now,
                now,
            ),
        )

        # Log creation
        self._log_transition(
            issue_id, "", "detected", TransitionReason.SYSTEM_AGGREGATION, "system"
        )

        return issue_id

    def transition(
        self, issue_id: str, action: str, user_id: str, payload: dict | None = None
    ) -> tuple[bool, str | None]:
        """
        Execute a user transition action.

        Spec: 7.6 POST /api/issues/:id/transition

        Returns (success, error_message)
        """
        issue = self.get_issue(issue_id)
        if not issue:
            return False, "Issue not found"

        IssueState(issue["state"])
        payload = payload or {}
        now = now_iso()

        # Dispatch by action
        if action == "acknowledge":
            return self._action_acknowledge(issue, user_id, payload, now)
        if action == "snooze":
            return self._action_snooze(issue, user_id, payload, now)
        if action == "unsnooze":
            return self._action_unsnooze(issue, user_id, now)
        if action == "assign":
            return self._action_assign(issue, user_id, payload, now)
        if action == "mark_awaiting":
            return self._action_mark_awaiting(issue, user_id, now)
        if action == "resolve":
            return self._action_resolve(issue, user_id, payload, now)
        if action == "escalate":
            return self._action_escalate(issue, user_id, now)
        return False, f"Unknown action: {action}"

    def _action_acknowledge(
        self, issue: dict, user_id: str, payload: dict, now: str
    ) -> tuple[bool, str | None]:
        """Transition to acknowledged state."""
        current = IssueState(issue["state"])
        target = IssueState.ACKNOWLEDGED

        if target not in VALID_TRANSITIONS.get(current, set()):
            return False, f"Cannot transition from {current.value} to {target.value}"

        self.conn.execute(
            """
            UPDATE issues_v29 SET
                state = ?,
                tagged_by_user_id = COALESCE(tagged_by_user_id, ?),
                tagged_at = COALESCE(tagged_at, ?),
                updated_at = ?
            WHERE id = ?
        """,
            (target.value, user_id, now, now, issue["id"]),
        )

        self._log_transition(
            issue["id"],
            current.value,
            target.value,
            TransitionReason.USER,
            user_id,
            payload.get("note"),
        )

        return True, None

    def _action_snooze(
        self, issue: dict, user_id: str, payload: dict, now: str
    ) -> tuple[bool, str | None]:
        """Transition to snoozed state."""
        from datetime import timedelta

        current = IssueState(issue["state"])
        target = IssueState.SNOOZED

        if target not in VALID_TRANSITIONS.get(current, set()):
            return False, f"Cannot transition from {current.value} to {target.value}"

        snooze_days = payload.get("snooze_days", 7)
        snooze_until = to_iso(from_iso(now) + timedelta(days=snooze_days))

        self.conn.execute(
            """
            UPDATE issues_v29 SET
                state = ?,
                snoozed_until = ?,
                snoozed_by = ?,
                snoozed_at = ?,
                snooze_reason = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (
                target.value,
                snooze_until,
                user_id,
                now,
                payload.get("note"),
                now,
                issue["id"],
            ),
        )

        self._log_transition(
            issue["id"],
            current.value,
            target.value,
            TransitionReason.USER,
            user_id,
            payload.get("note"),
        )

        # Archive any active inbox item for this issue (spec 6.5)
        self._archive_inbox_item_for_issue(issue["id"], now)

        return True, None

    def _action_unsnooze(self, issue: dict, user_id: str, now: str) -> tuple[bool, str | None]:
        """Transition from snoozed to surfaced."""
        current = IssueState(issue["state"])

        if current != IssueState.SNOOZED:
            return False, "Issue is not snoozed"

        target = IssueState.SURFACED

        self.conn.execute(
            """
            UPDATE issues_v29 SET
                state = ?,
                snoozed_until = NULL,
                snoozed_by = NULL,
                snoozed_at = NULL,
                snooze_reason = NULL,
                updated_at = ?
            WHERE id = ?
        """,
            (target.value, now, issue["id"]),
        )

        self._log_transition(
            issue["id"], current.value, target.value, TransitionReason.USER, user_id
        )

        return True, None

    def _action_assign(
        self, issue: dict, user_id: str, payload: dict, now: str
    ) -> tuple[bool, str | None]:
        """Transition to addressing state with assignment."""
        current = IssueState(issue["state"])
        target = IssueState.ADDRESSING

        if target not in VALID_TRANSITIONS.get(current, set()):
            return False, f"Cannot transition from {current.value} to {target.value}"

        assign_to = payload.get("assigned_to")
        if not assign_to:
            return False, "assigned_to is required"

        self.conn.execute(
            """
            UPDATE issues_v29 SET
                state = ?,
                tagged_by_user_id = COALESCE(tagged_by_user_id, ?),
                tagged_at = COALESCE(tagged_at, ?),
                assigned_to = ?,
                assigned_at = ?,
                assigned_by = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (target.value, user_id, now, assign_to, now, user_id, now, issue["id"]),
        )

        self._log_transition(
            issue["id"],
            current.value,
            target.value,
            TransitionReason.USER,
            user_id,
            payload.get("note"),
        )

        return True, None

    def _action_mark_awaiting(self, issue: dict, user_id: str, now: str) -> tuple[bool, str | None]:
        """Transition to awaiting_resolution state."""
        current = IssueState(issue["state"])
        target = IssueState.AWAITING_RESOLUTION

        if target not in VALID_TRANSITIONS.get(current, set()):
            return False, f"Cannot transition from {current.value} to {target.value}"

        self.conn.execute(
            """
            UPDATE issues_v29 SET state = ?, updated_at = ? WHERE id = ?
        """,
            (target.value, now, issue["id"]),
        )

        self._log_transition(
            issue["id"], current.value, target.value, TransitionReason.USER, user_id
        )

        return True, None

    def _action_resolve(
        self, issue: dict, user_id: str, payload: dict, now: str
    ) -> tuple[bool, str | None]:
        """
        Transition to resolved state.

        Spec: §6.5, §7.6 — resolved → regression_watch is ATOMIC.

        CRITICAL: 'resolved' is NEVER persisted to DB. The user action is "resolve",
        but the DB state goes directly to 'regression_watch'. Both transitions are
        logged for audit trail, but the DB only ever sees 'regression_watch'.

        This enforces the v2.9 constraint: chk_no_resolved_state.
        """
        current = IssueState(issue["state"])

        if IssueState.RESOLVED not in VALID_TRANSITIONS.get(current, set()):
            return False, f"Cannot transition from {current.value} to resolved"

        # Calculate regression_watch_until (90 days from now)
        from datetime import timedelta

        regression_until = to_iso(from_iso(now) + timedelta(days=90))

        # ATOMIC: Go directly to regression_watch, never persist 'resolved'
        # This is compliant with chk_no_resolved_state constraint (§6.5)
        self.conn.execute(
            """
            UPDATE issues_v29 SET
                state = 'regression_watch',
                regression_watch_until = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (regression_until, now, issue["id"]),
        )

        # Log BOTH transitions for audit trail (resolved is conceptual, not persisted)
        self._log_transition(
            issue["id"],
            current.value,
            "resolved",
            TransitionReason.USER,
            user_id,
            payload.get("note"),
        )

        self._log_transition(
            issue["id"],
            "resolved",
            "regression_watch",
            TransitionReason.SYSTEM_TIMER,
            "system",
            trigger_rule="enter_regression_watch",
        )

        # Archive any active inbox item for this issue (spec 6.5)
        self._archive_inbox_item_for_issue(issue["id"], now, "issue_resolved_directly")

        return True, None

    def _action_escalate(self, issue: dict, user_id: str, now: str) -> tuple[bool, str | None]:
        """
        Escalate action.

        Spec: 7.6 Escalate Action
        - Sets escalated flag
        - Optionally increases severity
        - Does not change state
        """
        # Increase severity by one level if not already critical
        current_severity = issue["severity"]
        new_severity = current_severity

        severity_order = ["info", "low", "medium", "high", "critical"]
        current_idx = severity_order.index(current_severity)
        if current_idx < len(severity_order) - 1:
            new_severity = severity_order[current_idx + 1]

        self.conn.execute(
            """
            UPDATE issues_v29 SET
                escalated = 1,
                escalated_at = ?,
                escalated_by = ?,
                severity = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (now, user_id, new_severity, now, issue["id"]),
        )

        return True, None

    def surface_issue(self, issue_id: str) -> bool:
        """
        Transition issue from detected to surfaced.

        Called when aggregation threshold is reached.
        """
        now = now_iso()

        issue = self.get_issue(issue_id)
        if not issue or issue["state"] != "detected":
            return False

        self.conn.execute(
            """
            UPDATE issues_v29 SET state = 'surfaced', updated_at = ? WHERE id = ?
        """,
            (now, issue_id),
        )

        self._log_transition(
            issue_id,
            "detected",
            "surfaced",
            TransitionReason.SYSTEM_THRESHOLD,
            "system",
            trigger_rule="threshold_reached",
        )

        return True

    def process_snooze_expiry(self) -> int:
        """
        Process expired issue snoozes.

        Spec: 6.5 Snooze Timer Execution (hourly job)

        Returns count of issues transitioned.
        """
        now = now_iso()

        cursor = self.conn.execute(
            """
            SELECT id FROM issues_v29
            WHERE state = 'snoozed' AND snoozed_until <= ?
        """,
            (now,),
        )

        count = 0
        for row in cursor.fetchall():
            issue_id = row[0]

            self.conn.execute(
                """
                UPDATE issues_v29 SET
                    state = 'surfaced',
                    snoozed_until = NULL,
                    snoozed_by = NULL,
                    snoozed_at = NULL,
                    snooze_reason = NULL,
                    updated_at = ?
                WHERE id = ?
            """,
                (now, issue_id),
            )

            self._log_transition(
                issue_id,
                "snoozed",
                "surfaced",
                TransitionReason.SYSTEM_TIMER,
                "system",
                trigger_rule="snooze_expired",
            )
            count += 1

        return count

    def process_regression_watch(self) -> tuple[int, int]:
        """
        Process regression watch timer.

        Spec: 6.5 System-Only Transitions
        - After 90d: regression_watch → closed

        v2.9: Uses regression_watch_until field (set when issue resolved)
        rather than calculating from updated_at.

        Returns (closed_count, regressed_count)
        """
        now = now_iso()

        # Find issues where regression_watch_until has passed
        cursor = self.conn.execute(
            """
            SELECT id FROM issues_v29
            WHERE state = 'regression_watch'
            AND regression_watch_until IS NOT NULL
            AND regression_watch_until <= ?
        """,
            (now,),
        )

        closed_count = 0
        for row in cursor.fetchall():
            issue_id = row[0]

            self.conn.execute(
                """
                UPDATE issues_v29 SET
                    state = 'closed',
                    updated_at = ?
                WHERE id = ?
            """,
                (now, issue_id),
            )

            self._log_transition(
                issue_id,
                "regression_watch",
                "closed",
                TransitionReason.SYSTEM_TIMER,
                "system",
                trigger_rule="90d_regression_cleared",
            )

            # Auto-archive inbox items for closed issue
            self._archive_inbox_item_for_issue(issue_id, now, "issue_closed")

            closed_count += 1

        return closed_count, 0  # Regression detection handled by detectors

    def trigger_regression(self, issue_id: str, signal_id: str) -> bool:
        """
        Trigger regression for an issue in regression_watch.

        Spec: 7.6 Regression Resurfacing

        Creates a new inbox item for the regressed issue.
        """
        now = now_iso()

        issue = self.get_issue(issue_id)
        if not issue or issue["state"] != "regression_watch":
            return False

        # Transition to regressed
        self.conn.execute(
            """
            UPDATE issues_v29 SET state = 'regressed', updated_at = ? WHERE id = ?
        """,
            (now, issue_id),
        )

        self._log_transition(
            issue_id,
            "regression_watch",
            "regressed",
            TransitionReason.SYSTEM_SIGNAL,
            "system",
            trigger_signal_id=signal_id,
            trigger_rule="signal_recurrence",
        )

        # Create new inbox item
        inbox_id = str(uuid4())
        self.conn.execute(
            """
            INSERT INTO inbox_items_v29 (
                id, type, state, severity, proposed_at, title, evidence,
                evidence_version, underlying_issue_id, client_id, brand_id,
                engagement_id, created_at, updated_at
            ) SELECT
                ?, 'issue', 'proposed', severity, ?, title, evidence,
                evidence_version, id, client_id, brand_id,
                engagement_id, ?, ?
            FROM issues_v29 WHERE id = ?
        """,
            (inbox_id, now, now, now, issue_id),
        )

        return True

    def unsuppress(self, issue_id: str) -> bool:
        """
        Unsuppress an issue.

        Spec: 7.6 POST /api/issues/:id/unsuppress

        Idempotent: returns success even if already unsuppressed.
        """
        now = now_iso()

        self.conn.execute(
            """
            UPDATE issues_v29 SET suppressed = 0, updated_at = ? WHERE id = ?
        """,
            (now, issue_id),
        )

        # Delete suppression rule (handled by SuppressionManager)

        return True

    def _archive_inbox_item_for_issue(
        self, issue_id: str, now: str, resolution_reason: str = "issue_snoozed_directly"
    ):
        """
        Archive any active inbox item for this issue.

        Spec: 6.5 Issue Snooze ↔ Inbox Item Behavior
        Spec: 6.5 Issue Resolved ↔ Inbox Item Behavior

        resolution_reason values:
        - 'issue_snoozed_directly' — when issue snoozed from client detail page
        - 'issue_resolved_directly' — when issue resolved from client detail page
        - 'issue_closed' — when regression_watch ends without recurrence
        """
        self.conn.execute(
            """
            UPDATE inbox_items_v29 SET
                state = 'linked_to_issue',
                resolved_at = ?,
                resolved_issue_id = ?,
                resolution_reason = ?,
                updated_at = ?
            WHERE underlying_issue_id = ?
            AND state IN ('proposed', 'snoozed')
        """,
            (now, issue_id, resolution_reason, now, issue_id),
        )

    def _log_transition(
        self,
        issue_id: str,
        prev_state: str,
        new_state: str,
        reason: TransitionReason,
        actor: str,
        note: str | None = None,
        trigger_signal_id: str | None = None,
        trigger_rule: str | None = None,
    ):
        """Log issue state transition."""
        self.conn.execute(
            """
            INSERT INTO issue_transitions (
                id, issue_id, previous_state, new_state, transition_reason,
                trigger_signal_id, trigger_rule, actor, actor_note, transitioned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                str(uuid4()),
                issue_id,
                prev_state,
                new_state,
                reason.value,
                trigger_signal_id,
                trigger_rule,
                actor,
                note,
                now_iso(),
            ),
        )

    def get_available_actions(self, issue_id: str) -> list[str]:
        """Get available actions for issue's current state."""
        issue = self.get_issue(issue_id)
        if not issue:
            return []

        state = IssueState(issue["state"])
        return AVAILABLE_ACTIONS.get(state, [])
