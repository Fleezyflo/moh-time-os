"""Item tracking with full context capture."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import date

from .entities import get_client, get_person, get_project
from .store import get_connection, now_iso


@dataclass
class ContextSnapshot:
    """Captured context at item creation time."""

    client: dict = None
    project: dict = None
    person: dict = None
    stakes: str = ""
    history: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "client": self.client,
                "project": self.project,
                "person": self.person,
                "stakes": self.stakes,
                "history": self.history,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> "ContextSnapshot":
        if not data:
            return cls()
        try:
            d = json.loads(data)
            return cls(**d)
        except (json.JSONDecodeError, TypeError):
            return cls()

    def summary(self) -> str:
        """One-line context summary."""
        parts = []
        if self.person:
            parts.append(self.person.get("summary", ""))
        if self.client:
            parts.append(self.client.get("summary", ""))
        if self.stakes:
            parts.append(self.stakes)
        return " — ".join(filter(None, parts))

    def has_context(self) -> bool:
        """Check if any context is present."""
        return bool(self.client or self.project or self.person or self.stakes or self.history)


@dataclass
class Item:
    id: str
    what: str
    status: str  # open, waiting, done, cancelled

    owner: str
    owner_id: str = None
    counterparty: str = None
    counterparty_id: str = None

    due: str = None
    waiting_since: str = None

    client_id: str = None
    project_id: str = None
    context: ContextSnapshot = None

    source_type: str = None
    source_ref: str = None
    captured_at: str = None

    resolution_outcome: str = None
    resolution_notes: str = None
    resolved_at: str = None

    created_at: str = None
    updated_at: str = None

    history: list[dict] = field(default_factory=list)

    def is_overdue(self) -> bool:
        """Check if item is overdue."""
        if not self.due or self.status != "open":
            return False
        return self.due < date.today().isoformat()

    def days_overdue(self) -> int:
        """Days overdue (0 if not overdue)."""
        if not self.is_overdue():
            return 0
        due_date = date.fromisoformat(self.due)
        return (date.today() - due_date).days

    def is_due_soon(self, days: int = 3) -> bool:
        """Check if due within N days."""
        if not self.due or self.status != "open":
            return False
        due_date = date.fromisoformat(self.due)
        today = date.today()
        return today <= due_date <= date.fromordinal(today.toordinal() + days)

    def short_display(self) -> str:
        """Short one-line display."""
        parts = [self.what]
        if self.due:
            if self.is_overdue():
                parts.append(f"⚠️ {self.days_overdue()}d overdue")
            else:
                parts.append(f"due {self.due}")
        if self.counterparty:
            parts.append(f"({self.counterparty})")
        return " — ".join(parts)

    def full_context_display(self) -> str:
        """Full context for surfacing (structured format)."""
        lines = [f"**{self.what}**"]

        if self.due:
            if self.is_overdue():
                lines.append(f"⚠️ OVERDUE by {self.days_overdue()} days (was due {self.due})")
            else:
                lines.append(f"Due: {self.due}")

        if self.context and self.context.has_context():
            if self.context.person:
                lines.append(
                    f"Who: {self.context.person.get('full', self.context.person.get('name', ''))}"
                )
            if self.context.client:
                lines.append(
                    f"Client: {self.context.client.get('full', self.context.client.get('name', ''))}"
                )
            if self.context.project:
                lines.append(
                    f"Project: {self.context.project.get('full', self.context.project.get('name', ''))}"
                )
            if self.context.stakes:
                lines.append(f"Stakes: {self.context.stakes}")
            if self.context.history:
                lines.append(f"History: {self.context.history}")

        if self.status == "waiting":
            lines.append(f"⏳ Waiting since {self.waiting_since}")

        return "\n".join(lines)

    def synthesize(self, refresh_context: bool = False) -> str:
        """
        Synthesize a natural language summary with full context.

        This is the "intelligence" - producing output like:
        "Dana's proposal is due tomorrow. She's Head of Marketing at SSS —
        Tier A client, 890K annual, AR current, relationship is good.
        This is for the Ramadan campaign (200K, flagship Q1)."

        Args:
            refresh_context: If True, refresh entity state from DB
        """
        parts = []

        # What + when
        if self.is_overdue():
            parts.append(f"**{self.what}** is {self.days_overdue()} days overdue.")
        elif self.due:
            due_date = date.fromisoformat(self.due)
            days_until = (due_date - date.today()).days
            if days_until == 0:
                parts.append(f"**{self.what}** is due today.")
            elif days_until == 1:
                parts.append(f"**{self.what}** is due tomorrow.")
            elif days_until <= 7:
                parts.append(f"**{self.what}** is due in {days_until} days ({self.due}).")
            else:
                parts.append(f"**{self.what}** is due {self.due}.")
        else:
            parts.append(f"**{self.what}** (no due date).")

        # Person context
        if self.context and self.context.person:
            person = self.context.person
            name = person.get("name", self.counterparty or "Unknown")
            role = person.get("role", "")
            company = person.get("company", "")

            if role and company:
                parts.append(f"{name} is {role} at {company}.")
            elif role:
                parts.append(f"{name} ({role}).")
            elif company:
                parts.append(f"{name} at {company}.")

        # Client context - refresh if requested
        client_info = self.context.client if self.context else None
        if refresh_context and self.client_id:
            client = get_client(self.client_id)
            if client:
                client_info = client.to_snapshot()

        if client_info:
            tier = client_info.get("tier", "C")
            name = client_info.get("name", "Unknown")
            health = client_info.get("health", "unknown")
            ar = client_info.get("ar_outstanding", 0)
            ar_aging = client_info.get("ar_aging", "Current")

            client_desc = f"Tier {tier} client"
            if ar > 0:
                client_desc += f", {ar:,.0f} AED AR ({ar_aging})"
            client_desc += f", relationship {health}"

            parts.append(f"{name} — {client_desc}.")

        # Project context
        if self.context and self.context.project:
            project = self.context.project
            name = project.get("name", "Unknown")
            status = project.get("status", "")
            stakes = project.get("stakes", "")

            if stakes:
                parts.append(f"Project: {name}. Stakes: {stakes}.")
            else:
                parts.append(f"Project: {name} ({status}).")

        # Stakes and history
        if self.context:
            if self.context.stakes and self.context.stakes not in " ".join(parts):
                parts.append(f"Stakes: {self.context.stakes}.")
            if self.context.history:
                parts.append(f"Background: {self.context.history}.")

        # Waiting status
        if self.status == "waiting" and self.waiting_since:
            parts.append(f"⏳ Waiting since {self.waiting_since}.")

        return " ".join(parts)


def build_context(
    client_id: str = None,
    project_id: str = None,
    counterparty_id: str = None,
    stakes: str = "",
    history: str = "",
) -> ContextSnapshot:
    """Build context snapshot from entity IDs."""
    context = ContextSnapshot(stakes=stakes, history=history)

    if client_id:
        client = get_client(client_id)
        if client:
            context.client = client.to_snapshot()

    if project_id:
        project = get_project(project_id)
        if project:
            context.project = project.to_snapshot()

    if counterparty_id:
        person = get_person(counterparty_id)
        if person:
            context.person = person.to_snapshot()

    return context


def create_item(
    what: str,
    owner: str,
    due: str = None,
    owner_id: str = None,
    counterparty: str = None,
    counterparty_id: str = None,
    client_id: str = None,
    project_id: str = None,
    stakes: str = "",
    history: str = "",
    source_type: str = "manual",
    source_ref: str = None,
    captured_by: str = "A",
) -> str:
    """Create item with full context. Returns item ID."""

    if not what or not what.strip():
        raise ValueError("'what' is required")
    if not owner or not owner.strip():
        raise ValueError("'owner' is required")

    item_id = str(uuid.uuid4())
    now = now_iso()

    # Build context snapshot
    context = build_context(
        client_id=client_id,
        project_id=project_id,
        counterparty_id=counterparty_id,
        stakes=stakes,
        history=history,
    )

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO items (
                id, what, status, owner, owner_id,
                counterparty, counterparty_id, due, waiting_since,
                client_id, project_id, context_snapshot_json,
                stakes, history_context,
                source_type, source_ref, captured_at,
                created_at, updated_at
            ) VALUES (?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                item_id,
                what.strip(),
                owner.strip(),
                owner_id,
                counterparty,
                counterparty_id,
                due,
                None,
                client_id,
                project_id,
                context.to_json(),
                stakes,
                history,
                source_type,
                source_ref,
                now,
                now,
                now,
            ),
        )

        # Record in history
        conn.execute(
            """
            INSERT INTO item_history (id, item_id, timestamp, change, changed_by)
            VALUES (?, ?, ?, 'Created', ?)
        """,
            (str(uuid.uuid4()), item_id, now, captured_by),
        )

    return item_id


def get_item(item_id: str, include_history: bool = False) -> Item | None:
    """Get item by ID with context."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

        if not row:
            return None

        item = _row_to_item(row)

        if include_history:
            history = conn.execute(
                """
                SELECT timestamp, change, changed_by
                FROM item_history WHERE item_id = ?
                ORDER BY timestamp ASC
            """,
                (item_id,),
            ).fetchall()
            item.history = [dict(h) for h in history]

        return item


