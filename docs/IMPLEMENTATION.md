# MOH Time OS — Implementation

> Complete code for the system.

---

## Directory Structure

```
moh_time_os/
├── config/
│   └── settings.yaml
├── data/
│   ├── moh_time_os.db
│   └── backups/
├── lib/
│   ├── __init__.py
│   ├── store.py          # Database connection, schema
│   ├── entities.py       # Client, Person, Project classes
│   ├── items.py          # Item CRUD + context capture
│   ├── queries.py        # Query helpers
│   ├── health.py         # Health checks, self-healing
│   └── backup.py         # Backup/restore
├── docs/
│   ├── SYSTEM_DESIGN.md
│   └── IMPLEMENTATION.md
└── tests/
    └── test_all.py
```

---

## store.py — Database Layer

```python
"""Database connection and schema management."""

import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

log = logging.getLogger("moh_time_os")

DB_PATH = Path(__file__).parent.parent / "data" / "moh_time_os.db"

SCHEMA = """
-- Clients
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tier TEXT CHECK (tier IN ('A', 'B', 'C')),
    type TEXT,

    financial_annual_value REAL,
    financial_ar_outstanding REAL,
    financial_ar_aging TEXT,
    financial_payment_pattern TEXT,

    relationship_health TEXT CHECK (relationship_health IN
        ('excellent', 'good', 'fair', 'poor', 'critical')),
    relationship_trend TEXT CHECK (relationship_trend IN
        ('improving', 'stable', 'declining')),
    relationship_last_interaction TEXT,
    relationship_notes TEXT,

    contacts_json TEXT,
    active_projects_json TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- People
CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,

    type TEXT CHECK (type IN ('internal', 'external')),
    company TEXT,
    client_id TEXT REFERENCES clients(id),
    role TEXT,
    department TEXT,

    relationship_trust TEXT CHECK (relationship_trust IN
        ('high', 'medium', 'low', 'unknown')),
    relationship_style TEXT,
    relationship_responsiveness TEXT,
    relationship_notes TEXT,

    reliability_rate REAL,
    reliability_notes TEXT,

    last_interaction TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    client_id TEXT REFERENCES clients(id),

    status TEXT CHECK (status IN
        ('discovery', 'active', 'delivery', 'on_hold', 'completed', 'cancelled')),
    health TEXT CHECK (health IN
        ('on_track', 'at_risk', 'blocked', 'late')),

    start_date TEXT,
    target_end_date TEXT,

    value REAL,
    stakes TEXT,
    description TEXT,

    milestones_json TEXT,
    blockers_json TEXT,
    team_json TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Items
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    what TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'waiting', 'done', 'cancelled')),

    owner TEXT NOT NULL,
    owner_id TEXT REFERENCES people(id),
    counterparty TEXT,
    counterparty_id TEXT REFERENCES people(id),

    due TEXT,
    waiting_since TEXT,

    client_id TEXT REFERENCES clients(id),
    project_id TEXT REFERENCES projects(id),
    context_snapshot_json TEXT,
    stakes TEXT,
    history_context TEXT,

    source_type TEXT,
    source_ref TEXT,
    captured_at TEXT NOT NULL,

    resolution_outcome TEXT,
    resolution_notes TEXT,
    resolved_at TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Item History
CREATE TABLE IF NOT EXISTS item_history (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES items(id),
    timestamp TEXT NOT NULL,
    change TEXT NOT NULL,
    changed_by TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_clients_tier ON clients(tier);
CREATE INDEX IF NOT EXISTS idx_clients_health ON clients(relationship_health);
CREATE INDEX IF NOT EXISTS idx_people_type ON people(type);
CREATE INDEX IF NOT EXISTS idx_people_client ON people(client_id);
CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_due ON items(due);
CREATE INDEX IF NOT EXISTS idx_items_client ON items(client_id);
CREATE INDEX IF NOT EXISTS idx_items_owner ON items(owner);
CREATE INDEX IF NOT EXISTS idx_history_item ON item_history(item_id);
"""

def init_db():
    """Initialize database with schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    log.info(f"Database initialized at {DB_PATH}")

@contextmanager
def get_connection():
    """Get database connection with auto-commit/rollback."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

def now_iso():
    """Current UTC time in ISO format."""
    return datetime.utcnow().isoformat() + "Z"
```

