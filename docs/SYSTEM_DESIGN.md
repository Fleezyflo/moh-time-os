# MOH Time OS — System Design

> Complete context, reliable storage, intelligent facilitation.

---

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      KNOWLEDGE LAYER                             │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │ CLIENTS  │───▶│ PROJECTS │    │  PEOPLE  │                  │
│  │          │    │          │    │          │                  │
│  │ Tier     │    │ Status   │    │ Role     │                  │
│  │ AR/Health│    │ Deadlines│    │ Company  │                  │
│  │ Contacts │    │ Stakes   │    │ Trust    │                  │
│  └──────────┘    └──────────┘    └──────────┘                  │
│        │              │               │                         │
│        └──────────────┴───────────────┘                         │
│                       │                                          │
│                       ▼                                          │
│               ┌──────────────┐                                  │
│               │    ITEMS     │                                  │
│               │              │                                  │
│               │ What/When    │                                  │
│               │ Full Context │                                  │
│               │ Linked to ↑  │                                  │
│               └──────────────┘                                  │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STORAGE LAYER                                 │
│                                                                  │
│  SQLite + WAL │ Full History │ Backups │ Health Checks          │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AGENT LAYER (A)                                │
│                                                                  │
│  Captures with context │ Surfaces with synthesis                │
│  Reasons with full picture │ Facilitates decisions              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Entity Model

### Clients

Companies/organizations we work with.

```yaml
Client:
  id: string
  name: string
  
  # Classification
  tier: A | B | C              # Strategic importance
  type: agency_client | vendor | partner | other
  
  # Financial State
  financial:
    annual_value: number       # Revenue from this client
    ar_outstanding: number     # Current AR
    ar_aging: string           # "Current" | "30 days" | "60+ days"
    payment_pattern: string    # "Reliable" | "Slow" | "Problematic"
  
  # Relationship State
  relationship:
    health: excellent | good | fair | poor | critical
    trend: improving | stable | declining
    last_interaction: date
    notes: string              # Key relationship context
  
  # Key Contacts (references to People)
  contacts:
    - person_id: reference
      role: string             # "Primary" | "Finance" | "Creative" | etc.
  
  # Active Work (references to Projects)
  active_projects: [project_id]
  
  # Metadata
  created_at: datetime
  updated_at: datetime
```

### People

Individuals we interact with (internal team + external contacts).

```yaml
Person:
  id: string
  name: string
  email: string
  phone: string | null
  
  # Affiliation
  type: internal | external
  company: string | null       # For external
  client_id: reference | null  # If linked to a client
  
  # Role & Relationship
  role: string                 # Job title or relationship role
  department: string | null
  
  # Working Relationship
  relationship:
    trust_level: high | medium | low | unknown
    communication_style: string   # "Direct" | "Formal" | "Casual" | notes
    responsiveness: string        # "Fast" | "Normal" | "Slow"
    notes: string                 # Key things to know about this person
  
  # For Internal Team
  reliability:
    commitments_kept_rate: number | null  # 0-100%
    typical_delivery: string              # "On time" | "Usually late" | etc.
  
  # Metadata
  last_interaction: datetime
  created_at: datetime
  updated_at: datetime
```

### Projects

Active work with deliverables and deadlines.

```yaml
Project:
  id: string
  name: string
  client_id: reference
  
  # Status
  status: discovery | active | delivery | on_hold | completed | cancelled
  health: on_track | at_risk | blocked | late
  
  # Timeline
  start_date: date
  target_end_date: date | null
  
  # Stakes
  value: number | null         # Project value in AED
  stakes: string               # Why this matters, what's riding on it
  
  # Key Info
  description: string
  key_milestones:
    - name: string
      due: date
      status: pending | done | late
  
  blockers:
    - description: string
      since: date
      owner: string
  
  # Team
  team:
    - person_id: reference
      role: string             # "Lead" | "Contributor" | etc.
  
  # Metadata
  created_at: datetime
  updated_at: datetime
```

### Items

Things that need to happen — the core tracking unit.

