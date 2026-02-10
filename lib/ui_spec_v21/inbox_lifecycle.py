"""
Inbox Lifecycle Manager — Spec Section 1.4

Implements inbox item state machine and actions.
"""

import json
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import uuid4

from .evidence import validate_evidence
from .suppression import SuppressionManager, check_suppression
from .time_utils import from_iso, now_iso


class InboxState(StrEnum):
    PROPOSED = "proposed"
    SNOOZED = "snoozed"
    DISMISSED = "dismissed"
    LINKED_TO_ISSUE = "linked_to_issue"


class InboxType(StrEnum):
    ISSUE = "issue"
    FLAGGED_SIGNAL = "flagged_signal"
    ORPHAN = "orphan"
    AMBIGUOUS = "ambiguous"


class InboxAction(StrEnum):
    TAG = "tag"
    ASSIGN = "assign"
    SNOOZE = "snooze"
    DISMISS = "dismiss"
    LINK = "link"
    CREATE = "create"
    SELECT = "select"


# Actions available by type (spec 7.10)
ACTIONS_BY_TYPE = {
    InboxType.ISSUE: [
        InboxAction.TAG,
        InboxAction.ASSIGN,
        InboxAction.SNOOZE,
        InboxAction.DISMISS,
    ],
    InboxType.FLAGGED_SIGNAL: [
        InboxAction.TAG,
        InboxAction.ASSIGN,
        InboxAction.SNOOZE,
        InboxAction.DISMISS,
    ],
    InboxType.ORPHAN: [InboxAction.LINK, InboxAction.CREATE, InboxAction.DISMISS],
    InboxType.AMBIGUOUS: [InboxAction.SELECT, InboxAction.DISMISS],
}

# Actions after select/link
ACTIONS_AFTER_RESOLUTION = [
    InboxAction.TAG,
    InboxAction.ASSIGN,
    InboxAction.SNOOZE,
    InboxAction.DISMISS,
]

# Severity ordering for sorting (spec 0.1)
SEVERITY_WEIGHTS = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}

# Action payload validation (spec 7.10)
ACTION_REQUIRED_FIELDS = {
    InboxAction.TAG: [],
    InboxAction.ASSIGN: ["assign_to"],
    InboxAction.SNOOZE: ["snooze_days"],
    InboxAction.DISMISS: [],
    InboxAction.LINK: ["link_engagement_id"],
    InboxAction.CREATE: [],
    InboxAction.SELECT: ["select_candidate_id"],
}

ACTION_OPTIONAL_FIELDS = {
    InboxAction.TAG: ["note"],
    InboxAction.ASSIGN: ["note"],
    InboxAction.SNOOZE: ["note"],
    InboxAction.DISMISS: ["note"],
    InboxAction.LINK: ["note"],
    InboxAction.CREATE: ["note"],
    InboxAction.SELECT: ["note"],
}

ACTION_REJECT_FIELDS = {
    InboxAction.TAG: [
        "assign_to",
        "snooze_days",
        "link_engagement_id",
        "select_candidate_id",
    ],
    InboxAction.ASSIGN: ["snooze_days", "link_engagement_id", "select_candidate_id"],
    InboxAction.SNOOZE: ["assign_to", "link_engagement_id", "select_candidate_id"],
    InboxAction.DISMISS: [
        "assign_to",
        "snooze_days",
        "link_engagement_id",
        "select_candidate_id",
    ],
    InboxAction.LINK: ["assign_to", "snooze_days", "select_candidate_id"],
    InboxAction.CREATE: [
        "assign_to",
        "snooze_days",
        "link_engagement_id",
        "select_candidate_id",
    ],
    InboxAction.SELECT: ["assign_to", "snooze_days", "link_engagement_id"],
}


@dataclass
class ActionResult:
    """Result of an inbox action."""

    success: bool
    inbox_item_state: str
    issue_id: str | None = None
    resolved_at: str | None = None
    snooze_until: str | None = None
    suppression_key: str | None = None
    actions: list[str] | None = None
    engagement_id: str | None = None
    client_id: str | None = None
    brand_id: str | None = None
    error: str | None = None


