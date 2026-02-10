"""
Suppression Module — Spec Section 1.8

Implements suppression key computation and rule management.
Suppression prevents re-proposal of dismissed items.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from .time_utils import now_iso, to_iso

# Suppression expiry defaults (spec 1.8)
SUPPRESSION_EXPIRY_DAYS = {
    "issue": 90,
    "flagged_signal": 30,
    "orphan": 180,
    "ambiguous": 30,
}


def compute_suppression_key(item_type: str, data: dict[str, Any]) -> str:
    """
    Compute deterministic suppression key.

    Spec: 1.8 Suppression Key Algorithm

    Algorithm: SHA-256
    Input: JSON canonical form, UTF-8, sorted keys

    Args:
        item_type: 'issue' | 'flagged_signal' | 'orphan' | 'ambiguous'
        data: Key data for suppression

    Returns:
        Suppression key string: "sk_" + 32-char hex
    """
    payload = {
        "v": "v1",  # Key version for future-proofing
        "t": item_type,
        **data,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    hash_hex = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"sk_{hash_hex}"


def suppression_key_for_issue(
    issue_type: str,
    client_id: str,
    engagement_id: str | None = None,
    brand_id: str | None = None,
    root_cause_fingerprint: str | None = None,
) -> str:
    """
    Compute suppression key for an issue.

    Spec: 1.8 Suppression Key Formula - Issue

    If engagement_id is null:
    - Use brand_id if present
    - Else use root_cause_fingerprint
    """
    data = {
        "issue_type": issue_type,
        "client_id": client_id,
    }

    if engagement_id:
        data["engagement_id"] = engagement_id
    elif brand_id:
        data["brand_id"] = brand_id
    elif root_cause_fingerprint:
        data["root_cause_fingerprint"] = root_cause_fingerprint

    return compute_suppression_key("issue", data)


def suppression_key_for_flagged_signal(
    client_id: str, engagement_id: str | None, source: str, rule_triggered: str
) -> str:
    """
    Compute suppression key for a flagged signal.

    Spec: 1.8 Suppression Key Formula - Flagged Signal

    Note: Does NOT include source_id (scope-based, not instance-based)
    """
    data = {
        "client_id": client_id,
        "source": source,
        "rule_triggered": rule_triggered,
    }
    if engagement_id:
        data["engagement_id"] = engagement_id

    return compute_suppression_key("flagged_signal", data)


def suppression_key_for_orphan(identifier_type: str, identifier_value: str) -> str:
    """
    Compute suppression key for an orphan signal.

    Spec: 1.8 Suppression Key Formula - Orphan
    """
    return compute_suppression_key(
        "orphan",
        {
            "identifier_type": identifier_type,
            "identifier_value": identifier_value,
        },
    )


def suppression_key_for_ambiguous(signal_id: str) -> str:
    """
    Compute suppression key for an ambiguous signal (before select).

    Spec: 1.8 Suppression Key Formula - Ambiguous
    """
    return compute_suppression_key(
        "ambiguous",
        {
            "signal_id": signal_id,
        },
    )


def compute_root_cause_fingerprint(issue_type: str, evidence_keys: list) -> str:
    """
    Compute root cause fingerprint for issues without engagement_id.

    Spec: 1.8 Null Engagement Fallback

    fingerprint = sha256(issue_type + sorted(evidence.keys()))
    """
    sorted_keys = sorted(evidence_keys)
    data = f"{issue_type}:{','.join(sorted_keys)}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def get_expiry_date(item_type: str) -> str:
    """
    Get expiry timestamp for suppression rule.

    Spec: 1.8 Suppression Expiry Defaults
    """
    days = SUPPRESSION_EXPIRY_DAYS.get(item_type, 30)
    expiry = datetime.utcnow() + timedelta(days=days)
    return to_iso(expiry)


def check_suppression(conn: sqlite3.Connection, suppression_key: str) -> bool:
    """
    Check if a suppression rule exists and is not expired.

    Spec: 1.8 Suppression Source of Truth

    Args:
        conn: Database connection
        suppression_key: Key to check

    Returns:
        True if suppressed (should not create inbox item)
    """
    cursor = conn.execute(
        """
        SELECT 1 FROM inbox_suppression_rules_v29
        WHERE suppression_key = ?
          AND (expires_at IS NULL OR expires_at > ?)
    """,
        (suppression_key, now_iso()),
    )

    return cursor.fetchone() is not None


def insert_suppression_rule(
    conn: sqlite3.Connection,
    suppression_key: str,
    item_type: str,
    created_by: str,
    reason: str | None = None,
) -> str:
    """
    Insert a suppression rule.

    Spec: 1.8 Store in inbox_suppression_rules

    Args:
        conn: Database connection
        suppression_key: Computed key
        item_type: 'issue' | 'flagged_signal' | 'orphan' | 'ambiguous'
        created_by: User ID who dismissed
        reason: Optional dismiss reason

    Returns:
        ID of inserted rule
    """
    # Check if rule already exists (idempotency)
    cursor = conn.execute(
        """
        SELECT id FROM inbox_suppression_rules_v29 WHERE suppression_key = ?
    """,
        (suppression_key,),
    )
    existing = cursor.fetchone()
    if existing:
        # Rule already exists - return existing ID (idempotent)
        return existing[0]

    rule_id = str(uuid4())
    expires_at = get_expiry_date(item_type)
    created_at = now_iso()

    # Use INSERT OR IGNORE as additional safety
    conn.execute(
        """
        INSERT OR IGNORE INTO inbox_suppression_rules_v29
        (id, suppression_key, item_type, created_by, created_at, expires_at, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            rule_id,
            suppression_key,
            item_type,
            created_by,
            created_at,
            expires_at,
            reason,
        ),
    )

    return rule_id


