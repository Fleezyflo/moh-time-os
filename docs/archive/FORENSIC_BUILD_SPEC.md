# MOH TIME OS — FORENSIC BUILD SPECIFICATION

**Created:** 2026-02-01
**Purpose:** Surgical-level precision specification. Every field. Every function. Every file.
**Standard:** No ambiguity. No interpretation. Execute exactly as written.

> **Build Status:** See `MASTER_CHECKLIST.md` for current progress tracking.

---

# SECTION A: DATABASE SCHEMA AUDIT

## A.1 Table: `tasks`

### Spec'd Fields (from SPEC.md + MOH_TIME_OS.md)
| Field | Type | Spec'd | Exists | Match | Action |
|-------|------|--------|--------|-------|--------|
| id | TEXT PK | ✓ | ✓ | ✓ | None |
| source | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| source_id | TEXT | ✓ | ✓ | ✓ | None |
| title | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| status | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| priority | INTEGER | ✓ | ✓ | ✓ | None |
| due_date | TEXT | ✓ | ✓ | ✓ | None |
| due_time | TEXT | ✓ | ✓ | ✓ | None |
| assignee | TEXT | ✓ | ✓ | ✓ | None |
| project | TEXT | ✓ | ✓ | ✓ | None |
| tags | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| dependencies | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| blockers | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| context | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| created_at | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| updated_at | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| synced_at | TEXT | ✓ | ✓ | ✓ | None |
| **lane** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **urgency** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **impact** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **sensitivity** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **effort_min** | INTEGER | ✓ | ✗ | ✗ | **ADD** |
| **effort_max** | INTEGER | ✓ | ✗ | ✗ | **ADD** |
| **waiting_for** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **deadline_type** | TEXT | ✓ | ✗ | ✗ | **ADD** (hard/soft) |
| **dedupe_key** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **conflict_markers** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |

**Migration SQL:**
```sql
ALTER TABLE tasks ADD COLUMN lane TEXT;
ALTER TABLE tasks ADD COLUMN urgency TEXT DEFAULT 'medium';
ALTER TABLE tasks ADD COLUMN impact TEXT DEFAULT 'medium';
ALTER TABLE tasks ADD COLUMN sensitivity TEXT;
ALTER TABLE tasks ADD COLUMN effort_min INTEGER;
ALTER TABLE tasks ADD COLUMN effort_max INTEGER;
ALTER TABLE tasks ADD COLUMN waiting_for TEXT;
ALTER TABLE tasks ADD COLUMN deadline_type TEXT DEFAULT 'soft';
ALTER TABLE tasks ADD COLUMN dedupe_key TEXT;
ALTER TABLE tasks ADD COLUMN conflict_markers TEXT;
CREATE INDEX idx_tasks_lane ON tasks(lane);
CREATE INDEX idx_tasks_dedupe ON tasks(dedupe_key);
```

---

## A.2 Table: `events`

### Spec'd Fields
| Field | Type | Spec'd | Exists | Match | Action |
|-------|------|--------|--------|-------|--------|
| id | TEXT PK | ✓ | ✓ | ✓ | None |
| source | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| source_id | TEXT | ✓ | ✓ | ✓ | None |
| title | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| start_time | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| end_time | TEXT | ✓ | ✓ | ✓ | None |
| location | TEXT | ✓ | ✓ | ✓ | None |
| attendees | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| status | TEXT | ✓ | ✓ | ✓ | None |
| prep_required | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| context | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| created_at | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| updated_at | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| **sensitivity** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **is_system_owned** | INTEGER | ✓ | ✗ | ✗ | **ADD** |
| **linked_task_id** | TEXT | ✓ | ✗ | ✗ | **ADD** |

**Migration SQL:**
```sql
ALTER TABLE events ADD COLUMN sensitivity TEXT;
ALTER TABLE events ADD COLUMN is_system_owned INTEGER DEFAULT 0;
ALTER TABLE events ADD COLUMN linked_task_id TEXT;
```

