"""
Time OS V4 - Commitment Detector

Detects commitment-related signals from communications:
- Explicit commitments made
- Commitments at risk of being missed
- Unacknowledged commitments
"""

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from ..artifact_service import decrypt_blob_payload
from .base import BaseDetector

DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "moh_time_os.db"
)


class CommitmentDetector(BaseDetector):
    """
    Detects commitment-related signals.

    Signal types produced:
    - commitment_made: New commitment detected
    - commitment_at_risk: Commitment may be missed
    - commitment_overdue: Commitment past due
    """

    detector_id = "commitment_detector"
    version = "1.0.0"
    description = "Detects commitments from communications and tracks their status"
    signal_types = ["commitment_made", "commitment_at_risk", "commitment_overdue"]

    # Commitment patterns - expanded for better detection
    COMMITMENT_PATTERNS = [
        # Direct commitments with dates
        r"(?:i|we)\s+will\s+(?:have|get|send|deliver|complete|finish|provide|share)\s+(.+?)(?:by|before|on)\s+(\w+)",
        r"(?:i|we)\s+(?:promise|commit|guarantee)\s+to\s+(.+?)(?:by|before|on)?\s*(\w+)?",
        r"you'?ll\s+(?:have|get|receive)\s+(.+?)(?:by|before|on)\s+(\w+)",
        r"expect(?:ing)?\s+(?:it|this|delivery|the)\s+(?:by|before|on)\s+(\w+)",
        # Softer commitments
        r"(?:i|we)\s+(?:can|should|plan\s+to)\s+(?:have|get|send|deliver)\s+(.+?)(?:by|before|on)\s+(\w+)",
        r"(?:i|we)'?(?:ll|will)\s+(?:follow\s+up|get\s+back|respond|reply)\s+(.+?)(?:by|before|on|within)\s+(\w+)",
        r"(?:i|we)\s+(?:aim|intend|plan)\s+to\s+(.+?)(?:by|before|on)\s+(\w+)",
        # Task-style commitments (common in Asana/project management)
        r"(?:need\s+to|must|should)\s+(.+?)(?:by|before|due)\s+(\w+)",
        r"deadline[:\s]+(.+?)(?:is|on)\s+(\w+)",
        r"due\s+(?:by|on|date)[:\s]*(\w+)",
        # Meeting/email commitments
        r"(?:let'?s|we\s+should)\s+(?:schedule|meet|discuss|review)\s+(.+?)(?:by|before|on)\s+(\w+)",
        r"(?:i|we)\s+(?:need|want)\s+(?:this|it|everything)\s+(?:ready|done|complete)\s+(?:by|before)\s+(\w+)",
        # Waiting for / follow up patterns
        r"waiting\s+(?:for|on)\s+(.+?)(?:from|by)\s+(\w+)",
        r"following\s+up\s+(?:on|with)\s+(.+)",
        r"awaiting\s+(.+?)(?:from|by)\s+(\w+)",
    ]

    # Date patterns to validate extracted dates
    DATE_PATTERNS = [
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\b(today|tomorrow|next\s+week|end\s+of\s+(?:day|week|month))\b",
        r"\b(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b",
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}\b",
    ]

    def get_parameters(self) -> dict[str, Any]:
        return {"patterns_count": len(self.COMMITMENT_PATTERNS)}

    def _extract_commitments_from_text(self, text: str) -> list[dict]:
        """Extract potential commitments from text."""
        commitments = []
        text_lower = text.lower()

        # Skip very short text
        if len(text_lower) < 10:
            return commitments

        for pattern in self.COMMITMENT_PATTERNS:
            try:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        what = match[0] if len(match) > 0 else ""
                        when = match[1] if len(match) > 1 else ""
                    else:
                        what = match
                        when = ""

                    # Clean up extracted text
                    what = what.strip(" .,;:")
                    when = when.strip(" .,;:") if when else None

                    # Skip if too short or too long (likely false positive)
                    if not what or len(what) < 3 or len(what) > 200:
                        continue

                    # Determine confidence based on pattern strength
                    confidence = 0.7
                    if when:
                        # Has a date reference - higher confidence
                        for date_pattern in self.DATE_PATTERNS:
                            if re.search(date_pattern, when, re.IGNORECASE):
                                confidence = 0.85
                                break

                    # Check for strong commitment language
                    if any(
                        word in text_lower
                        for word in ["promise", "commit", "guarantee", "definitely"]
                    ):
                        confidence = min(confidence + 0.1, 0.95)

                    commitments.append(
                        {
                            "what": what,
                            "when": when,
                            "confidence": confidence,
                            "pattern": pattern[:50],  # For debugging
                        }
                    )
            except re.error:
                continue

        # Deduplicate similar commitments
        seen = set()
        unique_commitments = []
        for c in commitments:
            key = c["what"][:30].lower()
            if key not in seen:
                seen.add(key)
                unique_commitments.append(c)

        return unique_commitments

    def detect(self, scope: dict) -> list[dict[str, Any]]:
        """Run commitment detection."""
        signals = []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check for commitments in recent artifacts (messages AND tasks with notes)
            since = scope.get("since", (datetime.now() - timedelta(days=7)).isoformat())

            cursor.execute(
                """
                SELECT a.artifact_id, a.source, a.occurred_at, a.payload_ref,
                       a.actor_person_id
                FROM artifacts a
                WHERE a.type IN ('message', 'task')
                AND a.occurred_at >= ?
                ORDER BY a.occurred_at DESC
                LIMIT 500
            """,
                (since,),
            )

            for row in cursor.fetchall():
                artifact_id, source, occurred_at, payload_ref, actor_id = row

                # Get payload
                if payload_ref.startswith("blob:"):
                    blob_ref = payload_ref.replace("blob:", "")
                    blob_id = (
                        blob_ref
                        if blob_ref.startswith("blob_")
                        else f"blob_{blob_ref[:16]}"
                    )
                    cursor.execute(
                        "SELECT payload FROM artifact_blobs WHERE blob_id = ?",
                        (blob_id,),
                    )
                    blob_row = cursor.fetchone()
                    if blob_row:
                        payload_data = decrypt_blob_payload(blob_row[0])
                        payload = json.loads(payload_data)
                    else:
                        continue
                else:
                    payload = json.loads(payload_ref)

                # Extract text to analyze
                text = (
                    payload.get("body", "")
                    or payload.get("snippet", "")
                    or payload.get("notes", "")
                )
                if not text:
                    continue

                # Look for commitments
                commitments = self._extract_commitments_from_text(text)

                for commitment in commitments:
                    # Get linked entities for context
                    cursor.execute(
                        """
                        SELECT to_entity_type, to_entity_id, confidence
                        FROM entity_links
                        WHERE from_artifact_id = ? AND status = 'confirmed'
                        ORDER BY confidence DESC
                        LIMIT 5
                    """,
                        (artifact_id,),
                    )

                    linked_entities = [
                        {"type": r[0], "id": r[1], "confidence": r[2]}
                        for r in cursor.fetchall()
                    ]

                    # Primary entity for signal
                    primary_entity = (
                        linked_entities[0]
                        if linked_entities
                        else {"type": "artifact", "id": artifact_id}
                    )

                    signal = self.create_signal(
                        signal_type="commitment_made",
                        entity_ref_type=primary_entity["type"],
                        entity_ref_id=primary_entity["id"],
                        value={
                            "commitment_text": commitment["what"],
                            "due_indicator": commitment["when"],
                            "source": source,
                            "artifact_id": artifact_id,
                            "actor_id": actor_id,
                            "linked_entities": linked_entities,
                        },
                        severity="low",
                        interpretation_confidence=commitment["confidence"],
                        linkage_confidence_floor=0.6,
                        evidence_artifact_ids=[artifact_id],
                    )
                    signals.append(signal)

            # Check existing commitments table if it exists
            try:
                cursor.execute("""
                    SELECT commitment_id, scope_ref_type, scope_ref_id,
                           committed_by_type, committed_by_id, commitment_text,
                           due_at, status, confidence
                    FROM commitments
                    WHERE status = 'open' AND due_at IS NOT NULL
                """)

                today = datetime.now().date()

                for row in cursor.fetchall():
                    (
                        commitment_id,
                        scope_type,
                        scope_id,
                        by_type,
                        by_id,
                        text,
                        due_at,
                        status,
                        confidence,
                    ) = row

                    if due_at:
                        due_date = datetime.fromisoformat(due_at[:10]).date()
                        days_until = (due_date - today).days

                        if days_until < 0:
                            # Overdue
                            signal = self.create_signal(
                                signal_type="commitment_overdue",
                                entity_ref_type=scope_type,
                                entity_ref_id=scope_id,
                                value={
                                    "commitment_id": commitment_id,
                                    "commitment_text": text,
                                    "due_at": due_at,
                                    "days_overdue": abs(days_until),
                                    "committed_by": f"{by_type}:{by_id}",
                                },
                                severity="high" if days_until < -3 else "medium",
                                interpretation_confidence=confidence or 0.8,
                                linkage_confidence_floor=0.9,
                            )
                            signals.append(signal)

                        elif days_until <= 2:
                            # At risk
                            signal = self.create_signal(
                                signal_type="commitment_at_risk",
                                entity_ref_type=scope_type,
                                entity_ref_id=scope_id,
                                value={
                                    "commitment_id": commitment_id,
                                    "commitment_text": text,
                                    "due_at": due_at,
                                    "days_until": days_until,
                                    "committed_by": f"{by_type}:{by_id}",
                                },
                                severity="medium",
                                interpretation_confidence=confidence or 0.8,
                                linkage_confidence_floor=0.9,
                            )
                            signals.append(signal)

            except sqlite3.OperationalError:
                # commitments table doesn't exist yet
                pass

            return signals

        finally:
            conn.close()