def validate_action_payload(
    action: InboxAction, payload: dict[str, Any]
) -> tuple[bool, str | None]:
    """
    Validate action payload per spec 7.10.

    Returns (is_valid, error_message)
    """
    # Check required fields
    for field in ACTION_REQUIRED_FIELDS.get(action, []):
        if field not in payload or payload[field] is None:
            return False, f"Missing required field: {field}"

    # Check rejected fields
    for field in ACTION_REJECT_FIELDS.get(action, []):
        if field in payload and payload[field] is not None:
            return False, f"Unexpected field for {action.value}: {field}"

    return True, None


class InboxLifecycleManager:
    """
    Manages inbox item lifecycle and actions.

    Spec: 1.4 Inbox Item Lifecycle
    """

    def __init__(self, conn: sqlite3.Connection, org_tz: str = "Asia/Dubai"):
        self.conn = conn
        self.org_tz = org_tz
        self.suppression = SuppressionManager(conn)

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        """Fetch inbox item by ID."""
        cursor = self.conn.execute(
            """
            SELECT * FROM inbox_items_v29 WHERE id = ?
        """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)

    def get_actions(self, item_type: str, is_resolved: bool = False) -> list[str]:
        """
        Get available actions for item type.

        Spec: 7.10 Actions by type
        """
        if is_resolved:
            return [a.value for a in ACTIONS_AFTER_RESOLUTION]

        item_type_enum = InboxType(item_type)
        return [a.value for a in ACTIONS_BY_TYPE.get(item_type_enum, [])]

    def create_inbox_item(
        self,
        item_type: str,
        severity: str,
        title: str,
        evidence: dict[str, Any],
        underlying_issue_id: str | None = None,
        underlying_signal_id: str | None = None,
        client_id: str | None = None,
        brand_id: str | None = None,
        engagement_id: str | None = None,
        suppression_key: str | None = None,
    ) -> tuple[str | None, str | None]:
        """
        Create a new inbox item.

        Returns (item_id, error) - error if suppressed or constraint violation.

        Spec: 1.8 Suppression enforcement
        """
        # Check suppression first
        if suppression_key and check_suppression(self.conn, suppression_key):
            return None, "Item suppressed"

        # Validate evidence
        is_valid, error = validate_evidence(evidence)
        if not is_valid:
            return None, f"Invalid evidence: {error}"

        item_id = str(uuid4())
        now = now_iso()

        try:
            self.conn.execute(
                """
                INSERT INTO inbox_items_v29 (
                    id, type, state, severity, proposed_at, title, evidence,
                    evidence_version, underlying_issue_id, underlying_signal_id,
                    client_id, brand_id, engagement_id, created_at, updated_at
                ) VALUES (?, ?, 'proposed', ?, ?, ?, ?, 'v1', ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    item_id,
                    item_type,
                    severity,
                    now,
                    title,
                    json.dumps(evidence),
                    underlying_issue_id,
                    underlying_signal_id,
                    client_id,
                    brand_id,
                    engagement_id,
                    now,
                    now,
                ),
            )
            return item_id, None
        except sqlite3.IntegrityError as e:
            return None, str(e)

    def execute_action(
        self, item_id: str, action: str, payload: dict[str, Any], user_id: str
    ) -> ActionResult:
        """
        Execute an action on an inbox item.

        Spec: 7.10 POST /api/inbox/:id/action
        """
        # Get item
        item = self.get_item(item_id)
        if not item:
            return ActionResult(
                success=False, inbox_item_state="", error="Item not found"
            )

        # Validate action
        try:
            action_enum = InboxAction(action)
        except ValueError:
            return ActionResult(
                success=False,
                inbox_item_state=item["state"],
                error=f"Invalid action: {action}",
            )

        # Validate payload
        is_valid, error = validate_action_payload(action_enum, payload)
        if not is_valid:
            return ActionResult(
                success=False, inbox_item_state=item["state"], error=error
            )

        # Dispatch to handler
        handlers = {
            InboxAction.TAG: self._action_tag,
            InboxAction.ASSIGN: self._action_assign,
            InboxAction.SNOOZE: self._action_snooze,
            InboxAction.DISMISS: self._action_dismiss,
            InboxAction.LINK: self._action_link,
            InboxAction.SELECT: self._action_select,
            InboxAction.CREATE: self._action_create,
        }

        handler = handlers.get(action_enum)
        if not handler:
            return ActionResult(
                success=False,
                inbox_item_state=item["state"],
                error=f"Handler not implemented: {action}",
            )

        return handler(item, payload, user_id)

    def _action_tag(self, item: dict, payload: dict, user_id: str) -> ActionResult:
        """
        Tag & Watch action.

        Spec: 1.7 Tag & Watch Action
        """
        now = now_iso()
        note = payload.get("note")

        if item["type"] == InboxType.ISSUE.value:
            # Use existing issue
            issue_id = item["underlying_issue_id"]
        else:
            # Create new issue from signal
            issue_id = self._create_issue_from_signal(item, user_id, note)

        # Update issue: set tagged fields, transition to acknowledged
        self.conn.execute(
            """
            UPDATE issues_v29 SET
                tagged_by_user_id = ?,
                tagged_at = ?,
                state = 'acknowledged',
                updated_at = ?
            WHERE id = ?
        """,
            (user_id, now, now, issue_id),
        )

        # Log transition
        self._log_issue_transition(
            issue_id,
            item.get("issue_state", "surfaced"),
            "acknowledged",
            "user",
            user_id,
            note,
        )

        # Archive inbox item
        self.conn.execute(
            """
            UPDATE inbox_items_v29 SET
                state = 'linked_to_issue',
                resolved_at = ?,
                resolved_issue_id = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (now, issue_id, now, item["id"]),
        )

        return ActionResult(
            success=True,
            inbox_item_state="linked_to_issue",
            issue_id=issue_id,
            resolved_at=now,
        )

    def _action_assign(self, item: dict, payload: dict, user_id: str) -> ActionResult:
        """
        Assign action.

        Spec: 1.7.1 Assign Action
        """
        now = now_iso()
        assign_to = payload["assign_to"]
        note = payload.get("note")

        if item["type"] == InboxType.ISSUE.value:
            issue_id = item["underlying_issue_id"]
        else:
            issue_id = self._create_issue_from_signal(item, user_id, note)

        # Update issue: preserve tagged_* if set, set assigned_*, transition to addressing
        self.conn.execute(
            """
            UPDATE issues_v29 SET
                tagged_by_user_id = COALESCE(tagged_by_user_id, ?),
                tagged_at = COALESCE(tagged_at, ?),
                assigned_to = ?,
                assigned_at = ?,
                assigned_by = ?,
                state = 'addressing',
                updated_at = ?
            WHERE id = ?
        """,
            (user_id, now, assign_to, now, user_id, now, issue_id),
        )

        # Log transition
        self._log_issue_transition(
            issue_id,
            item.get("issue_state", "surfaced"),
            "addressing",
            "user",
            user_id,
            note,
        )

        # Archive inbox item
        self.conn.execute(
            """
            UPDATE inbox_items_v29 SET
                state = 'linked_to_issue',
                resolved_at = ?,
                resolved_issue_id = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (now, issue_id, now, item["id"]),
        )

        return ActionResult(
            success=True,
            inbox_item_state="linked_to_issue",
            issue_id=issue_id,
            resolved_at=now,
        )

    def _action_snooze(self, item: dict, payload: dict, user_id: str) -> ActionResult:
        """
        Snooze action.

        Spec: 1.4 Snooze hides for N days
        """
        from datetime import timedelta

        from .time_utils import to_iso

        now = now_iso()
        snooze_days = payload["snooze_days"]
        note = payload.get("note")

        # Calculate snooze_until
        snooze_until = to_iso(from_iso(now) + timedelta(days=snooze_days))

        self.conn.execute(
            """
            UPDATE inbox_items_v29 SET
                state = 'snoozed',
                snooze_until = ?,
                snoozed_by = ?,
                snoozed_at = ?,
                snooze_reason = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (snooze_until, user_id, now, note, now, item["id"]),
        )

        return ActionResult(
            success=True,
            inbox_item_state="snoozed",
            snooze_until=snooze_until,
        )

    def _action_dismiss(self, item: dict, payload: dict, user_id: str) -> ActionResult:
        """
        Dismiss action.

        Spec: 1.8 Dismiss Action
        """
        note = payload.get("note")

        if item["type"] == InboxType.ISSUE.value:
            result = self.suppression.dismiss_issue(
                inbox_item_id=item["id"],
                issue_id=item["underlying_issue_id"],
                issue_type=item.get("issue_type", "risk"),
                client_id=item["client_id"],
                engagement_id=item.get("engagement_id"),
                brand_id=item.get("brand_id"),
                evidence_keys=list(
                    json.loads(item["evidence"]).get("payload", {}).keys()
                ),
                user_id=user_id,
                reason=note,
            )
        else:
            result = self.suppression.dismiss_signal(
                inbox_item_id=item["id"],
                signal_id=item["underlying_signal_id"],
                item_type=item["type"],
                client_id=item["client_id"],
                engagement_id=item.get("engagement_id"),
                source=json.loads(item["evidence"]).get("source_system", "unknown"),
                rule_triggered=json.loads(item["evidence"]).get("rule_triggered"),
                user_id=user_id,
                reason=note,
            )

        return ActionResult(
            success=True,
            inbox_item_state="dismissed",
            suppression_key=result["suppression_key"],
            resolved_at=now_iso(),
        )

    def _action_link(self, item: dict, payload: dict, user_id: str) -> ActionResult:
        """
        Link to engagement action (for orphans).

        Spec: 1.6 Link to Engagement
        """
        now = now_iso()
        engagement_id = payload["link_engagement_id"]

        # Get engagement details
        cursor = self.conn.execute(
            """
            SELECT client_id, brand_id FROM engagements WHERE id = ?
        """,
            (engagement_id,),
        )
        eng = cursor.fetchone()

        if not eng:
            return ActionResult(
                success=False,
                inbox_item_state=item["state"],
                error="Engagement not found",
            )

        client_id, brand_id = eng[0], eng[1]

        # Update signal scoping
        self.conn.execute(
            """
            UPDATE signals SET
                engagement_id = ?,
                client_id = ?,
                brand_id = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (engagement_id, client_id, brand_id, now, item["underlying_signal_id"]),
        )

        # Update inbox item scoping
        self.conn.execute(
            """
            UPDATE inbox_items_v29 SET
                engagement_id = ?,
                client_id = ?,
                brand_id = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (engagement_id, client_id, brand_id, now, item["id"]),
        )

        return ActionResult(
            success=True,
            inbox_item_state="proposed",
            actions=[a.value for a in ACTIONS_AFTER_RESOLUTION],
            engagement_id=engagement_id,
            client_id=client_id,
            brand_id=brand_id,
        )

    def _action_select(self, item: dict, payload: dict, user_id: str) -> ActionResult:
        """
        Select primary action (for ambiguous).

        Spec: 1.6 Select Primary Flow
        """
        now = now_iso()
        candidate_id = payload["select_candidate_id"]

        # Get candidate engagement details
        cursor = self.conn.execute(
            """
            SELECT id, client_id, brand_id FROM engagements WHERE id = ?
        """,
            (candidate_id,),
        )
        eng = cursor.fetchone()

        if not eng:
            return ActionResult(
                success=False,
                inbox_item_state=item["state"],
                error="Candidate engagement not found",
            )

        engagement_id, client_id, brand_id = eng[0], eng[1], eng[2]

        # Update signal scoping
        self.conn.execute(
            """
            UPDATE signals SET
                engagement_id = ?,
                client_id = ?,
                brand_id = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (engagement_id, client_id, brand_id, now, item["underlying_signal_id"]),
        )

        # Update inbox item scoping
        self.conn.execute(
            """
            UPDATE inbox_items_v29 SET
                engagement_id = ?,
                client_id = ?,
                brand_id = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (engagement_id, client_id, brand_id, now, item["id"]),
        )

        return ActionResult(
            success=True,
            inbox_item_state="proposed",
            actions=[a.value for a in ACTIONS_AFTER_RESOLUTION],
            engagement_id=engagement_id,
            client_id=client_id,
            brand_id=brand_id,
        )

    def _action_create(self, item: dict, payload: dict, user_id: str) -> ActionResult:
        """
        Create engagement action.

        Spec: 7.10 Create Action (Two-Step Flow)
        """
        # This initiates the creation flow but doesn't complete it
        evidence = json.loads(item["evidence"])

        {
            "suggested_name": evidence.get("display_text", "New Engagement"),
            "client_id": item.get("client_id"),
            "brand_id": item.get("brand_id"),
        }

        return ActionResult(
            success=True,
            inbox_item_state="proposed",
            # In real implementation, would include next_step_url
        )

    def _create_issue_from_signal(
        self, item: dict, user_id: str, note: str | None
    ) -> str:
        """Create a new issue from signal-based inbox item."""
        issue_id = str(uuid4())
        now = now_iso()

        # Create aggregation_key from signal_id or item_id
        signal_id = item.get("underlying_signal_id") or item["id"]
        aggregation_key = f"inbox_{signal_id}"

        self.conn.execute(
            """
            INSERT INTO issues_v29 (
                id, type, state, severity, client_id, brand_id, engagement_id,
                title, evidence, evidence_version, aggregation_key, created_at, updated_at
            ) VALUES (?, ?, 'surfaced', ?, ?, ?, ?, ?, ?, 'v1', ?, ?, ?)
        """,
            (
                issue_id,
                "risk",
                item["severity"],
                item.get("client_id") or "unknown",
                item.get("brand_id"),
                item.get("engagement_id"),
                item["title"],
                item["evidence"],
                aggregation_key,
                now,
                now,
            ),
        )

        return issue_id

    def _log_issue_transition(
        self,
        issue_id: str,
        prev_state: str,
        new_state: str,
        reason: str,
        actor: str,
        note: str | None = None,
    ):
        """Log issue state transition."""
        self.conn.execute(
            """
            INSERT INTO issue_transitions (
                id, issue_id, previous_state, new_state, transition_reason,
                actor, actor_note, transitioned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                str(uuid4()),
                issue_id,
                prev_state,
                new_state,
                reason,
                actor,
                note,
                now_iso(),
            ),
        )

    def process_snooze_expiry(self) -> int:
        """
        Process expired inbox item snoozes.

        Spec: 1.4 Inbox Item Snooze Timer Execution
        v2.9: Sets resurfaced_at for is_unprocessed() calculation (§0.5)

        Returns count of items transitioned.
        """
        now = now_iso()

        # Find expired snoozes
        cursor = self.conn.execute(
            """
            SELECT id FROM inbox_items_v29
            WHERE state = 'snoozed' AND snooze_until <= ?
        """,
            (now,),
        )

        count = 0
        for row in cursor.fetchall():
            item_id = row[0]
            # v2.9: Set resurfaced_at so is_unprocessed() works correctly
            self.conn.execute(
                """
                UPDATE inbox_items_v29 SET
                    state = 'proposed',
                    resurfaced_at = ?,
                    snooze_until = NULL,
                    snoozed_by = NULL,
                    snoozed_at = NULL,
                    snooze_reason = NULL,
                    updated_at = ?
                WHERE id = ?
            """,
                (now, now, item_id),
            )
            count += 1

        return count

    def mark_read(self, item_id: str) -> bool:
        """
        Mark inbox item as read.

        Spec: 1.10 Setting read_at
        """
        now = now_iso()
        cursor = self.conn.execute(
            """
            UPDATE inbox_items_v29 SET read_at = ?, updated_at = ?
            WHERE id = ? AND read_at IS NULL
        """,
            (now, now, item_id),
        )
        return cursor.rowcount > 0

    def mark_all_read(self) -> int:
        """
        Mark all proposed items as read.

        Spec: 7.10 POST /api/inbox/mark_all_read
        """
        now = now_iso()
        cursor = self.conn.execute(
            """
            UPDATE inbox_items_v29 SET read_at = ?, updated_at = ?
            WHERE state = 'proposed' AND read_at IS NULL
        """,
            (now, now),
        )
        return cursor.rowcount