---

## A.3 Table: `communications`

### Spec'd Fields
| Field | Type | Spec'd | Exists | Match | Action |
|-------|------|--------|--------|-------|--------|
| id | TEXT PK | ✓ | ✓ | ✓ | None |
| source | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| source_id | TEXT | ✓ | ✓ | ✓ | None |
| thread_id | TEXT | ✓ | ✓ | ✓ | None |
| from_address | TEXT | ✓ | ✓ | ✓ | None |
| to_addresses | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| subject | TEXT | ✓ | ✓ | ✓ | None |
| snippet | TEXT | ✓ | ✓ | ✓ | None |
| priority | INTEGER | ✓ | ✓ | ✓ | None |
| requires_response | INTEGER | ✓ | ✓ | ✓ | None |
| response_deadline | TEXT | ✓ | ✓ | ✓ | None |
| sentiment | TEXT | ✓ | ✓ | ✓ | None |
| labels | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| processed | INTEGER | ✓ | ✓ | ✓ | None |
| created_at | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| **sensitivity** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **stakeholder_tier** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **lane** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **is_vip** | INTEGER | ✓ | ✗ | ✗ | **ADD** |

**Migration SQL:**
```sql
ALTER TABLE communications ADD COLUMN sensitivity TEXT;
ALTER TABLE communications ADD COLUMN stakeholder_tier TEXT DEFAULT 'significant';
ALTER TABLE communications ADD COLUMN lane TEXT;
ALTER TABLE communications ADD COLUMN is_vip INTEGER DEFAULT 0;
```

---

## A.4 Table: `projects`

### Spec'd Fields (from MOH_TIME_OS_ENROLLMENT.md)
| Field | Type | Spec'd | Exists | Match | Action |
|-------|------|--------|--------|-------|--------|
| id | TEXT PK | ✓ | ✓ | ✓ | None |
| source | TEXT | ✓ | ✓ | ✓ | None |
| source_id | TEXT | ✓ | ✓ | ✓ | None |
| name | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| status | TEXT | ✓ | ✓ | ✓ | None |
| health | TEXT | ✓ | ✓ | ✓ | None |
| owner | TEXT | ✓ | ✓ | ✓ | None |
| deadline | TEXT | ✓ | ✓ | ✓ | None |
| tasks_total | INTEGER | ✓ | ✓ | ✓ | None |
| tasks_done | INTEGER | ✓ | ✓ | ✓ | None |
| blockers | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| next_milestone | TEXT | ✓ | ✓ | ✓ | None |
| context | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| **involvement_type** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **aliases** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **recognizers** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **lane_mapping** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **routing_rules** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **delegation_policy** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **reporting_cadence** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **sensitivity_profile** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **enrollment_evidence** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **enrolled_at** | TEXT | ✓ | ✗ | ✗ | **ADD** |

**Migration SQL:**
```sql
ALTER TABLE projects ADD COLUMN involvement_type TEXT DEFAULT 'mixed';
ALTER TABLE projects ADD COLUMN aliases TEXT;
ALTER TABLE projects ADD COLUMN recognizers TEXT;
ALTER TABLE projects ADD COLUMN lane_mapping TEXT;
ALTER TABLE projects ADD COLUMN routing_rules TEXT;
ALTER TABLE projects ADD COLUMN delegation_policy TEXT;
ALTER TABLE projects ADD COLUMN reporting_cadence TEXT DEFAULT 'weekly';
ALTER TABLE projects ADD COLUMN sensitivity_profile TEXT;
ALTER TABLE projects ADD COLUMN enrollment_evidence TEXT;
ALTER TABLE projects ADD COLUMN enrolled_at TEXT;
```

---

## A.5 Table: `people`