```yaml
Item:
  id: string
  
  # Core
  what: string                 # What needs to happen
  status: open | waiting | done | cancelled
  
  # Ownership
  owner: string                # Who's responsible ("me" or person name)
  owner_id: reference | null   # Link to Person if applicable
  
  # Counterparty (who's on the other side)
  counterparty: string | null
  counterparty_id: reference | null  # Link to Person
  
  # Timing
  due: date | null
  waiting_since: date | null   # If status=waiting
  
  # Context (REQUIRED — this is what provides intelligence)
  context:
    client_id: reference | null
    client_snapshot:           # Denormalized at capture time
      name: string
      tier: string
      health: string
      ar_status: string
    
    project_id: reference | null
    project_snapshot:
      name: string
      status: string
      stakes: string
    
    person_snapshot:           # The counterparty
      name: string
      role: string
      company: string
      relationship: string
    
    stakes: string             # Why this specific item matters
    history: string            # What led to this, relevant background
  
  # Source
  source:
    type: email | chat | meeting | call | conversation | manual
    ref: string | null         # Message ID, meeting ID, etc.
    captured_at: datetime
  
  # Resolution
  resolution:
    outcome: completed | cancelled | transferred | superseded | null
    notes: string | null
    resolved_at: datetime | null
  
  # History (append-only)
  history:
    - timestamp: datetime
      change: string
      by: string
```

**Key Design Decision:** Items have both references (client_id, person_id) AND snapshots (client_snapshot, person_snapshot). 

- References = for queries ("all items for this client")
- Snapshots = for context at surfacing time (even if entity changes, Item retains context from when it was created)

---

## Storage Schema

```sql
-- Clients
CREATE TABLE clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tier TEXT CHECK (tier IN ('A', 'B', 'C')),
    type TEXT,
    
    financial_annual_value REAL,
    financial_ar_outstanding REAL,
    financial_ar_aging TEXT,
    financial_payment_pattern TEXT,
    
    relationship_health TEXT,
    relationship_trend TEXT,
    relationship_last_interaction TEXT,
    relationship_notes TEXT,
    
    contacts_json TEXT,        -- JSON array of {person_id, role}
    active_projects_json TEXT, -- JSON array of project_ids
    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- People
CREATE TABLE people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    
    type TEXT CHECK (type IN ('internal', 'external')),
    company TEXT,
    client_id TEXT REFERENCES clients(id),
    role TEXT,
    department TEXT,
    
    relationship_trust TEXT,
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
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    client_id TEXT REFERENCES clients(id),
    
    status TEXT,
    health TEXT,
    
    start_date TEXT,
    target_end_date TEXT,
    
    value REAL,
    stakes TEXT,
    description TEXT,
    
    milestones_json TEXT,      -- JSON array
    blockers_json TEXT,        -- JSON array
    team_json TEXT,            -- JSON array
    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Items
CREATE TABLE items (
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
    context_snapshot_json TEXT,  -- Full context snapshot
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
CREATE TABLE item_history (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES items(id),
    timestamp TEXT NOT NULL,
    change TEXT NOT NULL,
    changed_by TEXT NOT NULL
);

-- Indexes
CREATE INDEX idx_clients_tier ON clients(tier);
CREATE INDEX idx_clients_health ON clients(relationship_health);

CREATE INDEX idx_people_type ON people(type);
CREATE INDEX idx_people_client ON people(client_id);

CREATE INDEX idx_projects_client ON projects(client_id);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_health ON projects(health);

CREATE INDEX idx_items_status ON items(status);
CREATE INDEX idx_items_due ON items(due);
CREATE INDEX idx_items_client ON items(client_id);
CREATE INDEX idx_items_project ON items(project_id);
CREATE INDEX idx_items_owner ON items(owner);
```

---

## Operational Excellence

### Health Model

```
HEALTHY  →  All checks pass, full operation
DEGRADED →  Issues exist but core works, warn + continue
FAILED   →  Core broken, memory mode, guide recovery
```

### Health Checks (Every Session Start)

| Check | What | Threshold |
|-------|------|-----------|
| db_exists | File present | Must exist |
| db_readable | Can query | Must work |
| db_writable | Can write | Must work |
| db_integrity | PRAGMA integrity_check | Must be "ok" |
| backup_recent | Last backup age | < 48 hours |
| disk_space | Free space | > 100MB |

### Failure Recovery Runbook

**Database Missing:**
```
1. A announces: "Database missing. Working from memory."
2. Check backups: moh_time_os/data/backups/
3. Restore: items.restore(latest_backup)
4. Verify: health_check()
5. A announces: "Restored from [date]. [N] items recovered."
```

**Database Corrupted:**
```
1. A announces: "Corruption detected. Switching to memory mode."
2. Attempt: sqlite3 items.db ".recover" > recovered.sql
3. If works: Rebuild from recovered.sql
4. If fails: Restore from backup
5. Verify: integrity_check()
```

**Disk Full:**
```
1. A announces: "Disk full. Queuing operations."
2. User clears space
3. A replays queued operations
4. Verify: health_check()
```

