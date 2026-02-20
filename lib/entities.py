"""Entity classes for Clients, People, Projects."""

import json
import uuid
from dataclasses import dataclass, field

from .store import get_connection, now_iso

# ============================================================================
# CLIENT
# ============================================================================


@dataclass
class Client:
    id: str
    name: str
    tier: str  # A, B, C
    type: str = "agency_client"

    # Financial
    annual_value: float = 0
    ar_outstanding: float = 0
    ar_aging: str = "Current"
    payment_pattern: str = "Unknown"

    # Relationship
    health: str = "good"
    trend: str = "stable"
    last_interaction: str = None
    relationship_notes: str = ""

    # References
    contacts: list[dict] = field(default_factory=list)
    active_projects: list[str] = field(default_factory=list)

    # External IDs
    xero_contact_id: str = None

    created_at: str = None
    updated_at: str = None

    def summary(self) -> str:
        """One-line summary for context snapshots."""
        return f"{self.name} (Tier {self.tier}, {self.health}, AR: {self.ar_aging})"

    def full_context(self) -> str:
        """Full context for surfacing."""
        parts = [f"{self.name} — Tier {self.tier} client"]
        if self.annual_value:
            parts.append(f"{self.annual_value:,.0f} AED annual")
        parts.append(f"Relationship: {self.health} ({self.trend})")
        if self.ar_outstanding:
            parts.append(f"AR: {self.ar_outstanding:,.0f} AED ({self.ar_aging})")
        if self.relationship_notes:
            parts.append(self.relationship_notes)
        return ". ".join(parts)

    def to_snapshot(self) -> dict:
        """Create snapshot dict for item context."""
        return {
            "id": self.id,
            "name": self.name,
            "tier": self.tier,
            "health": self.health,
            "ar_aging": self.ar_aging,
            "ar_outstanding": self.ar_outstanding,
            "summary": self.summary(),
            "full": self.full_context(),
        }


def create_client(name: str, tier: str, **kwargs) -> str:
    """Create a new client. Returns client ID."""
    client_id = kwargs.get("id") or str(uuid.uuid4())
    now = now_iso()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO clients (
                id, name, tier, type,
                financial_annual_value, financial_ar_outstanding,
                financial_ar_aging, financial_payment_pattern,
                relationship_health, relationship_trend,
                relationship_last_interaction, relationship_notes,
                contacts_json, active_projects_json,
                xero_contact_id,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                client_id,
                name,
                tier,
                kwargs.get("type", "agency_client"),
                kwargs.get("annual_value", 0),
                kwargs.get("ar_outstanding", 0),
                kwargs.get("ar_aging", "Current"),
                kwargs.get("payment_pattern", "Unknown"),
                kwargs.get("health", "good"),
                kwargs.get("trend", "stable"),
                kwargs.get("last_interaction"),
                kwargs.get("relationship_notes", ""),
                json.dumps(kwargs.get("contacts", [])),
                json.dumps(kwargs.get("active_projects", [])),
                kwargs.get("xero_contact_id"),
                now,
                now,
            ),
        )

    return client_id


def get_client(client_id: str) -> Client | None:
    """Get client by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()

        if not row:
            return None

        return _row_to_client(row)


def _row_to_client(row) -> Client:
    """Convert database row to Client object."""
    return Client(
        id=row["id"],
        name=row["name"],
        tier=row["tier"],
        type=row["type"] or "agency_client",
        annual_value=row["financial_annual_value"] or 0,
        ar_outstanding=row["financial_ar_outstanding"] or 0,
        ar_aging=row["financial_ar_aging"] or "Current",
        payment_pattern=row["financial_payment_pattern"] or "Unknown",
        health=row["relationship_health"] or "good",
        trend=row["relationship_trend"] or "stable",
        last_interaction=row["relationship_last_interaction"],
        relationship_notes=row["relationship_notes"] or "",
        contacts=json.loads(row["contacts_json"] or "[]"),
        active_projects=json.loads(row["active_projects_json"] or "[]"),
        xero_contact_id=row["xero_contact_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def find_client(name: str = None, xero_id: str = None) -> Client | None:
    """Find client by name (fuzzy) or xero_contact_id."""
    with get_connection() as conn:
        if xero_id:
            row = conn.execute(
                "SELECT * FROM clients WHERE xero_contact_id = ? LIMIT 1", (xero_id,)
            ).fetchone()
        elif name:
            # Try exact match first
            row = conn.execute(
                "SELECT * FROM clients WHERE LOWER(name) = LOWER(?) LIMIT 1", (name,)
            ).fetchone()
            # Then fuzzy
            if not row:
                row = conn.execute(
                    "SELECT * FROM clients WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
                    (f"%{name}%",),
                ).fetchone()
        else:
            return None

        if row:
            return _row_to_client(row)
        return None


def update_client_interaction(client_id: str) -> bool:
    """Update last_interaction to now."""
    from .store import now_iso

    return update_client(client_id, last_interaction=now_iso())


def update_client_active_projects(client_id: str) -> int:
    """Update client's active_projects field from projects table. Returns count."""
    projects = list_projects(client_id=client_id, status="active")
    project_refs = [{"id": p.id, "name": p.name} for p in projects]
    update_client(client_id, active_projects=project_refs)
    return len(project_refs)