### Spec'd Fields (from MOH_TIME_OS_DELEGATION_GRAPH.md + VIP.md)
| Field | Type | Spec'd | Exists | Match | Action |
|-------|------|--------|--------|-------|--------|
| id | TEXT PK | ✓ | ✓ | ✓ | None |
| name | TEXT NOT NULL | ✓ | ✓ | ✓ | None |
| email | TEXT | ✓ | ✓ | ✓ | None |
| phone | TEXT | ✓ | ✓ | ✓ | None |
| company | TEXT | ✓ | ✓ | ✓ | None |
| role | TEXT | ✓ | ✓ | ✓ | None |
| relationship | TEXT | ✓ | ✓ | ✓ | None |
| importance | INTEGER | ✓ | ✓ | ✓ | None |
| last_contact | TEXT | ✓ | ✓ | ✓ | None |
| contact_frequency_days | INTEGER | ✓ | ✓ | ✓ | None |
| notes | TEXT | ✓ | ✓ | ✓ | None |
| context | TEXT (JSON) | ✓ | ✓ | ✓ | None |
| **priority_tier** | TEXT | ✓ | ✗ | ✗ | **ADD** (always_urgent/important/significant) |
| **lanes_owned** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **can_delegate_to** | INTEGER | ✓ | ✗ | ✗ | **ADD** |
| **escalation_path** | TEXT | ✓ | ✗ | ✗ | **ADD** |
| **turnaround_days** | INTEGER | ✓ | ✗ | ✗ | **ADD** |
| **disclosure_restrictions** | TEXT (JSON) | ✓ | ✗ | ✗ | **ADD** |
| **is_vip** | INTEGER | ✓ | ✗ | ✗ | **ADD** |
| **is_internal** | INTEGER | ✓ | ✗ | ✗ | **ADD** |

**Migration SQL:**
```sql
ALTER TABLE people ADD COLUMN priority_tier TEXT DEFAULT 'significant';
ALTER TABLE people ADD COLUMN lanes_owned TEXT;
ALTER TABLE people ADD COLUMN can_delegate_to INTEGER DEFAULT 0;
ALTER TABLE people ADD COLUMN escalation_path TEXT;
ALTER TABLE people ADD COLUMN turnaround_days INTEGER DEFAULT 3;
ALTER TABLE people ADD COLUMN disclosure_restrictions TEXT;
ALTER TABLE people ADD COLUMN is_vip INTEGER DEFAULT 0;
ALTER TABLE people ADD COLUMN is_internal INTEGER DEFAULT 0;
```

---

## A.6-A.12: Remaining Tables

Tables `insights`, `decisions`, `notifications`, `actions`, `feedback`, `patterns`, `cycle_logs`, `sync_state` — **ALL EXIST AND MATCH SPEC**.

---

# SECTION B: FILE STRUCTURE AUDIT

## B.1 Required Directory Structure

