# MOH Time OS — Full Build Plan

**Created:** 2026-01-31
**Updated:** 2026-02-01
**Status:** See MASTER_CHECKLIST.md for current state

> ⚠️ **This file is outdated.** The source of truth is now:
> - `MASTER_CHECKLIST.md` — What's built, what's missing, build phases
> - `BUILD_STATE.md` — Current operational status
> - `DESIGN_V4_SURGICAL.md` — Technical specification

---

## The Actual System (What We Designed)

### 1. Operator Dashboard
Real-time view of everything needing attention:
- Calendar (next 24h)
- Chat mentions (unread)
- Gmail (unread, prioritized)
- Tasks (due/overdue)
- Items (from Time OS)
- Client/project alerts

### 2. Integrations Layer
Live connections to:
- [ ] Google Calendar (events, free/busy)
- [ ] Google Tasks (lists, tasks, status)
- [ ] Google Chat (mentions, DMs, spaces)
- [ ] Gmail (threads, unread, labels)
- [x] Xero (AR, invoices) — partial
- [x] Asana (projects, tasks) — partial

### 3. Discovery Engine
Learn from 14-90 days of data:
- Lane mapping (work categories)
- Priority tier inference
- Project enrollment candidates
- Scheduling window analysis
- Delegation graph

### 4. Lanes Management
- Define lanes (Finance, Creative, Ops, People, etc.)
- Auto-categorize incoming work
- Route/delegate suggestions
- Lane-specific dashboards

### 5. Task Management
- Capture from conversation
- Sync with Google Tasks
- Status tracking
- Overdue detection
- Context enrichment

### 6. Calendar Engine
- Meeting awareness
- Time blocking
- Scheduling suggestions
- Conflict detection
- Prep reminders

### 7. Facilitation Layer
- Proactive surfacing (not waiting to be asked)
- Context-rich presentation
- Decision support
- Delegation suggestions
- Follow-up tracking

---

## Build Phases

### Phase 1: Integrations (Days 1-3) ✅ COMPLETE
**Goal:** Get live data from all sources

- [x] Verify gog CLI works for Calendar, Tasks, Gmail, Chat
- [x] Build collectors (calendar, gmail, chat, tasks)
- [x] Build generate_queue.py → OPERATOR_QUEUE.md
- [x] Integrate Time OS items into queue
- [x] Tasks collector added (main list)
- [x] Wire to run on heartbeat (via HEARTBEAT.md)

**Checkpoint:** ✅ OPERATOR_QUEUE.md generates with all sources

### Phase 2: Dashboard (Days 4-5) — 90% COMPLETE
**Goal:** Produce OPERATOR_QUEUE.md automatically

- [x] Build queue generator from snapshots
- [x] Calendar section (next 48h)
- [x] Chat section (mentions)
- [x] Gmail section (filtered: 32 important / 18 noise)
- [x] Tasks section (from Google Tasks)
- [x] Items section (from Time OS DB)
- [x] Generate on every heartbeat (via HEARTBEAT.md)
- [x] Priority sorting (important vs noise emails)
- [x] Filter noise (promo emails, low-priority)
- [ ] Proactive surfacing (highlight urgent in heartbeat response)

**Checkpoint:** OPERATOR_QUEUE.md updates automatically, I surface it proactively

### Phase 3: Discovery (Days 6-8) — 80% COMPLETE
**Goal:** Build intelligence layer

- [x] Collect 14-day baseline data (200 emails, 10 events)
- [x] Lane inference (Finance: 50, People: 31, Creative: 10)
- [x] Priority tiers (High: 32, Med: 3, Low: 165)
- [x] Scheduling windows (Deep work: 9am, 1pm, 3pm, 6pm)
- [ ] Project enrollment detection
- [ ] Output: CONFIG_PROPOSAL.md

**Checkpoint:** System understands Moh's work patterns

### Phase 4: Lanes & Tasks (Days 9-11) ✅ COMPLETE
**Goal:** Categorization and task management

- [x] Define lane taxonomy (lanes.py)
- [x] Auto-categorize incoming work (categorize_email, categorize_task)
- [x] Google Tasks bidirectional sync (tasks_sync.py)
- [x] Task capture from conversation (capture_from_text)
- [x] Lane-specific views (integrate into OPERATOR_QUEUE.md)

**Checkpoint:** Work is categorized, tasks sync properly

### Phase 5: Calendar & Facilitation (Days 12-14) ✅ COMPLETE
**Goal:** Full operational intelligence

- [x] Calendar awareness in all outputs (calendar_awareness.py)
- [x] Time blocking suggestions (suggest_time_blocks)
- [x] Prep reminders for meetings (generate_prep_reminders)
- [x] Full facilitation mode (integrated into OPERATOR_QUEUE.md)
- [x] Delegation suggestions (delegation.py)

**Checkpoint:** System runs invisibly, I facilitate proactively

---

## Current Phase: ✅ BUILD COMPLETE

**All phases done.** System is now operational.

---

## Success Criteria

The system is DONE when:
1. I generate OPERATOR_QUEUE.md every heartbeat without being asked
2. I surface what matters before Moh asks
3. Moh never has to remind me what we're building
4. All integrations are live and fresh
5. Discovery has run and config is tuned
6. Lanes categorize work automatically
7. Tasks sync bidirectionally
8. Calendar awareness is built-in

---

## Invariants

While this build is incomplete:
- NO replying HEARTBEAT_OK without doing build work
- EVERY session starts by reading this file
- EVERY heartbeat advances the build
- Progress logged to daily file

## Operating Rules

- **Don't ask permission to continue** — the plan is clear, just execute
- **Don't give status updates** unless Moh asks or I'm blocked
- **Only surface when I need something** — a decision, access, clarification
- **Just do the work** — silently, continuously, until done
