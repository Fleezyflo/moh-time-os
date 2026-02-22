"""
Time OS V4 - Proposal Service

Proposals are the unit of executive attention.
They bundle related signals into actionable briefings with proof.
"""

import json
import logging
import os
import sqlite3
import uuid
from typing import Any

from .signal_service import get_signal_service

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "moh_time_os.db")


class ProposalService:
    """
    Service for managing proposals - bundled signals for executive review.

    Proposals are surfaced only when they have sufficient evidence (≥3 excerpts).
    They can be tagged to create monitored Issues.
    """

    # Minimum evidence required to surface a proposal
    MIN_PROOF_EXCERPTS = 1  # Lowered from 3 - surface with any evidence
    MIN_SIGNALS = 2  # Never create single-signal proposals

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.signal_svc = get_signal_service()
        self._ensure_tables()

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)

    def _generate_id(self, prefix: str = "prop") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    def _ensure_tables(self):
        """Ensure proposal tables exist."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS proposals_v4 (
                    proposal_id TEXT PRIMARY KEY,
                    proposal_type TEXT NOT NULL,  -- risk, opportunity, request, decision_needed, anomaly, compliance
                    primary_ref_type TEXT NOT NULL,
                    primary_ref_id TEXT NOT NULL,
                    scope_refs TEXT NOT NULL,  -- JSON array of {type, id}
                    headline TEXT NOT NULL,
                    summary TEXT,
                    impact TEXT NOT NULL,  -- JSON: time/cash/reputation + deadlines
                    top_hypotheses TEXT NOT NULL,  -- JSON array
                    signal_ids TEXT NOT NULL,  -- JSON array
                    proof_excerpt_ids TEXT NOT NULL,  -- JSON array
                    missing_confirmations TEXT,  -- JSON array
                    score REAL NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    trend TEXT NOT NULL DEFAULT 'flat',  -- worsening, improving, flat
                    supersedes_proposal_id TEXT,
                    ui_exposure_level TEXT DEFAULT 'none',  -- none, briefable, surfaced
                    status TEXT NOT NULL DEFAULT 'open',  -- open, snoozed, dismissed, accepted
                    snoozed_until TEXT,
                    dismissed_reason TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_proposals_v4_status ON proposals_v4(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_proposals_v4_type ON proposals_v4(proposal_type)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_proposals_v4_score ON proposals_v4(score DESC)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_proposals_v4_primary ON proposals_v4(primary_ref_type, primary_ref_id)"
            )

            conn.commit()
        finally:
            conn.close()

    # ===========================================
    # Proposal Generation
    # ===========================================

    def generate_proposals_from_signals(self) -> dict[str, Any]:
        """
        Generate proposals by aggregating signals at the project/client level.

        NEW STRATEGY (v4 redesign):
        1. Group signals by scope (project or client)
        2. Compute aggregate scores using new scoring module
        3. Build proposals with full hierarchy context
        4. Never create single-task proposals
        """
        from .proposal_aggregator import (
            build_signal_summary,
            get_affected_task_ids,
            get_scope_info,
            group_signals_by_scope,
        )
        from .proposal_scoring import compute_proposal_score, get_worst_signal_text

        stats = {"created": 0, "updated": 0, "skipped": 0}

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Step 1: Group all active signals by scope (project/client)
            grouped = group_signals_by_scope(self.db_path)

            for (scope_level, scope_id), signals in grouped.items():
                if len(signals) < self.MIN_SIGNALS:
                    stats["skipped"] += 1
                    continue

                # Step 2: Get scope details (hierarchy info)
                scope_info = get_scope_info(scope_level, scope_id, signals, self.db_path)

                # Step 3: Build hierarchy dict for scoring
                hierarchy = {
                    "client_tier": scope_info.get("client_tier"),
                    "engagement_type": scope_info.get("engagement_type", "project"),
                    "project_value": scope_info.get("project_value", 0),
                }

                # Step 4: Compute score using new scoring module
                score_result = compute_proposal_score(signals, hierarchy)
                score = score_result["score"]
                score_breakdown = score_result["breakdown"]

                # Step 5: Build signal summary
                signal_summary = build_signal_summary(signals)

                # Step 6: Get affected task IDs
                affected_task_ids = get_affected_task_ids(signals)

                # Step 7: Collect signal IDs and evidence
                all_signal_ids = [s.get("signal_id") for s in signals if s.get("signal_id")]
                all_excerpts = []
                for sig in signals:
                    excerpts = sig.get("excerpt_ids", [])
                    if excerpts:
                        all_excerpts.extend(excerpts)
                all_excerpts = list(set(all_excerpts))

                # Step 8: Generate headline
                scope_name = scope_info.get("scope_name", scope_id[:20])
                total_issues = signal_summary["total"]
                headline = f"{scope_name}: {total_issues} issue{'s' if total_issues != 1 else ''} requiring attention"

                # Determine proposal type from dominant signal category
                categories = signal_summary["by_category"]
                if (
                    categories["overdue"] > 0
                    or categories["approaching"] > 0
                    or categories["financial"] > 0
                    or categories["health"] > 0
                ):
                    proposal_type = "risk"
                elif categories["process"] > 0:
                    proposal_type = "compliance"
                else:
                    proposal_type = "anomaly"

                # Step 9: Check for existing proposal
                cursor.execute(
                    """
                    SELECT proposal_id, occurrence_count, score
                    FROM proposals_v4
                    WHERE scope_level = ? AND primary_ref_id = ? AND status = 'open'
                """,
                    (scope_level, scope_id),
                )

                existing = cursor.fetchone()

                # Get worst signal text
                worst_signal_text = get_worst_signal_text(signals)

                # Build impact JSON
                impact = {
                    "severity": "critical" if score > 100 else "high" if score > 50 else "medium",
                    "signal_count": len(signals),
                    "entity_type": scope_level,
                    "worst_signal": worst_signal_text,
                }

                if existing:
                    # Update existing proposal
                    old_id, old_count, old_score = existing
                    trend = (
                        "worsening"
                        if score > old_score
                        else "improving"
                        if score < old_score
                        else "flat"
                    )

                    cursor.execute(
                        """
                        UPDATE proposals_v4
                        SET signal_ids = ?, proof_excerpt_ids = ?, score = ?,
                            occurrence_count = ?, trend = ?, last_seen_at = datetime('now'),
                            updated_at = datetime('now'), headline = ?,
                            ui_exposure_level = 'surfaced', impact = ?,
                            scope_level = ?, scope_name = ?,
                            client_id = ?, client_name = ?, client_tier = ?,
                            brand_id = ?, brand_name = ?, engagement_type = ?,
                            signal_summary_json = ?, score_breakdown_json = ?,
                            affected_task_ids_json = ?
                        WHERE proposal_id = ?
                    """,
                        (
                            json.dumps(all_signal_ids),
                            json.dumps(all_excerpts),
                            score,
                            old_count + 1,
                            trend,
                            headline,
                            json.dumps(impact),
                            scope_level,
                            scope_info.get("scope_name"),
                            scope_info.get("client_id"),
                            scope_info.get("client_name"),
                            scope_info.get("client_tier"),
                            scope_info.get("brand_id"),
                            scope_info.get("brand_name"),
                            scope_info.get("engagement_type"),
                            json.dumps(signal_summary),
                            json.dumps(score_breakdown),
                            json.dumps(affected_task_ids),
                            old_id,
                        ),
                    )
                    stats["updated"] += 1
                else:
                    # Create new proposal with unique ID based on scope
                    import hashlib

                    scope_hash = hashlib.sha256(f"{scope_level}:{scope_id}".encode()).hexdigest()[
                        :16
                    ]
                    proposal_id = f"prop_{scope_hash}"

                    # Build hypotheses from top signals
                    hypotheses = [
                        {
                            "signal_type": sig.get("signal_type"),
                            "summary": self._signal_to_hypothesis(sig),
                        }
                        for sig in signals[:5]
                    ]

                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO proposals_v4
                        (proposal_id, proposal_type, primary_ref_type, primary_ref_id,
                         scope_refs, headline, impact, top_hypotheses, signal_ids,
                         proof_excerpt_ids, score, first_seen_at, last_seen_at,
                         ui_exposure_level, status, created_at, updated_at,
                         scope_level, scope_name, client_id, client_name, client_tier,
                         brand_id, brand_name, engagement_type,
                         signal_summary_json, score_breakdown_json, affected_task_ids_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'),
                                datetime('now'), 'surfaced', 'open', datetime('now'), datetime('now'),
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            proposal_id,
                            proposal_type,
                            scope_level,
                            scope_id,
                            json.dumps([{"type": scope_level, "id": scope_id}]),
                            headline,
                            json.dumps(impact),
                            json.dumps(hypotheses),
                            json.dumps(all_signal_ids),
                            json.dumps(all_excerpts),
                            score,
                            scope_level,
                            scope_info.get("scope_name"),
                            scope_info.get("client_id"),
                            scope_info.get("client_name"),
                            scope_info.get("client_tier"),
                            scope_info.get("brand_id"),
                            scope_info.get("brand_name"),
                            scope_info.get("engagement_type"),
                            json.dumps(signal_summary),
                            json.dumps(score_breakdown),
                            json.dumps(affected_task_ids),
                        ),
                    )
                    stats["created"] += 1

            conn.commit()
            return stats

        finally:
            conn.close()

    def _generate_headline(
        self, entity_type: str, entity_id: str, category: str, signals: list
    ) -> str:
        """Generate a headline for a proposal."""
        # Get entity name
        conn = self._get_conn()
        cursor = conn.cursor()

        entity_name = entity_id
        try:
            if entity_type == "client":
                cursor.execute("SELECT name FROM clients WHERE id = ?", (entity_id,))
            elif entity_type == "project":
                cursor.execute("SELECT name FROM projects WHERE id = ?", (entity_id,))
            elif entity_type == "task":
                # Try by id first, then by source_id (handles different ID formats)
                cursor.execute(
                    "SELECT title FROM tasks WHERE id = ? OR source_id = ?",
                    (entity_id, entity_id),
                )
            elif entity_type == "person" or entity_type == "team_member":
                cursor.execute("SELECT name FROM people WHERE id = ?", (entity_id,))

            row = cursor.fetchone()
            if row and row[0]:
                entity_name = row[0][:80]  # Truncate long names
        finally:
            conn.close()

        # Build headline based on category
        signal_types = [s["signal_type"] for s in signals]

        if "deadline_overdue" in signal_types:
            return f"⚠️ {entity_name}: Overdue deadlines require attention"
        if "deadline_approaching" in signal_types:
            return f"📅 {entity_name}: Deadlines approaching"
        if "client_health_declining" in signal_types:
            return f"🔻 {entity_name}: Relationship health declining"
        if "ar_aging_risk" in signal_types:
            return f"💰 {entity_name}: AR aging concerns"
        if "communication_gap" in signal_types:
            return f"📭 {entity_name}: Communication gap detected"
        if "commitment" in category:
            return f"🤝 {entity_name}: Commitment tracking required"
        if category == "protocol":
            return f"⚡ {entity_name}: Process violations detected"
        return f"📋 {entity_name}: {len(signals)} signal(s) require review"

    def _signal_to_hypothesis(self, sig: dict) -> str:
        """Convert a signal to a hypothesis statement."""
        value = sig.get("value", {})
        # Handle JSON string values
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                value = {}
        signal_type = sig.get("signal_type", "")

        if signal_type == "deadline_overdue":
            return f"Task '{value.get('title', 'Unknown')}' is {value.get('days_overdue', '?')} days overdue"
        if signal_type == "deadline_approaching":
            return (
                f"Task '{value.get('title', 'Unknown')}' due in {value.get('days_until', '?')} days"
            )
        if signal_type == "ar_aging_risk":
            return f"${value.get('ar_overdue', 0):,.0f} overdue in {value.get('aging_bucket', 'unknown')} bucket"
        if signal_type == "communication_gap":
            return f"No contact in {value.get('days_since_contact', '?')} days"
        if signal_type == "client_health_declining":
            return f"Health: {value.get('current_health', '?')}, Trend: {value.get('trend', '?')}"
        return f"{signal_type}: {str(value)[:100]}"

    def _compute_score(self, signals: list, max_severity: str, total_weight: float) -> float:
        """Compute proposal priority score."""
        severity_scores = {"low": 1, "medium": 2, "high": 4, "critical": 8}
        base = severity_scores.get(max_severity, 1)

        # Factor in signal count and weights
        signal_factor = min(len(signals) * 0.5, 3)  # Cap at 3x
        weight_factor = min(total_weight / len(signals), 2)  # Cap at 2x

        return base * signal_factor * weight_factor

    # ===========================================
    # Proposal Retrieval
    # ===========================================

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        """Get a proposal by ID with full hierarchy context."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT proposal_id, proposal_type, primary_ref_type, primary_ref_id,
                       scope_refs, headline, summary, impact, top_hypotheses,
                       signal_ids, proof_excerpt_ids, score, first_seen_at,
                       last_seen_at, occurrence_count, trend, status, ui_exposure_level,
                       scope_level, scope_name, client_id, client_name, client_tier,
                       brand_id, brand_name, engagement_type,
                       signal_summary_json, score_breakdown_json, affected_task_ids_json
                FROM proposals_v4 WHERE proposal_id = ?
            """,
                (proposal_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            # Safely parse JSON fields
            def safe_json(val):
                if val is None:
                    return {}
                if isinstance(val, str):
                    try:
                        return json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        return {}
                return val

            return {
                "proposal_id": row[0],
                "proposal_type": row[1],
                "primary_ref_type": row[2],
                "primary_ref_id": row[3],
                "scope_refs": safe_json(row[4]),
                "headline": row[5],
                "summary": row[6],
                "impact": safe_json(row[7]),
                "top_hypotheses": safe_json(row[8]),
                "signal_ids": safe_json(row[9]) if row[9] else [],
                "proof_excerpt_ids": safe_json(row[10]) if row[10] else [],
                "score": row[11],
                "first_seen_at": row[12],
                "last_seen_at": row[13],
                "occurrence_count": row[14],
                "trend": row[15],
                "status": row[16],
                "ui_exposure_level": row[17],
                # New hierarchy fields
                "scope_level": row[18],
                "scope_name": row[19],
                "client_id": row[20],
                "client_name": row[21],
                "client_tier": row[22],
                "brand_id": row[23],
                "brand_name": row[24],
                "engagement_type": row[25],
                "signal_summary_json": row[26],
                "score_breakdown_json": row[27],
                "affected_task_ids_json": row[28],
            }
        finally:
            conn.close()

    def get_surfaceable_proposals(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get proposals that meet surfacing criteria with full hierarchy."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT proposal_id, proposal_type, primary_ref_type, primary_ref_id,
                       headline, impact, score, occurrence_count, trend, status,
                       ui_exposure_level, first_seen_at, last_seen_at,
                       scope_level, scope_name, client_id, client_name, client_tier,
                       brand_id, brand_name, engagement_type,
                       signal_summary_json, score_breakdown_json, affected_task_ids_json
                FROM proposals_v4
                WHERE status = 'open'
                AND ui_exposure_level IN ('briefable', 'surfaced')
                ORDER BY score DESC, last_seen_at DESC
                LIMIT ?
            """,
                (limit,),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "proposal_id": row[0],
                        "proposal_type": row[1],
                        "primary_ref_type": row[2],
                        "primary_ref_id": row[3],
                        "headline": row[4],
                        "impact": row[5],
                        "score": row[6],
                        "occurrence_count": row[7],
                        "trend": row[8],
                        "status": row[9],
                        "ui_exposure_level": row[10],
                        "first_seen_at": row[11],
                        "last_seen_at": row[12],
                        "scope_level": row[13],
                        "scope_name": row[14],
                        "client_id": row[15],
                        "client_name": row[16],
                        "client_tier": row[17],
                        "brand_id": row[18],
                        "brand_name": row[19],
                        "engagement_type": row[20],
                        "signal_summary_json": row[21],
                        "score_breakdown_json": row[22],
                        "affected_task_ids_json": row[23],
                    }
                )
            return results
        finally:
            conn.close()

    def get_all_open_proposals(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get all open proposals with full hierarchy context."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT proposal_id, proposal_type, primary_ref_type, primary_ref_id,
                       headline, impact, score, occurrence_count, trend, status,
                       ui_exposure_level, first_seen_at, last_seen_at,
                       scope_level, scope_name, client_id, client_name, client_tier,
                       brand_id, brand_name, engagement_type,
                       signal_summary_json, score_breakdown_json, affected_task_ids_json
                FROM proposals_v4
                WHERE status = 'open'
                ORDER BY score DESC
                LIMIT ?
            """,
                (limit,),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "proposal_id": row[0],
                        "proposal_type": row[1],
                        "primary_ref_type": row[2],
                        "primary_ref_id": row[3],
                        "headline": row[4],
                        "impact": row[5],
                        "score": row[6],
                        "occurrence_count": row[7],
                        "trend": row[8],
                        "status": row[9],
                        "ui_exposure_level": row[10],
                        "first_seen_at": row[11],
                        "last_seen_at": row[12],
                        "scope_level": row[13],
                        "scope_name": row[14],
                        "client_id": row[15],
                        "client_name": row[16],
                        "client_tier": row[17],
                        "brand_id": row[18],
                        "brand_name": row[19],
                        "engagement_type": row[20],
                        "signal_summary_json": row[21],
                        "score_breakdown_json": row[22],
                        "affected_task_ids_json": row[23],
                    }
                )
            return results
        finally:
            conn.close()

    # ===========================================
    # Proposal Actions
    # ===========================================

    def snooze_proposal(self, proposal_id: str, until: str) -> dict[str, Any]:
        """Snooze a proposal until a specified time."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE proposals_v4
                SET status = 'snoozed', snoozed_until = ?, updated_at = datetime('now')
                WHERE proposal_id = ? AND status = 'open'
            """,
                (until, proposal_id),
            )

            if cursor.rowcount == 0:
                return {"status": "error", "error": "Proposal not found or not open"}

            conn.commit()
            return {"status": "snoozed", "proposal_id": proposal_id, "until": until}
        finally:
            conn.close()

    def dismiss_proposal(self, proposal_id: str, reason: str) -> dict[str, Any]:
        """Dismiss a proposal."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE proposals_v4
                SET status = 'dismissed', dismissed_reason = ?, updated_at = datetime('now')
                WHERE proposal_id = ? AND status = 'open'
            """,
                (reason, proposal_id),
            )

            if cursor.rowcount == 0:
                return {"status": "error", "error": "Proposal not found or not open"}

            conn.commit()
            return {"status": "dismissed", "proposal_id": proposal_id}
        finally:
            conn.close()

    def accept_proposal(self, proposal_id: str) -> dict[str, Any]:
        """Accept a proposal (marks it for Issue creation)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE proposals_v4
                SET status = 'accepted', updated_at = datetime('now')
                WHERE proposal_id = ? AND status = 'open'
            """,
                (proposal_id,),
            )

            if cursor.rowcount == 0:
                return {"status": "error", "error": "Proposal not found or not open"}

            conn.commit()
            return {"status": "accepted", "proposal_id": proposal_id}
        finally:
            conn.close()

    # ===========================================
    # Statistics
    # ===========================================

    def get_stats(self) -> dict[str, Any]:
        """Get proposal statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            stats = {}

            cursor.execute("SELECT status, COUNT(*) FROM proposals_v4 GROUP BY status")
            stats["by_status"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("""
                SELECT proposal_type, COUNT(*) FROM proposals_v4
                WHERE status = 'open'
                GROUP BY proposal_type
            """)
            stats["open_by_type"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("""
                SELECT ui_exposure_level, COUNT(*) FROM proposals_v4
                WHERE status = 'open'
                GROUP BY ui_exposure_level
            """)
            stats["open_by_exposure"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("""
                SELECT AVG(score), MAX(score), MIN(score) FROM proposals_v4
                WHERE status = 'open'
            """)
            row = cursor.fetchone()
            stats["score_stats"] = {"avg": row[0], "max": row[1], "min": row[2]}

            return stats
        finally:
            conn.close()


# Singleton
_proposal_service = None


def get_proposal_service() -> ProposalService:
    global _proposal_service
    if _proposal_service is None:
        _proposal_service = ProposalService()
    return _proposal_service