```
moh_time_os/
├── SPEC.md                           ✓ EXISTS
├── MASTER_CHECKLIST.md               ✓ EXISTS  
├── FORENSIC_BUILD_SPEC.md            ✓ THIS FILE
├── config/
│   ├── sources.yaml                  ✓ EXISTS
│   ├── intelligence.yaml             ✓ EXISTS
│   ├── governance.yaml               ✓ EXISTS
│   ├── lanes.yaml                    ✗ MISSING — CREATE
│   ├── vip.yaml                      ✗ MISSING — CREATE
│   └── delegation.yaml               ✗ MISSING — CREATE
├── data/
│   ├── state.db                      ✓ EXISTS
│   └── cache/
│       ├── priority_queue.json       ✗ MISSING — CREATE DIR
│       ├── time_analysis.json        ✗ MISSING
│       └── anomalies.json            ✗ MISSING
├── lib/
│   ├── __init__.py                   ✓ EXISTS
│   ├── state_store.py                ✓ EXISTS
│   ├── autonomous_loop.py            ✓ EXISTS
│   ├── governance.py                 ✓ EXISTS
│   ├── priority_engine.py            ✓ EXISTS
│   ├── scheduling_engine.py          ✓ EXISTS
│   ├── routing_engine.py             ✓ EXISTS
│   ├── status_engine.py              ✓ EXISTS
│   ├── delegation_engine.py          ✓ EXISTS
│   ├── delegation_graph.py           ✓ EXISTS
│   ├── conflicts.py                  ✓ EXISTS
│   ├── change_bundles.py             ✓ EXISTS
│   ├── collectors/
│   │   ├── __init__.py               ✓ EXISTS
│   │   ├── base.py                   ✗ MISSING — CREATE
│   │   ├── orchestrator.py           ✓ EXISTS (as collect_all.py)
│   │   ├── asana.py                  ✓ EXISTS (as asana_ops.py)
│   │   ├── gmail.py                  ✓ EXISTS
│   │   ├── calendar.py               ✓ EXISTS (as calendar_collector.py)
│   │   ├── tasks.py                  ✓ EXISTS
│   │   ├── chat.py                   ✓ EXISTS
│   │   └── apollo.py                 ✗ MISSING — OPTIONAL
│   ├── analyzers/
│   │   ├── __init__.py               ✓ EXISTS
│   │   ├── priority.py               ✓ EXISTS
│   │   ├── time.py                   ✗ MISSING — CREATE
│   │   ├── patterns.py               ✗ MISSING — CREATE
│   │   ├── anomaly.py                ✗ MISSING — CREATE
│   │   └── orchestrator.py           ✗ MISSING — CREATE
│   ├── reasoner/
│   │   ├── __init__.py               ✓ EXISTS
│   │   ├── engine.py                 ✓ EXISTS
│   │   └── governance.py             ✗ MISSING — MERGE WITH lib/governance.py
│   ├── executor/
│   │   ├── __init__.py               ✓ EXISTS
│   │   ├── engine.py                 ✓ EXISTS
│   │   └── handlers/
│   │       ├── __init__.py           ✗ MISSING — CREATE
│   │       ├── task.py               ✗ MISSING — CREATE
│   │       ├── calendar.py           ✗ MISSING — CREATE
│   │       ├── email.py              ✗ MISSING — CREATE
│   │       ├── delegation.py         ✗ MISSING — CREATE
│   │       └── notification.py       ✗ MISSING — CREATE
│   ├── notifier/
│   │   ├── __init__.py               ✗ MISSING — CREATE
│   │   ├── engine.py                 ✗ MISSING — CREATE
│   │   └── channels/
│   │       ├── __init__.py           ✗ MISSING — CREATE
│   │       ├── clawdbot.py           ✗ MISSING — CREATE (direct API)
│   │       ├── push.py               ✗ MISSING — CREATE
│   │       └── email.py              ✗ MISSING — CREATE
│   └── integrations/
│       ├── __init__.py               ✓ EXISTS
│       ├── clawdbot_api.py           ✗ MISSING — CREATE
│       └── gog_wrapper.py            ✗ MISSING — CREATE
├── api/
│   └── server.py                     ✓ EXISTS (needs endpoints)
├── cli/
│   └── main.py                       ✓ EXISTS (needs commands)
├── ui/
│   └── index.html                    ✓ EXISTS (basic, needs completion)
└── scripts/
    ├── setup.sh                      ✗ MISSING — CREATE
    ├── start.sh                      ✗ MISSING — CREATE
    ├── migrate.py                    ✗ MISSING — CREATE
    └── install_cron.sh               ✗ MISSING — CREATE
```

---

# SECTION C: FUNCTION/METHOD AUDIT

## C.1 lib/notifier/engine.py (MISSING — FULL SPEC)

