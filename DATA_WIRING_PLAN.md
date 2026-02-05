# Data Wiring Plan — MOH Time OS

## Executive Summary

The system has **collectors that work** but **linking that's broken**. Data flows in but doesn't connect together.

| Component | Status | Impact |
|-----------|--------|--------|
| Task Collection | ✅ Working | 3,748 tasks |
| Calendar Collection | ✅ Working | 168 events |
| Gmail Collection | ✅ Working | 488 comms |
| Asana Collection | ✅ Working | Projects/tasks sync |
| Xero Collection | ⚠️ Works but wasn't running | 34 invoices (just fixed) |
| **Communications→Client Linking** | ❌ Broken | 0% linked |
| **Project→Client Linking** | ❌ Broken | 11% linked |
| **Commitment Extraction** | ❌ Not built | 0 commitments |
| **Team Member Registry** | ❌ Empty | 0 team members |
| **Client Identities** | ❌ Empty | 0 identities (required for comm linking) |

---

## Phase 1: Fix Critical Data Gaps (Day 1)

### 1.1 Populate client_identities Table

**Problem:** Communications can't link to clients because `client_identities` is empty.

**Solution:** Build identity registry from existing data.

```sql
-- client_identities schema
CREATE TABLE client_identities (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    identity_type TEXT NOT NULL,  -- 'email', 'domain', 'phone'
    identity_value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    created_at TEXT,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);
```

**Action:** Create `lib/build_client_identities.py`

```python
# Extract domains from:
# 1. Existing communications matched to invoices (same contact name)
# 2. Known client email patterns (hrmny clients)
# 3. Invoice contact emails from Xero

def build_identities():
    # From invoices (Xero has client names, we have emails)
    # Match invoice.client_name → communications.from_email where subject mentions client
    
    # From known patterns
    KNOWN_DOMAINS = {
        'gmg.ae': 'GMG Consumer LLC',
        'gargash.com': 'Gargash Enterprises L.L.C',
        'supercarepharmacy.com': 'Super Care Pharmacy L.L.C',
        'binsina.com': 'BinSina Pharmacy L.L.C',
        'sixt.ae': 'SIXT Rent a Car LLC',
        # ... etc
    }
```

**Deliverable:** Script that populates client_identities with domain mappings.

---

### 1.2 Run Project→Client Linker

**Problem:** 89% of projects have no client_id.

**Solution:** `lib/link_projects.py` exists but isn't being run automatically.

**Action:** 
1. Add to autonomous loop after normalization
2. Or run once manually to catch up

```python
# In lib/autonomous_loop.py, add after _normalize_data():
from .link_projects import link_all_projects
link_all_projects()
```

**Deliverable:** Projects linked to clients via name pattern matching.

---

### 1.3 Wire Xero Collector Properly

**Problem:** Xero collector exists but wasn't in sync_state (not being tracked).

**Root Cause:** The `core_sources` dict in orchestrator.py didn't include xero.

**Action:** Update `lib/collectors/orchestrator.py`:

```python
# Line 49-55: Add xero to core_sources
core_sources = {
    'tasks': {'enabled': True, 'sync_interval': 300},
    'calendar': {'enabled': True, 'sync_interval': 60},
    'gmail': {'enabled': True, 'sync_interval': 120},
    'asana': {'enabled': True, 'sync_interval': 300},
    'xero': {'enabled': True, 'sync_interval': 300},  # ADD THIS
}
```

**Deliverable:** Xero syncs every 5 minutes automatically.

---

## Phase 2: Build Missing Linkers (Day 2)

### 2.1 Communication→Client Linker

**Problem:** 488 communications, 0 linked to clients.

**Dependency:** Requires client_identities populated (Phase 1.1).

**Current Flow (broken):**
```
Gmail Collector → communications table (from_email populated)
                → normalizer._normalize_communications()
                → tries to match via client_identities (EMPTY!)
                → 0 links
```

**Fixed Flow:**
```
Gmail Collector → communications table
                → normalizer._normalize_communications()
                → matches from_domain against client_identities.identity_value
                → sets client_id and link_status='linked'
```

**Action:** After Phase 1.1, run normalizer to link existing communications:

```python
from lib.normalizer import Normalizer
n = Normalizer()
n._normalize_communications()  # Will now find matches
```

**Deliverable:** Communications linked to clients via email domain.

---

### 2.2 Task→Client Linker (via Project Chain)

**Problem:** Only 6.7% of tasks have client_id.

**Current Chain:**
```
tasks.project_id → projects.id → projects.client_id
```

**Solution:** The normalizer already does this, but projects need client_id first.

**Dependencies:**
1. Project→Client linking (Phase 1.2)
2. Task→Project linking (already 64%)

**Action:** Normalizer `_normalize_tasks()` already derives client_id from project chain. Just needs projects linked first.

---

