# MOH Time OS v2

Entity-centric tracking with full context.

## Quick Start

```bash
cd ~/clawd/moh_time_os
source .venv/bin/activate

# Status
python3 cli_v2.py status

# What needs attention?
python3 cli_v2.py attention

# Daily brief
python3 cli_v2.py brief

# Track an item
python3 cli_v2.py track "Send proposal to Dana" --due friday --client SSS

# Query
python3 cli_v2.py query "what about GMG?"
```

## Architecture

```
lib/
├── store.py      # SQLite + WAL, schema
├── entities.py   # Client, Person, Project CRUD
├── items.py      # Items with context snapshots
├── queries.py    # Query helpers (overdue, due_today, brief)
├── health.py     # Health checks, self-healing
├── backup.py     # Backup/restore
├── resolve.py    # Entity resolution (fuzzy matching)
├── capture.py    # Conversation-based capture
└── protocol.py   # A Protocol (session start, heartbeat, queries)
```

## Entities

- **Clients**: Companies we work with (tier, AR, health, relationship)
- **People**: Internal team + external contacts (role, company, trust)
- **Projects**: Active work (status, health, stakes, milestones)
- **Items**: Things that need to happen (linked to above, with context snapshots)

## Context Snapshots

Every Item captures entity state at creation time:
- Even if client health changes later, Item retains original context
- Enables intelligent surfacing ("this was urgent when you tracked it because...")

## A Protocol

### Session Start
```python
from lib import on_session_start
healthy, msg = on_session_start()
# Returns health status and message
```

### Heartbeat
```python
from lib import on_heartbeat
needs_attention, msg = on_heartbeat()
# Returns True + alert if items need attention
```

### Capture
```python
from lib import capture_item, quick_capture

# Explicit capture
item_id, msg = capture_item(
    what="Send proposal",
    due="friday",
    client="SSS",
    person="Dana",
    stakes="200K project"
)

# Quick capture (parses natural language)
item_id, msg = quick_capture("Follow up with GMG re: invoice tomorrow")
```

### Query
```python
from lib import handle_query
response = handle_query("what about GMG?")
response = handle_query("what's overdue?")
response = handle_query("brief")
```

## Database

Location: `data/moh_time_os_v2.db`

Backups: `data/backups/`

## Cron Jobs

- **09:00 daily**: Morning brief
- **03:00 daily**: Backup

## Current State

```
Clients:  152 (from Xero)
Projects: 70 (from Asana)
People:   82 (78 team + contacts)
Items:    179 (174 migrated from v1 + new)
```