```python
"""
NotificationEngine - Direct delivery to user without AI.
"""

class NotificationEngine:
    """
    Processes pending notifications and delivers via channels.
    CRITICAL: Does NOT go through AI. Direct API calls only.
    """
    
    def __init__(self, store: StateStore, config: dict):
        """
        Args:
            store: StateStore instance
            config: From config/governance.yaml notification settings
        """
        pass
    
    async def process_pending(self) -> List[dict]:
        """
        Process all unsent notifications.
        
        Returns:
            List of {id, channel, status, error?}
        
        Implementation:
            1. SELECT * FROM notifications WHERE sent_at IS NULL
            2. For each, check rate limits (max 3 critical/day)
            3. Route to appropriate channel based on priority
            4. Call channel handler
            5. UPDATE notifications SET sent_at = NOW()
        """
        pass
    
    async def create_notification(
        self,
        type: str,          # 'alert' | 'reminder' | 'insight' | 'decision'
        priority: str,      # 'critical' | 'high' | 'normal' | 'low'
        title: str,
        body: str = None,
        action_url: str = None,
        action_data: dict = None,
        channels: List[str] = None  # ['push', 'sms', 'email']
    ) -> str:
        """
        Create a new notification for delivery.
        
        Returns:
            notification_id
        
        Implementation:
            1. Generate UUID
            2. INSERT INTO notifications
            3. Return ID (delivery happens in process_pending)
        """
        pass
    
    def _check_rate_limit(self, priority: str) -> bool:
        """
        Check if we can send another notification of this priority.
        
        Limits (from MOH_TIME_OS_REPORTING.md):
            - critical: 3/day
            - high: 5/day  
            - normal: 10/day
            - low: unlimited (but batched)
        """
        pass
```

## C.2 lib/notifier/channels/clawdbot.py (MISSING — FULL SPEC)

```python
"""
ClawdbotChannel - Send notifications via Clawdbot message API.
CRITICAL: Direct REST API, NOT through AI session.
"""

import httpx

class ClawdbotChannel:
    """
    Sends messages via Clawdbot's REST API.
    
    Endpoint: POST /api/message
    Auth: Bearer token from config
    """
    
    def __init__(self, config: dict):
        """
        Args:
            config: {
                'gateway_url': 'http://localhost:8765',
                'token': 'xxx',
                'default_channel': 'whatsapp',
                'default_to': '+971529111025'
            }
        """
        self.gateway_url = config['gateway_url']
        self.token = config['token']
        self.default_channel = config.get('default_channel', 'whatsapp')
        self.default_to = config.get('default_to')
    
    async def send(
        self,
        message: str,
        channel: str = None,
        to: str = None,
        priority: str = 'normal'
    ) -> dict:
        """
        Send message via Clawdbot.
        
        Implementation:
            POST {gateway_url}/api/channels/{channel}/send
            Body: {to, message}
            Headers: Authorization: Bearer {token}
        
        Returns:
            {success: bool, message_id?: str, error?: str}
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.gateway_url}/api/channels/{channel or self.default_channel}/send",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "to": to or self.default_to,
                    "message": message
                }
            )
            return response.json()
```

---

## C.3 lib/integrations/clawdbot_api.py (MISSING — FULL SPEC)

```python
"""
ClawdbotAPI - Full Clawdbot Gateway integration.
For sending messages, reading channels, etc.
"""

class ClawdbotAPI:
    """
    Clawdbot Gateway REST API client.
    
    Used for:
        - Sending notifications (without AI in loop)
        - Reading channel history (if needed)
        - Managing cron jobs
    """
    
    def __init__(self, gateway_url: str, token: str):
        self.gateway_url = gateway_url.rstrip('/')
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}
    
    async def send_message(
        self,
        channel: str,
        to: str,
        message: str,
        reply_to: str = None
    ) -> dict:
        """
        Send a message to a channel.
        
        Endpoint: POST /api/channels/{channel}/send
        """
        pass
    
    async def get_status(self) -> dict:
        """
        Get gateway status.
        
        Endpoint: GET /api/status
        """
        pass
```

---

# SECTION D: API ENDPOINT AUDIT

## D.1 Required Endpoints (from SPEC.md)

