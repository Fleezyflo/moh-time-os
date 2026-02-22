"""
Commitment Manager - CRUD and linking for commitments.

Handles:
- Creating commitments from detected patterns
- Linking commitments to tasks
- Querying untracked/due commitments

Column mapping (dataclass -> DB):
    id          -> commitment_id
    source_type -> scope_ref_type
    source_id   -> scope_ref_id  (also source_id column exists for pipeline compat)
    text        -> commitment_text
    owner       -> speaker
    target_date -> due_at
    task_id     -> task_id
    updated_at  -> updated_at
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from lib.commitment_truth.detector import extract_all
from lib.state_store import get_store

logger = logging.getLogger(__name__)


@dataclass
class Commitment:
    id: str
    source_type: str
    source_id: str
    text: str
    owner: str | None
    target: str | None
    target_date: str | None
    status: str
    task_id: str | None
    confidence: float
    created_at: str
    updated_at: str


class CommitmentManager:
    """
    Manages commitments extracted from communications.

    Responsibilities:
    - Extract commitments from emails/messages
    - Link commitments to tasks
    - Query untracked/overdue commitments
    - Prevent duplicates
    """

    def __init__(self, store=None, db_path=None):
        if isinstance(store, str):
            # Handle case where store is actually a db_path
            db_path = store
            store = None
        self.store = store or get_store(db_path)

    def extract_commitments_from_email(
        self, email_id: str, email_text: str, sender: str = None, recipient: str = None
    ) -> list[Commitment]:
        """
        Extract and store commitments from an email.

        Args:
            email_id: Unique ID of the email
            email_text: Full text content
            sender: Email sender
            recipient: Email recipient

        Returns:
            List of created Commitment objects
        """
        # Check if we already processed this email
        existing = self.store.query(
            "SELECT commitment_id FROM commitments WHERE scope_ref_type = 'email' AND scope_ref_id = ?",
            [email_id],
        )
        if existing:
            return []

        # Extract commitments
        extracted = extract_all(email_text)
        created = []

        # Process promises
        for promise in extracted["promises"]:
            if promise["confidence"] < 0.7:
                continue

            commitment = self._create_commitment(
                source_type="email",
                source_id=email_id,
                text=promise["text"],
                owner=sender,
                target=recipient,
                target_date=promise["deadline"],
                confidence=promise["confidence"],
            )
            if commitment:
                created.append(commitment)

        # Process requests (as commitments expected from recipient)
        for request in extracted["requests"]:
            if request["confidence"] < 0.7:
                continue

            commitment = self._create_commitment(
                source_type="email",
                source_id=email_id,
                text=request["text"],
                owner=recipient,
                target=sender,
                target_date=request["deadline"],
                confidence=request["confidence"],
            )
            if commitment:
                created.append(commitment)

        return created

    def _create_commitment(
        self,
        source_type: str,
        source_id: str,
        text: str,
        owner: str = None,
        target: str = None,
        target_date: str = None,
        confidence: float = 0.8,
    ) -> Commitment | None:
        """Create a single commitment."""
        now = datetime.now().isoformat()
        commitment_id = f"commit_{uuid.uuid4().hex[:12]}"

        # Map to actual DB columns
        data = {
            "commitment_id": commitment_id,
            "scope_ref_type": source_type,
            "scope_ref_id": source_id,
            "committed_by_type": "person",
            "committed_by_id": owner or "",
            "commitment_text": text,
            "speaker": owner,
            "target": target,
            "due_at": target_date,
            "status": "open",
            "task_id": None,
            "confidence": confidence,
            "source_id": source_id,
            "created_at": now,
            "updated_at": now,
        }

        self.store.insert("commitments", data)

        return Commitment(
            id=commitment_id,
            source_type=source_type,
            source_id=source_id,
            text=text,
            owner=owner,
            target=target,
            target_date=target_date,
            status="open",
            task_id=None,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )

    def link_commitment_to_task(self, commitment_id: str, task_id: str) -> tuple[bool, str]:
        """
        Link a commitment to a task.

        Args:
            commitment_id: ID of the commitment
            task_id: ID of the task to link

        Returns:
            (success, message)
        """
        commitment = self.get_commitment(commitment_id)
        if not commitment:
            return False, "Commitment not found"

        task = self.store.get("tasks", task_id)
        if not task:
            return False, "Task not found"

        if commitment.task_id:
            return False, f"Commitment already linked to task {commitment.task_id}"

        now = datetime.now().isoformat()
        self.store.query(
            "UPDATE commitments SET task_id = ?, status = 'linked', updated_at = ? WHERE commitment_id = ?",
            [task_id, now, commitment_id],
        )

        return True, f"Linked commitment to task {task_id}"

    # Alias for API compat
    def link_to_task(self, commitment_id: str, task_id: str) -> bool:
        """Link a commitment to a task. Returns bool for API compat."""
        success, _ = self.link_commitment_to_task(commitment_id, task_id)
        return success

    def unlink_commitment(self, commitment_id: str) -> tuple[bool, str]:
        """Remove task link from a commitment."""
        commitment = self.get_commitment(commitment_id)
        if not commitment:
            return False, "Commitment not found"

        now = datetime.now().isoformat()
        self.store.query(
            "UPDATE commitments SET task_id = NULL, status = 'open', updated_at = ? WHERE commitment_id = ?",
            [now, commitment_id],
        )

        return True, "Commitment unlinked"

    def mark_done(self, commitment_id: str) -> tuple[bool, str]:
        """Mark a commitment as done."""
        now = datetime.now().isoformat()
        self.store.query(
            "UPDATE commitments SET status = 'done', updated_at = ? WHERE commitment_id = ?",
            [now, commitment_id],
        )
        return True, "Commitment marked done"

    def mark_broken(self, commitment_id: str) -> tuple[bool, str]:
        """Mark a commitment as broken (not fulfilled)."""
        now = datetime.now().isoformat()
        self.store.query(
            "UPDATE commitments SET status = 'broken', updated_at = ? WHERE commitment_id = ?",
            [now, commitment_id],
        )
        return True, "Commitment marked broken"

    def get_commitment(self, commitment_id: str) -> Commitment | None:
        """Get a single commitment by ID."""
        rows = self.store.query(
            "SELECT * FROM commitments WHERE commitment_id = ?", [commitment_id]
        )
        if not rows:
            return None
        return self._row_to_commitment(rows[0])

    def get_untracked_commitments(self, limit: int = 50) -> list[Commitment]:
        """
        Get commitments that aren't linked to any task.
        These need attention.
        """
        rows = self.store.query(
            """
            SELECT * FROM commitments
            WHERE status = 'open'
            AND (task_id IS NULL OR task_id = '')
            ORDER BY due_at ASC, confidence DESC
            LIMIT ?
        """,
            [limit],
        )

        return [self._row_to_commitment(r) for r in rows]

    def get_overdue(self) -> list[Commitment]:
        """Get overdue commitments (due before today, still open/linked)."""
        today = date.today().isoformat()
        rows = self.store.query(
            """
            SELECT * FROM commitments
            WHERE status IN ('open', 'linked')
            AND due_at IS NOT NULL
            AND due_at < ?
            ORDER BY due_at ASC
        """,
            [today],
        )
        return [self._row_to_commitment(r) for r in rows]

    def get_commitments_due(
        self, target_date: str = None, include_overdue: bool = True
    ) -> list[Commitment]:
        """
        Get commitments due on or before a date.

        Args:
            target_date: Date to check (defaults to today)
            include_overdue: Include past-due commitments
        """
        if not target_date:
            target_date = date.today().isoformat()

        if include_overdue:
            rows = self.store.query(
                """
                SELECT * FROM commitments
                WHERE status IN ('open', 'linked')
                AND due_at IS NOT NULL
                AND due_at <= ?
                ORDER BY due_at ASC
            """,
                [target_date],
            )
        else:
            rows = self.store.query(
                """
                SELECT * FROM commitments
                WHERE status IN ('open', 'linked')
                AND due_at = ?
                ORDER BY confidence DESC
            """,
                [target_date],
            )

        return [self._row_to_commitment(r) for r in rows]

    def get_commitments_by_owner(self, owner: str) -> list[Commitment]:
        """Get all open commitments owned by someone."""
        rows = self.store.query(
            """
            SELECT * FROM commitments
            WHERE speaker LIKE ?
            AND status IN ('open', 'linked')
            ORDER BY due_at ASC
        """,
            [f"%{owner}%"],
        )

        return [self._row_to_commitment(r) for r in rows]

    def get_commitments_for_task(self, task_id: str) -> list[Commitment]:
        """Get all commitments linked to a task."""
        rows = self.store.query("SELECT * FROM commitments WHERE task_id = ?", [task_id])
        return [self._row_to_commitment(r) for r in rows]

    def get_all_commitments(self, status: str = None, limit: int = 100) -> list[Commitment]:
        """Get all commitments with optional status filter."""
        if status:
            rows = self.store.query(
                "SELECT * FROM commitments WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                [status, limit],
            )
        else:
            rows = self.store.query(
                "SELECT * FROM commitments ORDER BY created_at DESC LIMIT ?", [limit]
            )
        return [self._row_to_commitment(r) for r in rows]

    def _row_to_commitment(self, row: dict) -> Commitment:
        """Convert database row to Commitment object.

        Maps actual DB columns to Commitment dataclass fields.
        """
        return Commitment(
            id=row.get("commitment_id", row.get("id", "")),
            source_type=row.get("scope_ref_type", row.get("source_type", "")),
            source_id=row.get("scope_ref_id", row.get("source_id", "")),
            text=row.get("commitment_text", row.get("text", "")),
            owner=row.get("speaker", row.get("owner")),
            target=row.get("target"),
            target_date=row.get("due_at", row.get("target_date")),
            status=row.get("status", "open"),
            task_id=row.get("task_id"),
            confidence=row.get("confidence", 0.8),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )

    def get_summary(self) -> dict:
        """Get summary statistics for commitments."""
        total = self.store.query("SELECT COUNT(*) as c FROM commitments")[0]["c"]
        open_count = self.store.query(
            "SELECT COUNT(*) as c FROM commitments WHERE status = 'open'"
        )[0]["c"]
        linked = self.store.query("SELECT COUNT(*) as c FROM commitments WHERE status = 'linked'")[
            0
        ]["c"]
        done = self.store.query("SELECT COUNT(*) as c FROM commitments WHERE status = 'done'")[0][
            "c"
        ]
        broken = self.store.query("SELECT COUNT(*) as c FROM commitments WHERE status = 'broken'")[
            0
        ]["c"]

        overdue = self.store.query("""
            SELECT COUNT(*) as c FROM commitments
            WHERE status IN ('open', 'linked')
            AND due_at < date('now')
        """)[0]["c"]

        return {
            "total": total,
            "open": open_count,
            "linked": linked,
            "done": done,
            "broken": broken,
            "overdue": overdue,
            "untracked": open_count,
        }
