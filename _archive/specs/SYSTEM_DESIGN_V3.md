# MOH Time OS — System Design V3

> Bootstrap-first. Value in days. Surgical precision.

**Document version:** 3.0  
**Created:** 2025-06-30  
**Status:** ACTIVE PLAN

---

## Executive Summary

**What this is:** A personal operating system that ensures nothing falls through the cracks by tracking commitments with full context.

**Core insight from V2 critique:** The previous plan optimized for architectural purity over time-to-value. It would take 4 weeks before the system did anything useful, and it started with zero data.

**This plan:** Value in 3 days. Bootstrap from existing systems. Start dumb, get smart.

**Success criteria:** By end of Day 3, Moh can ask "what's overdue?" and get a useful answer with context.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Data Model](#2-data-model)
3. [Bootstrap Strategy](#3-bootstrap-strategy)
4. [Daily Workflow](#4-daily-workflow)
5. [Capture Protocol](#5-capture-protocol)
6. [Surfacing Protocol](#6-surfacing-protocol)
7. [Query Interface](#7-query-interface)
8. [Decision Heuristics](#8-decision-heuristics)
9. [Sync & Conflict Resolution](#9-sync--conflict-resolution)
10. [Failure Modes & Recovery](#10-failure-modes--recovery)
11. [Implementation Plan](#11-implementation-plan)
12. [File-by-File Specification](#12-file-by-file-specification)
13. [Test Plan](#13-test-plan)
14. [Migration Path](#14-migration-path)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                   │
│                                                                          │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────────┐            │
│   │  XERO   │   │  ASANA  │   │ GOOGLE  │   │ CONVERSATION │            │
│   │ (AR/AP) │   │ (tasks) │   │ (cal)   │   │   (chat)     │            │
│   └────┬────┘   └────┬────┘   └────┬────┘   └──────┬───────┘            │
│        │             │             │                │                    │
└────────┼─────────────┼─────────────┼────────────────┼────────────────────┘
         │             │             │                │
         ▼             ▼             ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BOOTSTRAP / SYNC LAYER                           │
│                                                                          │
│   xero_sync.py       asana_sync.py      (manual via A)                  │
│   - Contacts → KB    - Projects → KB    - Items from conversation       │
│   - AR aging         - Tasks → Items                                    │
│   - Invoice status   - Assignees                                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         KNOWLEDGE BASE (SQLite)                          │
│                                                                          │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│   │  ENTITIES   │  │    ITEMS    │  │   CONTEXT   │  │   HISTORY   │   │
│   │             │  │             │  │             │  │             │   │
│   │ - clients   │  │ - what      │  │ - snapshots │  │ - changes   │   │
│   │ - people    │  │ - who       │  │ - at create │  │ - by whom   │   │
│   │ - projects  │  │ - when      │  │ - refresh   │  │ - when      │   │
│   │             │  │ - status    │  │             │  │             │   │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              AGENT (A)                                   │
│                                                                          │
│   CAPTURE          SURFACE           QUERY            BRIEF             │
│   - From convo     - Overdue         - "what's open"  - Daily 09:00     │
│   - From sources   - Due soon        - "how's GMG"    - Synthesized     │
│   - With context   - At risk         - "status"       - Actionable      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Bootstrap before build** — System is useless without data. Data comes first.
2. **Text context before linked entities** — Start with searchable text, add relationships later.
3. **Value in days, not weeks** — If it takes >3 days to be useful, the plan is wrong.
4. **Explicit heuristics** — No "A reasons about it." Specify the rules.
5. **Single source of truth per domain** — Asana owns tasks. This owns commitments/promises.
6. **Graceful degradation** — Missing data = work anyway, flag the gap.

---

## 2. Data Model

### 2.1 Entity: Client

```yaml
Client:
  id: string                    # UUID
  name: string                  # "Sun Sand Sports", "GMG"
  name_normalized: string       # Lowercase, no punctuation (for matching)
  aliases: [string]             # ["SSS", "Sun & Sand"] (for matching)
  
  # Source
  xero_contact_id: string|null  # Link to Xero contact
  source: "xero"|"manual"       # Where this came from
  
  # Classification
  tier: "A"|"B"|"C"|null        # Strategic importance (null = unclassified)
  type: "agency_client"|"vendor"|"partner"|"internal"|"other"
  
  # Financial (from Xero sync)
  financial:
    ar_total: number            # Total outstanding AR
    ar_overdue: number          # AR > 30 days
    ar_aging_bucket: "current"|"30"|"60"|"90+"|null
    last_invoice_date: date|null
    last_payment_date: date|null
    annual_value: number|null   # Manual or calculated
  
  # Relationship (manual, A-maintained)
  relationship:
    health: "excellent"|"good"|"fair"|"poor"|"critical"|null
    trend: "improving"|"stable"|"declining"|null
    notes: string               # Free text context
    last_interaction: datetime|null
  
  # Metadata
  created_at: datetime
  updated_at: datetime
  last_synced_at: datetime|null
```

**Key decisions:**
- `name_normalized` + `aliases` enable fuzzy matching ("GMG" matches "GMG Consumer LLC")
- `xero_contact_id` enables re-sync without duplicates
- `tier` and `relationship` are A-maintained (not synced from anywhere)
- Financial data synced from Xero, everything else manual

### 2.2 Entity: Person

```yaml
Person:
  id: string
  name: string
  name_normalized: string
  email: string|null            # Primary identifier for matching
  phone: string|null
  
  # Affiliation
  type: "internal"|"external"
  company: string|null          # Company name (text, for display)
  client_id: string|null        # FK to Client (if external + linked)
  
  # Role
  role: string|null             # "Head of Marketing", "CFO"
  department: string|null       # "Finance", "Creative"
  
  # Relationship context (A-maintained)
  relationship:
    trust: "high"|"medium"|"low"|"unknown"
    communication_style: string|null  # "Direct", "Formal", etc.
    responsiveness: "fast"|"normal"|"slow"|"unknown"
    notes: string
  
  # For internal team
  asana_user_id: string|null    # Link to Asana user
  
  # Metadata
  created_at: datetime
  updated_at: datetime
```

**Key decisions:**
- Email is the primary matching key for external contacts
- `asana_user_id` enables linking Asana tasks to people
- Most fields nullable — person can exist with just a name

### 2.3 Entity: Project

```yaml
Project:
  id: string
  name: string
  name_normalized: string
  
  # Links
  client_id: string|null        # FK to Client
  asana_project_id: string|null # Link to Asana project
  
  # Status (synced from Asana if linked)
  status: "discovery"|"active"|"delivery"|"on_hold"|"completed"|"cancelled"
  health: "on_track"|"at_risk"|"blocked"|"late"|null
  
  # Timeline
  start_date: date|null
  target_end_date: date|null
  
  # Context (A-maintained)
  value: number|null            # Project value in AED
  stakes: string                # Why this matters
  description: string
  
  # Metadata
  created_at: datetime
  updated_at: datetime
  last_synced_at: datetime|null
```

**Key decisions:**
- `asana_project_id` enables sync without duplicates
- Status/health can come from Asana or be manually set
- `stakes` is the critical context field — "Why does this matter?"

### 2.4 Entity: Item (Core Tracking Unit)

```yaml
Item:
  id: string
  
  # Core (REQUIRED)
  what: string                  # "Send proposal to Dana"
  status: "open"|"waiting"|"done"|"cancelled"
  owner: string                 # "me" or person name
  
  # Timing
  due: date|null                # When it's due
  waiting_since: datetime|null  # When it entered waiting status
  
  # Links (all optional)
  owner_id: string|null         # FK to Person (if owner is someone else)
  counterparty: string|null     # Who's on the other side (text)
  counterparty_id: string|null  # FK to Person
  client_id: string|null        # FK to Client
  project_id: string|null       # FK to Project
  
  # Context (THE IMPORTANT PART)
  context:
    # Text context (always captured)
    client_name: string|null    # "Sun Sand Sports"
    project_name: string|null   # "Ramadan Campaign"
    person_name: string|null    # "Dana Oraibi"
    stakes: string              # "Flagship Q1 project, 200K"
    history: string             # "Requested Jan 28 after kickoff"
    
    # Snapshot at creation (for surfacing)
    snapshot:
      client_tier: string|null
      client_health: string|null
      client_ar_status: string|null
      project_status: string|null
      project_health: string|null
      person_role: string|null
      captured_at: datetime
  
  # Source tracking
  source:
    type: "conversation"|"email"|"asana"|"manual"|"other"
    ref: string|null            # Message ID, task ID, etc.
    captured_at: datetime
    captured_by: string         # "A" or "Moh"
  
  # Resolution
  resolution:
    outcome: "completed"|"cancelled"|"transferred"|"superseded"|null
    notes: string|null
    resolved_at: datetime|null
    resolved_by: string|null
  
  # Metadata
  created_at: datetime
  updated_at: datetime
```

**Key decisions:**
- **Text context fields exist alongside FK links** — Even if client_id is null, client_name can have "GMG"
- **Snapshot captures state at creation** — For surfacing context even if entities change
- **Source tracking** — Know where every item came from
- **Resolution is explicit** — Not just "done" but why/how

### 2.5 Entity: ItemHistory (Append-Only)

```yaml
ItemHistory:
  id: string
  item_id: string               # FK to Item
  timestamp: datetime
  change_type: "created"|"updated"|"status_changed"|"resolved"
  change_detail: string         # "status: open → waiting"
  changed_by: string            # "A" or "Moh"
  
  # Optional context
  notes: string|null            # Why the change happened
```

---

## 3. Bootstrap Strategy

**Critical insight:** The system is worthless without data. Bootstrap is not Week 4 — it's Day 1.

### 3.1 Bootstrap Sources

| Source | What We Get | Priority | Effort |
|--------|-------------|----------|--------|
| Xero Contacts | Clients (name, AR, aging) | P0 | 2 hours |
| Asana Projects | Projects (name, status, client link) | P0 | 3 hours |
| Asana Tasks (overdue) | Items (what, due, owner) | P1 | 2 hours |
| Google Sheets (Forecast) | Team list, client list | P2 | 1 hour |
| Manual | Tier, health, stakes, relationship | Ongoing | N/A |

### 3.2 Bootstrap Sequence

```
DAY 1 (Bootstrap Day)
├── Hour 1-2: Xero Contacts → Clients
│   ├── Fetch all contacts from Xero API
│   ├── Filter: ContactStatus = ACTIVE
│   ├── For each contact:
│   │   ├── Create Client record
│   │   ├── name = Contact.Name
│   │   ├── xero_contact_id = Contact.ContactID
│   │   ├── aliases = extract_aliases(name)  # "GMG Consumer LLC" → ["GMG"]
│   │   ├── ar_total = sum(invoices where status=AUTHORISED)
│   │   ├── ar_aging_bucket = calculate_aging(oldest_invoice)
│   │   └── tier = null (unclassified)
│   └── Result: ~150 clients with AR data
│
├── Hour 3-5: Asana Projects → Projects
│   ├── Fetch all projects from hrmny.co workspace
│   ├── Filter: archived = false
│   ├── For each project:
│   │   ├── Create Project record
│   │   ├── name = Project.name
│   │   ├── asana_project_id = Project.gid
│   │   ├── status = map_asana_status(custom_fields)
│   │   ├── client_id = match_client(project.name)  # Fuzzy match
│   │   └── stakes = null (to be filled)
│   └── Result: ~289 projects linked to clients
│
├── Hour 6-7: Asana Overdue Tasks → Items
│   ├── Fetch tasks where due_on < today AND completed = false
│   ├── For each task:
│   │   ├── Create Item record
│   │   ├── what = Task.name
│   │   ├── due = Task.due_on
│   │   ├── owner = Task.assignee.name or "unassigned"
│   │   ├── project_id = match_project(Task.projects[0])
│   │   ├── client_id = project.client_id (inherited)
│   │   ├── source.type = "asana"
│   │   ├── source.ref = Task.gid
│   │   └── Build context from linked entities
│   └── Result: All overdue items with context
│
└── Hour 8: Verification
    ├── Query: How many clients?
    ├── Query: How many projects?
    ├── Query: How many overdue items?
    ├── Query: What % of projects linked to clients?
    └── Manual spot-check: Pick 5 items, verify context is correct
```

### 3.3 Client Matching Algorithm

When linking Projects/Items to Clients, we need fuzzy matching.

```python
def match_client(text: str) -> Optional[str]:
    """
    Match text to a client. Returns client_id or None.
    
    Matching priority:
    1. Exact name match (case-insensitive)
    2. Alias match
    3. Normalized substring match
    4. None (log for manual review)
    """
    text_normalized = normalize(text)  # lowercase, remove punctuation
    
    # 1. Exact match
    client = db.query("SELECT id FROM clients WHERE name_normalized = ?", text_normalized)
    if client:
        return client.id
    
    # 2. Alias match
    client = db.query("""
        SELECT id FROM clients 
        WHERE ? = ANY(aliases_normalized)
    """, text_normalized)
    if client:
        return client.id
    
    # 3. Substring match (client name appears in text)
    clients = db.query("SELECT id, name_normalized FROM clients")
    for c in clients:
        if c.name_normalized in text_normalized:
            return c.id
        if text_normalized in c.name_normalized:
            return c.id
    
    # 4. No match — log for review
    log.warning(f"No client match for: {text}")
    return None
```

### 3.4 Post-Bootstrap Manual Tasks

After automated bootstrap, A prompts Moh to fill critical gaps:

```
BOOTSTRAP COMPLETE

Imported:
- 153 clients from Xero
- 289 projects from Asana  
- 47 overdue tasks → Items

Gaps requiring input:
1. 153 clients have no tier (A/B/C). Want to classify the top 20 by AR?
2. 42 projects couldn't match to a client. Review list?
3. 289 projects have no "stakes" context. Fill in for active projects?

Recommended first action: Classify top 10 clients by AR as Tier A.
```

---

## 4. Daily Workflow

**The system is only useful if it fits into Moh's actual day.**

### 4.1 Workflow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     MOH'S DAY                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  09:00  ┌──────────────────────────────────────┐                │
│         │         MORNING BRIEF                 │                │
│         │                                       │                │
│         │  • What's overdue? (with context)     │                │
│         │  • What's due today?                  │                │
│         │  • Any clients at risk?               │                │
│         │  • Calendar: big meetings today?      │                │
│         │                                       │                │
│         │  Delivered via cron to main channel   │                │
│         └──────────────────────────────────────┘                │
│                                                                  │
│  09:00-18:00  WORK DAY                                          │
│         │                                                        │
│         │  ┌────────────────────────────────┐                   │
│         │  │      CAPTURE (as it happens)   │                   │
│         │  │                                │                   │
│         │  │  Moh: "Need to call Dana about │                   │
│         │  │        the proposal"           │                   │
│         │  │                                │                   │
│         │  │  A: "Track it? When's it due?" │                   │
│         │  │                                │                   │
│         │  │  Moh: "Tomorrow"               │                   │
│         │  │                                │                   │
│         │  │  A: "Got it: Call Dana re      │                   │
│         │  │      proposal. Due Jul 1.      │                   │
│         │  │      (SSS, Ramadan Campaign)"  │                   │
│         │  └────────────────────────────────┘                   │
│         │                                                        │
│         │  ┌────────────────────────────────┐                   │
│         │  │      QUERY (on demand)         │                   │
│         │  │                                │                   │
│         │  │  "What's open?"                │                   │
│         │  │  "What about GMG?"             │                   │
│         │  │  "Anything waiting on others?" │                   │
│         │  │  "Status"                      │                   │
│         │  └────────────────────────────────┘                   │
│         │                                                        │
│  19:30  ┌──────────────────────────────────────┐                │
│         │         EVENING REVIEW                │                │
│         │                                       │                │
│         │  • What got done today?               │                │
│         │  • What's still open?                 │                │
│         │  • What's due tomorrow?               │                │
│         │  • Any items stuck in waiting?        │                │
│         │                                       │                │
│         │  Optional — only if Moh asks          │                │
│         └──────────────────────────────────────┘                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Morning Brief Specification

**Trigger:** Cron job at 09:00 Dubai time  
**Destination:** Main chat channel  
**Max length:** 500 words (be concise)

**Structure:**

```markdown
## Morning Brief — {date}

### 🔴 Overdue ({count})
{For each overdue item, max 5:}
- **{what}** — due {due_date} ({days} days ago)
  {context: who, client, stakes}

{If > 5: "+ {n} more overdue items"}

### 📅 Due Today ({count})
{For each item due today:}
- **{what}**
  {context: who, client}

### ⚠️ Attention
{Only if there are issues:}
- {client_name} AR is {days}+ days overdue ({amount} AED)
- {project_name} has been blocked for {days} days
- {n} items waiting on others for 5+ days

### 📊 Summary
{open} open | {waiting} waiting | {due_this_week} due this week
```

**Example:**

```markdown
## Morning Brief — Jul 1, 2025

### 🔴 Overdue (3)
- **Send Ramadan campaign proposal to Dana** — due Jun 28 (3 days ago)
  Dana Oraibi (Head of Marketing) @ SSS. Tier A, 890K annual. Flagship Q1 project.

- **Follow up on GMG invoice** — due Jun 25 (6 days ago)
  Finance @ GMG. Tier A. AR: 484K overdue 60+ days.

- **Review Chalhoub creative brief** — due Jun 30 (1 day ago)
  Chalhoub Group, Brand refresh project.

### 📅 Due Today (2)
- **Call Careem re: partnership terms**
  Sarah (Partnerships) @ Careem

- **Submit ADCB final assets**
  ADCB Q2 Campaign, delivery milestone

### ⚠️ Attention
- GMG AR is 67 days overdue (484,352 AED) — escalation recommended
- 2 items waiting on others for 7+ days

### 📊 Summary
12 open | 4 waiting | 6 due this week
```

### 4.3 Evening Review (On Request)

**Trigger:** Moh asks "how'd today go?" or similar  
**Not automatic** — only on request

**Structure:**

```markdown
## Day Review — {date}

### ✅ Completed ({count})
{Items marked done today}

### 🔄 Still Open ({count})
{Open items, sorted by due date}

### ⏰ Due Tomorrow ({count})
{Items due tomorrow — heads up}

### ⏳ Waiting ({count}, {oldest} days oldest)
{Items in waiting status}
```

---

## 5. Capture Protocol

**When A captures something, it follows this exact protocol.**

### 5.1 Capture Triggers

A captures an Item when:

| Trigger | Example | Action |
|---------|---------|--------|
| Explicit request | "Track this" / "Remind me to" / "I need to" | Capture immediately |
| Commitment detected | "I'll send that by Friday" | Confirm, then capture |
| Task delegated | "Can you follow up with..." | Capture with owner |
| External commitment | "Dana said she'll send..." | Capture as waiting |

A does NOT capture:
- General discussion ("We should think about...")
- Already-tracked items (check first)
- Items clearly in Asana (defer to Asana)

### 5.2 Capture Conversation Flow

```
TRIGGER: Moh says something that sounds like a commitment

A's INTERNAL PROCESS:
1. Is this a trackable commitment? (not just discussion)
2. Is it already tracked? (search items)
3. Who owns it? (Moh or someone else)
4. When is it due? (explicit or infer)
5. What's the context? (client, project, person, stakes)

A's RESPONSE OPTIONS:

Option A — Clear commitment, context known:
"Got it: [what]. Due [when]. ([client], [project])"

Option B — Commitment unclear, need confirmation:
"Want me to track: [what]? When's it due?"

Option C — Context missing:
"Track: [what] by [when]. Which client/project is this for?"

Option D — Already tracked:
"Already tracking: [what] (due [when]). Update it?"
```

### 5.3 Capture Data Requirements

| Field | Required | Source |
|-------|----------|--------|
| what | YES | Conversation (exact or paraphrased) |
| owner | YES | Inferred ("me" if Moh's commitment) |
| due | NO | Explicit or ask |
| client | NO | Infer from context or ask |
| project | NO | Infer from context or ask |
| counterparty | NO | Infer from conversation |
| stakes | NO | Infer or leave blank |
| history | NO | Capture conversation context |

### 5.4 Context Inference Rules

```python
def infer_context(conversation_text: str, recent_messages: list) -> dict:
    """
    Infer context from conversation.
    
    Rules:
    1. If a client name mentioned in last 5 messages → use that client
    2. If a person name mentioned → lookup person → get their client
    3. If a project name mentioned → use that project → get its client
    4. If multiple possible → ask
    5. If none → capture without, flag for review
    """
    context = {}
    
    # Check last 5 messages for entity mentions
    for msg in recent_messages[-5:]:
        # Client match
        client = match_client(msg.text)
        if client:
            context['client_id'] = client.id
            context['client_name'] = client.name
            break
        
        # Person match
        person = match_person(msg.text)
        if person and person.client_id:
            context['counterparty_id'] = person.id
            context['counterparty'] = person.name
            context['client_id'] = person.client_id
            break
        
        # Project match
        project = match_project(msg.text)
        if project:
            context['project_id'] = project.id
            context['project_name'] = project.name
            if project.client_id:
                context['client_id'] = project.client_id
            break
    
    return context
```

### 5.5 Capture Confirmation Format

After capturing, A confirms with this format:

```
✓ Tracked: {what}
  Due: {due_date or "no date"}
  Owner: {owner}
  Context: {client_name}, {project_name}
```

Short. No fluff.

---

## 6. Surfacing Protocol

**When and how A surfaces items to Moh.**

### 6.1 Surfacing Triggers

| Trigger | When | What to Surface |
|---------|------|-----------------|
| Morning brief | 09:00 cron | Overdue + due today + attention items |
| Heartbeat | Every ~2 hours | Only critical items (overdue 3+ days, Tier A client risk) |
| Query response | On demand | Whatever was asked |
| Proactive alert | Real-time | Only if truly urgent (see criteria below) |

### 6.2 Urgency Criteria (Explicit Rules)

**Surface immediately (proactive alert) if:**
- Item is 5+ days overdue AND client tier = A
- Item is due today AND client tier = A AND stakes mention "deadline" or "contract"
- Client AR is 90+ days AND amount > 100K AED

**Surface in next brief if:**
- Item is overdue (any)
- Item is due within 24 hours
- Item has been waiting 7+ days

**Do not surface (unless asked):**
- Open items with no due date
- Items due 3+ days from now
- Tier C client items (unless specifically asked)

### 6.3 Surfacing Format

**Single item:**
```
**{what}** — due {due_date} ({status})
{counterparty} @ {client_name} ({client_tier}, {client_health})
{project_name}: {stakes}
{history if relevant}
```

**Example:**
```
**Send Ramadan campaign proposal to Dana** — due Jun 28 (3 days overdue)
Dana Oraibi (Head of Marketing) @ Sun Sand Sports (Tier A, good)
Ramadan Campaign: Flagship Q1 project, 200K AED
Requested after kickoff meeting Jan 28. She's direct, values detail.
```

**List of items (brief format):**
```
- **{what}** — {due_date} | {client_name} | {one-line context}
```

### 6.4 Context Refresh on Surfacing

When surfacing an item, A checks if context needs refresh:

```python
def should_refresh_context(item: Item) -> bool:
    """
    Refresh context if:
    1. Item is overdue (context might have changed)
    2. Snapshot is > 7 days old
    3. Client is Tier A (always want fresh data)
    """
    if item.is_overdue():
        return True
    
    snapshot_age = now() - item.context.snapshot.captured_at
    if snapshot_age > timedelta(days=7):
        return True
    
    if item.context.snapshot.client_tier == 'A':
        return True
    
    return False

def refresh_context(item: Item) -> Item:
    """Refresh context from current entity state."""
    if item.client_id:
        client = get_client(item.client_id)
        item.context.snapshot.client_health = client.health
        item.context.snapshot.client_ar_status = client.ar_aging_bucket
    
    if item.project_id:
        project = get_project(item.project_id)
        item.context.snapshot.project_status = project.status
        item.context.snapshot.project_health = project.health
    
    return item
```

---

## 7. Query Interface

**Natural language queries A handles.**

### 7.1 Query Patterns

| Query | Intent | Response |
|-------|--------|----------|
| "What's open?" | All open items | List with context, sorted by due date |
| "What's overdue?" | Overdue items | List with urgency context |
| "What's due this week?" | Due within 7 days | List sorted by date |
| "What about {client}?" | Client status | Client health + open items + AR status |
| "How's {project}?" | Project status | Project health + open items + blockers |
| "What am I waiting on?" | Waiting items | List with who/how long |
| "Status" | System summary | Open/waiting/overdue counts + health |
| "What's urgent?" | High priority | Tier A overdue + critical AR + due today |

### 7.2 Query Response Format

**"What's open?"**
```
## Open Items ({count})

### Due This Week ({count})
- **{what}** — {due_date} | {client} | {context}
...

### Due Later ({count})
- **{what}** — {due_date} | {client}
...

### No Due Date ({count})
- **{what}** | {client}
...
```

**"What about GMG?"**
```
## GMG Consumer LLC

**Tier:** A | **Health:** fair (declining) | **AR:** 484K (67 days overdue)

### Open Items ({count})
- **{what}** — {due}
...

### Attention
- AR significantly overdue — recommend escalation
- Last interaction: {date} ({days} days ago)
```

**"Status"**
```
## System Status

**Items:** {open} open | {waiting} waiting | {overdue} overdue
**Due this week:** {count}
**Clients at risk:** {count with health = poor/critical}
**AR attention:** {count with ar_aging > 60 days}

**System health:** {HEALTHY|DEGRADED|FAILED}
**Last backup:** {datetime}
```

---

## 8. Decision Heuristics

**Explicit rules for A's judgment. No ambiguity.**

### 8.1 Priority Scoring

Every item gets a priority score (0-100). Not shown to Moh, but used for ordering.

```python
def calculate_priority(item: Item) -> int:
    """
    Priority score 0-100. Higher = more urgent.
    
    Components:
    - Due date pressure (0-40)
    - Client tier (0-25)
    - Client health (0-15)
    - Stakes keywords (0-10)
    - Waiting duration (0-10)
    """
    score = 0
    
    # Due date pressure
    if item.due:
        days_until = (item.due - today()).days
        if days_until < 0:  # Overdue
            score += min(40, 20 + abs(days_until) * 2)  # 20-40
        elif days_until == 0:  # Due today
            score += 20
        elif days_until <= 2:
            score += 15
        elif days_until <= 7:
            score += 10
        else:
            score += 5
    
    # Client tier
    tier = item.context.snapshot.client_tier
    if tier == 'A':
        score += 25
    elif tier == 'B':
        score += 15
    elif tier == 'C':
        score += 5
    
    # Client health
    health = item.context.snapshot.client_health
    if health == 'critical':
        score += 15
    elif health == 'poor':
        score += 10
    elif health == 'fair':
        score += 5
    
    # Stakes keywords
    stakes = (item.context.stakes or '').lower()
    high_stakes_keywords = ['contract', 'deadline', 'launch', 'critical', 'urgent', 'escalate']
    if any(kw in stakes for kw in high_stakes_keywords):
        score += 10
    
    # Waiting duration
    if item.status == 'waiting' and item.waiting_since:
        waiting_days = (now() - item.waiting_since).days
        score += min(10, waiting_days)
    
    return min(100, score)
```

### 8.2 Surfacing Threshold

```python
SURFACE_IMMEDIATELY_THRESHOLD = 70   # Proactive alert
SURFACE_IN_BRIEF_THRESHOLD = 40      # Include in morning brief
SURFACE_ON_QUERY_THRESHOLD = 0       # Always show when asked
```

### 8.3 Classification Heuristics

**Auto-classify client tier (suggestion to Moh):**
```python
def suggest_tier(client: Client) -> str:
    """Suggest tier based on objective data."""
    if client.annual_value and client.annual_value >= 500000:
        return 'A'
    if client.annual_value and client.annual_value >= 100000:
        return 'B'
    if client.ar_total and client.ar_total >= 200000:
        return 'A'  # High AR = important to track
    return 'C'
```

**Auto-classify project health:**
```python
def calculate_project_health(project: Project) -> str:
    """Calculate project health from signals."""
    signals = []
    
    # Overdue items
    overdue_count = count_items(project_id=project.id, status='open', overdue=True)
    if overdue_count >= 3:
        signals.append('late')
    elif overdue_count >= 1:
        signals.append('at_risk')
    
    # Blockers
    if project.blockers and len(project.blockers) > 0:
        signals.append('blocked')
    
    # Past target date
    if project.target_end_date and project.target_end_date < today():
        signals.append('late')
    
    # Return worst status
    if 'late' in signals:
        return 'late'
    if 'blocked' in signals:
        return 'blocked'
    if 'at_risk' in signals:
        return 'at_risk'
    return 'on_track'
```

### 8.4 When to Ask vs Infer

| Situation | Action |
|-----------|--------|
| Client unclear, only one recent client discussed | Infer, confirm |
| Client unclear, multiple clients discussed | Ask |
| Due date not stated | Ask "When's it due?" |
| Due date implied ("end of week") | Infer Friday, confirm |
| Owner unclear | Assume "me" unless clearly delegated |
| Stakes unclear | Leave blank, don't ask (not critical) |

---

## 9. Sync & Conflict Resolution

### 9.1 Source of Truth by Domain

| Domain | Source of Truth | This System's Role |
|--------|-----------------|-------------------|
| Tasks (project work) | Asana | Import overdue for context |
| Financial data | Xero | Sync AR for client health |
| Commitments/promises | **This system** | Primary owner |
| Calendar | Google Calendar | Read only |
| Client relationship | **This system** | Primary owner (tier, health, notes) |

### 9.2 Sync Strategy

**Xero → Clients (daily via cron)**
```python
def sync_xero_clients():
    """
    Sync AR data from Xero to clients.
    Does NOT overwrite: tier, health, relationship_notes
    """
    xero_contacts = xero_api.get_contacts()
    
    for contact in xero_contacts:
        client = find_client_by_xero_id(contact.id)
        if not client:
            # New contact — create minimal client
            create_client(
                name=contact.name,
                xero_contact_id=contact.id,
                source='xero'
            )
            client = find_client_by_xero_id(contact.id)
        
        # Update financial data only
        update_client(client.id,
            ar_total=contact.ar_total,
            ar_overdue=contact.ar_overdue,
            ar_aging_bucket=calculate_aging(contact),
            last_synced_at=now()
        )
```

**Asana → Projects (daily via cron)**
```python
def sync_asana_projects():
    """
    Sync project status from Asana.
    Does NOT overwrite: stakes, value, client_id (if set)
    """
    asana_projects = asana_api.get_projects(workspace='hrmny.co')
    
    for proj in asana_projects:
        project = find_project_by_asana_id(proj.gid)
        if not project:
            # New project — create, attempt client match
            client_id = match_client(proj.name)
            create_project(
                name=proj.name,
                asana_project_id=proj.gid,
                client_id=client_id,
                source='asana'
            )
            project = find_project_by_asana_id(proj.gid)
        
        # Update status only
        update_project(project.id,
            status=map_asana_status(proj),
            last_synced_at=now()
        )
```

### 9.3 Conflict Resolution Rules

| Conflict | Resolution |
|----------|------------|
| Same item in Asana and here | This system for commitments, Asana for tasks. They're different. |
| Client name changed in Xero | Update name, keep all other data |
| Project archived in Asana | Set status='cancelled' here, keep history |
| AR data differs from manual notes | Xero wins for numbers, notes preserved |
| Person exists with same email, different name | Keep existing, add alias |

---

## 10. Failure Modes & Recovery

### 10.1 Health Model

```
HEALTHY   → All checks pass
DEGRADED  → Non-critical issues, continue with warnings
FAILED    → Cannot operate, memory mode
```

### 10.2 Health Checks

| Check | Threshold | On Fail |
|-------|-----------|---------|
| db_exists | File exists | FAILED |
| db_readable | Can SELECT | FAILED |
| db_writable | Can INSERT (test table) | DEGRADED (read-only mode) |
| db_integrity | PRAGMA integrity_check = ok | FAILED |
| backup_age | < 48 hours | DEGRADED (warn, attempt backup) |
| disk_space | > 100MB free | DEGRADED (warn) |
| xero_connected | Can auth | DEGRADED (stale AR data warning) |
| asana_connected | Can auth | DEGRADED (stale project data warning) |

### 10.3 Failure Runbooks

**FAILED: Database Missing**
```
1. A announces: "Database missing. Entering memory mode. Will queue operations."
2. Check for backups: ls moh_time_os/data/backups/
3. If backup exists:
   a. cp backups/latest.db data/moh_time_os.db
   b. Run health_check()
   c. A announces: "Restored from backup ({date}). {n} items recovered."
4. If no backup:
   a. A announces: "No backup found. Starting fresh. Bootstrap required."
   b. init_db()
   c. Run bootstrap sequence
```

**FAILED: Database Corrupted**
```
1. A announces: "Database corruption detected. Attempting recovery."
2. Try: sqlite3 moh_time_os.db ".recover" > recovered.sql
3. If recovery works:
   a. Create new db, execute recovered.sql
   b. Run integrity_check()
   c. A announces: "Recovered {n}% of data."
4. If recovery fails:
   a. Restore from backup (see above)
```

**DEGRADED: Xero Auth Failed**
```
1. A announces: "Xero connection lost. AR data may be stale."
2. Continue operation with cached data
3. Add to morning brief: "⚠️ Xero disconnected — AR data from {last_sync}"
4. Prompt Moh: "Want me to re-authenticate Xero?"
```

**DEGRADED: Backup Overdue**
```
1. Attempt immediate backup
2. If backup succeeds: Continue silently
3. If backup fails: Warn in next interaction
```

### 10.4 Self-Healing (Every Startup)

```python
def self_heal():
    """Run on every session start."""
    
    # 1. Ensure WAL mode
    db.execute("PRAGMA journal_mode=WAL")
    
    # 2. Checkpoint WAL (prevent bloat)
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    
    # 3. Ensure indexes exist
    for index in REQUIRED_INDEXES:
        db.execute(f"CREATE INDEX IF NOT EXISTS {index}")
    
    # 4. Prune old backups (keep 7)
    backups = sorted(glob("backups/*.db"))
    for old in backups[:-7]:
        os.remove(old)
    
    # 5. Clean temp files
    for tmp in glob("data/*.tmp"):
        os.remove(tmp)
    
    # 6. Verify foreign keys
    db.execute("PRAGMA foreign_key_check")
```

---

## 11. Implementation Plan

### Phase 0: Pre-Work (2 hours)

| Task | Time | Output |
|------|------|--------|
| Verify Xero OAuth still works | 15 min | Confirmed or re-auth |
| Verify Asana token works | 15 min | Confirmed or re-auth |
| Create directory structure | 15 min | `lib/`, `data/`, etc. |
| Set up test database | 15 min | `data/test.db` |
| Review existing code in `engine/` | 60 min | Reuse list |

### Phase 1: Foundation (Day 1)

| Task | Time | Output |
|------|------|--------|
| `lib/store.py` — DB connection + schema | 1 hr | Working schema |
| `lib/entities.py` — Client CRUD | 1 hr | create/get/find/update client |
| `lib/entities.py` — Person CRUD | 45 min | create/get/find/update person |
| `lib/entities.py` — Project CRUD | 45 min | create/get/find/update project |
| `lib/items.py` — Item CRUD + context | 1.5 hr | create/get/update item with context |
| `lib/queries.py` — Basic queries | 1 hr | open/overdue/due_today/for_client |
| `lib/health.py` — Health checks | 30 min | health_check() returns status |
| Unit tests | 1 hr | All CRUD tested |

**Deliverable:** Can create and query all entities via Python.

### Phase 2: Bootstrap (Day 2)

| Task | Time | Output |
|------|------|--------|
| `lib/sync_xero.py` — Xero contact sync | 2 hr | 153 clients imported |
| `lib/sync_asana.py` — Asana project sync | 2 hr | 289 projects imported |
| `lib/sync_asana.py` — Overdue tasks → Items | 1.5 hr | Overdue items imported |
| `lib/match.py` — Entity matching utils | 1 hr | match_client, match_person |
| Client ↔ Project linking | 1 hr | Projects linked to clients |
| Bootstrap verification | 30 min | Counts + spot checks |

**Deliverable:** System has real data. Can query "what's overdue?" with context.

### Phase 3: A Integration (Day 3)

| Task | Time | Output |
|------|------|--------|
| Session start health check | 30 min | A runs health_check on start |
| Capture via conversation | 2 hr | A can capture items naturally |
| Query handlers | 2 hr | A responds to "what's open?" etc. |
| Morning brief generation | 1.5 hr | Formatted brief output |
| Heartbeat integration | 1 hr | Pulse check in heartbeats |

**Deliverable:** System is live. A uses it for capture/surface/query.

### Phase 4: Hardening (Day 4-5)

| Task | Time | Output |
|------|------|--------|
| Backup automation (cron) | 1 hr | Daily backups |
| Xero sync automation (cron) | 1 hr | Daily AR refresh |
| Asana sync automation (cron) | 1 hr | Daily project refresh |
| Morning brief cron | 30 min | 09:00 brief delivery |
| Edge case handling | 2 hr | Graceful degradation |
| Manual tier/health classification (with Moh) | 2 hr | Top clients classified |

**Deliverable:** System runs autonomously. Moh is using it.

### Phase 5: Polish (Week 2+)

- Learn from usage patterns
- Refine surfacing thresholds
- Add more query patterns
- Entity relationship views
- Dashboard/reporting if needed

---

## 12. File-by-File Specification

### Directory Structure

```
moh_time_os/
├── __init__.py
├── config/
│   ├── settings.yaml          # Thresholds, cron times, etc.
│   └── .credentials.json      # API tokens (gitignored)
├── data/
│   ├── moh_time_os.db         # Main database
│   ├── backups/               # Daily backups
│   └── test.db                # Test database
├── lib/
│   ├── __init__.py
│   ├── store.py               # DB connection, schema, utils
│   ├── entities.py            # Client, Person, Project CRUD
│   ├── items.py               # Item CRUD + context capture
│   ├── queries.py             # Query helpers
│   ├── match.py               # Entity matching/resolution
│   ├── health.py              # Health checks, self-healing
│   ├── backup.py              # Backup/restore
│   ├── sync_xero.py           # Xero → Clients sync
│   ├── sync_asana.py          # Asana → Projects/Items sync
│   ├── brief.py               # Morning brief generation
│   └── priority.py            # Priority scoring
├── docs/
│   ├── SYSTEM_DESIGN_V3.md    # This document
│   └── CHANGELOG.md           # Version history
└── tests/
    ├── test_entities.py
    ├── test_items.py
    ├── test_queries.py
    └── test_sync.py
```

### 12.1 lib/store.py

```python
"""
Database connection and schema management.

Responsibilities:
- SQLite connection with WAL mode
- Schema creation and migration
- Connection context manager
- Utility functions (now_iso, generate_id)
"""

import sqlite3
import uuid
import logging
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

log = logging.getLogger("moh_time_os")

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "moh_time_os.db"
BACKUP_DIR = DATA_DIR / "backups"

# Schema version (for migrations)
SCHEMA_VERSION = 1

SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- Clients
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    aliases_json TEXT DEFAULT '[]',
    
    xero_contact_id TEXT UNIQUE,
    source TEXT DEFAULT 'manual',
    
    tier TEXT CHECK (tier IN ('A', 'B', 'C') OR tier IS NULL),
    type TEXT DEFAULT 'agency_client',
    
    financial_ar_total REAL DEFAULT 0,
    financial_ar_overdue REAL DEFAULT 0,
    financial_ar_aging_bucket TEXT,
    financial_last_invoice_date TEXT,
    financial_last_payment_date TEXT,
    financial_annual_value REAL,
    
    relationship_health TEXT CHECK (relationship_health IN 
        ('excellent', 'good', 'fair', 'poor', 'critical') OR relationship_health IS NULL),
    relationship_trend TEXT CHECK (relationship_trend IN 
        ('improving', 'stable', 'declining') OR relationship_trend IS NULL),
    relationship_notes TEXT DEFAULT '',
    relationship_last_interaction TEXT,
    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_synced_at TEXT
);

-- People
CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    
    type TEXT CHECK (type IN ('internal', 'external')) DEFAULT 'external',
    company TEXT,
    client_id TEXT REFERENCES clients(id),
    role TEXT,
    department TEXT,
    
    relationship_trust TEXT DEFAULT 'unknown',
    relationship_style TEXT,
    relationship_responsiveness TEXT DEFAULT 'unknown',
    relationship_notes TEXT DEFAULT '',
    
    asana_user_id TEXT UNIQUE,
    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    
    client_id TEXT REFERENCES clients(id),
    asana_project_id TEXT UNIQUE,
    source TEXT DEFAULT 'manual',
    
    status TEXT DEFAULT 'active',
    health TEXT DEFAULT 'on_track',
    
    start_date TEXT,
    target_end_date TEXT,
    
    value REAL,
    stakes TEXT DEFAULT '',
    description TEXT DEFAULT '',
    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_synced_at TEXT
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
    
    context_client_name TEXT,
    context_project_name TEXT,
    context_person_name TEXT,
    context_stakes TEXT DEFAULT '',
    context_history TEXT DEFAULT '',
    context_snapshot_json TEXT,
    
    source_type TEXT DEFAULT 'manual',
    source_ref TEXT,
    source_captured_at TEXT NOT NULL,
    source_captured_by TEXT DEFAULT 'A',
    
    resolution_outcome TEXT,
    resolution_notes TEXT,
    resolution_resolved_at TEXT,
    resolution_resolved_by TEXT,
    
    priority_score INTEGER DEFAULT 0,
    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Item History
CREATE TABLE IF NOT EXISTS item_history (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES items(id),
    timestamp TEXT NOT NULL,
    change_type TEXT NOT NULL,
    change_detail TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    notes TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_clients_name_normalized ON clients(name_normalized);
CREATE INDEX IF NOT EXISTS idx_clients_tier ON clients(tier);
CREATE INDEX IF NOT EXISTS idx_clients_xero_id ON clients(xero_contact_id);

CREATE INDEX IF NOT EXISTS idx_people_name_normalized ON people(name_normalized);
CREATE INDEX IF NOT EXISTS idx_people_email ON people(email);
CREATE INDEX IF NOT EXISTS idx_people_client ON people(client_id);

CREATE INDEX IF NOT EXISTS idx_projects_name_normalized ON projects(name_normalized);
CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id);
CREATE INDEX IF NOT EXISTS idx_projects_asana_id ON projects(asana_project_id);

CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_due ON items(due);
CREATE INDEX IF NOT EXISTS idx_items_client ON items(client_id);
CREATE INDEX IF NOT EXISTS idx_items_project ON items(project_id);
CREATE INDEX IF NOT EXISTS idx_items_priority ON items(priority_score DESC);

CREATE INDEX IF NOT EXISTS idx_history_item ON item_history(item_id);
"""


def init_db(db_path: Path = None):
    """Initialize database with schema."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    with get_connection(path) as conn:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        
        # Record schema version
        conn.execute("""
            INSERT OR IGNORE INTO _schema_version (version, applied_at)
            VALUES (?, ?)
        """, (SCHEMA_VERSION, now_iso()))
    
    log.info(f"Database initialized at {path}")


@contextmanager
def get_connection(db_path: Path = None):
    """Get database connection with auto-commit/rollback."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def now_iso() -> str:
    """Current UTC time in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def generate_id() -> str:
    """Generate a new UUID."""
    return str(uuid.uuid4())


def normalize_name(name: str) -> str:
    """Normalize name for matching."""
    import re
    # Lowercase, remove punctuation, collapse whitespace
    normalized = name.lower()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized
```

### 12.2 lib/entities.py

```python
"""
Entity CRUD for Clients, People, Projects.

Each entity has:
- create_X() → returns ID
- get_X(id) → returns entity or None
- find_X(query) → returns entity or None (fuzzy match)
- update_X(id, **changes) → returns bool
- list_X(**filters) → returns list
"""

import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from .store import get_connection, now_iso, generate_id, normalize_name


# ═══════════════════════════════════════════════════════════════════════════
# CLIENT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Client:
    id: str
    name: str
    name_normalized: str
    aliases: List[str] = field(default_factory=list)
    
    xero_contact_id: str = None
    source: str = "manual"
    
    tier: str = None  # A, B, C
    type: str = "agency_client"
    
    # Financial
    ar_total: float = 0
    ar_overdue: float = 0
    ar_aging_bucket: str = None
    last_invoice_date: str = None
    last_payment_date: str = None
    annual_value: float = None
    
    # Relationship
    health: str = None
    trend: str = None
    notes: str = ""
    last_interaction: str = None
    
    created_at: str = None
    updated_at: str = None
    last_synced_at: str = None
    
    def summary(self) -> str:
        """One-line summary."""
        parts = [self.name]
        if self.tier:
            parts.append(f"Tier {self.tier}")
        if self.health:
            parts.append(self.health)
        if self.ar_aging_bucket and self.ar_aging_bucket != 'current':
            parts.append(f"AR: {self.ar_aging_bucket}")
        return " | ".join(parts)
    
    def full_context(self) -> str:
        """Full context for surfacing."""
        parts = [f"{self.name}"]
        if self.tier:
            parts.append(f"Tier {self.tier}")
        if self.annual_value:
            parts.append(f"{self.annual_value:,.0f} AED annual")
        if self.health:
            parts.append(f"Health: {self.health}")
            if self.trend and self.trend != 'stable':
                parts[-1] += f" ({self.trend})"
        if self.ar_overdue > 0:
            parts.append(f"AR overdue: {self.ar_overdue:,.0f} AED ({self.ar_aging_bucket})")
        if self.notes:
            parts.append(self.notes)
        return ". ".join(parts)


def create_client(
    name: str,
    tier: str = None,
    xero_contact_id: str = None,
    source: str = "manual",
    **kwargs
) -> str:
    """Create a new client. Returns client ID."""
    client_id = generate_id()
    now = now_iso()
    
    # Extract aliases from name (e.g., "GMG Consumer LLC" → ["GMG"])
    aliases = kwargs.get('aliases', [])
    name_parts = name.split()
    if len(name_parts) > 1 and name_parts[0] not in aliases:
        aliases.append(name_parts[0])
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO clients (
                id, name, name_normalized, aliases_json,
                xero_contact_id, source, tier, type,
                financial_ar_total, financial_ar_overdue,
                financial_ar_aging_bucket, financial_last_invoice_date,
                financial_last_payment_date, financial_annual_value,
                relationship_health, relationship_trend,
                relationship_notes, relationship_last_interaction,
                created_at, updated_at, last_synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id, name, normalize_name(name), json.dumps(aliases),
            xero_contact_id, source, tier, kwargs.get('type', 'agency_client'),
            kwargs.get('ar_total', 0), kwargs.get('ar_overdue', 0),
            kwargs.get('ar_aging_bucket'), kwargs.get('last_invoice_date'),
            kwargs.get('last_payment_date'), kwargs.get('annual_value'),
            kwargs.get('health'), kwargs.get('trend'),
            kwargs.get('notes', ''), kwargs.get('last_interaction'),
            now, now, kwargs.get('last_synced_at')
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
        
        return _row_to_client(row)


def find_client(query: str = None, xero_id: str = None) -> Optional[Client]:
    """
    Find client by name (fuzzy) or Xero ID.
    
    Matching priority:
    1. Exact xero_contact_id match
    2. Exact name_normalized match
    3. Alias match
    4. Substring match
    """
    with get_connection() as conn:
        # 1. Xero ID match
        if xero_id:
            row = conn.execute(
                "SELECT * FROM clients WHERE xero_contact_id = ?", (xero_id,)
            ).fetchone()
            if row:
                return _row_to_client(row)
        
        if not query:
            return None
        
        query_normalized = normalize_name(query)
        
        # 2. Exact name match
        row = conn.execute(
            "SELECT * FROM clients WHERE name_normalized = ?", (query_normalized,)
        ).fetchone()
        if row:
            return _row_to_client(row)
        
        # 3. Check all clients for alias or substring match
        rows = conn.execute("SELECT * FROM clients").fetchall()
        for row in rows:
            aliases = json.loads(row['aliases_json'] or '[]')
            aliases_normalized = [normalize_name(a) for a in aliases]
            
            # Alias match
            if query_normalized in aliases_normalized:
                return _row_to_client(row)
            
            # Substring match (query in name or name in query)
            if query_normalized in row['name_normalized']:
                return _row_to_client(row)
            if row['name_normalized'] in query_normalized:
                return _row_to_client(row)
        
        return None


def update_client(client_id: str, **changes) -> bool:
    """Update client fields."""
    if not changes:
        return False
    
    # Field mapping
    field_map = {
        'ar_total': 'financial_ar_total',
        'ar_overdue': 'financial_ar_overdue',
        'ar_aging_bucket': 'financial_ar_aging_bucket',
        'last_invoice_date': 'financial_last_invoice_date',
        'last_payment_date': 'financial_last_payment_date',
        'annual_value': 'financial_annual_value',
        'health': 'relationship_health',
        'trend': 'relationship_trend',
        'notes': 'relationship_notes',
        'last_interaction': 'relationship_last_interaction',
    }
    
    updates = {}
    for k, v in changes.items():
        col = field_map.get(k, k)
        if col == 'aliases':
            updates['aliases_json'] = json.dumps(v)
        else:
            updates[col] = v
    
    updates['updated_at'] = now_iso()
    
    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [client_id]
    
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE clients SET {set_clause} WHERE id = ?", values
        )
        return cursor.rowcount > 0


def list_clients(
    tier: str = None,
    health: str = None,
    has_ar_overdue: bool = None,
    limit: int = 100
) -> List[Client]:
    """List clients with optional filters."""
    conditions = []
    params = []
    
    if tier:
        conditions.append("tier = ?")
        params.append(tier)
    if health:
        conditions.append("relationship_health = ?")
        params.append(health)
    if has_ar_overdue:
        conditions.append("financial_ar_overdue > 0")
    
    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)
    
    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT * FROM clients 
            WHERE {where}
            ORDER BY 
                CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
                name
            LIMIT ?
        """, params).fetchall()
        
        return [_row_to_client(row) for row in rows]


def _row_to_client(row) -> Client:
    """Convert database row to Client object."""
    return Client(
        id=row['id'],
        name=row['name'],
        name_normalized=row['name_normalized'],
        aliases=json.loads(row['aliases_json'] or '[]'),
        xero_contact_id=row['xero_contact_id'],
        source=row['source'],
        tier=row['tier'],
        type=row['type'],
        ar_total=row['financial_ar_total'] or 0,
        ar_overdue=row['financial_ar_overdue'] or 0,
        ar_aging_bucket=row['financial_ar_aging_bucket'],
        last_invoice_date=row['financial_last_invoice_date'],
        last_payment_date=row['financial_last_payment_date'],
        annual_value=row['financial_annual_value'],
        health=row['relationship_health'],
        trend=row['relationship_trend'],
        notes=row['relationship_notes'] or '',
        last_interaction=row['relationship_last_interaction'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        last_synced_at=row['last_synced_at']
    )


# ═══════════════════════════════════════════════════════════════════════════
# PERSON
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Person:
    id: str
    name: str
    name_normalized: str
    email: str = None
    phone: str = None
    
    type: str = "external"
    company: str = None
    client_id: str = None
    role: str = None
    department: str = None
    
    trust: str = "unknown"
    style: str = None
    responsiveness: str = "unknown"
    notes: str = ""
    
    asana_user_id: str = None
    
    created_at: str = None
    updated_at: str = None
    
    def summary(self) -> str:
        parts = [self.name]
        if self.role:
            parts.append(f"({self.role})")
        if self.company:
            parts.append(f"@ {self.company}")
        return " ".join(parts)
    
    def full_context(self) -> str:
        parts = [self.name]
        if self.role:
            parts.append(f"({self.role})")
        if self.company:
            parts.append(f"at {self.company}")
        if self.notes:
            parts.append(f"— {self.notes}")
        return " ".join(parts)


def create_person(name: str, **kwargs) -> str:
    """Create a new person. Returns person ID."""
    person_id = generate_id()
    now = now_iso()
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO people (
                id, name, name_normalized, email, phone,
                type, company, client_id, role, department,
                relationship_trust, relationship_style,
                relationship_responsiveness, relationship_notes,
                asana_user_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            person_id, name, normalize_name(name),
            kwargs.get('email'), kwargs.get('phone'),
            kwargs.get('type', 'external'), kwargs.get('company'),
            kwargs.get('client_id'), kwargs.get('role'), kwargs.get('department'),
            kwargs.get('trust', 'unknown'), kwargs.get('style'),
            kwargs.get('responsiveness', 'unknown'), kwargs.get('notes', ''),
            kwargs.get('asana_user_id'), now, now
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
        
        return _row_to_person(row)


def find_person(name: str = None, email: str = None) -> Optional[Person]:
    """Find person by name or email."""
    with get_connection() as conn:
        if email:
            row = conn.execute(
                "SELECT * FROM people WHERE LOWER(email) = LOWER(?)", (email,)
            ).fetchone()
            if row:
                return _row_to_person(row)
        
        if name:
            name_normalized = normalize_name(name)
            row = conn.execute(
                "SELECT * FROM people WHERE name_normalized = ?", (name_normalized,)
            ).fetchone()
            if row:
                return _row_to_person(row)
            
            # Partial match
            row = conn.execute(
                "SELECT * FROM people WHERE name_normalized LIKE ?", (f"%{name_normalized}%",)
            ).fetchone()
            if row:
                return _row_to_person(row)
        
        return None


def _row_to_person(row) -> Person:
    return Person(
        id=row['id'],
        name=row['name'],
        name_normalized=row['name_normalized'],
        email=row['email'],
        phone=row['phone'],
        type=row['type'],
        company=row['company'],
        client_id=row['client_id'],
        role=row['role'],
        department=row['department'],
        trust=row['relationship_trust'],
        style=row['relationship_style'],
        responsiveness=row['relationship_responsiveness'],
        notes=row['relationship_notes'] or '',
        asana_user_id=row['asana_user_id'],
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )


# ═══════════════════════════════════════════════════════════════════════════
# PROJECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Project:
    id: str
    name: str
    name_normalized: str
    
    client_id: str = None
    asana_project_id: str = None
    source: str = "manual"
    
    status: str = "active"
    health: str = "on_track"
    
    start_date: str = None
    target_end_date: str = None
    
    value: float = None
    stakes: str = ""
    description: str = ""
    
    created_at: str = None
    updated_at: str = None
    last_synced_at: str = None
    
    def summary(self) -> str:
        return f"{self.name} ({self.status}, {self.health})"
    
    def full_context(self) -> str:
        parts = [f"{self.name} — {self.status}"]
        if self.health != 'on_track':
            parts.append(f"({self.health})")
        if self.value:
            parts.append(f"Value: {self.value:,.0f} AED")
        if self.stakes:
            parts.append(f"Stakes: {self.stakes}")
        if self.target_end_date:
            parts.append(f"Due: {self.target_end_date}")
        return ". ".join(parts)


def create_project(name: str, client_id: str = None, **kwargs) -> str:
    """Create a new project. Returns project ID."""
    project_id = generate_id()
    now = now_iso()
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO projects (
                id, name, name_normalized, client_id, asana_project_id, source,
                status, health, start_date, target_end_date,
                value, stakes, description,
                created_at, updated_at, last_synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id, name, normalize_name(name),
            client_id, kwargs.get('asana_project_id'), kwargs.get('source', 'manual'),
            kwargs.get('status', 'active'), kwargs.get('health', 'on_track'),
            kwargs.get('start_date'), kwargs.get('target_end_date'),
            kwargs.get('value'), kwargs.get('stakes', ''), kwargs.get('description', ''),
            now, now, kwargs.get('last_synced_at')
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
        
        return _row_to_project(row)


def find_project(name: str = None, asana_id: str = None, client_id: str = None) -> Optional[Project]:
    """Find project by name, Asana ID, or client."""
    with get_connection() as conn:
        if asana_id:
            row = conn.execute(
                "SELECT * FROM projects WHERE asana_project_id = ?", (asana_id,)
            ).fetchone()
            if row:
                return _row_to_project(row)
        
        if name:
            name_normalized = normalize_name(name)
            row = conn.execute(
                "SELECT * FROM projects WHERE name_normalized = ?", (name_normalized,)
            ).fetchone()
            if row:
                return _row_to_project(row)
            
            # Partial match
            row = conn.execute(
                "SELECT * FROM projects WHERE name_normalized LIKE ?", (f"%{name_normalized}%",)
            ).fetchone()
            if row:
                return _row_to_project(row)
        
        if client_id:
            row = conn.execute(
                "SELECT * FROM projects WHERE client_id = ? AND status = 'active' LIMIT 1",
                (client_id,)
            ).fetchone()
            if row:
                return _row_to_project(row)
        
        return None


def _row_to_project(row) -> Project:
    return Project(
        id=row['id'],
        name=row['name'],
        name_normalized=row['name_normalized'],
        client_id=row['client_id'],
        asana_project_id=row['asana_project_id'],
        source=row['source'],
        status=row['status'],
        health=row['health'],
        start_date=row['start_date'],
        target_end_date=row['target_end_date'],
        value=row['value'],
        stakes=row['stakes'] or '',
        description=row['description'] or '',
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        last_synced_at=row['last_synced_at']
    )
```

### 12.3 lib/items.py

```python
"""
Item tracking with context capture.

Items are the core tracking unit — things that need to happen.
Every item captures context at creation for intelligent surfacing.
"""

import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import date, datetime

from .store import get_connection, now_iso, generate_id
from .entities import get_client, get_person, get_project


@dataclass
class ContextSnapshot:
    """Captured context at item creation."""
    client_name: str = None
    client_tier: str = None
    client_health: str = None
    client_ar_status: str = None
    
    project_name: str = None
    project_status: str = None
    project_health: str = None
    
    person_name: str = None
    person_role: str = None
    person_company: str = None
    
    stakes: str = ""
    history: str = ""
    captured_at: str = None
    
    def to_dict(self) -> dict:
        return {
            'client_name': self.client_name,
            'client_tier': self.client_tier,
            'client_health': self.client_health,
            'client_ar_status': self.client_ar_status,
            'project_name': self.project_name,
            'project_status': self.project_status,
            'project_health': self.project_health,
            'person_name': self.person_name,
            'person_role': self.person_role,
            'person_company': self.person_company,
            'stakes': self.stakes,
            'history': self.history,
            'captured_at': self.captured_at
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'ContextSnapshot':
        if not d:
            return cls()
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


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
    
    # Text context (always available)
    context_client_name: str = None
    context_project_name: str = None
    context_person_name: str = None
    context_stakes: str = ""
    context_history: str = ""
    
    # Snapshot (for surfacing)
    snapshot: ContextSnapshot = None
    
    # Source
    source_type: str = "manual"
    source_ref: str = None
    captured_at: str = None
    captured_by: str = "A"
    
    # Resolution
    resolution_outcome: str = None
    resolution_notes: str = None
    resolved_at: str = None
    resolved_by: str = None
    
    # Computed
    priority_score: int = 0
    
    created_at: str = None
    updated_at: str = None
    
    history: List[Dict] = field(default_factory=list)
    
    def is_overdue(self) -> bool:
        if not self.due or self.status != 'open':
            return False
        return self.due < date.today().isoformat()
    
    def days_overdue(self) -> int:
        if not self.is_overdue():
            return 0
        due_date = date.fromisoformat(self.due)
        return (date.today() - due_date).days
    
    def brief_display(self) -> str:
        """Short format for lists."""
        parts = [f"**{self.what}**"]
        if self.due:
            if self.is_overdue():
                parts.append(f"— ⚠️ {self.days_overdue()}d overdue")
            else:
                parts.append(f"— due {self.due}")
        if self.context_client_name:
            parts.append(f"| {self.context_client_name}")
        return " ".join(parts)
    
    def full_display(self) -> str:
        """Full context for surfacing."""
        lines = [f"**{self.what}**"]
        
        # Timing
        if self.due:
            if self.is_overdue():
                lines.append(f"⚠️ OVERDUE — was due {self.due} ({self.days_overdue()} days ago)")
            else:
                lines.append(f"Due: {self.due}")
        
        # People
        if self.counterparty:
            person_ctx = self.counterparty
            if self.snapshot and self.snapshot.person_role:
                person_ctx += f" ({self.snapshot.person_role})"
            if self.snapshot and self.snapshot.person_company:
                person_ctx += f" @ {self.snapshot.person_company}"
            lines.append(f"Who: {person_ctx}")
        
        # Client
        if self.context_client_name:
            client_ctx = self.context_client_name
            if self.snapshot:
                details = []
                if self.snapshot.client_tier:
                    details.append(f"Tier {self.snapshot.client_tier}")
                if self.snapshot.client_health:
                    details.append(self.snapshot.client_health)
                if self.snapshot.client_ar_status and self.snapshot.client_ar_status != 'current':
                    details.append(f"AR: {self.snapshot.client_ar_status}")
                if details:
                    client_ctx += f" ({', '.join(details)})"
            lines.append(f"Client: {client_ctx}")
        
        # Project
        if self.context_project_name:
            project_ctx = self.context_project_name
            if self.snapshot and self.snapshot.project_health and self.snapshot.project_health != 'on_track':
                project_ctx += f" ({self.snapshot.project_health})"
            lines.append(f"Project: {project_ctx}")
        
        # Stakes
        if self.context_stakes:
            lines.append(f"Stakes: {self.context_stakes}")
        
        # History
        if self.context_history:
            lines.append(f"Background: {self.context_history}")
        
        return "\n".join(lines)


def build_snapshot(
    client_id: str = None,
    project_id: str = None,
    counterparty_id: str = None,
    stakes: str = "",
    history: str = ""
) -> ContextSnapshot:
    """Build context snapshot from entity IDs."""
    snapshot = ContextSnapshot(
        stakes=stakes,
        history=history,
        captured_at=now_iso()
    )
    
    if client_id:
        client = get_client(client_id)
        if client:
            snapshot.client_name = client.name
            snapshot.client_tier = client.tier
            snapshot.client_health = client.health
            snapshot.client_ar_status = client.ar_aging_bucket
    
    if project_id:
        project = get_project(project_id)
        if project:
            snapshot.project_name = project.name
            snapshot.project_status = project.status
            snapshot.project_health = project.health
    
    if counterparty_id:
        person = get_person(counterparty_id)
        if person:
            snapshot.person_name = person.name
            snapshot.person_role = person.role
            snapshot.person_company = person.company
    
    return snapshot


def create_item(
    what: str,
    owner: str = "me",
    due: str = None,
    counterparty: str = None,
    counterparty_id: str = None,
    client_id: str = None,
    client_name: str = None,
    project_id: str = None,
    project_name: str = None,
    person_name: str = None,
    stakes: str = "",
    history: str = "",
    source_type: str = "manual",
    source_ref: str = None,
    captured_by: str = "A"
) -> str:
    """
    Create item with full context.
    
    Returns item ID.
    Raises ValueError if required fields missing.
    """
    if not what or not what.strip():
        raise ValueError("'what' is required")
    
    item_id = generate_id()
    now = now_iso()
    
    # Build snapshot
    snapshot = build_snapshot(
        client_id=client_id,
        project_id=project_id,
        counterparty_id=counterparty_id,
        stakes=stakes,
        history=history
    )
    
    # Fill text context from snapshot if not provided
    if not client_name and snapshot.client_name:
        client_name = snapshot.client_name
    if not project_name and snapshot.project_name:
        project_name = snapshot.project_name
    if not person_name and snapshot.person_name:
        person_name = snapshot.person_name
    
    # Calculate initial priority
    from .priority import calculate_priority
    priority = calculate_priority(
        due=due,
        client_tier=snapshot.client_tier,
        client_health=snapshot.client_health,
        stakes=stakes
    )
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO items (
                id, what, status, owner, owner_id,
                counterparty, counterparty_id, due, waiting_since,
                client_id, project_id,
                context_client_name, context_project_name, context_person_name,
                context_stakes, context_history, context_snapshot_json,
                source_type, source_ref, source_captured_at, source_captured_by,
                priority_score, created_at, updated_at
            ) VALUES (?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id, what.strip(), owner, None,
            counterparty, counterparty_id, due, None,
            client_id, project_id,
            client_name, project_name, person_name,
            stakes, history, json.dumps(snapshot.to_dict()),
            source_type, source_ref, now, captured_by,
            priority, now, now
        ))
        
        # Record creation in history
        conn.execute("""
            INSERT INTO item_history (id, item_id, timestamp, change_type, change_detail, changed_by)
            VALUES (?, ?, ?, 'created', 'Item created', ?)
        """, (generate_id(), item_id, now, captured_by))
    
    return item_id


def get_item(item_id: str, include_history: bool = False) -> Optional[Item]:
    """Get item by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        
        if not row:
            return None
        
        item = _row_to_item(row)
        
        if include_history:
            history = conn.execute("""
                SELECT timestamp, change_type, change_detail, changed_by, notes
                FROM item_history WHERE item_id = ?
                ORDER BY timestamp ASC
            """, (item_id,)).fetchall()
            item.history = [dict(h) for h in history]
        
        return item


def update_item(item_id: str, changed_by: str = "A", **changes) -> bool:
    """
    Update item fields.
    
    Tracks history automatically.
    Handles status transitions (waiting_since, resolved_at).
    """
    valid_fields = {
        'what', 'status', 'owner', 'counterparty', 'due',
        'context_stakes', 'context_history',
        'resolution_outcome', 'resolution_notes'
    }
    
    updates = {k: v for k, v in changes.items() if k in valid_fields}
    if not updates:
        return False
    
    now = now_iso()
    
    # Handle status transitions
    if 'status' in updates:
        new_status = updates['status']
        if new_status not in ('open', 'waiting', 'done', 'cancelled'):
            raise ValueError(f"Invalid status: {new_status}")
        
        if new_status == 'waiting':
            updates['waiting_since'] = now
        elif new_status in ('done', 'cancelled'):
            updates['resolution_resolved_at'] = now
            updates['resolution_resolved_by'] = changed_by
            if 'resolution_outcome' not in updates:
                updates['resolution_outcome'] = 'completed' if new_status == 'done' else 'cancelled'
    
    updates['updated_at'] = now
    
    # Recalculate priority if due changed
    if 'due' in updates:
        item = get_item(item_id)
        if item:
            from .priority import calculate_priority
            updates['priority_score'] = calculate_priority(
                due=updates['due'],
                client_tier=item.snapshot.client_tier if item.snapshot else None,
                client_health=item.snapshot.client_health if item.snapshot else None,
                stakes=item.context_stakes
            )
    
    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [item_id]
    
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE items SET {set_clause} WHERE id = ?", values
        )
        
        if cursor.rowcount == 0:
            return False
        
        # Record history
        change_desc = ", ".join(f"{k}={v}" for k, v in changes.items() if k in valid_fields)
        conn.execute("""
            INSERT INTO item_history (id, item_id, timestamp, change_type, change_detail, changed_by)
            VALUES (?, ?, ?, 'updated', ?, ?)
        """, (generate_id(), item_id, now, change_desc, changed_by))
    
    return True


def mark_done(item_id: str, notes: str = None, by: str = "A") -> bool:
    """Mark item as done."""
    return update_item(
        item_id,
        changed_by=by,
        status='done',
        resolution_outcome='completed',
        resolution_notes=notes
    )


def mark_waiting(item_id: str, by: str = "A") -> bool:
    """Mark item as waiting."""
    return update_item(item_id, changed_by=by, status='waiting')


def mark_cancelled(item_id: str, notes: str = None, by: str = "A") -> bool:
    """Cancel an item."""
    return update_item(
        item_id,
        changed_by=by,
        status='cancelled',
        resolution_outcome='cancelled',
        resolution_notes=notes
    )


def _row_to_item(row) -> Item:
    """Convert database row to Item."""
    snapshot_data = json.loads(row['context_snapshot_json'] or '{}')
    
    return Item(
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
        context_client_name=row['context_client_name'],
        context_project_name=row['context_project_name'],
        context_person_name=row['context_person_name'],
        context_stakes=row['context_stakes'] or '',
        context_history=row['context_history'] or '',
        snapshot=ContextSnapshot.from_dict(snapshot_data),
        source_type=row['source_type'],
        source_ref=row['source_ref'],
        captured_at=row['source_captured_at'],
        captured_by=row['source_captured_by'],
        resolution_outcome=row['resolution_outcome'],
        resolution_notes=row['resolution_notes'],
        resolved_at=row['resolution_resolved_at'],
        resolved_by=row['resolution_resolved_by'],
        priority_score=row['priority_score'] or 0,
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )
```

### 12.4 lib/priority.py

```python
"""
Priority scoring for items.

Explicit, deterministic scoring. No magic, no LLM vibes.
Score 0-100. Higher = more urgent.
"""

from datetime import date, timedelta
from typing import Optional


def calculate_priority(
    due: str = None,
    status: str = 'open',
    waiting_since: str = None,
    client_tier: str = None,
    client_health: str = None,
    stakes: str = None
) -> int:
    """
    Calculate priority score 0-100.
    
    Components:
    - Due date pressure (0-40 points)
    - Client tier (0-25 points)
    - Client health (0-15 points)
    - Stakes keywords (0-10 points)
    - Waiting duration (0-10 points)
    """
    score = 0
    today = date.today()
    
    # ─────────────────────────────────────────────────────────────────
    # DUE DATE PRESSURE (0-40 points)
    # ─────────────────────────────────────────────────────────────────
    if due and status == 'open':
        try:
            due_date = date.fromisoformat(due)
            days_until = (due_date - today).days
            
            if days_until < 0:
                # Overdue: 20 base + 2 per day, max 40
                score += min(40, 20 + abs(days_until) * 2)
            elif days_until == 0:
                # Due today
                score += 20
            elif days_until == 1:
                # Due tomorrow
                score += 17
            elif days_until <= 3:
                # Due in 2-3 days
                score += 15
            elif days_until <= 7:
                # Due this week
                score += 10
            elif days_until <= 14:
                # Due in 2 weeks
                score += 5
            # > 14 days: 0 points
        except ValueError:
            pass  # Invalid date format, skip
    
    # ─────────────────────────────────────────────────────────────────
    # CLIENT TIER (0-25 points)
    # ─────────────────────────────────────────────────────────────────
    tier_scores = {
        'A': 25,
        'B': 15,
        'C': 5
    }
    if client_tier:
        score += tier_scores.get(client_tier.upper(), 0)
    
    # ─────────────────────────────────────────────────────────────────
    # CLIENT HEALTH (0-15 points)
    # ─────────────────────────────────────────────────────────────────
    health_scores = {
        'critical': 15,
        'poor': 10,
        'fair': 5,
        'good': 2,
        'excellent': 0
    }
    if client_health:
        score += health_scores.get(client_health.lower(), 0)
    
    # ─────────────────────────────────────────────────────────────────
    # STAKES KEYWORDS (0-10 points)
    # ─────────────────────────────────────────────────────────────────
    if stakes:
        stakes_lower = stakes.lower()
        high_stakes_keywords = [
            'contract', 'deadline', 'launch', 'critical', 'urgent',
            'escalate', 'legal', 'compliance', 'penalty', 'expiring'
        ]
        if any(kw in stakes_lower for kw in high_stakes_keywords):
            score += 10
        elif any(kw in stakes_lower for kw in ['important', 'key', 'major', 'significant']):
            score += 5
    
    # ─────────────────────────────────────────────────────────────────
    # WAITING DURATION (0-10 points)
    # ─────────────────────────────────────────────────────────────────
    if status == 'waiting' and waiting_since:
        try:
            waiting_date = date.fromisoformat(waiting_since[:10])
            waiting_days = (today - waiting_date).days
            score += min(10, waiting_days)  # 1 point per day, max 10
        except ValueError:
            pass
    
    return min(100, score)


# ─────────────────────────────────────────────────────────────────────
# THRESHOLDS
# ─────────────────────────────────────────────────────────────────────

SURFACE_IMMEDIATELY_THRESHOLD = 70   # Proactive alert (Tier A + overdue)
SURFACE_IN_BRIEF_THRESHOLD = 40      # Include in morning brief
SURFACE_ON_QUERY_THRESHOLD = 0       # Always show when asked


def should_surface_immediately(score: int) -> bool:
    """Should this item trigger an immediate proactive alert?"""
    return score >= SURFACE_IMMEDIATELY_THRESHOLD


def should_surface_in_brief(score: int) -> bool:
    """Should this item be included in the morning brief?"""
    return score >= SURFACE_IN_BRIEF_THRESHOLD
```

### 12.5 lib/queries.py

```python
"""
Query helpers for common access patterns.

All queries return Item objects with full context.
"""

from typing import List, Optional
from datetime import date, timedelta

from .store import get_connection
from .items import Item, get_item


def open_items(limit: int = 100) -> List[Item]:
    """All open items, sorted by priority."""
    return _query_items(status='open', limit=limit)


def overdue(limit: int = 50) -> List[Item]:
    """Open items past due date."""
    today = date.today().isoformat()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id FROM items
            WHERE status = 'open' AND due IS NOT NULL AND due < ?
            ORDER BY due ASC, priority_score DESC
            LIMIT ?
        """, (today, limit)).fetchall()
        
        return [get_item(row['id']) for row in rows]


def due_today() -> List[Item]:
    """Items due today."""
    today = date.today().isoformat()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id FROM items
            WHERE status = 'open' AND due = ?
            ORDER BY priority_score DESC
        """, (today,)).fetchall()
        
        return [get_item(row['id']) for row in rows]


def due_this_week(limit: int = 50) -> List[Item]:
    """Open items due within 7 days."""
    today = date.today()
    end = (today + timedelta(days=7)).isoformat()
    
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id FROM items
            WHERE status = 'open' AND due IS NOT NULL AND due <= ?
            ORDER BY due ASC, priority_score DESC
            LIMIT ?
        """, (end, limit)).fetchall()
        
        return [get_item(row['id']) for row in rows]


def waiting(limit: int = 50) -> List[Item]:
    """Items in waiting status, sorted by how long waiting."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id FROM items
            WHERE status = 'waiting'
            ORDER BY waiting_since ASC
            LIMIT ?
        """, (limit,)).fetchall()
        
        return [get_item(row['id']) for row in rows]


def for_client(client_id: str, status: str = 'open') -> List[Item]:
    """Items for a specific client."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id FROM items
            WHERE client_id = ? AND status = ?
            ORDER BY priority_score DESC
        """, (client_id, status)).fetchall()
        
        return [get_item(row['id']) for row in rows]


def for_client_name(client_name: str, status: str = 'open') -> List[Item]:
    """Items by client name (text match)."""
    from .store import normalize_name
    name_normalized = normalize_name(client_name)
    
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id FROM items
            WHERE LOWER(context_client_name) LIKE ? AND status = ?
            ORDER BY priority_score DESC
        """, (f"%{name_normalized}%", status)).fetchall()
        
        return [get_item(row['id']) for row in rows]


def for_project(project_id: str, status: str = 'open') -> List[Item]:
    """Items for a specific project."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id FROM items
            WHERE project_id = ? AND status = ?
            ORDER BY priority_score DESC
        """, (project_id, status)).fetchall()
        
        return [get_item(row['id']) for row in rows]


def high_priority(threshold: int = 70, limit: int = 20) -> List[Item]:
    """Items above priority threshold."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id FROM items
            WHERE status = 'open' AND priority_score >= ?
            ORDER BY priority_score DESC
            LIMIT ?
        """, (threshold, limit)).fetchall()
        
        return [get_item(row['id']) for row in rows]


def summary_stats() -> dict:
    """Get summary statistics."""
    today = date.today().isoformat()
    week_end = (date.today() + timedelta(days=7)).isoformat()
    
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
            "SELECT COUNT(*) FROM items WHERE status = 'open' AND due < ?",
            (today,)
        ).fetchone()[0]
        
        stats['due_today'] = conn.execute(
            "SELECT COUNT(*) FROM items WHERE status = 'open' AND due = ?",
            (today,)
        ).fetchone()[0]
        
        stats['due_this_week'] = conn.execute("""
            SELECT COUNT(*) FROM items 
            WHERE status = 'open' AND due IS NOT NULL AND due <= ?
        """, (week_end,)).fetchone()[0]
        
        stats['high_priority'] = conn.execute(
            "SELECT COUNT(*) FROM items WHERE status = 'open' AND priority_score >= 70"
        ).fetchone()[0]
        
        # Client stats
        stats['clients_total'] = conn.execute(
            "SELECT COUNT(*) FROM clients"
        ).fetchone()[0]
        
        stats['clients_at_risk'] = conn.execute(
            "SELECT COUNT(*) FROM clients WHERE relationship_health IN ('poor', 'critical')"
        ).fetchone()[0]
        
        stats['clients_ar_overdue'] = conn.execute(
            "SELECT COUNT(*) FROM clients WHERE financial_ar_overdue > 0"
        ).fetchone()[0]
        
        return stats


def _query_items(
    status: str = None,
    client_id: str = None,
    project_id: str = None,
    limit: int = 100
) -> List[Item]:
    """Generic query helper."""
    conditions = []
    params = []
    
    if status:
        conditions.append("status = ?")
        params.append(status)
    if client_id:
        conditions.append("client_id = ?")
        params.append(client_id)
    if project_id:
        conditions.append("project_id = ?")
        params.append(project_id)
    
    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)
    
    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT id FROM items
            WHERE {where}
            ORDER BY priority_score DESC, due ASC NULLS LAST
            LIMIT ?
        """, params).fetchall()
        
        return [get_item(row['id']) for row in rows]
```

---

## 13. Test Plan

### 13.1 Unit Tests

```python
# tests/test_entities.py

def test_create_client():
    """Client creation with all fields."""
    client_id = create_client(
        name="Test Corp",
        tier="A",
        ar_total=50000,
        health="good"
    )
    assert client_id is not None
    
    client = get_client(client_id)
    assert client.name == "Test Corp"
    assert client.tier == "A"
    assert client.ar_total == 50000

def test_find_client_fuzzy():
    """Client fuzzy matching."""
    create_client(name="GMG Consumer LLC", tier="A")
    
    # Exact match
    assert find_client("GMG Consumer LLC") is not None
    
    # Alias match (auto-generated)
    assert find_client("GMG") is not None
    
    # Substring match
    assert find_client("Consumer") is not None
    
    # No match
    assert find_client("XYZ Corp") is None

def test_create_item_with_context():
    """Item creation captures context."""
    client_id = create_client(name="SSS", tier="A", health="good")
    project_id = create_project(name="Campaign", client_id=client_id)
    
    item_id = create_item(
        what="Send proposal",
        due="2025-07-15",
        client_id=client_id,
        project_id=project_id,
        stakes="Flagship project"
    )
    
    item = get_item(item_id)
    assert item.context_client_name == "SSS"
    assert item.snapshot.client_tier == "A"
    assert item.snapshot.client_health == "good"
    assert item.context_stakes == "Flagship project"

def test_priority_scoring():
    """Priority calculation is correct."""
    # Overdue Tier A = high priority
    score1 = calculate_priority(
        due=(date.today() - timedelta(days=3)).isoformat(),
        client_tier="A",
        client_health="good"
    )
    assert score1 >= 50  # Overdue (26) + Tier A (25) + good (2)
    
    # Future date, Tier C = low priority
    score2 = calculate_priority(
        due=(date.today() + timedelta(days=30)).isoformat(),
        client_tier="C"
    )
    assert score2 < 20

def test_item_status_transitions():
    """Status transitions work correctly."""
    item_id = create_item(what="Test item", owner="me")
    
    # Open → Waiting
    mark_waiting(item_id)
    item = get_item(item_id)
    assert item.status == "waiting"
    assert item.waiting_since is not None
    
    # Waiting → Done
    mark_done(item_id, notes="Completed")
    item = get_item(item_id)
    assert item.status == "done"
    assert item.resolved_at is not None
    assert item.resolution_notes == "Completed"
```

### 13.2 Integration Tests

```python
# tests/test_integration.py

def test_bootstrap_xero():
    """Xero sync creates clients with AR."""
    # Requires live Xero connection
    sync_xero_clients()
    
    clients = list_clients()
    assert len(clients) > 0
    
    # At least some have AR data
    with_ar = [c for c in clients if c.ar_total > 0]
    assert len(with_ar) > 0

def test_bootstrap_asana():
    """Asana sync creates projects."""
    # Requires live Asana connection
    sync_asana_projects()
    
    from .store import get_connection
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    
    assert count > 0

def test_morning_brief_generation():
    """Morning brief generates without error."""
    # Create test data
    client_id = create_client(name="Test", tier="A")
    create_item(
        what="Overdue item",
        due=(date.today() - timedelta(days=2)).isoformat(),
        client_id=client_id
    )
    create_item(
        what="Due today",
        due=date.today().isoformat(),
        client_id=client_id
    )
    
    brief = generate_morning_brief()
    
    assert "Overdue" in brief
    assert "Due Today" in brief
    assert "Overdue item" in brief
```

### 13.3 Smoke Tests (Manual)

After each phase, verify:

| Test | Expected |
|------|----------|
| `python -c "from moh_time_os.lib.store import init_db; init_db()"` | DB created, no errors |
| `python -c "from moh_time_os.lib.queries import summary_stats; print(summary_stats())"` | Stats dict returned |
| Query "what's overdue?" | A returns list with context |
| Create item via conversation | Item captured with context |
| Check morning brief | Formatted, includes overdue items |

---

## 14. Migration Path

### From Current State

Current `moh_time_os/` has:
- `engine/` — Discovery/pulse code (keep for reference)
- `config/` — Credentials (keep, use)
- `data/` — May have test DBs (clear)

**Migration steps:**

1. Back up current state: `cp -r moh_time_os moh_time_os_backup`
2. Create new `lib/` directory
3. Move credentials: Keep `config/.credentials.json`
4. Clear data: `rm -rf data/*.db data/backups/*`
5. Initialize fresh: `init_db()`
6. Run bootstrap

### Rollback

If something breaks:
1. Stop using new system
2. Restore: `cp -r moh_time_os_backup moh_time_os`
3. Old pulse/discovery code still works

---

## Appendix A: Cron Jobs

```yaml
# To be added to HEARTBEAT.md or cron config

morning_brief:
  schedule: "0 9 * * *"  # 09:00 Dubai daily
  action: Generate and send morning brief
  
xero_sync:
  schedule: "0 6 * * *"  # 06:00 Dubai daily
  action: Sync AR from Xero
  
asana_sync:
  schedule: "0 6 * * *"  # 06:00 Dubai daily
  action: Sync project status from Asana
  
backup:
  schedule: "0 3 * * *"  # 03:00 Dubai daily
  action: Backup database
```

---

## Appendix B: A Quick Reference

### Capture Phrases

When Moh says any of these, A should consider capturing:
- "I need to..."
- "Remind me to..."
- "Track this..."
- "I'll send..." / "I'll do..."
- "Follow up on..."
- "Don't let me forget..."
- "[Person] said they'll..." (capture as waiting)

### Query Phrases

| Moh Says | A Does |
|----------|--------|
| "What's open?" | `open_items()` |
| "What's overdue?" | `overdue()` |
| "What's due today?" | `due_today()` |
| "What's due this week?" | `due_this_week()` |
| "What am I waiting on?" | `waiting()` |
| "What about [client]?" | `for_client_name(client)` + client status |
| "Status" | `summary_stats()` |
| "What's urgent?" | `high_priority(70)` |

### Status Transitions

```
open ──────────────┬──────────────▶ done
                   │
                   ├──────────────▶ cancelled
                   │
                   └───▶ waiting ──┬──▶ done
                                   └──▶ cancelled
```

---

*End of document. This is the plan. Execute it.*
