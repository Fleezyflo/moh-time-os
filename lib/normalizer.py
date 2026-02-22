"""
Normalizer - Single Source of Truth for Derived Columns

Per MASTER_SPEC.md §4:
- Writes: projects.client_id (from brand, NULL if internal)
- Writes: tasks.brand_id, client_id, project_link_status, client_link_status
- Writes: communications.from_domain, client_id, link_status
- Writes: invoices.aging_bucket (only for valid AR)
- Runs: AFTER collect, BEFORE truth modules
"""

import logging
import sqlite3
from datetime import date
from pathlib import Path

from lib import paths

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()


class Normalizer:
    """Single source of truth for derived columns."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")  # Enable FK enforcement
        return conn

    def run(self) -> dict:
        """Run full normalization cycle. Returns counts of updated rows."""
        return {
            "projects": self._normalize_projects(),
            "tasks_project_bridge": self._bridge_task_project_ids(),  # NEW: bridge project→project_id
            "tasks": self._normalize_tasks(),
            "communications": self._normalize_communications(),
            "invoices": self._normalize_invoices(),
        }

    def _bridge_task_project_ids(self) -> int:
        """
        Bridge tasks.project (legacy name/id text) → tasks.project_id (FK).

        Collectors write to 'project' column. This step resolves it to project_id
        by matching against projects.id or projects.name.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Match by project.id first (most common case)
            cursor.execute("""
                UPDATE tasks
                SET project_id = project,
                    updated_at = datetime('now')
                WHERE project IS NOT NULL
                AND project != ''
                AND (project_id IS NULL OR project_id = '')
                AND EXISTS (SELECT 1 FROM projects WHERE id = tasks.project)
            """)
            by_id = cursor.rowcount

            # Match by project.name (fallback)
            cursor.execute("""
                UPDATE tasks
                SET project_id = (SELECT id FROM projects WHERE name = tasks.project LIMIT 1),
                    updated_at = datetime('now')
                WHERE project IS NOT NULL
                AND project != ''
                AND (project_id IS NULL OR project_id = '')
                AND EXISTS (SELECT 1 FROM projects WHERE name = tasks.project)
            """)
            by_name = cursor.rowcount

            conn.commit()
            return by_id + by_name
        finally:
            conn.close()

    def _normalize_projects(self) -> int:
        """Derive projects.client_id from brand.client_id (NULL if internal)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # For non-internal projects: client_id = brand.client_id
            # For internal projects: client_id = NULL
            cursor.execute("""
                UPDATE projects
                SET client_id = (
                    SELECT CASE
                        WHEN projects.is_internal = 1 THEN NULL
                        ELSE b.client_id
                    END
                    FROM brands b
                    WHERE b.id = projects.brand_id
                ),
                updated_at = datetime('now')
                WHERE brand_id IS NOT NULL
                AND (
                    client_id IS NOT (
                        SELECT CASE
                            WHEN projects.is_internal = 1 THEN NULL
                            ELSE b.client_id
                        END
                        FROM brands b
                        WHERE b.id = projects.brand_id
                    )
                    OR client_id IS NULL AND is_internal = 0 AND brand_id IS NOT NULL
                )
            """)
            updated = cursor.rowcount

            # For internal projects without brand, ensure client_id is NULL
            cursor.execute("""
                UPDATE projects
                SET client_id = NULL, updated_at = datetime('now')
                WHERE is_internal = 1 AND client_id IS NOT NULL
            """)
            updated += cursor.rowcount

            conn.commit()
            return updated
        finally:
            conn.close()

    def _normalize_tasks(self) -> int:
        """Derive brand_id, client_id, project_link_status, client_link_status."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Fetch all tasks with their linked data
            cursor.execute("""
                SELECT t.id, t.project_id, t.brand_id, t.client_id,
                       t.project_link_status, t.client_link_status,
                       p.id as proj_exists, p.brand_id as proj_brand_id, p.is_internal as proj_internal,
                       b.id as brand_exists, b.client_id as brand_client_id,
                       c.id as client_exists
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                LEFT JOIN brands b ON p.brand_id = b.id
                LEFT JOIN clients c ON b.client_id = c.id
            """)

            tasks = cursor.fetchall()
            updated = 0

            for task in tasks:
                new_brand_id = None
                new_client_id = None
                new_project_link = "unlinked"
                new_client_link = "unlinked"

                if task["project_id"] is None:
                    # No project assigned
                    new_project_link = "unlinked"
                    new_client_link = "unlinked"
                elif not task["proj_exists"]:
                    # project_id set but project doesn't exist
                    new_project_link = "partial"
                    new_client_link = "unlinked"
                elif task["proj_internal"]:
                    # Internal project - no client chain
                    new_brand_id = task["proj_brand_id"]
                    new_project_link = "linked"
                    new_client_link = "n/a"
                elif not task["proj_brand_id"]:
                    # Non-internal project missing brand
                    new_project_link = "partial"
                    new_client_link = "unlinked"
                elif not task["brand_exists"]:
                    # Brand ID set but brand doesn't exist
                    new_brand_id = task["proj_brand_id"]
                    new_project_link = "partial"
                    new_client_link = "unlinked"
                elif not task["brand_client_id"]:
                    # Brand exists but has no client
                    new_brand_id = task["proj_brand_id"]
                    new_project_link = "partial"
                    new_client_link = "unlinked"
                elif not task["client_exists"]:
                    # Client ID on brand but client doesn't exist
                    new_brand_id = task["proj_brand_id"]
                    new_client_id = task["brand_client_id"]
                    new_project_link = "partial"
                    new_client_link = "unlinked"
                else:
                    # Full chain valid
                    new_brand_id = task["proj_brand_id"]
                    new_client_id = task["brand_client_id"]
                    new_project_link = "linked"
                    new_client_link = "linked"

                # Check if update needed
                if (
                    task["brand_id"] != new_brand_id
                    or task["client_id"] != new_client_id
                    or task["project_link_status"] != new_project_link
                    or task["client_link_status"] != new_client_link
                ):
                    cursor.execute(
                        """
                        UPDATE tasks
                        SET brand_id = ?, client_id = ?,
                            project_link_status = ?, client_link_status = ?,
                            updated_at = datetime('now')
                        WHERE id = ?
                    """,
                        [
                            new_brand_id,
                            new_client_id,
                            new_project_link,
                            new_client_link,
                            task["id"],
                        ],
                    )
                    updated += 1

            conn.commit()
            return updated
        finally:
            conn.close()

    def _normalize_communications(self) -> int:
        """Derive from_domain, client_id, link_status from client_identities."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            updated = 0

            # Extract domain from from_email if from_domain is NULL
            cursor.execute("""
                UPDATE communications
                SET from_domain = LOWER(SUBSTR(from_email, INSTR(from_email, '@') + 1))
                WHERE from_email IS NOT NULL
                AND from_email LIKE '%@%'
                AND (from_domain IS NULL OR from_domain = '')
            """)
            updated += cursor.rowcount

            # Link communications to clients via client_identities
            # Try email match first, then domain match
            cursor.execute("""
                UPDATE communications
                SET client_id = (
                    SELECT ci.client_id FROM client_identities ci
                    WHERE (ci.identity_type = 'email' AND LOWER(ci.identity_value) = LOWER(communications.from_email))
                    OR (ci.identity_type = 'domain' AND LOWER(ci.identity_value) = LOWER(communications.from_domain))
                    LIMIT 1
                ),
                link_status = 'linked'
                WHERE client_id IS NULL
                AND EXISTS (
                    SELECT 1 FROM client_identities ci
                    WHERE (ci.identity_type = 'email' AND LOWER(ci.identity_value) = LOWER(communications.from_email))
                    OR (ci.identity_type = 'domain' AND LOWER(ci.identity_value) = LOWER(communications.from_domain))
                )
            """)
            updated += cursor.rowcount

            # Link communications to clients via subject line matching client names
            # Only for unlinked communications
            cursor.execute("""
                UPDATE communications
                SET client_id = (
                    SELECT c.id FROM clients c
                    WHERE LENGTH(c.name) >= 4
                    AND LOWER(communications.subject) LIKE '%' || LOWER(c.name) || '%'
                    ORDER BY LENGTH(c.name) DESC
                    LIMIT 1
                ),
                link_status = 'linked'
                WHERE client_id IS NULL
                AND EXISTS (
                    SELECT 1 FROM clients c
                    WHERE LENGTH(c.name) >= 4
                    AND LOWER(communications.subject) LIKE '%' || LOWER(c.name) || '%'
                )
            """)
            updated += cursor.rowcount

            # Link via invoice client names in subject
            cursor.execute("""
                UPDATE communications
                SET client_id = (
                    SELECT i.client_id FROM invoices i
                    WHERE i.client_name IS NOT NULL
                    AND LENGTH(i.client_name) >= 4
                    AND LOWER(communications.subject) LIKE '%' || LOWER(i.client_name) || '%'
                    LIMIT 1
                ),
                link_status = 'linked'
                WHERE client_id IS NULL
                AND EXISTS (
                    SELECT 1 FROM invoices i
                    WHERE i.client_name IS NOT NULL
                    AND LENGTH(i.client_name) >= 4
                    AND LOWER(communications.subject) LIKE '%' || LOWER(i.client_name) || '%'
                )
            """)
            updated += cursor.rowcount

            # Set link_status to 'linked' for communications that have client_id
            cursor.execute("""
                UPDATE communications
                SET link_status = 'linked'
                WHERE client_id IS NOT NULL AND link_status != 'linked'
            """)
            updated += cursor.rowcount

            # Set link_status to 'unlinked' for communications without client_id
            cursor.execute("""
                UPDATE communications
                SET link_status = 'unlinked'
                WHERE client_id IS NULL AND link_status != 'unlinked'
            """)
            updated += cursor.rowcount

            conn.commit()
            return updated
        finally:
            conn.close()

    def _normalize_invoices(self) -> int:
        """Derive aging_bucket for valid AR invoices."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            today = date.today().isoformat()

            # Calculate aging bucket for unpaid invoices with due_date
            # Aging buckets: current, 1-30, 31-60, 61-90, 90+
            # Only write aging_bucket for VALID AR per §10:
            # status IN ('sent','overdue') AND paid_date IS NULL
            # AND due_date IS NOT NULL AND client_id IS NOT NULL
            cursor.execute(
                """
                UPDATE invoices
                SET aging_bucket = CASE
                    WHEN julianday(?) - julianday(due_date) <= 0 THEN 'current'
                    WHEN julianday(?) - julianday(due_date) <= 30 THEN '1-30'
                    WHEN julianday(?) - julianday(due_date) <= 60 THEN '31-60'
                    WHEN julianday(?) - julianday(due_date) <= 90 THEN '61-90'
                    ELSE '90+'
                END,
                updated_at = datetime('now')
                WHERE status IN ('sent', 'overdue')
                AND payment_date IS NULL
                AND due_date IS NOT NULL
                AND client_id IS NOT NULL
                AND (
                    aging_bucket IS NULL
                    OR aging_bucket != CASE
                        WHEN julianday(?) - julianday(due_date) <= 0 THEN 'current'
                        WHEN julianday(?) - julianday(due_date) <= 30 THEN '1-30'
                        WHEN julianday(?) - julianday(due_date) <= 60 THEN '31-60'
                        WHEN julianday(?) - julianday(due_date) <= 90 THEN '61-90'
                        ELSE '90+'
                    END
                )
            """,
                [today] * 8,
            )

            updated = cursor.rowcount
            conn.commit()
            return updated
        finally:
            conn.close()


def run_normalization() -> dict:
    """Convenience function to run normalization."""
    normalizer = Normalizer()
    return normalizer.run()


if __name__ == "__main__":
    logger.info("Running normalization...")
    results = run_normalization()
    logger.info(f"Results: {results}")
    total = sum(results.values())
    logger.info(f"Total rows updated: {total}")