def refresh_all_client_projects() -> dict[str, int]:
    """Refresh active_projects for all clients. Returns {client_name: count}."""
    results = {}
    for client in list_clients(limit=500):
        count = update_client_active_projects(client.id)
        if count > 0:
            results[client.name] = count
    return results


def update_client(client_id: str, **changes) -> bool:
    """Update client fields."""
    field_map = {
        "annual_value": "financial_annual_value",
        "ar_outstanding": "financial_ar_outstanding",
        "ar_aging": "financial_ar_aging",
        "payment_pattern": "financial_payment_pattern",
        "health": "relationship_health",
        "trend": "relationship_trend",
        "last_interaction": "relationship_last_interaction",
        "relationship_notes": "relationship_notes",
    }

    updates = {}
    for k, v in changes.items():
        col = field_map.get(k, k)
        if col in ["contacts", "active_projects"]:
            updates[col + "_json"] = json.dumps(v)
        else:
            updates[col] = v

    if not updates:
        return False

    updates["updated_at"] = now_iso()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [client_id]

    with get_connection() as conn:
        cursor = conn.execute(f"UPDATE clients SET {set_clause} WHERE id = ?", values)
        return cursor.rowcount > 0


def list_clients(tier: str = None, health: str = None, limit: int = 500) -> list[Client]:
    """List clients with optional filters."""
    conditions = []
    params = []

    if tier:
        conditions.append("tier = ?")
        params.append(tier)
    if health:
        conditions.append("relationship_health = ?")
        params.append(health)

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM clients WHERE {where} ORDER BY tier, name LIMIT ?", params
        ).fetchall()

        return [_row_to_client(row) for row in rows]


def upsert_client(name: str, tier: str, xero_contact_id: str = None, **kwargs) -> str:
    """Create or update client. Returns client ID."""
    existing = None
    if xero_contact_id:
        existing = find_client(xero_id=xero_contact_id)
    if not existing:
        existing = find_client(name=name)

    if existing:
        update_client(existing.id, tier=tier, xero_contact_id=xero_contact_id, **kwargs)
        return existing.id
    return create_client(name, tier, xero_contact_id=xero_contact_id, **kwargs)


# ============================================================================
# PERSON
# ============================================================================


@dataclass
class Person:
    id: str
    name: str
    email: str = None
    phone: str = None

    type: str = "external"  # internal | external
    company: str = None
    client_id: str = None
    role: str = None
    department: str = None

    trust: str = "unknown"
    style: str = None
    responsiveness: str = None
    relationship_notes: str = ""

    reliability_rate: float = None
    reliability_notes: str = None

    last_interaction: str = None
    created_at: str = None
    updated_at: str = None

    def summary(self) -> str:
        """One-line summary."""
        parts = [self.name]
        if self.role:
            parts.append(self.role)
        if self.company:
            parts.append(f"@ {self.company}")
        return ", ".join(parts)

    def full_context(self) -> str:
        """Full context for surfacing."""
        parts = [f"{self.name}"]
        if self.role:
            parts.append(f"({self.role})")
        if self.company:
            parts.append(f"at {self.company}")
        if self.relationship_notes:
            parts.append(f"— {self.relationship_notes}")
        return " ".join(parts)

    def to_snapshot(self) -> dict:
        """Create snapshot dict for item context."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "company": self.company,
            "summary": self.summary(),
            "full": self.full_context(),
        }


def create_person(name: str, **kwargs) -> str:
    """Create a new person. Returns person ID."""
    person_id = kwargs.get("id") or str(uuid.uuid4())
    now = now_iso()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO people (
                id, name, email, phone, type, company, client_id,
                role, department, relationship_trust, relationship_style,
                relationship_responsiveness, relationship_notes,
                reliability_rate, reliability_notes,
                last_interaction, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                person_id,
                name,
                kwargs.get("email"),
                kwargs.get("phone"),
                kwargs.get("type", "external"),
                kwargs.get("company"),
                kwargs.get("client_id"),
                kwargs.get("role"),
                kwargs.get("department"),
                kwargs.get("trust", "unknown"),
                kwargs.get("style"),
                kwargs.get("responsiveness"),
                kwargs.get("relationship_notes", ""),
                kwargs.get("reliability_rate"),
                kwargs.get("reliability_notes"),
                kwargs.get("last_interaction"),
                now,
                now,
            ),
        )

    return person_id


def get_person(person_id: str) -> Person | None:
    """Get person by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()

        if not row:
            return None

        return _row_to_person(row)