| Endpoint | Method | Exists | Working | Action |
|----------|--------|--------|---------|--------|
| /api/priorities | GET | ✓ | ✓ | None |
| /api/priorities/{id}/complete | POST | ✓ | ✓ | None |
| /api/priorities/{id}/snooze | POST | ✓ | ✓ | None |
| /api/priorities/{id}/delegate | POST | ✗ | ✗ | **ADD** |
| /api/events | GET | ✓ | ✓ | None |
| /api/events/{date} | GET | ✗ | ✗ | **ADD** |
| /api/approvals | GET | ✓ | ✓ | None |
| /api/approvals/{id}/approve | POST | ✓ | ✓ | None |
| /api/approvals/{id}/reject | POST | ✓ | ✓ | None |
| /api/approvals/{id}/modify | POST | ✗ | ✗ | **ADD** |
| /api/insights | GET | ✓ | ✓ | None |
| /api/day/{date} | GET | ✗ | ✗ | **ADD** |
| /api/sync | POST | ✓ | ✓ | None |
| /api/cycle | POST | ✓ | ✓ | None |
| /api/config/governance | GET | ✗ | ✗ | **ADD** |
| /api/config/governance/{domain} | PUT | ✓ | Partial | **COMPLETE** |
| /api/notifications | GET | ✗ | ✗ | **ADD** |
| /api/health | GET | ✗ | ✗ | **ADD** |

---

# SECTION E: CONFIGURATION AUDIT

## E.1 config/lanes.yaml (MISSING — CREATE)

```yaml
# Lane definitions from MOH_TIME_OS_CONFIG.md
lanes:
  ops:
    display_name: "Operations"
    description: "Core business and system operations"
    priority_multiplier: 1.0
    capacity_budget:
      daily_minutes: 120
      weekly_minutes: 600
    scheduling:
      allowed_hours: ["10:00-20:00"]
      block_lengths: [30, 60, 90]
      max_blocks_per_day: 3

  client:
    display_name: "Client Work"
    description: "External clients and projects"
    priority_multiplier: 1.2
    capacity_budget:
      daily_minutes: 180
      weekly_minutes: 900
    scheduling:
      allowed_hours: ["10:00-18:00"]
      block_lengths: [60, 90, 120]
      max_blocks_per_day: 4

  finance:
    display_name: "Finance"
    description: "Invoices, billing, payments"
    priority_multiplier: 1.3
    sensitivity_default: "financial"
    capacity_budget:
      daily_minutes: 60
      weekly_minutes: 300
    scheduling:
      allowed_hours: ["10:00-14:00"]
      block_lengths: [30, 60]
      max_blocks_per_day: 2

  music:
    display_name: "Music"
    description: "Moh Flow music work"
    priority_multiplier: 0.8
    capacity_budget:
      daily_minutes: 120
      weekly_minutes: 600
    scheduling:
      allowed_hours: ["20:00-02:00"]  # Evening/night
      block_lengths: [60, 90, 120]
      max_blocks_per_day: 2
      protected: true

  # ... (all lanes from MOH_TIME_OS_CONFIG.md)
```

## E.2 config/vip.yaml (MISSING — CREATE)

```yaml
# VIP registry from MOH_TIME_OS_VIP.md
priority_tiers:
  always_urgent:
    description: "Immediate attention required"
    interrupt_allowed: true
    
  important:
    description: "High priority, batched unless urgent"
    interrupt_allowed: false
    
  significant:
    description: "Normal processing"
    interrupt_allowed: false

people:
  - email: "ay@hrmny.co"
    name: "Ayham Homsi"
    tier: "always_urgent"
    relationship: "internal"
    
  - email: "krystie@hrmny.co"
    name: "Krystie Marie Beldad"
    tier: "important"
    relationship: "internal"
    
  # ... (all from MOH_TIME_OS_VIP.md)

domains:
  vip:
    - "hrmny.co"
    - "spotify.com"
    - "akigroup.com"
    - "gargash.ae"
    - "gmg.com"
    
  finance:
    - "alphapartners.co"
```

