# Collector Audit Report

**Date:** 2025-02-10
**Auditor:** Clawdbot Repo Audit Agent

---

## 1. Root Cause: Why Multiple Collector Stacks Exist

### Evidence

**Four parallel cron entries (from `crontab -l`):**
```
*/15 * * * * ... python -m lib.autonomous_loop run
*/5 * * * *  ... python -m lib.collectors.orchestrator sync
*/30 * * * * ... python cli_v4.py cycle
*/15 * * * * ... python collectors/scheduled_collect.py
```

**Two independent collector architectures:**

| Stack | Entry Point | Sources | Target |
|-------|------------|---------|--------|
| `lib/collectors/` | `CollectorOrchestrator` | 5 sources | StateStore tables |
| `collectors/` | `scheduled_collect.py` | 8 sources | JSON files + V4/V5 pipeline |

**Historical evolution:**
1. `lib/collectors/` was the original class-based architecture (BaseCollector pattern)
2. `collectors/` was added for V4/V5 with JSON-based data flow
3. Both were wired into cron, daemon, and CLI without consolidation
4. `api/server.py:62` instantiates `CollectorOrchestrator` but doesn't use it for collection
5. `lib/daemon.py:120` calls `scheduled_collect.py` via subprocess

### Files involved in the split:

| File | Line | Role |
|------|------|------|
| `lib/daemon.py` | 120 | Calls `collectors/scheduled_collect.py` via subprocess |
| `lib/autonomous_loop.py` | 49 | Instantiates `CollectorOrchestrator` |
| `api/server.py` | 62 | Instantiates `CollectorOrchestrator` (unused for collection) |
| `cli/main.py` | 203 | Uses `CollectorOrchestrator.force_sync()` |
| `run_cycle.sh` | 14 | Calls `collectors/scheduled_collect.py` |

---

## 2. Canonical Runner Path

**CANONICAL:** `collectors/scheduled_collect.py`

### Justification:

1. **More complete:** 8 sources vs 5 sources
   - `scheduled_collect.py`: calendar, gmail, tasks, chat, asana, xero, drive, contacts
   - `CollectorOrchestrator`: tasks, calendar, gmail, asana, xero (no chat, drive, contacts)

2. **Full pipeline integration:** Runs V4 ingest, entity linking, V5 detection, inbox enrichment
   - Lines 295-344 in `scheduled_collect.py`

3. **V5 data flow:** V5 detectors read from JSON files (`out/*.json`) written by `scheduled_collect.py`
   - `lib/v5/data_loader.py:67,96,124,151` — reads from `out/asana-ops.json`, `out/xero-ar.json`, etc.

4. **API data flow:**
   - API reads from `inbox_items_v29`, `issues_v29`, `signals_v29` (populated by V5)
   - V5 reads from JSON files written by `scheduled_collect.py`

### Canonical path (exact lines):

```
Entry:     collectors/scheduled_collect.py:252 → collect_all()
           collectors/scheduled_collect.py:367 → __main__ entry

Daemon:    lib/daemon.py:120 → subprocess call

Cron:      */15 * * * * collectors/scheduled_collect.py

Pipeline:  collect_all() → V4 ingest (295-302)
                        → Entity linking (305-312)
                        → V5 detection (315-330)
                        → Inbox enrichment (333-344)
```

---

## 3. Collector Classification

### A. CANONICAL (wired, intended to run)

| Module | Class/Function | Entry | Tables Written | Config |
|--------|---------------|-------|----------------|--------|
| `collectors/scheduled_collect.py` | `collect_calendar()` | Line 40 | `out/calendar-next.json` | GOG_ACCOUNT |
| `collectors/scheduled_collect.py` | `collect_gmail()` | Line 70 | `out/gmail-full.json` | via gmail_multi_user |
| `collectors/scheduled_collect.py` | `collect_tasks()` | Line 88 | `out/tasks.json` | GOG_ACCOUNT |
| `collectors/scheduled_collect.py` | `collect_chat()` | Line 106 | `out/chat-full.json` | via chat_direct |
| `collectors/scheduled_collect.py` | `collect_asana()` | Line 122 | `out/asana-ops.json` | WORKSPACE_GID |
| `collectors/scheduled_collect.py` | `collect_xero()` | Line 176 | `out/xero-ar.json`, `out/xero-client-revenue.json` | via xero_ops |
| `collectors/scheduled_collect.py` | `collect_drive()` | Line 217 | `out/drive-recent.json` | via drive_direct |
| `collectors/scheduled_collect.py` | `collect_contacts()` | Line 231 | `out/contacts.json` | via contacts_direct |
| `collectors/gmail_multi_user.py` | `collect_one_user()` | Line 143 | `data/gmail_collector_state.db` | TEAM_USERS |
| `collectors/chat_direct.py` | `list_spaces()`, `list_messages()` | Lines 46, 65 | `out/chat-full.json` | SA_FILE |
| `collectors/drive_direct.py` | `list_recent_files()` | Line 39 | via scheduled_collect | SA_FILE |
| `collectors/contacts_direct.py` | `list_contacts()` | Line 42 | via scheduled_collect | SA_FILE |
| `collectors/xero_ops.py` | `get_all_client_revenue()` | Line 22 | via scheduled_collect | xero_client |
| `lib/collectors/xero.py` | `XeroCollector.sync()` | Line 130 | `invoices` table | sources.yaml |

### B. LEGACY (older path, should be removed from wiring)