def _row_to_person(row) -> Person:
    """Convert database row to Person object."""
    return Person(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        phone=row["phone"],
        type=row["type"] or "external",
        company=row["company"],
        client_id=row["client_id"],
        role=row["role"],
        department=row["department"],
        trust=row["relationship_trust"] or "unknown",
        style=row["relationship_style"],
        responsiveness=row["relationship_responsiveness"],
        relationship_notes=row["relationship_notes"] or "",
        reliability_rate=row["reliability_rate"],
        reliability_notes=row["reliability_notes"],
        last_interaction=row["last_interaction"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def find_person(name: str = None, email: str = None) -> Person | None:
    """Find person by name or email."""
    with get_connection() as conn:
        row = None
        if email:
            row = conn.execute(
                "SELECT * FROM people WHERE LOWER(email) = LOWER(?) LIMIT 1", (email,)
            ).fetchone()

        if not row and name:
            # Exact match first
            row = conn.execute(
                "SELECT * FROM people WHERE LOWER(name) = LOWER(?) LIMIT 1", (name,)
            ).fetchone()
            # Fuzzy
            if not row:
                row = conn.execute(
                    "SELECT * FROM people WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
                    (f"%{name}%",),
                ).fetchone()

        if row:
            return _row_to_person(row)
        return None


def update_person_interaction(person_id: str) -> bool:
    """Update last_interaction to now."""
    from .store import now_iso

    return update_person(person_id, last_interaction=now_iso())


def update_person(person_id: str, **changes) -> bool:
    """Update person fields."""
    field_map = {
        "trust": "relationship_trust",
        "style": "relationship_style",
        "responsiveness": "relationship_responsiveness",
        "relationship_notes": "relationship_notes",
    }

    updates = {}
    for k, v in changes.items():
        col = field_map.get(k, k)
        updates[col] = v

    if not updates:
        return False

    updates["updated_at"] = now_iso()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [person_id]

    with get_connection() as conn:
        cursor = conn.execute(f"UPDATE people SET {set_clause} WHERE id = ?", values)
        return cursor.rowcount > 0


def list_people(type: str = None, client_id: str = None, limit: int = 500) -> list[Person]:
    """List people with optional filters."""
    conditions = []
    params = []

    if type:
        conditions.append("type = ?")
        params.append(type)
    if client_id:
        conditions.append("client_id = ?")
        params.append(client_id)

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM people WHERE {where} ORDER BY name LIMIT ?", params
        ).fetchall()

        return [_row_to_person(row) for row in rows]


def upsert_person(name: str, email: str = None, **kwargs) -> str:
    """Create or update person. Returns person ID."""
    existing = None
    if email:
        existing = find_person(email=email)
    if not existing:
        existing = find_person(name=name)

    if existing:
        update_person(existing.id, email=email, **kwargs)
        return existing.id
    return create_person(name, email=email, **kwargs)


# ============================================================================
# PROJECT
# ============================================================================


@dataclass
class Project:
    id: str
    name: str
    client_id: str

    status: str = "active"
    health: str = "on_track"

    start_date: str = None
    target_end_date: str = None

    value: float = None
    stakes: str = ""
    description: str = ""

    milestones: list[dict] = field(default_factory=list)
    blockers: list[dict] = field(default_factory=list)
    team: list[dict] = field(default_factory=list)

    asana_project_id: str = None

    created_at: str = None
    updated_at: str = None

    def summary(self) -> str:
        """One-line summary."""
        return f"{self.name} ({self.status}, {self.health})"

    def full_context(self) -> str:
        """Full context."""
        parts = [f"{self.name} — {self.status}, {self.health}"]
        if self.value:
            parts.append(f"Value: {self.value:,.0f} AED")
        if self.stakes:
            parts.append(f"Stakes: {self.stakes}")
        if self.target_end_date:
            parts.append(f"Due: {self.target_end_date}")
        return ". ".join(parts)

    def to_snapshot(self) -> dict:
        """Create snapshot dict for item context."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "health": self.health,
            "stakes": self.stakes,
            "summary": self.summary(),
            "full": self.full_context(),
        }


def create_project(name: str, client_id: str = None, **kwargs) -> str:
    """Create a new project. Returns project ID."""
    project_id = kwargs.get("id") or str(uuid.uuid4())
    now = now_iso()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (
                id, name, client_id, source, source_id,
                status, health, deadline, owner,
                is_internal, type,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                project_id,
                name,
                client_id,
                kwargs.get("source", "manual"),
                kwargs.get("source_id"),
                kwargs.get("status", "active"),
                kwargs.get("health", "green"),
                kwargs.get("deadline"),
                kwargs.get("owner"),
                kwargs.get("is_internal", 0),
                kwargs.get("type", "project"),
                now,
                now,
            ),
        )

    return project_id


def get_project(project_id: str) -> Project | None:
    """Get project by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()

        if not row:
            return None

        return _row_to_project(row)


def _row_to_project(row) -> Project:
    """Convert database row to Project object."""
    # Handle both column naming schemes (v2: *_json, state: no suffix)
    row_dict = dict(row)
    milestones_raw = row_dict.get("milestones_json") or row_dict.get("milestones") or "[]"
    blockers_raw = row_dict.get("blockers_json") or row_dict.get("blockers") or "[]"
    team_raw = row_dict.get("team_json") or row_dict.get("team") or "[]"

    return Project(
        id=row["id"],
        name=row["name"],
        client_id=row_dict.get("client_id"),
        status=row_dict.get("status") or "active",
        health=row_dict.get("health") or "on_track",
        start_date=row_dict.get("start_date"),
        target_end_date=row_dict.get("target_end_date"),
        value=row_dict.get("value"),
        stakes=row_dict.get("stakes") or "",
        description=row_dict.get("description") or "",
        milestones=json.loads(milestones_raw)
        if isinstance(milestones_raw, str)
        else milestones_raw or [],
        blockers=json.loads(blockers_raw) if isinstance(blockers_raw, str) else blockers_raw or [],
        team=json.loads(team_raw) if isinstance(team_raw, str) else team_raw or [],
        asana_project_id=row_dict.get("asana_project_id"),
        created_at=row_dict.get("created_at"),
        updated_at=row_dict.get("updated_at"),
    )


def find_project(name: str = None, client_id: str = None, asana_id: str = None) -> Project | None:
    """Find project by name, client, or asana_project_id (source_id)."""
    with get_connection() as conn:
        row = None

        if asana_id:
            # Try source_id first (new schema), fallback to asana_project_id (old schema)
            row = conn.execute(
                "SELECT * FROM projects WHERE source_id = ? OR source_id = ? LIMIT 1",
                (asana_id, asana_id),
            ).fetchone()

        if not row and name:
            row = conn.execute(
                "SELECT * FROM projects WHERE LOWER(name) = LOWER(?) LIMIT 1", (name,)
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT * FROM projects WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
                    (f"%{name}%",),
                ).fetchone()

        if not row and client_id:
            row = conn.execute(
                "SELECT * FROM projects WHERE client_id = ? AND status = 'active' LIMIT 1",
                (client_id,),
            ).fetchone()

        if row:
            return _row_to_project(row)
        return None


def update_project(project_id: str, **changes) -> bool:
    """Update project fields."""
    updates = {}
    for k, v in changes.items():
        if k in ["milestones", "blockers", "team"]:
            updates[k + "_json"] = json.dumps(v)
        else:
            updates[k] = v

    if not updates:
        return False

    updates["updated_at"] = now_iso()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [project_id]

    with get_connection() as conn:
        cursor = conn.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)
        return cursor.rowcount > 0


def list_projects(
    client_id: str = None, status: str = None, health: str = None, limit: int = 500
) -> list[Project]:
    """List projects with optional filters."""
    conditions = []
    params = []

    if client_id:
        conditions.append("client_id = ?")
        params.append(client_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if health:
        conditions.append("health = ?")
        params.append(health)

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM projects WHERE {where} ORDER BY name LIMIT ?", params
        ).fetchall()

        return [_row_to_project(row) for row in rows]


def upsert_project(name: str, client_id: str, asana_project_id: str = None, **kwargs) -> str:
    """Create or update project. Returns project ID."""
    existing = None
    if asana_project_id:
        existing = find_project(asana_id=asana_project_id)
    if not existing:
        existing = find_project(name=name, client_id=client_id)

    if existing:
        update_project(existing.id, asana_project_id=asana_project_id, **kwargs)
        return existing.id
    return create_project(name, client_id, asana_project_id=asana_project_id, **kwargs)
