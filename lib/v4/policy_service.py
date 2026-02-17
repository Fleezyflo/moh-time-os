"""
Time OS V4 - Policy Service

Manages access control, retention rules, and redaction.
Provides governance layer for the executive OS.
"""

import json
import os
import sqlite3
import uuid
from typing import Any

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "moh_time_os.db")


class PolicyService:
    """
    Service for managing access control, retention, and redaction policies.
    """

    DEFAULT_ROLES = {
        "exec": {
            "permissions": {"read": ["*"], "write": ["proposals", "issues"]},
            "description": "Executive access - full read, limited write",
        },
        "lead": {
            "permissions": {
                "read": ["projects", "tasks", "signals"],
                "write": ["tasks"],
            },
            "description": "Team lead access",
        },
        "finance": {
            "permissions": {
                "read": ["clients", "invoices", "payments", "ar"],
                "write": ["invoices"],
            },
            "description": "Finance team access",
        },
        "ops": {
            "permissions": {"read": ["*"], "write": ["tasks", "projects"]},
            "description": "Operations access",
        },
    }

    DEFAULT_RETENTION = {
        "gmail": {"days": 365, "legal_hold": True},
        "calendar": {"days": 730, "legal_hold": True},
        "asana": {"days": 365, "legal_hold": True},
        "xero": {"days": 2555, "legal_hold": True},  # 7 years for financial
        "transcripts": {"days": 90, "legal_hold": True},
        "system": {"days": 180, "legal_hold": False},
    }

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._ensure_defaults()

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)

    def _generate_id(self, prefix: str = "pol") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    def _ensure_defaults(self):
        """Ensure default roles and retention rules exist."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Create default roles
            for role_name, config in self.DEFAULT_ROLES.items():
                cursor.execute("SELECT role_id FROM access_roles WHERE role_name = ?", (role_name,))
                if not cursor.fetchone():
                    role_id = self._generate_id("role")
                    cursor.execute(
                        """
                        INSERT INTO access_roles (role_id, role_name, permissions)
                        VALUES (?, ?, ?)
                    """,
                        (role_id, role_name, json.dumps(config["permissions"])),
                    )

            # Create default retention rules
            for source, config in self.DEFAULT_RETENTION.items():
                cursor.execute(
                    "SELECT rule_id FROM retention_rules WHERE source = ? AND type IS NULL",
                    (source,),
                )
                if not cursor.fetchone():
                    rule_id = self._generate_id("ret")
                    cursor.execute(
                        """
                        INSERT INTO retention_rules (rule_id, source, retention_days, legal_hold_supported)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            rule_id,
                            source,
                            config["days"],
                            1 if config["legal_hold"] else 0,
                        ),
                    )

            conn.commit()
        finally:
            conn.close()

    # ===========================================
    # Access Control
    # ===========================================

    def get_roles(self) -> list[dict[str, Any]]:
        """Get all access roles."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT role_id, role_name, permissions FROM access_roles")
            return [
                {"role_id": r[0], "role_name": r[1], "permissions": json.loads(r[2])}
                for r in cursor.fetchall()
            ]
        finally:
            conn.close()

    def grant_access(
        self, entity_type: str, entity_id: str, role_name: str, permission: str = "read"
    ) -> dict[str, Any]:
        """Grant access to an entity for a role."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Get role_id
            cursor.execute("SELECT role_id FROM access_roles WHERE role_name = ?", (role_name,))
            row = cursor.fetchone()
            if not row:
                return {"status": "error", "error": f"Role {role_name} not found"}

            role_id = row[0]
            acl_id = self._generate_id("acl")

            cursor.execute(
                """
                INSERT OR REPLACE INTO entity_acl
                (acl_id, entity_type, entity_id, role_id, permission)
                VALUES (?, ?, ?, ?, ?)
            """,
                (acl_id, entity_type, entity_id, role_id, permission),
            )

            conn.commit()
            return {"status": "granted", "acl_id": acl_id}
        finally:
            conn.close()

    def check_access(
        self, role_id: str, entity_type: str, entity_id: str, permission: str = "read"
    ) -> bool:
        """Check if a role has access to an entity (supports wildcards)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Check for matching ACL rules (entity_id can be '*' for wildcard)
            cursor.execute(
                """
                SELECT permission FROM entity_acl
                WHERE role_id = ? AND entity_type = ?
                AND (entity_id = ? OR entity_id = '*')
            """,
                (role_id, entity_type, entity_id),
            )

            return any(
                permission in perm_str or perm_str == permission
                for (perm_str,) in cursor.fetchall()
            )
        finally:
            conn.close()

    def get_entity_acl(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        """Get ACL entries for an entity."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT a.acl_id, r.role_name, a.permission, a.created_at
                FROM entity_acl a
                JOIN access_roles r ON a.role_id = r.role_id
                WHERE a.entity_type = ? AND a.entity_id = ?
            """,
                (entity_type, entity_id),
            )

            return [
                {
                    "acl_id": r[0],
                    "role_name": r[1],
                    "permission": r[2],
                    "created_at": r[3],
                }
                for r in cursor.fetchall()
            ]
        finally:
            conn.close()

    # ===========================================
    # Retention
    # ===========================================

    def get_retention_rules(self) -> list[dict[str, Any]]:
        """Get all retention rules."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT rule_id, source, type, retention_days, legal_hold_supported
                FROM retention_rules
            """)
            return [
                {
                    "rule_id": r[0],
                    "source": r[1],
                    "type": r[2],
                    "retention_days": r[3],
                    "legal_hold_supported": bool(r[4]),
                }
                for r in cursor.fetchall()
            ]
        finally:
            conn.close()

    def get_retention_for_source(self, source: str, artifact_type: str = None) -> dict | None:
        """Get retention rule for a source/type combination."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Try specific type first
            if artifact_type:
                cursor.execute(
                    """
                    SELECT retention_days, legal_hold_supported
                    FROM retention_rules
                    WHERE source = ? AND type = ?
                """,
                    (source, artifact_type),
                )
                row = cursor.fetchone()
                if row:
                    return {"retention_days": row[0], "legal_hold": bool(row[1])}

            # Fall back to source-level rule
            cursor.execute(
                """
                SELECT retention_days, legal_hold_supported
                FROM retention_rules
                WHERE source = ? AND type IS NULL
            """,
                (source,),
            )
            row = cursor.fetchone()
            if row:
                return {"retention_days": row[0], "legal_hold": bool(row[1])}

            return None
        finally:
            conn.close()

    def find_expired_artifacts(self, limit: int = 100) -> list[dict[str, Any]]:
        """Find artifacts past their retention period."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Join artifacts with retention rules
            cursor.execute(
                """
                SELECT a.artifact_id, a.source, a.type, a.occurred_at, r.retention_days
                FROM artifacts a
                JOIN retention_rules r ON a.source = r.source AND r.type IS NULL
                WHERE date(a.occurred_at, '+' || r.retention_days || ' days') < date('now')
                LIMIT ?
            """,
                (limit,),
            )

            return [
                {
                    "artifact_id": r[0],
                    "source": r[1],
                    "type": r[2],
                    "occurred_at": r[3],
                    "retention_days": r[4],
                }
                for r in cursor.fetchall()
            ]
        finally:
            conn.close()

    # ===========================================
    # Redaction
    # ===========================================

    def redact_excerpt(
        self, excerpt_id: str, redaction_type: str, redacted_by: str, reason: str = None
    ) -> dict[str, Any]:
        """Mark an excerpt for redaction."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            marker_id = self._generate_id("red")

            cursor.execute(
                """
                INSERT INTO redaction_markers
                (marker_id, excerpt_id, redaction_type, redacted_by, reason)
                VALUES (?, ?, ?, ?, ?)
            """,
                (marker_id, excerpt_id, redaction_type, redacted_by, reason),
            )

            # Update excerpt status
            cursor.execute(
                """
                UPDATE artifact_excerpts
                SET redaction_status = 'redacted'
                WHERE excerpt_id = ?
            """,
                (excerpt_id,),
            )

            conn.commit()
            return {"status": "redacted", "marker_id": marker_id}
        finally:
            conn.close()

    def get_redaction_markers(self, excerpt_id: str = None) -> list[dict[str, Any]]:
        """Get redaction markers."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            if excerpt_id:
                cursor.execute(
                    """
                    SELECT marker_id, excerpt_id, redaction_type, redacted_by, redacted_at, reason
                    FROM redaction_markers WHERE excerpt_id = ?
                """,
                    (excerpt_id,),
                )
            else:
                cursor.execute("""
                    SELECT marker_id, excerpt_id, redaction_type, redacted_by, redacted_at, reason
                    FROM redaction_markers ORDER BY redacted_at DESC LIMIT 100
                """)

            return [
                {
                    "marker_id": r[0],
                    "excerpt_id": r[1],
                    "redaction_type": r[2],
                    "redacted_by": r[3],
                    "redacted_at": r[4],
                    "reason": r[5],
                }
                for r in cursor.fetchall()
            ]
        finally:
            conn.close()

    # ===========================================
    # Protocol Violations
    # ===========================================

    def log_protocol_violation(
        self,
        violation_type: str,
        scope_refs: list[dict],
        severity: str,
        evidence_excerpt_ids: list[str] = None,
    ) -> dict[str, Any]:
        """Log a protocol violation."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            violation_id = self._generate_id("vio")

            cursor.execute(
                """
                INSERT INTO protocol_violations
                (violation_id, violation_type, scope_refs, severity, evidence_excerpt_ids)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    violation_id,
                    violation_type,
                    json.dumps(scope_refs),
                    severity,
                    json.dumps(evidence_excerpt_ids or []),
                ),
            )

            conn.commit()
            return {"status": "logged", "violation_id": violation_id}
        finally:
            conn.close()

    def get_open_violations(self, severity: str = None, limit: int = 50) -> list[dict[str, Any]]:
        """Get open protocol violations."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            query = """
                SELECT violation_id, violation_type, scope_refs, severity, detected_at
                FROM protocol_violations WHERE status = 'open'
            """
            params = []

            if severity:
                query += " AND severity = ?"
                params.append(severity)

            query += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [
                {
                    "violation_id": r[0],
                    "violation_type": r[1],
                    "scope_refs": json.loads(r[2]),
                    "severity": r[3],
                    "detected_at": r[4],
                }
                for r in cursor.fetchall()
            ]
        finally:
            conn.close()

    def resolve_violation(self, violation_id: str) -> dict[str, Any]:
        """Mark a violation as resolved."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE protocol_violations SET status = 'resolved'
                WHERE violation_id = ? AND status = 'open'
            """,
                (violation_id,),
            )

            if cursor.rowcount == 0:
                return {
                    "status": "error",
                    "error": "Violation not found or already resolved",
                }

            conn.commit()
            return {"status": "resolved", "violation_id": violation_id}
        finally:
            conn.close()

    # ===========================================
    # Statistics
    # ===========================================

    def get_stats(self) -> dict[str, Any]:
        """Get policy statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) FROM access_roles")
            roles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM entity_acl")
            acl_entries = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM retention_rules")
            retention_rules = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM redaction_markers")
            redactions = cursor.fetchone()[0]

            cursor.execute("SELECT status, COUNT(*) FROM protocol_violations GROUP BY status")
            violations = {r[0]: r[1] for r in cursor.fetchall()}

            return {
                "roles": roles,
                "acl_entries": acl_entries,
                "retention_rules": retention_rules,
                "redactions": redactions,
                "violations": violations,
            }
        finally:
            conn.close()

    # ===========================================
    # Runtime Enforcement (Gap Fix #5)
    # ===========================================

    def purge_expired_artifacts(self, dry_run: bool = True) -> dict[str, Any]:
        """
        Purge artifacts past their retention period.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Stats on purged artifacts
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        stats = {"found": 0, "purged": 0, "blobs_deleted": 0, "legal_hold_skipped": 0}

        try:
            # Find expired artifacts (respecting legal hold)
            cursor.execute("""
                SELECT a.artifact_id, a.payload_ref, r.legal_hold_supported
                FROM artifacts a
                JOIN retention_rules r ON a.source = r.source AND (r.type IS NULL OR r.type = a.type)
                WHERE date(a.occurred_at, '+' || r.retention_days || ' days') < date('now')
            """)

            expired = cursor.fetchall()
            stats["found"] = len(expired)

            for artifact_id, payload_ref, legal_hold_supported in expired:
                if legal_hold_supported:
                    stats["legal_hold_skipped"] += 1
                    continue

                if not dry_run:
                    # Delete excerpts
                    cursor.execute(
                        "DELETE FROM artifact_excerpts WHERE artifact_id = ?",
                        (artifact_id,),
                    )

                    # Delete entity links
                    cursor.execute(
                        "DELETE FROM entity_links WHERE from_artifact_id = ?",
                        (artifact_id,),
                    )

                    # Delete blob if exists
                    if payload_ref and payload_ref.startswith("blob:"):
                        blob_id = payload_ref.replace("blob:", "")
                        cursor.execute("DELETE FROM artifact_blobs WHERE blob_id = ?", (blob_id,))
                        stats["blobs_deleted"] += 1

                    # Delete artifact
                    cursor.execute("DELETE FROM artifacts WHERE artifact_id = ?", (artifact_id,))

                stats["purged"] += 1

            if not dry_run:
                conn.commit()

            return stats

        finally:
            conn.close()

    def enforce_acl(
        self,
        actor_role: str,
        operation: str,  # 'read' or 'write'
        entity_type: str,
        entity_id: str = None,
    ) -> dict[str, Any]:
        """
        Enforce ACL and return whether access is allowed.

        Returns:
            {'allowed': bool, 'reason': str}
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Get role permissions
            cursor.execute(
                "SELECT permissions FROM access_roles WHERE role_id = ? OR role_name = ?",
                (actor_role, actor_role),
            )
            row = cursor.fetchone()

            if not row:
                return {"allowed": False, "reason": f"Unknown role: {actor_role}"}

            permissions = json.loads(row[0])
            allowed_entities = permissions.get(operation, [])

            # Check if entity type is allowed
            if "*" in allowed_entities or entity_type in allowed_entities:
                # Check entity-specific ACL if entity_id provided
                if entity_id:
                    cursor.execute(
                        """
                        SELECT role_id FROM entity_acl
                        WHERE entity_type = ? AND entity_id = ? AND permission = ?
                    """,
                        (entity_type, entity_id, operation),
                    )

                    acl_row = cursor.fetchone()
                    if acl_row and acl_row[0] != actor_role:
                        return {
                            "allowed": False,
                            "reason": f"Entity {entity_type}:{entity_id} requires role {acl_row[0]}",
                        }

                return {"allowed": True, "reason": "Access granted"}

            return {
                "allowed": False,
                "reason": f"Role {actor_role} cannot {operation} {entity_type}",
            }

        finally:
            conn.close()

    def run_retention_enforcement(self, dry_run: bool = True) -> dict[str, Any]:
        """
        Run full retention enforcement cycle.

        1. Find expired artifacts
        2. Purge non-legal-hold items
        3. Log results

        Returns stats.
        """
        import logging

        log = logging.getLogger("moh_time_os.v4.policy")

        stats = self.purge_expired_artifacts(dry_run=dry_run)

        mode = "DRY RUN" if dry_run else "ENFORCED"
        log.info(
            f"Retention enforcement ({mode}): found={stats['found']}, "
            f"purged={stats['purged']}, legal_hold_skipped={stats['legal_hold_skipped']}"
        )

        return stats


_policy_service = None


def get_policy_service() -> PolicyService:
    global _policy_service
    if _policy_service is None:
        _policy_service = PolicyService()
    return _policy_service