def _row_to_item(row) -> Item:
    """Convert database row to Item object."""
    return Item(
        id=row["id"],
        what=row["what"],
        status=row["status"],
        owner=row["owner"],
        owner_id=row["owner_id"],
        counterparty=row["counterparty"],
        counterparty_id=row["counterparty_id"],
        due=row["due"],
        waiting_since=row["waiting_since"],
        client_id=row["client_id"],
        project_id=row["project_id"],
        context=ContextSnapshot.from_json(row["context_snapshot_json"]),
        source_type=row["source_type"],
        source_ref=row["source_ref"],
        captured_at=row["captured_at"],
        resolution_outcome=row["resolution_outcome"],
        resolution_notes=row["resolution_notes"],
        resolved_at=row["resolved_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def update_item(item_id: str, changed_by: str = "A", **changes) -> bool:
    """Update item. Tracks history."""

    valid_fields = {
        "what",
        "status",
        "owner",
        "counterparty",
        "due",
        "stakes",
        "resolution_outcome",
        "resolution_notes",
        "client_id",
        "project_id",
        "counterparty_id",
    }

    updates = {k: v for k, v in changes.items() if k in valid_fields}
    if not updates:
        return False

    now = now_iso()

    # Handle status transitions
    if "status" in updates:
        new_status = updates["status"]
        if new_status not in ("open", "waiting", "done", "cancelled"):
            raise ValueError(f"Invalid status: {new_status}")

        if new_status == "waiting":
            updates["waiting_since"] = now
        elif new_status in ("done", "cancelled"):
            updates["resolved_at"] = now

    updates["updated_at"] = now

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [item_id]

    with get_connection() as conn:
        cursor = conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", values)

        if cursor.rowcount == 0:
            return False

        # Record history
        change_desc = ", ".join(f"{k}→{v}" for k, v in changes.items() if k in valid_fields)
        conn.execute(
            """
            INSERT INTO item_history (id, item_id, timestamp, change, changed_by)
            VALUES (?, ?, ?, ?, ?)
        """,
            (str(uuid.uuid4()), item_id, now, change_desc, changed_by),
        )

    return True


def mark_done(item_id: str, notes: str = None, changed_by: str = "A") -> bool:
    """Mark item as done."""
    updates = {
        "status": "done",
        "resolution_outcome": "completed",
    }
    if notes:
        updates["resolution_notes"] = notes
    return update_item(item_id, changed_by=changed_by, **updates)


def mark_waiting(item_id: str, changed_by: str = "A") -> bool:
    """Mark item as waiting on someone."""
    return update_item(item_id, status="waiting", changed_by=changed_by)


def mark_cancelled(item_id: str, notes: str = None, changed_by: str = "A") -> bool:
    """Cancel an item."""
    updates = {
        "status": "cancelled",
        "resolution_outcome": "cancelled",
    }
    if notes:
        updates["resolution_notes"] = notes
    return update_item(item_id, changed_by=changed_by, **updates)


def reopen_item(item_id: str, changed_by: str = "A") -> bool:
    """Reopen a done/cancelled item."""
    return update_item(
        item_id,
        status="open",
        resolution_outcome=None,
        resolution_notes=None,
        changed_by=changed_by,
    )


def list_items(
    status: str = None,
    due_before: str = None,
    due_after: str = None,
    client_id: str = None,
    project_id: str = None,
    owner: str = None,
    limit: int = 100,
) -> list[Item]:
    """Query items with filters."""

    conditions = []
    params = []

    if status:
        conditions.append("status = ?")
        params.append(status)

    if due_before:
        conditions.append("due IS NOT NULL AND due <= ?")
        params.append(due_before)

    if due_after:
        conditions.append("due IS NOT NULL AND due >= ?")
        params.append(due_after)

    if client_id:
        conditions.append("client_id = ?")
        params.append(client_id)

    if project_id:
        conditions.append("project_id = ?")
        params.append(project_id)

    if owner:
        conditions.append("owner = ?")
        params.append(owner)

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(min(limit, 500))

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM items
            WHERE {where}
            ORDER BY
                CASE WHEN due IS NULL THEN 1 ELSE 0 END,
                due ASC,
                created_at DESC
            LIMIT ?
        """,
            params,
        ).fetchall()

        return [_row_to_item(row) for row in rows]