def delete_suppression_rule(conn: sqlite3.Connection, suppression_key: str) -> bool:
    """
    Delete a suppression rule (for unsuppress).

    Spec: 1.8 Reversing Suppression

    Returns:
        True if a rule was deleted
    """
    cursor = conn.execute(
        """
        DELETE FROM inbox_suppression_rules_v29 WHERE suppression_key = ?
    """,
        (suppression_key,),
    )

    return cursor.rowcount > 0


def cleanup_expired_rules(conn: sqlite3.Connection) -> int:
    """
    Delete expired suppression rules.

    Spec: 1.8 Suppression Expiry Enforcement (cleanup job)

    Returns:
        Number of rules deleted
    """
    cursor = conn.execute(
        """
        DELETE FROM inbox_suppression_rules_v29 WHERE expires_at < ?
    """,
        (now_iso(),),
    )

    return cursor.rowcount


class SuppressionManager:
    """
    Manager class for suppression operations.

    Ensures all dismiss operations are atomic per spec 1.8.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def dismiss_issue(
        self,
        inbox_item_id: str,
        issue_id: str,
        issue_type: str,
        client_id: str,
        engagement_id: str | None,
        brand_id: str | None,
        evidence_keys: list,
        user_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Dismiss an issue-type inbox item atomically.

        Spec: 1.8 Transaction Boundary (Dismiss Action)

        All operations in single transaction:
        1. Update inbox_items → dismissed
        2. Update issues.suppressed = true
        3. Insert inbox_suppression_rules
        """
        now = now_iso()

        # Compute suppression key
        root_cause = compute_root_cause_fingerprint(issue_type, evidence_keys)
        sk = suppression_key_for_issue(
            issue_type, client_id, engagement_id, brand_id, root_cause
        )

        # 1. Update inbox_items_v29
        self.conn.execute(
            """
            UPDATE inbox_items_v29 SET
                state = 'dismissed',
                resolved_at = ?,
                updated_at = ?,
                dismissed_by = ?,
                dismissed_at = ?,
                dismiss_reason = ?,
                suppression_key = ?
            WHERE id = ?
        """,
            (now, now, user_id, now, reason, sk, inbox_item_id),
        )

        # 2. Update issues_v29
        self.conn.execute(
            """
            UPDATE issues_v29 SET
                suppressed = 1,
                suppressed_at = ?,
                suppressed_by = ?,
                updated_at = ?
            WHERE id = ?
        """,
            (now, user_id, now, issue_id),
        )

        # 3. Insert suppression rule
        rule_id = insert_suppression_rule(self.conn, sk, "issue", user_id, reason)

        return {
            "suppression_key": sk,
            "rule_id": rule_id,
        }

    def dismiss_signal(
        self,
        inbox_item_id: str,
        signal_id: str,
        item_type: str,
        client_id: str,
        engagement_id: str | None,
        source: str,
        rule_triggered: str | None,
        user_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Dismiss a signal-type inbox item atomically.

        Handles: flagged_signal, orphan, ambiguous
        """
        now = now_iso()

        # Compute suppression key based on type
        if item_type == "flagged_signal":
            sk = suppression_key_for_flagged_signal(
                client_id, engagement_id, source, rule_triggered or ""
            )
        elif item_type == "orphan":
            # For orphan, use signal_id directly as identifier (signals table uses signal_id not id)
            sk = suppression_key_for_orphan(source or "unknown", signal_id)
        else:  # ambiguous
            sk = suppression_key_for_ambiguous(signal_id)

        # 1. Update inbox_items_v29
        self.conn.execute(
            """
            UPDATE inbox_items_v29 SET
                state = 'dismissed',
                resolved_at = ?,
                updated_at = ?,
                dismissed_by = ?,
                dismissed_at = ?,
                dismiss_reason = ?,
                suppression_key = ?
            WHERE id = ?
        """,
            (now, now, user_id, now, reason, sk, inbox_item_id),
        )

        # 2. Insert suppression rule (signals table has no dismissed column)
        rule_id = insert_suppression_rule(self.conn, sk, item_type, user_id, reason)

        return {
            "suppression_key": sk,
            "rule_id": rule_id,
        }

    def unsuppress_issue(self, issue_id: str) -> bool:
        """
        Unsuppress an issue.

        Spec: 7.6 POST /api/issues/:id/unsuppress

        Idempotent: returns success even if already unsuppressed.
        """
        now = now_iso()

        # Get issue details for suppression key
        cursor = self.conn.execute(
            """
            SELECT type, client_id, engagement_id, brand_id, evidence
            FROM issues_v29 WHERE id = ?
        """,
            (issue_id,),
        )
        row = cursor.fetchone()

        if not row:
            return False

        issue_type, client_id, engagement_id, brand_id, evidence_json = row
        evidence = json.loads(evidence_json) if evidence_json else {}
        evidence_keys = list(evidence.get("payload", {}).keys())

        root_cause = compute_root_cause_fingerprint(issue_type, evidence_keys)
        sk = suppression_key_for_issue(
            issue_type, client_id, engagement_id, brand_id, root_cause
        )

        # 1. Update issues_v29.suppressed = false
        self.conn.execute(
            """
            UPDATE issues_v29 SET
                suppressed = 0,
                updated_at = ?
            WHERE id = ?
        """,
            (now, issue_id),
        )

        # 2. Delete suppression rule
        delete_suppression_rule(self.conn, sk)

        return True