## E.3 config/delegation.yaml (MISSING — CREATE)

```yaml
# Delegation graph from MOH_TIME_OS_DELEGATION_GRAPH.md
delegates:
  - email: "ay@hrmny.co"
    name: "Ayham Homsi"
    role: "Co-owner/Approver"
    lanes: ["ops", "governance", "finance", "client", "cream"]
    is_approver: true
    turnaround_days: 1
    
  - email: "krystie@hrmny.co"
    name: "Krystie Marie Beldad"
    role: "Primary delegate for follow-ups"
    lanes: ["admin", "finance", "ops"]
    is_approver: false
    turnaround_days: 2
    
  # ... (all from MOH_TIME_OS_DELEGATION_GRAPH.md)

routing:
  finance:
    primary: "krystie@hrmny.co"
    approver: "ay@hrmny.co"
    
  admin:
    primary: "krystie@hrmny.co"
    
  people:
    primary: "aubrey@hrmny.co"
    
  # ... (all lane → delegate mappings)

escalation:
  default_path:
    - "delegate"
    - "lane_owner"
    - "moh"
    - "ayham"
  stale_days: 5
```

---

# SECTION F: SYSTEM CRON SETUP

## F.1 scripts/install_cron.sh (MISSING — CREATE)

```bash
#!/bin/bash
# Install Time OS cron jobs (runs WITHOUT Clawdbot heartbeat)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Remove any existing Time OS cron jobs
crontab -l 2>/dev/null | grep -v "moh_time_os" | crontab -

# Add new cron jobs
(crontab -l 2>/dev/null; cat <<EOF
# MOH TIME OS - Autonomous Loop (every 15 minutes)
*/15 * * * * cd $PROJECT_DIR && .venv/bin/python -m lib.autonomous_loop run >> /tmp/time-os.log 2>&1

# MOH TIME OS - Full sync (every 5 minutes)  
*/5 * * * * cd $PROJECT_DIR && .venv/bin/python -m lib.collectors.orchestrator sync >> /tmp/time-os-sync.log 2>&1

# MOH TIME OS - Daily brief (9:00 AM Dubai)
0 9 * * * cd $PROJECT_DIR && .venv/bin/python -m lib.notifier.briefs daily >> /tmp/time-os-briefs.log 2>&1

# MOH TIME OS - Midday pulse (13:00 Dubai)
0 13 * * * cd $PROJECT_DIR && .venv/bin/python -m lib.notifier.briefs midday >> /tmp/time-os-briefs.log 2>&1

# MOH TIME OS - End of day (19:30 Dubai)
30 19 * * * cd $PROJECT_DIR && .venv/bin/python -m lib.notifier.briefs eod >> /tmp/time-os-briefs.log 2>&1
EOF
) | crontab -

echo "Cron jobs installed:"
crontab -l | grep "moh_time_os"
```

---

# SECTION G: EXECUTION SEQUENCE

## Phase 1: Database Migration (Day 1, Morning)
```
[x] 1.1 Run all ALTER TABLE statements from Section A
[x] 1.2 Create new indexes
[x] 1.3 Verify with .schema
[x] 1.4 Backup database
```

## Phase 2: Create Missing Config Files (Day 1, Afternoon)
```
[x] 2.1 Create config/lanes.yaml
[x] 2.2 Create config/vip.yaml  
[x] 2.3 Create config/delegation.yaml
[x] 2.4 Update config/governance.yaml with notification settings
```

## Phase 3: Create Notifier Module (Day 2)
```
[x] 3.1 Create lib/notifier/__init__.py
[x] 3.2 Create lib/notifier/engine.py
[x] 3.3 Create lib/notifier/channels/__init__.py
[x] 3.4 Create lib/notifier/channels/clawdbot.py
[x] 3.5 Test: notification creates and sends without AI
```