---

## entities.py — Client, Person, Project

```python
"""Entity classes for Clients, People, Projects."""

import uuid
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from .store import get_connection, now_iso

# ============ CLIENT ============

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
    contacts: List[Dict] = field(default_factory=list)
    active_projects: List[str] = field(default_factory=list)

    created_at: str = None
    updated_at: str = None

    def summary(self) -> str:
        """One-line summary for context snapshots."""
        return f"{self.name} (Tier {self.tier}, {self.health}, AR: {self.ar_aging})"

    def full_context(self) -> str:
        """Full context for surfacing."""
        return (
            f"{self.name} — Tier {self.tier} client, "
            f"{self.annual_value:,.0f} AED annual. "
            f"Relationship: {self.health} ({self.trend}). "
            f"AR: {self.ar_outstanding:,.0f} AED ({self.ar_aging}). "
            f"{self.relationship_notes}"
        ).strip()


def create_client(name: str, tier: str, **kwargs) -> str:
    """Create a new client. Returns client ID."""
    client_id = str(uuid.uuid4())
    now = now_iso()

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO clients (
                id, name, tier, type,
                financial_annual_value, financial_ar_outstanding,
                financial_ar_aging, financial_payment_pattern,
                relationship_health, relationship_trend,
                relationship_last_interaction, relationship_notes,
                contacts_json, active_projects_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id, name, tier, kwargs.get('type', 'agency_client'),
            kwargs.get('annual_value', 0), kwargs.get('ar_outstanding', 0),
            kwargs.get('ar_aging', 'Current'), kwargs.get('payment_pattern', 'Unknown'),
            kwargs.get('health', 'good'), kwargs.get('trend', 'stable'),
            kwargs.get('last_interaction'), kwargs.get('relationship_notes', ''),
            json.dumps(kwargs.get('contacts', [])),
            json.dumps(kwargs.get('active_projects', [])),
            now, now
        ))

    return client_id


def get_client(client_id: str) -> Optional[Client]:
    """Get client by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()

        if not row:
            return None

        return Client(
            id=row['id'],
            name=row['name'],
            tier=row['tier'],
            type=row['type'],
            annual_value=row['financial_annual_value'] or 0,
            ar_outstanding=row['financial_ar_outstanding'] or 0,
            ar_aging=row['financial_ar_aging'] or 'Current',
            payment_pattern=row['financial_payment_pattern'] or 'Unknown',
            health=row['relationship_health'] or 'good',
            trend=row['relationship_trend'] or 'stable',
            last_interaction=row['relationship_last_interaction'],
            relationship_notes=row['relationship_notes'] or '',
            contacts=json.loads(row['contacts_json'] or '[]'),
            active_projects=json.loads(row['active_projects_json'] or '[]'),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )


def find_client(name: str) -> Optional[Client]:
    """Find client by name (case-insensitive, partial match)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
            (f"%{name}%",)
        ).fetchone()

        if row:
            return get_client(row['id'])
        return None


def update_client(client_id: str, **changes) -> bool:
    """Update client fields."""
    # Map friendly names to column names
    field_map = {
        'annual_value': 'financial_annual_value',
        'ar_outstanding': 'financial_ar_outstanding',
        'ar_aging': 'financial_ar_aging',
        'payment_pattern': 'financial_payment_pattern',
        'health': 'relationship_health',
        'trend': 'relationship_trend',
        'last_interaction': 'relationship_last_interaction',
        'relationship_notes': 'relationship_notes',
    }

    updates = {}
    for k, v in changes.items():
        col = field_map.get(k, k)
        if col in ['contacts', 'active_projects']:
            updates[col + '_json'] = json.dumps(v)
        else:
            updates[col] = v

    if not updates:
        return False

    updates['updated_at'] = now_iso()

    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [client_id]

    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE clients SET {set_clause} WHERE id = ?", values
        )
        return cursor.rowcount > 0


def list_clients(tier: str = None, health: str = None) -> List[Client]:
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

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT id FROM clients WHERE {where} ORDER BY tier, name",
            params
        ).fetchall()

        return [get_client(row['id']) for row in rows]


# ============ PERSON ============

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


def create_person(name: str, **kwargs) -> str:
    """Create a new person. Returns person ID."""
    person_id = str(uuid.uuid4())
    now = now_iso()

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO people (
                id, name, email, phone, type, company, client_id,
                role, department, relationship_trust, relationship_style,
                relationship_responsiveness, relationship_notes,
                reliability_rate, reliability_notes,
                last_interaction, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            person_id, name, kwargs.get('email'), kwargs.get('phone'),
            kwargs.get('type', 'external'), kwargs.get('company'),
            kwargs.get('client_id'), kwargs.get('role'), kwargs.get('department'),
            kwargs.get('trust', 'unknown'), kwargs.get('style'),
            kwargs.get('responsiveness'), kwargs.get('relationship_notes', ''),
            kwargs.get('reliability_rate'), kwargs.get('reliability_notes'),
            kwargs.get('last_interaction'), now, now
        ))

    return person_id


def get_person(person_id: str) -> Optional[Person]:
    """Get person by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM people WHERE id = ?", (person_id,)
        ).fetchone()

        if not row:
            return None

        return Person(
            id=row['id'],
            name=row['name'],
            email=row['email'],
            phone=row['phone'],
            type=row['type'],
            company=row['company'],
            client_id=row['client_id'],
            role=row['role'],
            department=row['department'],
            trust=row['relationship_trust'] or 'unknown',
            style=row['relationship_style'],
            responsiveness=row['relationship_responsiveness'],
            relationship_notes=row['relationship_notes'] or '',
            reliability_rate=row['reliability_rate'],
            reliability_notes=row['reliability_notes'],
            last_interaction=row['last_interaction'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )


def find_person(name: str = None, email: str = None) -> Optional[Person]:
    """Find person by name or email."""
    with get_connection() as conn:
        if email:
            row = conn.execute(
                "SELECT * FROM people WHERE LOWER(email) = LOWER(?) LIMIT 1",
                (email,)
            ).fetchone()
        elif name:
            row = conn.execute(
                "SELECT * FROM people WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
                (f"%{name}%",)
            ).fetchone()
        else:
            return None

        if row:
            return get_person(row['id'])
        return None


# ============ PROJECT ============

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

    milestones: List[Dict] = field(default_factory=list)
    blockers: List[Dict] = field(default_factory=list)
    team: List[Dict] = field(default_factory=list)

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


def create_project(name: str, client_id: str, **kwargs) -> str:
    """Create a new project. Returns project ID."""
    project_id = str(uuid.uuid4())
    now = now_iso()

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO projects (
                id, name, client_id, status, health,
                start_date, target_end_date, value, stakes, description,
                milestones_json, blockers_json, team_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id, name, client_id,
            kwargs.get('status', 'active'),
            kwargs.get('health', 'on_track'),
            kwargs.get('start_date'),
            kwargs.get('target_end_date'),
            kwargs.get('value'),
            kwargs.get('stakes', ''),
            kwargs.get('description', ''),
            json.dumps(kwargs.get('milestones', [])),
            json.dumps(kwargs.get('blockers', [])),
            json.dumps(kwargs.get('team', [])),
            now, now
        ))

    return project_id


def get_project(project_id: str) -> Optional[Project]:
    """Get project by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

        if not row:
            return None

        return Project(
            id=row['id'],
            name=row['name'],
            client_id=row['client_id'],
            status=row['status'],
            health=row['health'],
            start_date=row['start_date'],
            target_end_date=row['target_end_date'],
            value=row['value'],
            stakes=row['stakes'] or '',
            description=row['description'] or '',
            milestones=json.loads(row['milestones_json'] or '[]'),
            blockers=json.loads(row['blockers_json'] or '[]'),
            team=json.loads(row['team_json'] or '[]'),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )


def find_project(name: str = None, client_id: str = None) -> Optional[Project]:
    """Find project by name or client."""
    with get_connection() as conn:
        if name:
            row = conn.execute(
                "SELECT * FROM projects WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
                (f"%{name}%",)
            ).fetchone()
        elif client_id:
            row = conn.execute(
                "SELECT * FROM projects WHERE client_id = ? AND status = 'active' LIMIT 1",
                (client_id,)
            ).fetchone()
        else:
            return None

        if row:
            return get_project(row['id'])
        return None
```

