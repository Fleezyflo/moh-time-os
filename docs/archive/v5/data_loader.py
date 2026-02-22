"""
Time OS V5 — Data Loader

Loads data from collector JSON outputs for signal detection.
Also provides scope lookups from the main database.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from lib import paths

logger = logging.getLogger(__name__)

# Default paths
OUT_DIR = paths.out_dir()
MAIN_DB = paths.db_path()


class DataLoader:
    """Loads collected data from JSON files and provides scope lookups."""

    def __init__(self, out_dir: Path = OUT_DIR, main_db: Path = MAIN_DB):
        self.out_dir = out_dir
        self.main_db = main_db
        self._scope_cache: dict[str, dict[str, Any]] = {}
        self._project_name_cache: dict[str, str] = {}  # name → project_id
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get main database connection."""
        if self._conn is None and self.main_db.exists():
            self._conn = sqlite3.connect(str(self.main_db))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _load_json(self, filename: str) -> dict[str, Any] | None:
        """Load a JSON file from the output directory."""
        path = self.out_dir / filename
        if not path.exists():
            logger.warning(f"Data file not found: {path}")
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {filename}: {e}")
            return None

    # =========================================================================
    # Asana Data
    # =========================================================================

    def load_asana_ops(self) -> dict[str, Any] | None:
        """
        Load Asana operations data.

        Returns dict with keys:
        - overdue: List of overdue tasks
        - stale: List of stale tasks
        - no_assignee: List of unassigned tasks
        - no_due_date: List of tasks without due dates
        - total_tasks: Total task count
        """
        return self._load_json("asana-ops.json")

    def get_overdue_tasks(self) -> list[dict[str, Any]]:
        """Get list of overdue tasks."""
        data = self.load_asana_ops()
        if not data:
            return []
        return data.get("overdue", [])

    def get_stale_tasks(self) -> list[dict[str, Any]]:
        """Get list of stale tasks (not updated recently)."""
        data = self.load_asana_ops()
        if not data:
            return []
        return data.get("stale", [])

    # =========================================================================
    # Xero Data
    # =========================================================================

    def load_xero_ar(self) -> dict[str, Any] | None:
        """
        Load Xero AR data.

        Returns dict with keys:
        - collected_at: Timestamp
        - outstanding: List of outstanding invoices
        - summary: AR summary
        """
        return self._load_json("xero-ar.json")

    def get_outstanding_invoices(self) -> list[dict[str, Any]]:
        """Get list of outstanding invoices."""
        data = self.load_xero_ar()
        if not data:
            return []
        return data.get("outstanding", [])

    def get_overdue_invoices(self) -> list[dict[str, Any]]:
        """Get list of overdue invoices."""
        invoices = self.get_outstanding_invoices()
        return [inv for inv in invoices if inv.get("is_overdue")]

    # =========================================================================
    # Google Chat Data
    # =========================================================================

    def load_chat(self) -> dict[str, Any] | None:
        """
        Load Google Chat data.

        Returns dict with keys:
        - collected_at: Timestamp
        - spaces: List of spaces
        - messages: List of messages
        - mentions: List of mentions
        """
        return self._load_json("chat-full.json")

    def get_chat_messages(self) -> list[dict[str, Any]]:
        """Get list of chat messages."""
        data = self.load_chat()
        if not data:
            return []
        return data.get("messages", [])

    def get_chat_spaces(self) -> list[dict[str, Any]]:
        """Get list of chat spaces."""
        data = self.load_chat()
        if not data:
            return []
        return data.get("spaces", [])

    # =========================================================================
    # Calendar Data
    # =========================================================================

    def load_calendar(self) -> dict[str, Any] | None:
        """
        Load Calendar data.

        Returns dict with keys:
        - events: List of calendar events
        """
        return self._load_json("calendar-next.json")

    def get_calendar_events(self) -> list[dict[str, Any]]:
        """Get list of calendar events."""
        data = self.load_calendar()
        if not data:
            return []
        return data.get("events", [])

    # =========================================================================
    # Scope Lookups
    # =========================================================================

    def get_project_by_name(self, name: str) -> dict[str, Any] | None:
        """
        Look up project by name.

        Returns dict with id, client_id, brand_id.
        """
        if not name:
            return None

        # Check cache
        cache_key = f"project:{name}"
        if cache_key in self._scope_cache:
            return self._scope_cache[cache_key]

        conn = self._get_conn()
        if not conn:
            return None

        try:
            cur = conn.execute(
                """
                SELECT id, client_id, brand_id, name
                FROM projects
                WHERE name = ? OR name_normalized = ?
                LIMIT 1
            """,
                (name, name.lower().strip()),
            )
            row = cur.fetchone()

            if row:
                result = {
                    "project_id": row["id"],
                    "client_id": row["client_id"],
                    "brand_id": row["brand_id"],
                    "name": row["name"],
                }
                self._scope_cache[cache_key] = result
                return result
        except Exception as e:
            logger.warning(f"Project lookup failed for '{name}': {e}")

        return None

    def get_client_by_xero_contact(self, contact_name: str) -> dict[str, Any] | None:
        """
        Look up client by Xero contact name.

        Returns dict with id, name.
        """
        if not contact_name:
            return None

        cache_key = f"xero_contact:{contact_name}"
        if cache_key in self._scope_cache:
            return self._scope_cache[cache_key]

        conn = self._get_conn()
        if not conn:
            return None

        try:
            # Try exact match first, then normalized
            cur = conn.execute(
                """
                SELECT id, name
                FROM clients
                WHERE name = ? OR name_normalized = ?
                LIMIT 1
            """,
                (contact_name, contact_name.lower().strip()),
            )
            row = cur.fetchone()

            if row:
                result = {"client_id": row["id"], "name": row["name"]}
                self._scope_cache[cache_key] = result
                return result
        except Exception as e:
            logger.warning(f"Client lookup failed for '{contact_name}': {e}")

        return None

    def get_scope_for_task(self, task: dict[str, Any]) -> dict[str, str | None]:
        """
        Get scope IDs for a task.

        Returns dict with client_id, brand_id, project_id.
        """
        result = {"client_id": None, "brand_id": None, "project_id": None}

        project_name = task.get("project")
        if project_name:
            project = self.get_project_by_name(project_name)
            if project:
                result["project_id"] = project.get("project_id")
                result["client_id"] = project.get("client_id")
                result["brand_id"] = project.get("brand_id")

        return result

    def get_scope_for_invoice(self, invoice: dict[str, Any]) -> dict[str, str | None]:
        """
        Get scope IDs for an invoice.

        Returns dict with client_id.
        """
        result = {"client_id": None}

        contact_name = invoice.get("contact")
        if contact_name:
            client = self.get_client_by_xero_contact(contact_name)
            if client:
                result["client_id"] = client.get("client_id")

        return result


# Singleton instance
_loader: DataLoader | None = None


def get_data_loader() -> DataLoader:
    """Get the singleton data loader instance."""
    global _loader
    if _loader is None:
        _loader = DataLoader()
    return _loader