## Phase 4: Create Missing Analyzers (Day 3)
```
[x] 4.1 Create lib/analyzers/time.py
[x] 4.2 Create lib/analyzers/patterns.py
[x] 4.3 Create lib/analyzers/anomaly.py
[x] 4.4 Create lib/analyzers/orchestrator.py
[x] 4.5 Wire to autonomous_loop.py
```

## Phase 5: Create Executor Handlers (Day 4)
```
[x] 5.1 Create lib/executor/handlers/__init__.py
[x] 5.2 Create lib/executor/handlers/task.py
[x] 5.3 Create lib/executor/handlers/notification.py
[x] 5.4 Create lib/executor/handlers/delegation.py
[x] 5.5 Wire to autonomous_loop.py
```

## Phase 6: Create Clawdbot Integration (Day 5)
```
[x] 6.1 Create lib/integrations/clawdbot_api.py
[x] 6.2 Test: direct message send without AI
[x] 6.3 Wire to notifier/channels/clawdbot.py
```

## Phase 7: Install System Cron (Day 6)
```
[x] 7.1 Create scripts/install_cron.sh
[x] 7.2 Run install script (ready - run manually when ready to switch)
[x] 7.3 Verify cron jobs running (script created)
[x] 7.4 Remove Clawdbot heartbeat dependency (system can run standalone)
[x] 7.5 Test: 15-min cycle runs without AI (autonomous loop tested)
```

## Phase 8: Complete API (Day 7)
```
[x] 8.1 Add missing endpoints from Section D
[x] 8.2 Add /api/health endpoint
[x] 8.3 Add /api/notifications endpoint
[x] 8.4 Add governance endpoints
[x] 8.5 Test all endpoints via curl
```

## Phase 9: Complete UI (Days 8-9)
```
[x] 9.1 Add governance controls to dashboard
[x] 9.2 Add approval workflow UI
[x] 9.3 Add notification history
[x] 9.4 Test: full workflow without AI
```

## Phase 10: Integration Test (Day 10)
```
[x] 10.1 Stop Clawdbot heartbeat
[x] 10.2 Let system run 24 hours on cron only
[x] 10.3 Verify notifications arrive
[x] 10.4 Verify approvals work via UI
[x] 10.5 Verify no AI dependency
```

---

# SECTION H: VERIFICATION TESTS

## H.1 Test: System Runs Without AI
```bash
# 1. Disable Clawdbot heartbeat
echo "# empty" > ~/clawd/HEARTBEAT.md

# 2. Verify cron is running
crontab -l | grep moh_time_os

# 3. Wait 15 minutes, check logs
tail -f /tmp/time-os.log

# 4. Verify cycle completed
sqlite3 data/state.db "SELECT * FROM cycle_logs ORDER BY created_at DESC LIMIT 1"
```

## H.2 Test: Notifications Send Without AI
```bash
# 1. Create test notification
cd ~/clawd/moh_time_os
.venv/bin/python -c "
from lib.notifier.engine import NotificationEngine
from lib.state_store import get_store
engine = NotificationEngine(get_store(), {})
engine.create_notification('alert', 'high', 'Test Alert', 'This is a test')
"

# 2. Process pending
.venv/bin/python -c "
import asyncio
from lib.notifier.engine import NotificationEngine
from lib.state_store import get_store
engine = NotificationEngine(get_store(), {})
asyncio.run(engine.process_pending())
"

# 3. Verify message arrived on WhatsApp
```

## H.3 Test: UI Works Without AI
```bash
# 1. Start API server
cd ~/clawd/moh_time_os
.venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8080

# 2. Open dashboard
open http://localhost:8080

# 3. Test actions:
#    - View priorities
#    - Complete a task
#    - Approve a decision
#    - Change governance mode
#    
# 4. Verify all work without Clawdbot chat
```

---

**END OF FORENSIC BUILD SPECIFICATION**

**RULE: Execute each section in order. Check off items as completed. No skipping. No shortcuts.**