---

## items.py — Items with Context

```python
"""Item tracking with full context capture."""

import uuid
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import date

from .store import get_connection, now_iso
from .entities import get_client, get_person, get_project, Client, Person, Project


@dataclass
class ContextSnapshot:
    """Captured context at item creation time."""
    client: Dict = None
    project: Dict = None
    person: Dict = None
    stakes: str = ""
    history: str = ""

    def to_json(self) -> str:
        return json.dumps({
            'client': self.client,
            'project': self.project,
            'person': self.person,
            'stakes': self.stakes,
            'history': self.history
        })

    @classmethod
    def from_json(cls, data: str) -> 'ContextSnapshot':
        if not data:
            return cls()
        d = json.loads(data)
        return cls(**d)

    def summary(self) -> str:
        """One-line context summary."""
        parts = []
        if self.person:
            parts.append(self.person.get('summary', ''))
        if self.client:
            parts.append(self.client.get('summary', ''))
        if self.stakes:
            parts.append(self.stakes)
        return " — ".join(filter(None, parts))


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

    history: List[Dict] = field(default_factory=list)

    def is_overdue(self) -> bool:
        if not self.due or self.status != 'open':
            return False
        return self.due < date.today().isoformat()

    def full_context_display(self) -> str:
        """Full context for surfacing."""
        parts = [f"**{self.what}**"]

        if self.due:
            if self.is_overdue():
                parts.append(f"⚠️ OVERDUE (was due {self.due})")
            else:
                parts.append(f"Due: {self.due}")

        if self.context:
            if self.context.person:
                parts.append(f"Who: {self.context.person.get('full', '')}")
            if self.context.client:
                parts.append(f"Client: {self.context.client.get('full', '')}")
            if self.context.project:
                parts.append(f"Project: {self.context.project.get('full', '')}")
            if self.context.stakes:
                parts.append(f"Stakes: {self.context.stakes}")
            if self.context.history:
                parts.append(f"History: {self.context.history}")

        return "\n".join(parts)


def build_context(
    client_id: str = None,
    project_id: str = None,
    counterparty_id: str = None,
    stakes: str = "",
    history: str = ""
) -> ContextSnapshot:
    """Build context snapshot from entity IDs."""

    context = ContextSnapshot(stakes=stakes, history=history)

    if client_id:
        client = get_client(client_id)
        if client:
            context.client = {
                'id': client.id,
                'name': client.name,
                'summary': client.summary(),
                'full': client.full_context()
            }

    if project_id:
        project = get_project(project_id)
        if project:
            context.project = {
                'id': project.id,
                'name': project.name,
                'summary': project.summary(),
                'full': project.full_context()
            }

    if counterparty_id:
        person = get_person(counterparty_id)
        if person:
            context.person = {
                'id': person.id,
                'name': person.name,
                'summary': person.summary(),
                'full': person.full_context()
            }

    return context


def create_item(
    what: str,
    owner: str,
    due: str = None,
    counterparty: str = None,
    counterparty_id: str = None,
    client_id: str = None,
    project_id: str = None,
    stakes: str = "",
    history: str = "",
    source_type: str = "manual",
    source_ref: str = None,
    captured_by: str = "A"
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
        history=history
    )

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO items (
                id, what, status, owner, owner_id,
                counterparty, counterparty_id, due, waiting_since,
                client_id, project_id, context_snapshot_json,
                stakes, history_context,
                source_type, source_ref, captured_at,
                created_at, updated_at
            ) VALUES (?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id, what.strip(), owner.strip(), None,
            counterparty, counterparty_id, due, None,
            client_id, project_id, context.to_json(),
            stakes, history,
            source_type, source_ref, now,
            now, now
        ))

        # Record in history
        conn.execute("""
            INSERT INTO item_history (id, item_id, timestamp, change, changed_by)
            VALUES (?, ?, ?, 'Created', ?)
        """, (str(uuid.uuid4()), item_id, now, captured_by))

    return item_id


def get_item(item_id: str, include_history: bool = False) -> Optional[Item]:
    """Get item by ID with context."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()

        if not row:
            return None

        item = Item(
            id=row['id'],
            what=row['what'],
            status=row['status'],
            owner=row['owner'],
            owner_id=row['owner_id'],
            counterparty=row['counterparty'],
            counterparty_id=row['counterparty_id'],
            due=row['due'],
            waiting_since=row['waiting_since'],
            client_id=row['client_id'],
            project_id=row['project_id'],
            context=ContextSnapshot.from_json(row['context_snapshot_json']),
            source_type=row['source_type'],
            source_ref=row['source_ref'],
            captured_at=row['captured_at'],
            resolution_outcome=row['resolution_outcome'],
            resolution_notes=row['resolution_notes'],
            resolved_at=row['resolved_at'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

        if include_history:
            history = conn.execute("""
                SELECT timestamp, change, changed_by
                FROM item_history WHERE item_id = ?
                ORDER BY timestamp ASC
            """, (item_id,)).fetchall()
            item.history = [dict(h) for h in history]

        return item


def update_item(item_id: str, changed_by: str = "A", **changes) -> bool:
    """Update item. Tracks history."""

    valid_fields = {
        'what', 'status', 'owner', 'counterparty', 'due',
        'stakes', 'resolution_outcome', 'resolution_notes'
    }

    updates = {k: v for k, v in changes.items() if k in valid_fields}
    if not updates:
        return False

    # Handle status transitions
    if 'status' in updates:
        new_status = updates['status']
        if new_status not in ('open', 'waiting', 'done', 'cancelled'):
            raise ValueError(f"Invalid status: {new_status}")

        if new_status == 'waiting':
            updates['waiting_since'] = now_iso()
        elif new_status in ('done', 'cancelled'):
            updates['resolved_at'] = now_iso()

    now = now_iso()
    updates['updated_at'] = now

    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [item_id]

    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE items SET {set_clause} WHERE id = ?", values
        )

        if cursor.rowcount == 0:
            return False

        # Record history
        change_desc = ", ".join(f"{k}→{v}" for k, v in changes.items() if k in valid_fields)
        conn.execute("""
            INSERT INTO item_history (id, item_id, timestamp, change, changed_by)
            VALUES (?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), item_id, now, change_desc, changed_by))

    return True


def mark_done(item_id: str, notes: str = None) -> bool:
    """Mark item as done."""
    return update_item(
        item_id,
        status='done',
        resolution_outcome='completed',
        resolution_notes=notes
    )


def mark_waiting(item_id: str) -> bool:
    """Mark item as waiting on someone."""
    return update_item(item_id, status='waiting')


def mark_cancelled(item_id: str, notes: str = None) -> bool:
    """Cancel an item."""
    return update_item(
        item_id,
        status='cancelled',
        resolution_outcome='cancelled',
        resolution_notes=notes
    )
```