### Self-Healing (Every Startup)

- Ensure WAL mode enabled
- Checkpoint WAL to prevent bloat
- Ensure all indexes exist
- Prune old backups (keep 7)
- Clean temp files

### Backup Strategy

- **Daily:** Automatic backup via cron
- **Before restore:** Snapshot current state
- **Retention:** Keep last 7 backups
- **Integrity:** Weekly PRAGMA integrity_check

---

## A Protocol

### Session Start

```
1. Run health_check()
2. If FAILED: Announce, enter memory mode, guide recovery
3. If DEGRADED: Announce issue, continue
4. If HEALTHY: Proceed silently
```

### Heartbeat

```
1. Standard checks (email, calendar, chat)
2. Query: Items due today or overdue
3. Query: Items waiting > 3 days
4. If urgent items: Surface with full context
5. If nothing: HEARTBEAT_OK
```

### Creating Items

When A identifies something to track:

```
1. Identify/confirm counterparty → lookup/create Person
2. Identify/confirm client → lookup Client, get current state
3. Identify/confirm project if applicable → lookup Project
4. Capture context snapshot (client health, AR, relationship, stakes)
5. Create Item with full context
6. Confirm to Moh: "Tracked: [what] — [context summary]"
```

**Context is required, not optional.** If A can't determine context, A asks.

### Surfacing Items

When A surfaces an item:

```
1. Load Item with context snapshot
2. Optionally refresh entity state for critical items
3. Synthesize: What + Who + Why it matters + Stakes + History
4. Present with full picture, not just the "what"
```

Example:
> "Dana's proposal is due tomorrow. She's Head of Marketing at SSS — Tier A client, 890K annual, AR current, relationship is good. This is for the Ramadan campaign (200K, flagship Q1). She asked Jan 28 after the kickoff meeting. Standard request, just needs doing."

### Queries

Natural language queries work:

- "What's open?" → All open items with context
- "What's overdue?" → Overdue items with context + urgency
- "What about GMG?" → All items + current state for GMG
- "How's the SSS relationship?" → Client state + open items + recent history
- "Status" → System health + summary stats

### Daily Brief

If configured (09:00 via cron):

```
1. Query: Overdue, due today, due this week, waiting
2. Query: Clients with health != good
3. Query: Projects with health != on_track
4. Synthesize: What needs attention, why, context
5. Deliver to main channel
```

---

## What A Reasons About (Not Rules)

The system stores data. A reasons about:

| Question | A Considers |
|----------|-------------|
| Is this urgent? | Due date + client tier + stakes + relationship health |
| Should I surface this? | Overdue? Due soon? Waiting too long? Client at risk? |
| What's the priority? | Stakes + client tier + relationship trend + deadline pressure |
| What context matters? | Who's involved + what's the history + what's at stake |
| What should Moh know? | Full picture synthesized, not data dump |

No scoring formulas. A uses judgment informed by complete context.

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

- Database schema (all entities)
- CRUD operations for Clients, People, Projects, Items
- Health checks + self-healing
- Basic queries

**Deliverable:** A can create and query all entities.

### Phase 2: Context Flow (Week 2)

- Context capture on Item creation
- Entity lookups and snapshot creation
- Surfacing with full context synthesis
- Conversation-based capture

**Deliverable:** Moh can track items with full context through conversation.

### Phase 3: Operations (Week 3)

- Heartbeat integration
- Daily brief generation
- Query handlers ("what's open", "how's GMG")
- Backup automation

**Deliverable:** System is live and operational.

### Phase 4: Enrichment (Week 4+)

- Sync from Xero (AR data)
- Sync from Asana (project status)
- Periodic context refresh
- Learn from usage

**Deliverable:** Context stays fresh, system improves.

---

## Success Criteria

**Trust:** Moh trusts that if A doesn't surface something, it's either handled or not due.

**Context:** Every surfaced item has full context — who, what, why, stakes, history.

**Reliability:** System never loses data. Failures are detected and recoverable.

**Facilitation:** A helps Moh decide. A doesn't decide for Moh, doesn't spam, doesn't miss important things.

---

## Invariants

These are always true:

1. Every Item has an owner and a 'what'
2. Every Item has context (snapshot at minimum)
3. Clients have tier and health
4. History is append-only
5. Terminal statuses (done, cancelled) don't transition
6. Health check runs every session start
7. Backups exist and are < 48 hours old

If any invariant is violated, it's a bug.

---

*Intelligence requires context. Context requires structure. Structure must be reliable. This design provides all three.*
