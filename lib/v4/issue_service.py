"""
Time OS V4 - Issue Service

Issues are tagged monitored loops created from accepted proposals.
They have watchers, handoffs, commitments, and deterministic resolution criteria.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any

from .proposal_service import get_proposal_service
from .signal_service import get_signal_service

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "moh_time_os.db")


class IssueService:
    """
    Service for managing Issues - monitored work loops.

    Issues are created when an executive tags a Proposal.
    They track:
    - Resolution criteria (what needs to happen to close)
    - Watchers (triggers that keep the loop alive)
    - Handoffs (delegated work items)
    - Commitments (promises made related to the issue)
    - Decision log (audit trail)
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.proposal_svc = get_proposal_service()
        self.signal_svc = get_signal_service()
        self._ensure_tables()

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)

    def _generate_id(self, prefix: str = "iss") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    def _ensure_tables(self):
        """Ensure issue tables exist."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Issues
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS issues (
                    issue_id TEXT PRIMARY KEY,
                    source_proposal_id TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'open',  -- open, monitoring, awaiting, blocked, mitigated, resolved, handed_over
                    primary_ref_type TEXT NOT NULL,
                    primary_ref_id TEXT NOT NULL,
                    scope_refs TEXT NOT NULL,  -- JSON array
                    headline TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    resolution_criteria TEXT NOT NULL,  -- JSON structured
                    opened_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_activity_at TEXT NOT NULL DEFAULT (datetime('now')),
                    closed_at TEXT,
                    closed_reason TEXT,
                    visibility TEXT NOT NULL DEFAULT 'tagged_only'
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_state ON issues(state)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_priority ON issues(priority)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_issues_primary ON issues(primary_ref_type, primary_ref_id)"
            )

            # Issue-Signal links
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS issue_signals (
                    issue_id TEXT NOT NULL,
                    signal_id TEXT NOT NULL,
                    attached_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (issue_id, signal_id)
                )
            """)

            # Issue-Evidence links
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS issue_evidence (
                    issue_id TEXT NOT NULL,
                    excerpt_id TEXT NOT NULL,
                    attached_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (issue_id, excerpt_id)
                )
            """)

            # Decision log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decision_log (
                    decision_id TEXT PRIMARY KEY,
                    issue_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    decision_type TEXT NOT NULL,  -- tagged, snoozed, dismissed, changed_scope, changed_priority, resolved, handed_over, note
                    note TEXT,
                    evidence_excerpt_ids TEXT,  -- JSON array
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_decision_log_issue ON decision_log(issue_id)"
            )

            # Watchers
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchers (
                    watcher_id TEXT PRIMARY KEY,
                    issue_id TEXT NOT NULL,
                    watch_type TEXT NOT NULL,  -- no_reply_by, no_status_change_by, blocker_age_exceeds, deadline_approach, meeting_imminent, invoice_overdue_change
                    params TEXT NOT NULL,  -- JSON
                    active INTEGER NOT NULL DEFAULT 1,
                    next_check_at TEXT NOT NULL,
                    last_checked_at TEXT,
                    triggered_at TEXT,
                    trigger_count INTEGER NOT NULL DEFAULT 0
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchers_issue ON watchers(issue_id)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_watchers_next ON watchers(next_check_at) WHERE active = 1"
            )

            # Handoffs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS handoffs (
                    handoff_id TEXT PRIMARY KEY,
                    issue_id TEXT NOT NULL,
                    from_person_id TEXT NOT NULL,
                    to_person_id TEXT NOT NULL,
                    what_is_expected TEXT NOT NULL,
                    due_at TEXT,
                    done_definition TEXT NOT NULL,  -- JSON structured
                    state TEXT NOT NULL DEFAULT 'proposed',  -- proposed, accepted, completed, rejected
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_handoffs_issue ON handoffs(issue_id)")

            # Commitments (if not already exists from M1)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commitments (
                    commitment_id TEXT PRIMARY KEY,
                    scope_ref_type TEXT NOT NULL,
                    scope_ref_id TEXT NOT NULL,
                    committed_by_type TEXT NOT NULL,
                    committed_by_id TEXT NOT NULL,
                    commitment_text TEXT NOT NULL,
                    due_at TEXT,
                    confidence REAL NOT NULL DEFAULT 0.8,
                    evidence_excerpt_ids TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'open',  -- open, met, missed, superseded
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_commitments_scope ON commitments(scope_ref_type, scope_ref_id)"
            )

            conn.commit()
        finally:
            conn.close()

    # ===========================================
    # Issue Creation (Tag Transaction)
    # ===========================================

    def tag_proposal(self, proposal_id: str, actor: str) -> dict[str, Any]:
        """
        Tag a proposal to create a monitored Issue.
        This is an atomic transaction that:
        1. Creates the issue from proposal
        2. Attaches signals
        3. Attaches evidence
        4. Creates watchers
        5. Logs the decision
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Get proposal
            proposal = self.proposal_svc.get_proposal(proposal_id)
            if not proposal:
                return {"status": "error", "error": "Proposal not found"}

            if proposal["status"] != "open":
                return {
                    "status": "error",
                    "error": f"Proposal is {proposal['status']}, not open",
                }

            # Create issue
            issue_id = self._generate_id("iss")

            # Map proposal type to issue type
            issue_type = proposal["proposal_type"]

            # Compute priority from score
            priority = int(proposal["score"])

            # Default resolution criteria based on type
            resolution_criteria = self._default_resolution_criteria(issue_type, proposal)

            cursor.execute(
                """
                INSERT INTO issues
                (issue_id, source_proposal_id, issue_type, state, primary_ref_type,
                 primary_ref_id, scope_refs, headline, priority, resolution_criteria,
                 opened_at, last_activity_at)
                VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
                (
                    issue_id,
                    proposal_id,
                    issue_type,
                    proposal["primary_ref_type"],
                    proposal["primary_ref_id"],
                    json.dumps(proposal["scope_refs"]),
                    proposal["headline"],
                    priority,
                    json.dumps(resolution_criteria),
                ),
            )

            # Attach signals (batch insert)
            signal_ids = proposal.get("signal_ids", [])
            for signal_id in signal_ids:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO issue_signals (issue_id, signal_id, attached_at)
                    VALUES (?, ?, datetime('now'))
                """,
                    (issue_id, signal_id),
                )

            # Mark signals as consumed (batch update - single transaction)
            if signal_ids:
                placeholders = ",".join("?" * len(signal_ids))
                cursor.execute(
                    f"""
                    UPDATE signals SET status = 'consumed', consumed_by_proposal_id = ?
                    WHERE signal_id IN ({placeholders}) AND status = 'active'
                """,
                    [proposal_id] + signal_ids,
                )

            # Attach evidence excerpts
            for excerpt_id in proposal.get("proof_excerpt_ids", []):
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO issue_evidence (issue_id, excerpt_id, attached_at)
                    VALUES (?, ?, datetime('now'))
                """,
                    (issue_id, excerpt_id),
                )

            # Create default watchers
            watchers = self._create_default_watchers(issue_id, issue_type, proposal)
            for watcher in watchers:
                cursor.execute(
                    """
                    INSERT INTO watchers
                    (watcher_id, issue_id, watch_type, params, next_check_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        watcher["watcher_id"],
                        issue_id,
                        watcher["watch_type"],
                        json.dumps(watcher["params"]),
                        watcher["next_check_at"],
                    ),
                )

            # Log decision
            decision_id = self._generate_id("dec")
            cursor.execute(
                """
                INSERT INTO decision_log
                (decision_id, issue_id, actor, decision_type, note, created_at)
                VALUES (?, ?, ?, 'tagged', 'Issue created from proposal', datetime('now'))
            """,
                (decision_id, issue_id, actor),
            )

            # Mark proposal as accepted (direct SQL to avoid new connection)
            cursor.execute(
                """
                UPDATE proposals_v4 SET status = 'accepted', updated_at = datetime('now')
                WHERE proposal_id = ?
            """,
                (proposal_id,),
            )

            conn.commit()

            return {
                "status": "created",
                "issue_id": issue_id,
                "watchers_created": len(watchers),
                "signals_attached": len(proposal.get("signal_ids", [])),
                "evidence_attached": len(proposal.get("proof_excerpt_ids", [])),
            }

        except Exception as e:
            conn.rollback()
            return {"status": "error", "error": str(e)}
        finally:
            conn.close()

    def _default_resolution_criteria(self, issue_type: str, proposal: dict) -> dict:
        """Generate default resolution criteria based on issue type."""
        criteria = {"type": issue_type, "conditions": []}

        if issue_type == "risk":
            criteria["conditions"] = [
                {
                    "type": "risk_mitigated",
                    "description": "Risk addressed or mitigated",
                },
                {
                    "type": "manual_resolution",
                    "description": "Manually marked as resolved",
                },
            ]
        elif issue_type == "request":
            criteria["conditions"] = [
                {"type": "request_fulfilled", "description": "Request completed"},
                {
                    "type": "request_declined",
                    "description": "Request declined with reason",
                },
            ]
        elif issue_type == "compliance":
            criteria["conditions"] = [
                {"type": "violation_fixed", "description": "Violation corrected"},
                {"type": "exception_approved", "description": "Exception approved"},
            ]
        else:
            criteria["conditions"] = [
                {
                    "type": "manual_resolution",
                    "description": "Manually marked as resolved",
                }
            ]

        return criteria

    def _create_default_watchers(
        self, issue_id: str, issue_type: str, proposal: dict
    ) -> list[dict]:
        """Create default watchers for an issue."""
        watchers = []
        now = datetime.now()

        # All issues get a staleness watcher
        watchers.append(
            {
                "watcher_id": self._generate_id("wtc"),
                "watch_type": "no_status_change_by",
                "params": {"days": 7},
                "next_check_at": (now + timedelta(days=7)).isoformat(),
            }
        )

        # Type-specific watchers
        if issue_type == "risk":
            # Check if risk is worsening
            watchers.append(
                {
                    "watcher_id": self._generate_id("wtc"),
                    "watch_type": "blocker_age_exceeds",
                    "params": {"days": 3},
                    "next_check_at": (now + timedelta(days=3)).isoformat(),
                }
            )

        return watchers

    # ===========================================
    # Issue Retrieval
    # ===========================================

    def get_issue(self, issue_id: str) -> dict[str, Any] | None:
        """Get an issue by ID with full details."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT issue_id, source_proposal_id, issue_type, state,
                       primary_ref_type, primary_ref_id, scope_refs, headline,
                       priority, resolution_criteria, opened_at, last_activity_at,
                       closed_at, closed_reason
                FROM issues WHERE issue_id = ?
            """,
                (issue_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            issue = {
                "issue_id": row[0],
                "source_proposal_id": row[1],
                "issue_type": row[2],
                "state": row[3],
                "primary_ref_type": row[4],
                "primary_ref_id": row[5],
                "scope_refs": json.loads(row[6]),
                "headline": row[7],
                "priority": row[8],
                "resolution_criteria": json.loads(row[9]),
                "opened_at": row[10],
                "last_activity_at": row[11],
                "closed_at": row[12],
                "closed_reason": row[13],
            }

            # Get attached signals
            cursor.execute(
                """
                SELECT signal_id FROM issue_signals WHERE issue_id = ?
            """,
                (issue_id,),
            )
            issue["signal_ids"] = [r[0] for r in cursor.fetchall()]

            # Get attached evidence
            cursor.execute(
                """
                SELECT excerpt_id FROM issue_evidence WHERE issue_id = ?
            """,
                (issue_id,),
            )
            issue["evidence_excerpt_ids"] = [r[0] for r in cursor.fetchall()]

            # Get watchers
            cursor.execute(
                """
                SELECT watcher_id, watch_type, params, active, next_check_at, trigger_count
                FROM watchers WHERE issue_id = ?
            """,
                (issue_id,),
            )
            issue["watchers"] = [
                {
                    "watcher_id": r[0],
                    "watch_type": r[1],
                    "params": json.loads(r[2]),
                    "active": bool(r[3]),
                    "next_check_at": r[4],
                    "trigger_count": r[5],
                }
                for r in cursor.fetchall()
            ]

            # Get decision log (last 10)
            cursor.execute(
                """
                SELECT decision_id, actor, decision_type, note, created_at
                FROM decision_log WHERE issue_id = ?
                ORDER BY created_at DESC LIMIT 10
            """,
                (issue_id,),
            )
            issue["decisions"] = [
                {
                    "decision_id": r[0],
                    "actor": r[1],
                    "decision_type": r[2],
                    "note": r[3],
                    "created_at": r[4],
                }
                for r in cursor.fetchall()
            ]

            return issue
        finally:
            conn.close()

    def get_open_issues(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get all open issues."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT issue_id, issue_type, state, primary_ref_type, primary_ref_id,
                       headline, priority, opened_at, last_activity_at
                FROM issues
                WHERE state NOT IN ('resolved', 'handed_over')
                ORDER BY priority DESC, last_activity_at DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [
                {
                    "issue_id": row[0],
                    "issue_type": row[1],
                    "state": row[2],
                    "primary_ref_type": row[3],
                    "primary_ref_id": row[4],
                    "headline": row[5],
                    "priority": row[6],
                    "opened_at": row[7],
                    "last_activity_at": row[8],
                }
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    # ===========================================
    # Issue Actions
    # ===========================================

    def update_state(
        self, issue_id: str, new_state: str, actor: str, note: str = None
    ) -> dict[str, Any]:
        """Update issue state."""
        valid_states = {
            "open",
            "monitoring",
            "awaiting",
            "blocked",
            "mitigated",
            "resolved",
            "handed_over",
        }
        if new_state not in valid_states:
            return {"status": "error", "error": f"Invalid state: {new_state}"}

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE issues
                SET state = ?, last_activity_at = datetime('now'),
                    closed_at = CASE WHEN ? IN ('resolved', 'handed_over') THEN datetime('now') ELSE closed_at END,
                    closed_reason = CASE WHEN ? IN ('resolved', 'handed_over') THEN ? ELSE closed_reason END
                WHERE issue_id = ?
            """,
                (new_state, new_state, new_state, note, issue_id),
            )

            if cursor.rowcount == 0:
                return {"status": "error", "error": "Issue not found"}

            # Log decision
            decision_id = self._generate_id("dec")
            cursor.execute(
                """
                INSERT INTO decision_log
                (decision_id, issue_id, actor, decision_type, note, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
                (decision_id, issue_id, actor, f"state_change_{new_state}", note),
            )

            conn.commit()
            return {"status": "updated", "issue_id": issue_id, "new_state": new_state}
        finally:
            conn.close()

    def resolve_issue(self, issue_id: str, actor: str, reason: str) -> dict[str, Any]:
        """Resolve an issue."""
        return self.update_state(issue_id, "resolved", actor, reason)

    def create_handoff(
        self,
        issue_id: str,
        from_person_id: str,
        to_person_id: str,
        what_is_expected: str,
        done_definition: dict,
        due_at: str = None,
    ) -> dict[str, Any]:
        """Create a handoff for an issue."""
        handoff_id = self._generate_id("hnd")

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO handoffs
                (handoff_id, issue_id, from_person_id, to_person_id,
                 what_is_expected, due_at, done_definition, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
                (
                    handoff_id,
                    issue_id,
                    from_person_id,
                    to_person_id,
                    what_is_expected,
                    due_at,
                    json.dumps(done_definition),
                ),
            )

            # Update issue state
            cursor.execute(
                """
                UPDATE issues SET state = 'awaiting', last_activity_at = datetime('now')
                WHERE issue_id = ?
            """,
                (issue_id,),
            )

            conn.commit()
            return {"status": "created", "handoff_id": handoff_id}
        finally:
            conn.close()

    # ===========================================
    # Watcher Evaluation
    # ===========================================

    def evaluate_watchers(self) -> dict[str, Any]:
        """Evaluate all due watchers and trigger actions."""
        conn = self._get_conn()
        cursor = conn.cursor()

        stats = {"evaluated": 0, "triggered": 0}

        try:
            now = datetime.now().isoformat()

            cursor.execute(
                """
                SELECT w.watcher_id, w.issue_id, w.watch_type, w.params,
                       i.state, i.last_activity_at
                FROM watchers w
                JOIN issues i ON w.issue_id = i.issue_id
                WHERE w.active = 1 AND w.next_check_at <= ?
                AND i.state NOT IN ('resolved', 'handed_over')
            """,
                (now,),
            )

            for row in cursor.fetchall():
                watcher_id, issue_id, watch_type, params_json, state, last_activity = row
                params = json.loads(params_json)

                stats["evaluated"] += 1
                triggered = False

                if watch_type == "no_status_change_by":
                    days = params.get("days", 7)
                    if last_activity:
                        last_dt = datetime.fromisoformat(last_activity[:19])
                        if (datetime.now() - last_dt).days >= days:
                            triggered = True

                elif watch_type == "blocker_age_exceeds":
                    days = params.get("days", 3)
                    if state == "blocked":
                        # Would check actual block duration
                        triggered = True

                if triggered:
                    stats["triggered"] += 1
                    cursor.execute(
                        """
                        UPDATE watchers
                        SET triggered_at = datetime('now'), trigger_count = trigger_count + 1,
                            last_checked_at = datetime('now'),
                            next_check_at = datetime('now', '+1 day')
                        WHERE watcher_id = ?
                    """,
                        (watcher_id,),
                    )
                else:
                    # Reschedule
                    cursor.execute(
                        """
                        UPDATE watchers
                        SET last_checked_at = datetime('now'),
                            next_check_at = datetime('now', '+1 day')
                        WHERE watcher_id = ?
                    """,
                        (watcher_id,),
                    )

            conn.commit()
            return stats
        finally:
            conn.close()

    # ===========================================
    # Statistics
    # ===========================================

    def get_stats(self) -> dict[str, Any]:
        """Get issue statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            stats = {}

            cursor.execute("SELECT state, COUNT(*) FROM issues GROUP BY state")
            stats["by_state"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("""
                SELECT issue_type, COUNT(*) FROM issues
                WHERE state NOT IN ('resolved', 'handed_over')
                GROUP BY issue_type
            """)
            stats["open_by_type"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) FROM watchers WHERE active = 1")
            stats["active_watchers"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM handoffs WHERE state = 'proposed'")
            stats["pending_handoffs"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM decision_log")
            stats["total_decisions"] = cursor.fetchone()[0]

            return stats
        finally:
            conn.close()


# Singleton
_issue_service = None


def get_issue_service() -> IssueService:
    global _issue_service
    if _issue_service is None:
        _issue_service = IssueService()
    return _issue_service