---

## queries.py — Query Helpers

```python
"""Query helpers for common access patterns."""

from typing import List, Optional
from datetime import date, timedelta
from .store import get_connection
from .items import Item, get_item


def query_items(
    status: str = None,
    due_before: str = None,
    due_after: str = None,
    client_id: str = None,
    project_id: str = None,
    owner: str = None,
    limit: int = 100
) -> List[Item]:
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
        rows = conn.execute(f"""
            SELECT id FROM items
            WHERE {where}
            ORDER BY
                CASE WHEN due IS NULL THEN 1 ELSE 0 END,
                due ASC,
                created_at DESC
            LIMIT ?
        """, params).fetchall()

        return [get_item(row['id']) for row in rows]


# Convenience functions

def open_items() -> List[Item]:
    """All open items."""
    return query_items(status='open')


def overdue() -> List[Item]:
    """Open items past due."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return query_items(status='open', due_before=yesterday)


def due_today() -> List[Item]:
    """Items due today."""
    today = date.today().isoformat()
    items = query_items(status='open', due_before=today, due_after=today)
    return [i for i in items if i.due == today]


def due_this_week() -> List[Item]:
    """Open items due within 7 days."""
    end = (date.today() + timedelta(days=7)).isoformat()
    return query_items(status='open', due_before=end)


def waiting() -> List[Item]:
    """Items in waiting status."""
    return query_items(status='waiting')


def for_client(client_id: str) -> List[Item]:
    """All open items for a client."""
    return query_items(status='open', client_id=client_id)


def for_project(project_id: str) -> List[Item]:
    """All open items for a project."""
    return query_items(status='open', project_id=project_id)


def summary_stats() -> dict:
    """Get summary statistics."""
    with get_connection() as conn:
        stats = {}

        stats['total'] = conn.execute(
            "SELECT COUNT(*) FROM items"
        ).fetchone()[0]

        stats['open'] = conn.execute(
            "SELECT COUNT(*) FROM items WHERE status = 'open'"
        ).fetchone()[0]

        stats['waiting'] = conn.execute(
            "SELECT COUNT(*) FROM items WHERE status = 'waiting'"
        ).fetchone()[0]

        stats['overdue'] = conn.execute(
            "SELECT COUNT(*) FROM items WHERE status = 'open' AND due < date('now')"
        ).fetchone()[0]

        stats['due_this_week'] = conn.execute("""
            SELECT COUNT(*) FROM items
            WHERE status = 'open'
            AND due IS NOT NULL
            AND due <= date('now', '+7 days')
        """).fetchone()[0]

        return stats
```