| Module | Class | Evidence | Action |
|--------|-------|----------|--------|
| `lib/collectors/orchestrator.py` | `CollectorOrchestrator` | Cron `*/5 * * * *` — duplicate of scheduled_collect | Remove from cron |
| `lib/collectors/calendar.py` | `CalendarCollector` | Uses gog CLI (same as scheduled_collect) | Keep as fallback |
| `lib/collectors/tasks.py` | `TasksCollector` | Uses gog CLI (same as scheduled_collect) | Keep as fallback |
| `lib/collectors/gmail.py` | `GmailCollector` | Overlaps with gmail_multi_user | Keep as fallback |
| `lib/collectors/asana.py` | `AsanaCollector` | Overlaps with scheduled_collect's collect_asana | Keep as fallback |
| `lib/autonomous_loop.py` | Line 49 | Instantiates CollectorOrchestrator | Needs refactor |

### C. DEAD (unused, safe to delete)

| File | Evidence | Action |
|------|----------|--------|
| `lib/collectors/team_calendar.py` | Not in orchestrator's collector_map (line 51-57) | Move to _legacy/ |
| `lib/collectors/asana_sync.py` | Standalone script, not imported by canonical path | Move to _legacy/ |

---

## 4. Final "Functional + Recent" Collector List

These collectors are wired into the canonical runner (`scheduled_collect.py`) and have real write paths:

| source_name | module.class | entrypoint | tables_written | config_needed |
|-------------|--------------|------------|----------------|---------------|
| calendar | `scheduled_collect.collect_calendar` | Line 40 | `out/calendar-next.json` | `GOG_ACCOUNT` env |
| gmail | `gmail_multi_user.collect_one_user` | Line 143 | `gmail_collector_state.db`, `out/gmail-full.json` | `TEAM_USERS` list |
| tasks | `scheduled_collect.collect_tasks` | Line 88 | `out/tasks.json` | `GOG_ACCOUNT` env |
| chat | `chat_direct.list_spaces/messages` | Lines 46, 65 | `out/chat-full.json` | `SA_FILE` path |
| asana | `scheduled_collect.collect_asana` | Line 122 | `out/asana-ops.json` | `WORKSPACE_GID` |
| xero | `xero_ops.get_all_client_revenue` | Line 22 | `out/xero-ar.json`, `invoices` table | Xero OAuth |
| drive | `drive_direct.list_recent_files` | Line 39 | `out/drive-recent.json` | `SA_FILE` path |
| contacts | `contacts_direct.list_contacts` | Line 42 | `out/contacts.json` | `SA_FILE` path |

**XeroCollector Exception:**
`lib/collectors/xero.py:XeroCollector` (line 130) writes directly to `invoices` table which is read by `lib/ui_spec_v21/endpoints.py`.
This must remain wired. Best path: Call it from `scheduled_collect.py`.

---

## 5. Implementation (COMPLETED)

### ✅ Phase 1: Unified Registry

Created `lib/collector_registry.py` with `COLLECTOR_REGISTRY`:

```python
from lib.collector_registry import COLLECTOR_REGISTRY, get_enabled_collectors
# 8 collectors: calendar, gmail, tasks, chat, asana, xero, drive, contacts
```

### ✅ Phase 2: Cron Configuration

Created `scripts/cron_recommended.txt` with canonical entries:
```
*/15 * * * * ... python collectors/scheduled_collect.py
*/30 * * * * ... python cli_v4.py cycle
```

**User action required:** Update crontab to remove deprecated entries.

### ✅ Phase 3: XeroCollector DB Sync

Updated `collectors/scheduled_collect.py:collect_xero()` (lines 176-216):
- After JSON collection, now calls `XeroCollector.sync()` to populate `invoices` table
- This ensures API endpoints have fresh invoice data

### ✅ Phase 4: Legacy Collectors Moved

```
collectors/_legacy/
├── README.md
├── asana_sync.py    (from lib/collectors/)
└── team_calendar.py (from lib/collectors/)
```

### ✅ Phase 5: Regression Tests

Created `tests/contract/test_collector_registry.py`:
- `TestSingleRegistry` — Detects duplicate collector maps
- `TestCollectorAgreement` — Ensures scheduled_collect matches registry
- `TestNoLegacyImports` — Fails if canonical code imports from _legacy
- `TestCollectorTableDeclarations` — Validates table declarations

**Test Results:**
```
5 passed, 1 skipped (orchestrator still has hardcoded map — documented)
```

---

## 6. Files Changed

| File | Change |
|------|--------|
| `lib/collector_registry.py` | **CREATED** — Canonical registry |
| `collectors/scheduled_collect.py` | **MODIFIED** — Added XeroCollector DB sync |
| `collectors/_legacy/` | **CREATED** — Legacy collector storage |
| `collectors/_legacy/README.md` | **CREATED** — Documentation |
| `collectors/_legacy/asana_sync.py` | **MOVED** from lib/collectors/ |
| `collectors/_legacy/team_calendar.py` | **MOVED** from lib/collectors/ |
| `tests/contract/test_collector_registry.py` | **CREATED** — Regression tests |
| `scripts/cron_recommended.txt` | **CREATED** — Cron configuration |
| `COLLECTOR_AUDIT.md` | **CREATED** — This document |

---

## 7. User Actions Required

### Update Crontab

```bash
crontab -e
```

Remove these lines:
```
*/15 * * * * ... python -m lib.autonomous_loop run
*/5 * * * * ... python -m lib.collectors.orchestrator sync
```

Keep only:
```
*/15 * * * * cd /Users/molhamhomsi/clawd/moh_time_os && .venv/bin/python collectors/scheduled_collect.py >> /tmp/time-os-collect.log 2>&1
*/30 * * * * cd /Users/molhamhomsi/clawd/moh_time_os && .venv/bin/python cli_v4.py cycle >> /tmp/time-os-v4.log 2>&1
```

---