### 2.3 Build Commitment Extractor

**Problem:** 0 commitments tracked. No extractor running.

**Solution:** Use `lib/promise_tracker.py` (exists but not integrated).

**Action:** Create `lib/commitment_extractor.py`:

```python
"""
Extracts commitments from communications.

Scans communications.body_text for:
- "I'll send you X by Y"
- "Will follow up on Z"
- "Let me get back to you"
- etc.

Creates commitment records linked to client + communication.
"""

import re
from datetime import datetime, timedelta
from .promise_tracker import COMMITMENT_SIGNALS, extract_deadline

def extract_commitments(comm_id: str, body: str, client_id: str) -> list:
    """Extract commitments from a communication body."""
    commitments = []
    
    for pattern in COMMITMENT_SIGNALS:
        matches = re.findall(pattern, body, re.IGNORECASE)
        for match in matches:
            deadline = extract_deadline(body)
            commitments.append({
                'source_type': 'communication',
                'source_id': comm_id,
                'text': match,
                'type': 'promise',  # or 'request'
                'client_id': client_id,
                'deadline': deadline,
                'status': 'open',
                'confidence': 0.7,
            })
    
    return commitments

def run_extraction():
    """Run commitment extraction on all unprocessed communications."""
    # Get communications with body_text that haven't been processed
    # Extract commitments
    # Insert into commitments table
    pass
```

**Integration Point:** Add to autonomous loop after gmail collection.

**Deliverable:** Commitments extracted from communications.

---

## Phase 3: Populate Reference Data (Day 3)

### 3.1 Build Team Member Registry

**Problem:** 0 team members. Capacity calculations need assignee→person mapping.

**Current State:**
- `tasks.assignee` = text names ("Ahmed Salah", "Zeiad", etc.)
- `team_members` table = empty
- `people` table = 70 records (but may be clients, not team)

**Action:** Create `lib/build_team_registry.py`:

```python
"""
Builds team member registry from task assignees.
"""

def build_team_registry():
    # 1. Get distinct assignees from tasks
    assignees = query("SELECT DISTINCT assignee FROM tasks WHERE assignee IS NOT NULL AND assignee != 'unassigned'")
    
    # 2. For each, create team_member record
    for assignee in assignees:
        # Infer lane from most common task lane
        lane = query("""
            SELECT lane, COUNT(*) as cnt 
            FROM tasks WHERE assignee = ? 
            GROUP BY lane ORDER BY cnt DESC LIMIT 1
        """, [assignee])
        
        insert('team_members', {
            'id': generate_id(),
            'name': assignee,
            'default_lane': lane,
        })
    
    # 3. Update tasks.assignee_id to point to team_members.id
    query("""
        UPDATE tasks 
        SET assignee_id = (SELECT id FROM team_members WHERE name = tasks.assignee)
        WHERE assignee IS NOT NULL
    """)
```

**Deliverable:** Team members populated, assignees linked.

---

### 3.2 Build Brand Registry

**Problem:** Only 33% of projects have brand_id.

**Current State:**
- `brands` table = 21 records
- `projects.brand_id` = mostly NULL

**Action:** Enhance `lib/link_projects.py` to also extract/link brands:

```python
# Add brand extraction to project linker
BRAND_PATTERNS = {
    'monoprix': {'brand': 'Monoprix', 'client': 'GMG Consumer LLC'},
    'geant': {'brand': 'Geant', 'client': 'GMG Consumer LLC'},
    'aswaaq': {'brand': 'Aswaaq', 'client': 'GMG Consumer LLC'},
    'mercedes': {'brand': 'Mercedes-Benz', 'client': 'Gargash Enterprises L.L.C'},
    # etc.
}
```

**Deliverable:** Brands linked to projects.

---

## Phase 4: Validate Data Integrity (Day 4)

### 4.1 Run Full Gate Check

```python
from lib.gates import evaluate_gates

gates = evaluate_gates()
for gate, result in gates.items():
    status = "✓" if result.get('pass') else "✗"
    print(f"{status} {gate}: {result}")
```

**Expected Gates:**
- `data_integrity` — all 6 invariants pass
- `project_brand_required` — non-internal projects have brand
- `client_coverage` — ≥80% tasks linked to clients
- `commitment_ready` — ≥50% comms have body_text
- `finance_ar_coverage` — ≥95% AR linked

### 4.2 Implement Missing Gate: Communication Coverage

```python
def check_comm_coverage():
    """Verify communications are linked to clients."""
    result = query("""
        SELECT 
            COUNT(*) FILTER (WHERE client_id IS NOT NULL) as linked,
            COUNT(*) as total
        FROM communications
    """)
    pct = result['linked'] / result['total'] * 100
    return {'pass': pct >= 50, 'pct': pct}
```

---

## Phase 5: Wire Everything into Autonomous Loop (Day 5)