---

## health.py and backup.py

*(Same as before — health checks, self-healing, backup/restore)*

See previous implementation. No changes needed.

---

## Usage Examples

```python
from moh_time_os.lib.store import init_db
from moh_time_os.lib.entities import create_client, create_person, find_client, find_person
from moh_time_os.lib.items import create_item, get_item, mark_done
from moh_time_os.lib import queries

# Initialize
init_db()

# Create client
sss_id = create_client(
    name="Sun Sand Sports",
    tier="A",
    annual_value=890000,
    health="good",
    relationship_notes="Long-term partner, expanding relationship"
)

# Create person
dana_id = create_person(
    name="Dana Oraibi",
    email="dana@sss.ae",
    role="Head of Marketing",
    company="Sun Sand Sports",
    client_id=sss_id,
    relationship_notes="Direct, values detail, responsive"
)

# Create item with full context
item_id = create_item(
    what="Send Ramadan campaign proposal to Dana",
    owner="me",
    due="2026-02-03",
    counterparty="Dana Oraibi",
    counterparty_id=dana_id,
    client_id=sss_id,
    stakes="Flagship Q1 project, 200K AED",
    history="Requested Jan 28 after kickoff meeting"
)

# Query
overdue = queries.overdue()
for item in overdue:
    print(item.full_context_display())

# Mark done
mark_done(item_id, notes="Sent via email")
```

---

*Complete implementation. Context-rich, reliable, ready to build.*
