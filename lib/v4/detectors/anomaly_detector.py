"""
Time OS V4 - Anomaly Detector

Detects anomalous patterns:
- Unusual activity spikes/drops
- Data quality issues
- Protocol violations
"""

import json
import os
import sqlite3
from typing import Any

from .base import BaseDetector

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "moh_time_os.db")


class AnomalyDetector(BaseDetector):
    """
    Detects anomalous patterns and protocol violations.

    Signal types produced:
    - activity_spike: Unusual increase in activity
    - activity_drop: Unusual decrease in activity
    - data_quality_issue: Missing or inconsistent data
    - hierarchy_violation: Domain model violations
    """

    detector_id = "anomaly_detector"
    version = "1.0.0"
    description = "Detects anomalous patterns and data quality issues"
    signal_types = [
        "activity_spike",
        "activity_drop",
        "data_quality_issue",
        "hierarchy_violation",
    ]

    def get_parameters(self) -> dict[str, Any]:
        return {
            "spike_threshold": 2.0,  # 2x normal activity
            "drop_threshold": 0.3,  # 30% of normal activity
        }

    def detect(self, scope: dict) -> list[dict[str, Any]]:
        """Run anomaly detection."""
        signals = []
        protocol_violations = []  # Track violations for protocol_violations table

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Detect hierarchy violations (tasks without projects, projects without clients)

            # Tasks without valid project assignment
            cursor.execute("""
                SELECT t.id, t.title, t.source, t.project
                FROM tasks t
                WHERE t.project IS NULL
                AND t.status NOT IN ('done', 'cancelled', 'closed', 'archived')
                LIMIT 50
            """)

            for row in cursor.fetchall():
                task_id, title, source, project_id = row
                item_id = task_id
                domain = source

                # Find related artifact for evidence
                cursor.execute(
                    "SELECT artifact_id FROM artifacts WHERE source_id = ? LIMIT 1",
                    (item_id,),
                )
                art_row = cursor.fetchone()
                evidence_artifacts = [art_row[0]] if art_row else []

                signal = self.create_signal(
                    signal_type="hierarchy_violation",
                    entity_ref_type="task",
                    entity_ref_id=item_id,
                    value={
                        "violation_type": "task_no_project",
                        "title": title,
                        "domain": domain,
                        "message": "Task has no project assignment",
                    },
                    severity="low",
                    interpretation_confidence=0.95,
                    linkage_confidence_floor=1.0,
                    evidence_artifact_ids=evidence_artifacts,
                )
                signals.append(signal)
                protocol_violations.append(
                    {
                        "type": "task_no_project",
                        "entity_type": "task",
                        "entity_id": item_id,
                        "severity": "low",
                        "description": f"Task '{title}' has no project assignment",
                    }
                )

            # Projects without client assignment
            cursor.execute("""
                SELECT p.id, p.name, p.status, p.asana_project_id
                FROM projects p
                WHERE p.client_id IS NULL
                AND p.status = 'active'
                LIMIT 50
            """)

            for row in cursor.fetchall():
                project_id, name, status, asana_pid = row

                # Find related artifact for evidence
                cursor.execute(
                    "SELECT artifact_id FROM artifacts WHERE source_id = ? OR source_id = ? LIMIT 1",
                    (f"project_{asana_pid}", f"project_{project_id}"),
                )
                art_row = cursor.fetchone()
                evidence_artifacts = [art_row[0]] if art_row else []

                signal = self.create_signal(
                    signal_type="hierarchy_violation",
                    entity_ref_type="project",
                    entity_ref_id=project_id,
                    value={
                        "violation_type": "project_no_client",
                        "project_name": name,
                        "message": "Active project has no client assignment",
                    },
                    severity="medium",
                    interpretation_confidence=0.95,
                    linkage_confidence_floor=1.0,
                    evidence_artifact_ids=evidence_artifacts,
                )
                signals.append(signal)
                protocol_violations.append(
                    {
                        "type": "project_no_client",
                        "entity_type": "project",
                        "entity_id": project_id,
                        "severity": "medium",
                        "description": f"Active project '{name}' has no client assignment",
                    }
                )

            # Detect data quality issues

            # Clients with missing critical fields
            cursor.execute("""
                SELECT id, name, tier
                FROM clients
                WHERE tier = 'A'
                AND (relationship_health IS NULL OR relationship_last_interaction IS NULL)
            """)

            for row in cursor.fetchall():
                client_id, name, tier = row

                signal = self.create_signal(
                    signal_type="data_quality_issue",
                    entity_ref_type="client",
                    entity_ref_id=client_id,
                    value={
                        "issue_type": "missing_relationship_data",
                        "client_name": name,
                        "tier": tier,
                        "message": "Tier A client missing relationship tracking data",
                    },
                    severity="medium",
                    interpretation_confidence=0.95,
                    linkage_confidence_floor=1.0,
                )
                signals.append(signal)

            # Tasks with dates in the past but not completed
            cursor.execute("""
                SELECT id, title, due_date, status, assignee
                FROM tasks
                WHERE due_date < date('now', '-30 days')
                AND due_date IS NOT NULL
                AND status NOT IN ('done', 'cancelled', 'closed', 'archived')
                LIMIT 50
            """)

            for row in cursor.fetchall():
                item_id, title, due_date, status, owner = row

                signal = self.create_signal(
                    signal_type="data_quality_issue",
                    entity_ref_type="task",
                    entity_ref_id=item_id,
                    value={
                        "issue_type": "stale_task",
                        "title": title,
                        "due_date": due_date,
                        "status": status,
                        "owner": owner,
                        "message": "Task overdue by 30+ days but not closed",
                    },
                    severity="low",
                    interpretation_confidence=0.9,
                    linkage_confidence_floor=1.0,
                )
                signals.append(signal)

            # Check for low-confidence entity links in Fix Data queue
            cursor.execute("""
                SELECT fix_id, fix_type, entity_type, entity_id, description, severity
                FROM fix_data_queue
                WHERE status IN ('open', 'pending')
                LIMIT 50
            """)

            for row in cursor.fetchall():
                fix_id, fix_type, entity_type, entity_id, description, severity = row

                signal = self.create_signal(
                    signal_type="data_quality_issue",
                    entity_ref_type=entity_type or "system",
                    entity_ref_id=entity_id or fix_id,
                    value={
                        "issue_type": fix_type,
                        "fix_id": fix_id,
                        "description": description,
                    },
                    severity=severity or "medium",
                    interpretation_confidence=0.95,
                    linkage_confidence_floor=0.5,
                )
                signals.append(signal)

            # Insert protocol violations into the protocol_violations table
            self._record_protocol_violations(cursor, protocol_violations)
            conn.commit()

            return signals

        finally:
            conn.close()

    def _record_protocol_violations(self, cursor, violations: list[dict]):
        """Record detected protocol violations in the protocol_violations table."""
        import uuid

        for v in violations:
            violation_id = f"pv_{uuid.uuid4().hex[:16]}"

            # Check if similar violation already exists
            cursor.execute(
                """
                SELECT violation_id FROM protocol_violations
                WHERE violation_type = ? AND scope_refs LIKE ? AND status = 'open'
                LIMIT 1
            """,
                (v["type"], f'%"{v["entity_id"]}"%'),
            )

            if cursor.fetchone():
                continue  # Already exists

            scope_refs = json.dumps([{"type": v["entity_type"], "id": v["entity_id"]}])

            cursor.execute(
                """
                INSERT INTO protocol_violations
                (violation_id, violation_type, scope_refs, severity, evidence_excerpt_ids, detected_at, status)
                VALUES (?, ?, ?, ?, '[]', datetime('now'), 'open')
            """,
                (violation_id, v["type"], scope_refs, v["severity"]),
            )