### Current Loop Phases:
1. COLLECT — collectors sync external data
2. NORMALIZE — derive link statuses
3. GATES — check data integrity
4. RESOLUTION — populate resolution queue
5. SURFACE — generate moves
6. NOTIFY — send notifications

### Missing from Loop:
- Project→Client linking (should run in NORMALIZE)
- Communication→Client linking (runs, but depends on empty client_identities)
- Commitment extraction (not wired)
- Team member registry build (not wired)

### Updated Loop:

```python
def run_cycle(self):
    # Phase 1: COLLECT
    self.collectors.sync_all()  # includes xero now
    
    # Phase 1a: BUILD REGISTRIES (NEW)
    self._ensure_client_identities()
    self._ensure_team_registry()
    
    # Phase 2: LINK (NEW - before normalize)
    self._link_projects_to_clients()
    
    # Phase 3: NORMALIZE (existing)
    self._normalize_data()  # Now communications will link properly
    
    # Phase 3a: EXTRACT COMMITMENTS (NEW)
    self._extract_commitments()
    
    # Phase 4: GATES (existing)
    self._check_gates()
    
    # ... rest of cycle
```

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA COLLECTION                          │
├─────────────────────────────────────────────────────────────┤
│  Gmail → communications (✅)                                 │
│  Calendar → events (✅)                                      │
│  Asana → projects, tasks (✅)                                │
│  Google Tasks → tasks (✅)                                   │
│  Xero → invoices (✅ just fixed)                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   REFERENCE REGISTRIES                       │
├─────────────────────────────────────────────────────────────┤
│  client_identities (❌ EMPTY - BLOCKS COMM LINKING)         │
│  team_members (❌ EMPTY - BLOCKS CAPACITY)                   │
│  brands (⚠️ 21 records, 67% projects unlinked)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA LINKING                            │
├─────────────────────────────────────────────────────────────┤
│  projects → clients (⚠️ 11% linked)                         │
│  tasks → projects (⚠️ 64% linked)                           │
│  tasks → clients (❌ 6.7% linked, derived from project)     │
│  communications → clients (❌ 0% linked)                     │
│  invoices → clients (✅ 100% linked)                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   COMPUTED ENTITIES                          │
├─────────────────────────────────────────────────────────────┤
│  commitments (❌ 0 records - extractor not running)         │
│  client_health_log (✅ 1,401 records)                        │
│  resolution_queue (✅ working)                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Checklist

### Day 1: Critical Fixes
- [ ] Create `lib/build_client_identities.py` with known domain mappings
- [ ] Run client_identities population script
- [ ] Add xero to `core_sources` in orchestrator.py
- [ ] Run `lib/link_projects.py` to link projects→clients
- [ ] Verify invoices now show in dashboard

### Day 2: Linkers
- [ ] Run normalizer to link communications (after identities populated)
- [ ] Verify task→client linking works via project chain
- [ ] Create `lib/commitment_extractor.py`
- [ ] Test commitment extraction on sample communications

### Day 3: Registries
- [ ] Create `lib/build_team_registry.py`
- [ ] Populate team_members from task assignees
- [ ] Enhance brand linking in link_projects.py
- [ ] Verify capacity calculations work

### Day 4: Validation
- [ ] Run full gate check
- [ ] Fix any failing gates
- [ ] Verify client_coverage ≥80%
- [ ] Verify comm_coverage ≥50%

### Day 5: Integration
- [ ] Wire all new components into autonomous_loop.py
- [ ] Test full cycle with logging
- [ ] Verify dashboard shows accurate data
- [ ] Monitor for 24h

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Tasks → Client | 6.7% | ≥80% |
| Projects → Client | 11.1% | ≥90% |
| Comms → Client | 0% | ≥50% |
| Invoices → Client | 100% | 100% |
| Commitments | 0 | ≥50 extracted |
| Team Members | 0 | ≥10 |
| Client Identities | 0 | ≥20 |

---

## Files to Create/Modify

### New Files:
1. `lib/build_client_identities.py` — Domain registry builder
2. `lib/build_team_registry.py` — Team member builder
3. `lib/commitment_extractor.py` — Commitment extraction

### Modified Files:
1. `lib/collectors/orchestrator.py` — Add xero to core_sources
2. `lib/autonomous_loop.py` — Wire new components
3. `lib/link_projects.py` — Enhance brand linking
4. `lib/normalizer.py` — May need updates for new linking logic

---

## Estimated Effort

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1 | 2-3 hours | None |
| Phase 2 | 3-4 hours | Phase 1 |
| Phase 3 | 2-3 hours | Phase 2 |
| Phase 4 | 1-2 hours | Phase 3 |
| Phase 5 | 2-3 hours | Phase 4 |
| **Total** | **10-15 hours** | |

---

*Generated: 2026-02-04*
*System: MOH Time OS*
