# Detection System Design v4 — Collision, Drift, Bottleneck

**Date:** 2026-03-03
**Status:** Design (no code changes)
**Supersedes:** v1 (2026-03-02), v2 (2026-03-03), v3 (2026-03-03)
**Prerequisite:** Phase 14 committed, Agency Command Center merged (PRs #55, #56)
**Audit status:** All queries verified against live schema (schema.py v12, 73 tables). All collector capabilities verified against source code. All broken references from v3 corrected.

---

## The Problem

You run a 31-person agency with 20+ clients. You open the Command Center. Today it shows you scored lists — every client ranked by health, every team member ranked by load, color-coded labels everywhere. You scan it, absorb nothing useful, close it. The scores don't tell you what to do. They tell you what the system thinks about things, which isn't the same as telling you what's wrong.

This design replaces scored lists with three factual detections that either fire or don't. When they fire, they tell you what's wrong AND give you the adjacent information you'd need to respond. When they don't fire, the system is silent.

---

## Schema Reality Check

The following corrections were discovered during the feasibility audit and are integrated throughout this document. This section exists so anyone reading the design understands what the codebase actually provides.

**Tables that exist and are used by the detectors:**

| Table | Defined in | Key columns for detection |
|-------|-----------|--------------------------|
| `tasks` | `schema.py` line 143 | `assignee` (name string), `assignee_name`, `status`, `due_date`, `completed_at`, `updated_at`, `project_id`, `client_id` |
| `events` | `schema.py` line 210 | `start_time`, `end_time`, `title`, `organizer_email`, `attendee_count` |
| `calendar_attendees` | `schema.py` line 986 | `event_id`, `email`, `display_name`, `response_status` |
| `clients` | `schema.py` line 36 | `name`, `tier`, `financial_annual_value`. Revenue columns (`prior_year_revenue`, `ytd_revenue`, `lifetime_revenue`) exist at runtime (queried in `server.py` line 5228) but are NOT in schema.py — detectors must handle their absence gracefully. |
| `team_members` | `schema.py` line 362 | `name`, `email`, `asana_gid` |
| `projects` | `schema.py` line 81 | `client_id`, `is_internal` |
| `time_blocks` | NOT in `schema.py`. Created at runtime by `BlockManager`. Columns per SCHEMA_ATLAS: `id, date, start_time, end_time, lane, task_id, is_protected, is_buffer, created_at, updated_at`. **No `person_id` column** despite `db_opt/indexes.py` defining an index on it. Phase 15a must formalize this table. |
| `sync_state` | `schema.py` | `source` (PK), `last_sync`, `last_success`, `items_synced`, `error` |

**Tables that do NOT exist as referenced in v3:**

- ~~`calendar_events`~~ — Does NOT exist in `schema.py`. A V5 migration (`001_create_v5_schema.sql` line 804) defines one with different columns, but the CalendarCollector writes to `events` (`target_table = "events"`, `calendar.py` line 40). The existing `command_center.py` references `calendar_events` at lines 351 and 461 — those queries are already broken. All detector queries use `events` + `calendar_attendees` instead.
- ~~`calendar_events.subject_email`~~ — This column doesn't exist anywhere. Not in `events`, not in the V5 `calendar_events`, not in `calendar_attendees`. To find events for a team member, join `events` → `calendar_attendees` on `event_id` where `calendar_attendees.email = team_members.email`.

**Collector capabilities (verified against source):**

- `AsanaCollector.collect()` (`asana.py` line 38): Takes NO parameters. Fetches ALL projects and ALL tasks in the workspace. No assignee filter. Cannot do scoped per-person pulls.
- `CalendarCollector` (`calendar.py` line 36): Writes to `events` table AND `calendar_attendees` table (attendee rows with email per attendee). `target_table = "events"`.
- `all_users_runner.py`: Has `collect_calendar_for_user(user, since, until, limit, db_path)` (line 331) and `collect_gmail_for_user(user, since, until, limit, db_path)` (line 227). These use domain-wide delegation. However, `collect_calendar_for_user` only returns `{ok, count, calendars}` — it fetches but the DB storage is handled by CalendarCollector's `sync()` method separately.
- `CollectorOrchestrator.force_sync()` (`orchestrator.py` line 107): Delegates to `scheduled_collect.collect_all()` — runs full collectors, no per-entity filter.

**Autonomous loop structure (verified):**

Phases: COLLECT → NORMALIZE → GATES → AUTO-RESOLVE (line 215) → TRUTH MODULES (1b-1e, line 225) → INTELLIGENCE (1f, line 284). Detection phase fits between AUTO-RESOLVE and TRUTH MODULES (or after INTELLIGENCE). `_process_time_truth()` at line 851 is a private method — NOT TruthCycle (TruthCycle is dead code, unused by the loop).

---

## Three Detections

### 1. Collision — "Can anyone on the team get through this week?"

**What it detects:** Days where open time can't absorb the work due — for Molham AND every team member whose calendar data is available.

**Why team-level, not just Molham:** If Ahmad has 6 deliverables due Tuesday and 0 free hours, that's Molham's problem too — he'll get the escalation. Team member calendar data is available via the `events` table joined to `calendar_attendees` on `event_id`, filtering where `calendar_attendees.email` matches `team_members.email`. Collision runs per person, not just for the executive.

**Why ratio, not threshold:** The v1 design triggered collision when available minutes < 60. That meant 61 free minutes with 8 tasks due = silence. Instead: compute the ratio of tasks due to available hours. A 4:1 ratio (4 tasks, 1 hour) is always worth seeing. A 0.5:1 ratio (1 task, 2 hours) never is.

**Task weight — derived, not entered:** Raw task count treats every task equally, but "reply to email" and "write Q2 proposal" are not the same commitment. Instead of asking people to estimate hours (they won't), the system derives a weight from existing data:

- Title keywords: "review," "approve," "reply," "update" → `quick` (weight: 0.5)
- Project type / title keywords: "proposal," "report," "strategy," "audit" → `heavy` (weight: 4.0)
- Everything else → `standard` (weight: 1.0)

Classification rules are stored in a lookup table: `{pattern, field, assigned_weight, confidence, corrections_count}`. Once a week, the morning brief includes a confirmation line:

> **Weight check:** 5 tasks were auto-classified this week. Reply "weights" to review.

The review shows each task's derived weight and lets the executive confirm or correct. Each correction feeds back: if "invoice review" gets changed from `quick` to `standard` three times across different invoices, the rule updates. Confidence increases with confirmations, decreases with corrections. Manually set weights are never silently changed.

The collision ratio becomes: `sum(task_weights) / available_hours`. Tuesday with 4 quick tasks (total weight 2.0) and 2 free hours → ratio 1.0 (fine). Tuesday with 1 heavy task (weight 4.0) and 2 free hours → ratio 2.0 (collision).

**Detection logic — two paths based on data availability:**

**Path A: Molham (has `time_blocks` data)**

For each of the next 10 business days:

1. Query `time_blocks WHERE date = ? AND is_protected = 0 AND task_id IS NULL` → sum minutes → `available_minutes`
2. Query `tasks WHERE due_date = ? AND status IN ('active', 'in_progress') AND assignee = 'Molham Homsi'` → tasks list
3. Compute `weighted_total = sum(weight for each task)` using derived or confirmed weights
4. Compute `ratio = weighted_total / (available_minutes / 60)`. If `available_minutes = 0` and tasks exist, ratio is infinite.
5. **Collision fires when:** `ratio > 2.0` OR `available_minutes = 0 AND tasks exist`

**Path B: Team members (no `time_blocks`, compute from calendar events)**

For each team member in `team_members`, for each of the next 10 business days:

1. Compute meeting minutes from events:
   ```sql
   SELECT e.start_time, e.end_time
   FROM events e
   JOIN calendar_attendees ca ON ca.event_id = e.id
   WHERE ca.email = ?                              -- team_members.email
     AND date(e.start_time) = ?                    -- target date
     AND e.status != 'cancelled'
   ```
   Sum `(end_time - start_time)` → `meeting_minutes`
2. Compute `available_minutes = 480 - meeting_minutes` (8-hour working day minus meetings). Floor at 0.
3. Query `tasks WHERE due_date = ? AND status IN ('active', 'in_progress') AND assignee = ?` → tasks list (matched by `tasks.assignee = team_members.name`)
4. Same weighted ratio calculation as Path A.
5. Same firing condition.

**Why two paths:** Molham has `time_blocks` with block-level granularity (protected blocks, buffer time, lane assignments). Team members don't — their data comes from calendar events only. The working-day-minus-meetings calculation is less precise but sufficient for detecting "0 free hours with 5 tasks due."

**Why 10 days, not 5:** Agency deliverables are planned 1-2 weeks out. At 5 days you catch problems the day before they hit. At 10 days you catch them early enough to rearrange.

**Adjacent data (the "so what"):**

Each collision finding includes:
- The day's meetings with event titles (what's eating the time) — from `events` joined to `calendar_attendees`
- The specific tasks due, with client name, project, and derived weight
- Which tasks have flexible due dates (due_date > collision_date + 2 days = moveable)
- Which tasks could be reassigned (assignee = person, but peers on same project exist)

**What it says (for Molham):**

> Tuesday Mar 4 — 4 tasks due, 1 hour free (weighted ratio 3.5:1)
> Meetings: Client Flavor sync (10-11), Team standup (11:30-12), Cream review (14-16)
> Tasks due: "Flavor Q2 proposal" ■ heavy (Flavor), "Invoice review" (Cream), "Onboarding doc" (internal), "Budget approval" (finance)
> Moveable: "Onboarding doc" (due Mar 6), "Budget approval" (due Mar 7)

**What it says (for a team member):**

> Ahmad — Tuesday Mar 4: 5 tasks due, 0 hours free
> Tasks: "Social calendar" (Flavor), "Report draft" ■ heavy (Zest), "Reply to brief" (Flavor), ...

Team member collisions appear in a separate "Team Collisions" section below Molham's own findings, grouped by person.

**Existing code used:**
- `CalendarSync.ensure_blocks_for_week()` at line 235 of `calendar_sync.py` — generates blocks for 7 days, needs extension to 10 business days (change `timedelta(days=6)` to `timedelta(days=13)`)
- `BlockManager.get_available_blocks()` at line 84 of `block_manager.py` — queries `is_protected = 0 AND task_id IS NULL`
- `CalendarSync.get_day_summary()` at line 206 — returns `available_minutes`, `meeting_minutes` (Molham only)
- `events` + `calendar_attendees` JOIN — for team-level calendar data (replaces the broken `calendar_events.subject_email` reference)
- Tasks query pattern from `TeamLoadView.get_team_load()` lines 334-339 of `command_center.py`

---

### 2. Drift — "Is any client slipping while I'm not looking?"

**What it detects:** Clients whose tasks are past due and not moving — anchored to deadlines, not activity timestamps.

**Why deadlines, not activity:** "Task untouched for 14 days but not past due" isn't drift — that's someone pacing their work. With deadlines being enforced company-wide, the real signal is: past due date, no completion, no updates. A task within its deadline is fine regardless of when someone last looked at it. A task past its deadline with no movement is a fact worth surfacing.

**Why self-comparison, not group comparison:** v1 compared each client's completions to the team median. This breaks for small clients (3 tasks, never hits the 5-task minimum) and during slow weeks (median drops to 0, nobody drifts). Self-comparison avoids both: does THIS client have overdue tasks that aren't moving? That's the only question.

**Detection logic:**

For each non-internal client (where `projects.is_internal != 1`):

1. Count overdue tasks:
   ```sql
   SELECT t.id, t.title, t.assignee, t.due_date
   FROM tasks t
   JOIN projects p ON t.project_id = p.id
   WHERE p.client_id = ?
     AND t.status IN ('active', 'in_progress')
     AND t.due_date < date('now')
   ```
   → `overdue_count`

2. Count completions in last 5 business days:
   ```sql
   SELECT COUNT(*) as completions
   FROM tasks t
   JOIN projects p ON t.project_id = p.id
   WHERE p.client_id = ?
     AND t.status = 'done'
     AND t.updated_at > ?   -- 5 business days ago (computed in Python)
   ```
   → `completions_5d`

3. Query last meeting (search by client name in event title):
   ```sql
   SELECT e.start_time, e.title
   FROM events e
   WHERE e.title LIKE '%' || ? || '%'    -- client name
   ORDER BY e.start_time DESC
   LIMIT 1
   ```

4. **Drift fires when:** `overdue_count > 0 AND completions_5d = 0`
   - Translation: tasks are past due and nothing has been completed for this client in 5 business days

5. **Communication context (doesn't independently trigger):** `days_since_last_meeting > 21` — added to the finding as supplementary context

**Client priority from revenue:** The `clients` table has `tier` and `financial_annual_value` in schema.py. The revenue columns (`prior_year_revenue`, `ytd_revenue`, `lifetime_revenue`) exist at runtime but are NOT in schema.py (queried at `server.py` line 5228 — added via migration or ALTER TABLE). The detector queries them with fallback:

```sql
SELECT c.id, c.name, c.tier, c.financial_annual_value,
       COALESCE(c.ytd_revenue, 0) as ytd_revenue,
       COALESCE(c.lifetime_revenue, 0) as lifetime_revenue
FROM clients c
WHERE c.id = ?
```

If the columns don't exist, SQLite returns an error — the detector catches this and falls back to `tier` + `financial_annual_value` only. Each drift finding includes the client's tier and available revenue data. A platinum client drifting has different visual weight than a bronze one. The finding card shows the tier badge next to the client name.

**Handling legitimate quiet periods:** If a client has 0 active tasks, they can't drift. No overdue tasks = no finding. This naturally handles completed engagements and phase transitions.

**Adjacent data:**

Each drift finding includes:
- Client tier (platinum/gold/silver/bronze) and available revenue data
- The overdue tasks by title, with assignee name and days past due
- Who on the team is assigned to this client, with their current total active task count
- The last completed task for this client (title, date, who completed it)
- Days since last meeting (if > 21, highlighted)

**What it says:**

> 🥇 Client Flavor (platinum, $180K YTD) — 4 overdue tasks, 0 completions in 5 days
> Overdue: "Q2 proposal" (5 days past due, Ahmad), "Social calendar" (3 days, Ahmad), "Brand review" (2 days, Reem), "Invoice follow-up" (1 day, Reem)
> Assigned: Ahmad (34 active total, 4 for Flavor — all overdue), Reem (18 active total, 2 for Flavor — all overdue)
> Last completion: "Social media calendar" by Ahmad on Feb 10
> Last meeting: 24 days ago

**What it doesn't say:** No health score. No "critical" label. The overdue count, zero completions, client tier, and assignee context make the situation self-evident. A platinum client at $180K YTD with 4 overdue tasks and zero movement — the executive knows exactly how bad that is without a color code.

**Existing code used:**
- Active task query pattern from `ClientHealthView.get_client_health()` of `command_center.py`
- Task-to-client link via `tasks.project_id` → `projects.client_id` (both in schema.py)
- Client tier from `clients.tier` + `classify_tier()` in `revenue_analytics.py` line 113
- Revenue: `financial_annual_value` (schema.py), `ytd_revenue`/`lifetime_revenue` (runtime, with fallback)

---

### 3. Bottleneck — "Is someone drowning?"

**What it detects:** Team members whose work is piling up AND not getting done — not just busy, but falling behind.

**Why "piling up AND not completing," not just "more tasks than average":** v1 flagged anyone with >2x the team median active tasks. Problem: if Reem is the senior handling the biggest client, she'll always have 2x the load. That's not a bottleneck — that's the org structure. Flagging her every cycle teaches you to ignore findings. The dual condition (high load + low throughput) distinguishes "busy and handling it" from "busy and drowning."

**Vacation/absence handling:** If a team member has zero calendar events for 3+ consecutive business days AND zero task completions in the same period, the system marks them as "possibly away" and excludes them from team median calculations. Calendar check uses:

```sql
SELECT COUNT(*) as event_count
FROM events e
JOIN calendar_attendees ca ON ca.event_id = e.id
WHERE ca.email = ?                     -- team_members.email
  AND date(e.start_time) >= ?          -- 3 business days ago
  AND date(e.start_time) <= ?          -- today
```

This prevents absences from skewing the team numbers. The finding notes who was excluded: "Excluded from median: Sara (possibly away — no calendar activity since Feb 28)."

**Detection logic:**

1. For each team member, count `active_tasks`:
   ```sql
   SELECT COUNT(*) FROM tasks
   WHERE assignee = ?                  -- team_members.name (string match)
     AND status IN ('active', 'in_progress')
   ```

2. For each team member, count `completed_5d`:
   ```sql
   SELECT COUNT(*) FROM tasks
   WHERE assignee = ?
     AND status = 'done'
     AND updated_at > ?                -- 5 business days ago
   ```

3. Mark "possibly away" members (0 calendar events via query above + 0 completions for 3+ consecutive business days) and exclude from median calculations

4. Compute team medians from remaining members: `median_active`, `median_completed_5d`

5. For each team member, count `overdue_tasks`:
   ```sql
   SELECT COUNT(*) FROM tasks
   WHERE assignee = ?
     AND status IN ('active', 'in_progress')
     AND due_date < date('now')
   ```

6. Compute team `median_overdue` from remaining members

7. **Bottleneck fires when:** `active_tasks > 2 * median_active` AND `completed_5d < median_completed_5d`
   - Translation: they have double the typical load AND they're completing less than the typical amount

8. **Also fires when:** `overdue_tasks > 2 * median_overdue` AND `overdue_tasks > 3`
   - Translation: significantly more overdue items than peers, and not just 1-2 items

**Why two triggers:** The first catches slow drowning — tasks accumulating, throughput dropping. The second catches the acute case — deadlines blowing past while others are on track.

**Adjacent data:**

Each bottleneck finding includes:
- Task breakdown by client/project: where is the pile-up concentrated?
- The overdue tasks by title, client, and days overdue
- Nearest peers by project overlap: who else works on the same clients and could absorb?

**What it says:**

> Ahmad — 34 active tasks (team median: 16), 2 completed in 5 days (team median: 8)
> Breakdown: Client Flavor (12 tasks), Client Zest (8), ops (14)
> Overdue: 7 tasks (team median: 3) — "Flavor proposal" (5 days), "Zest report" (3 days), ...
> Peers on same clients: Reem (Flavor: 3 tasks, completed 6 in 5d), Sara (Zest: 5 tasks, completed 4 in 5d)
> Excluded from median: Dana (possibly away since Feb 28)

**What it doesn't say:** No "overloaded" label. No load percentage. The numbers tell the story.

**Existing code used:**
- Active task count query pattern from `TeamLoadView.get_team_load()` lines 334-339 of `command_center.py` (uses `tasks.assignee = team_members.name`)
- Overdue count pattern from same method, lines 344-346
- Task-by-project breakdown from `TeamLoadView.get_member_detail()` lines 426-444
- Calendar events per team member: `events` + `calendar_attendees` JOIN on `email` (replaces broken `calendar_events.subject_email` reference)

---

## Cross-Detection Correlation

Findings don't exist in isolation. If Client Flavor is drifting AND Ahmad (who handles Flavor) is bottlenecked AND Tuesday has a collision with Flavor tasks due — that's one problem, not three.

**Correlation rule:** After all three detectors run, check for shared entities.

**Rendering rule: the entity that appears in the most findings becomes the primary. Impacts fold under it.**

If Ahmad is bottlenecked and two clients are drifting because of him:

> **Ahmad — bottlenecked** (34 active, 2 completed in 5 days, team median: 8)
>
> Causing drift on:
> - 🥇 Client Flavor (platinum, $180K YTD): 4 tasks overdue, 0 completions in 5 days
> - 🥈 Client Zest (gold, $85K YTD): 3 tasks overdue, 0 completions in 5 days
>
> Peers who could absorb: Reem (Flavor: 3 tasks, completed 6), Sara (Zest: 5 tasks, completed 4)

One card, one root cause, multiple impacts listed beneath it.

If a collision day has tasks from a drifting client, the collision finding gets a cross-reference line: "Tuesday: 3 of 4 tasks are from Flavor (drifting — see above)" but doesn't merge into the drift card because the collision is about the day, not about the client.

Edge case — two people bottlenecked on the same drifting client: two separate bottleneck cards, each with the client drift as a subordinate reference.

**Implementation:** The correlator outputs a list of `FindingGroup` objects. Each group has one primary finding and zero or more subordinate findings. The UI renders one card per group. The correlator is a single pass through findings looking for shared `entity_id` values (client_id, assignee name). If a person appears in bottleneck AND is the assignee on a drifting client's overdue tasks, the bottleneck is primary and the drift folds under it.

---

## Feedback Loop — Acknowledgment and Suppression

Two interactions on each finding card: **"Got it"** and **"Expected."**

**"Got it"** = "I've seen this, I'm handling it." The finding stays active but stops appearing in the morning brief until it either resolves or gets worse. It shows in the Command Center but moves to an "Acknowledged" section at the bottom. If underlying numbers worsen (overdue count increases, ratio grows, stale count grows), it un-acknowledges and resurfaces.

**"Expected"** = "This is structural, stop telling me." Example: Reem always has 2x the load because she's the senior designer — mark her bottleneck as Expected. It suppresses the finding for 30 days, after which it reappears once for re-confirmation. The system still computes the finding internally (correlations still work), it just doesn't surface it.

**Storage:** Two columns on `detection_findings`: `acknowledged_at` (timestamp, null if not acknowledged) and `suppressed_until` (date, null if not suppressed). The morning brief skips acknowledged findings unless they worsened. The API filters suppressed findings to a collapsible "Suppressed" section.

**Why this matters:** Without this, the executive learns to ignore Tuesday collisions (always meeting-heavy) and Reem's bottleneck card (always high load). Once you start ignoring findings, you ignore all of them. "Got it" and "Expected" let the system respect that you know your patterns while still catching deviations from those patterns.

---

## Staleness Countermeasure

Two layers: passive detection and active refresh.

### Passive: System-Level Staleness Detection

If the detection phase hasn't completed successfully in 2+ hours during business hours (9 AM - 9 PM):

1. **Command Center banner** changes from "Last detection: 12 min ago" to a yellow warning: "Detection stale — last run 3 hours ago ⚠️". The "Nothing requires attention" text does NOT display when detection is stale — instead: "Detection hasn't run recently. Findings may be outdated."

2. **Google Chat push:** A single message: "⚠️ Detection system hasn't run since 10:14 AM. Findings may be stale." Fires once, clears on next successful detection.

**Implementation:** The autonomous loop already writes to `sync_state`. The detection phase updates a `detection_last_run` row on success. The staleness check: `NOW() - detection_last_run > 2 hours AND within_business_hours → set detection_stale flag`.

### Active: On-Demand Micro-Sync

When the executive drills into a specific finding, the system refreshes the relevant data first — but only for data sources that support scoped pulls.

**What can be micro-synced (verified against collector source code):**
- Calendar events: `all_users_runner.collect_calendar_for_user(user, since, until, limit, db_path)` at line 331 — supports per-user scoped pulls via domain-wide delegation. **Important:** This function fetches events from the Google Calendar API and returns `{ok, count, calendars}` but does NOT write to the DB. The actual DB persistence is handled by `CalendarCollector.sync()` → `transform()` → `store.insert_many("events", ...)` (line 407). Micro-sync must either: (a) instantiate a CalendarCollector scoped to one user and call `sync()`, or (b) extract the transform+store logic into a reusable helper that `collect_calendar_for_user()` can call. Option (b) is cleaner — ~30 additional lines in `all_users_runner.py` to add a `_store_calendar_events(raw_events, db_path)` helper that reuses `CalendarCollector.transform()` and `store.insert_many()`.
- Gmail/email: `all_users_runner.collect_gmail_for_user(user, since, until, limit, db_path)` at line 227 — same per-user support. Same storage caveat applies — fetches but doesn't persist. Needs equivalent storage wiring.

**What CANNOT be micro-synced:**
- Asana tasks: `AsanaCollector.collect()` takes no parameters. Always fetches ALL tasks in the workspace. No assignee, project, or client filter. Task data freshness depends on the scheduled 30-minute collection cycle.

**How it works:** Clicking a finding card to expand its detail view calls `GET /api/command/findings/{id}?refresh=true`. The API checks the freshness of the underlying calendar/email data for that specific entity. If older than 1 hour, it triggers a targeted micro-sync before returning the response:

- **Bottleneck finding for Ahmad** → micro-sync Ahmad's calendar events (`collect_calendar_for_user(ahmad_email, ...)`) + Ahmad's email (`collect_gmail_for_user(ahmad_email, ...)`). Task data from last scheduled collection.
- **Drift finding for Client Flavor** → micro-sync calendar for each team member assigned to Flavor. Task data from last scheduled collection.
- **Collision finding for Tuesday** → micro-sync calendar events for the person for that date range. Task data from last scheduled collection.

**Wiring needed:** The API endpoint triggers a scoped fetch+store cycle, bypassing the `CollectorOrchestrator` (which only supports full-collector runs). This requires: (1) calling `collect_calendar_for_user()` / `collect_gmail_for_user()` to fetch raw data, (2) running the fetched data through `CalendarCollector.transform()` / `GmailCollector.transform()` to normalize it, (3) calling `store.insert_many()` to persist. Steps 2-3 should be extracted into reusable `_store_calendar_events()` and `_store_gmail_messages()` helpers in `all_users_runner.py` (~30 lines each). The API wiring itself is ~40 lines. Total micro-sync wiring: ~100 lines across `all_users_runner.py` and `server.py`.

**UI behavior:** The detail panel shows a brief loading state ("Refreshing calendar & email...") for the 1-3 seconds the micro-sync takes, then renders with fresh numbers. If the micro-sync changes the underlying data, the finding's display updates. Note: task counts may be up to 30 minutes stale since Asana doesn't support scoped pulls.

**Why demand-driven:** Data that nobody's looking at doesn't get refreshed. Data that the executive is actively deciding on gets refreshed at the moment of decision. This is cheaper than polling every entity continuously and more reliable than hoping the last scheduled sync was recent enough.

---

## Dry-Run Preview Mode

Before going live, the detection system runs in preview mode for one week against real data.

**How it works:** Each detector has a `dry_run: bool` parameter. When true, findings write to `detection_findings_preview` instead of `detection_findings`. The morning brief doesn't fire. The Command Center gets a toggle: "Preview mode — showing draft findings."

During preview week, the executive reviews findings daily and flags:
- False positives (findings that fired but shouldn't have)
- Missing detections (situations that should have fired but didn't)
- Threshold adjustments needed (ratio too sensitive, overdue window too tight)

Each piece of feedback informs threshold tuning before the system goes live. This is cheaper and more realistic than synthetic test data because it uses actual agency patterns.

**After preview:** Flip `dry_run = False`, drop the preview table, and the system is live with tested thresholds.

**Implementation:** ~40 lines — a `dry_run` flag on each detector and a conditional table write path.

---

## Delivery Surface

### Command Center: One View

The three-tab layout (Client Health, Team Load, Decision Queue) is replaced with a single scrollable screen.

```
┌─────────────────────────────────────────────────────────────┐
│  Last detection: 12 min ago                                  │
│                                                              │
│  Week Strip (10 business days, always visible)               │
│  [Mon] [Tue] [Wed] [Thu] [Fri]  [Mon] [Tue] [Wed] [Thu] [Fri]│
│   2h    1h    5h    3h    6h     4h    2h    5h    4h    7h  │
│   3    4:1↑   1     2     0      1     3     1     0     0   │
│        ^^^red                                                │
├──────────────────────────────────────────────────────────────┤
│  Active Findings                                             │
│                                                              │
│  ┌─ Ahmad — bottlenecked ────────────────────────────────┐  │
│  │ 34 active tasks (median: 16), 2 completed in 5d (med: 8) │
│  │                                                        │  │
│  │ Causing drift on:                                      │  │
│  │ • 🥇 Flavor (platinum, $180K YTD): 4 overdue, 0 done  │  │
│  │ • 🥈 Zest (gold, $85K YTD): 3 overdue, 0 done        │  │
│  │                                                        │  │
│  │ Peers: Reem (Flavor: 3 tasks, 6 done), Sara (Zest: 5) │  │
│  │                                                        │  │
│  │ [Got it]  [Expected]                          ▸ Detail │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ Tuesday Mar 4 — collision (4:1) ─────────────────────┐  │
│  │ 4 tasks due, 1 hour free                               │  │
│  │ 3 of 4 tasks are Ahmad's (bottlenecked — see above)    │  │
│  │ Moveable: "Onboarding doc" (due Thu), "Budget" (due Fri)│  │
│  │                                                        │  │
│  │ [Got it]  [Expected]                          ▸ Detail │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  — or when clean: —                                          │
│                                                              │
│  Nothing requires attention.                                 │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  ▸ Acknowledged (1)                                          │
│  ▸ Suppressed (1)                                            │
├──────────────────────────────────────────────────────────────┤
│  ▸ Team Collisions (2 members with collisions this week)     │
├──────────────────────────────────────────────────────────────┤
│  Decision Queue                                              │
│  12 items awaiting action                                    │
│  ▸ 3 overdue tasks                                          │
│  ▸ 5 open commitments                                        │
│  ▸ 2 pending responses                                       │
│  ▸ 2 critical signals                                        │
└──────────────────────────────────────────────────────────────┘
```

**Sections top to bottom:**

1. **Staleness indicator** — always visible. "Last detection: X min ago" or yellow warning if stale.
2. **Week strip** — 10 business days. Each day shows available hours, task count, ratio color (green < 1.0, amber 1.0-2.0, red > 2.0). Clickable for day detail. Always visible even when no findings.
3. **Active findings** — correlated finding cards with adjacent data. "Got it" and "Expected" buttons. Expandable detail. When empty: "Nothing requires attention."
4. **Acknowledged** — collapsed by default. Shows findings you've marked "Got it."
5. **Suppressed** — collapsed by default. Shows findings marked "Expected" with re-confirmation date.
6. **Team Collisions** — collapsed by default. Shows team members with collisions, grouped by person.
7. **Decision Queue** — unchanged from current implementation.

**Why no tabs:** Tabs create a browsing experience. One scroll replaces three clicks.

---

## Morning Brief — Google Chat

**When:** Once daily at 8:00 AM local time (configurable via `governance.yaml` → `morning_brief_hour`). 8 AM avoids quiet hours (23:00-08:00 Dubai time). The autonomous loop runs its detection cycle and, if any findings changed since yesterday, pushes a single Google Chat message.

**What "changed" means:**
- New finding appeared (wasn't present yesterday)
- Existing finding got worse (ratio increased, overdue count grew)
- A finding resolved (was present yesterday, isn't today)
- Acknowledged findings are excluded UNLESS they worsened

**Format — if findings exist:**

> **Morning Brief — Tue Mar 4**
>
> ⚠️ **Tuesday collision:** 4 tasks due, 1 hour free (4:1). Moveable: "Onboarding doc" (due Thu), "Budget approval" (due Fri)
>
> 📉 **Client Flavor drifting** (🥇 platinum, $180K YTD): 4 overdue tasks, 0 completions in 5d. Ahmad has 4 Flavor tasks, all overdue.
>
> 🔴 **Ahmad bottlenecked:** 34 active (median: 16), 2 completed in 5d (median: 8). Top: Flavor (12), Zest (8).
>
> ✅ **Resolved:** Client Zest drift cleared (3 tasks completed yesterday)
>
> 📊 **Weight check:** 5 tasks auto-classified this week. Open Command Center to review.

**Format — if clean:**

> **Morning Brief — Tue Mar 4**
>
> Nothing requires attention.

**Format — if revenue data unavailable for a drifting client:**

> 📉 **Client Flavor drifting** (🥇 platinum): 4 overdue tasks, 0 completions in 5d.

Revenue figures omitted gracefully when columns don't exist.

**Timing gate:** The autonomous loop may run multiple times per day. Morning brief only sends if `current_hour >= morning_brief_hour` (default 8) AND `last_brief_sent < today`. Exactly one brief per day.

**Existing code used:**
- `GoogleChatChannel` in `lib/notifier/channels/google_chat.py` — async send with card v2 formatting
- `NotificationEngine` wired into autonomous loop at line 59
- Rate limits from `NotificationEngine`: critical=3/day, high=5/day, normal=10/day. Morning brief uses normal priority.
- Quiet hours: 23:00-08:00 Dubai time. Morning brief is set to 8 AM (configurable via `morning_brief_hour` in `governance.yaml`), which falls exactly at the end of quiet hours. The brief fires at or after `morning_brief_hour`, so it naturally avoids quiet hours.

---

## What This Design Explicitly Does Not Do

1. **No time estimates on tasks.** Task weight (quick/standard/heavy) is derived from existing data and confirmed via a learning loop. No manual hour estimates.

2. **No predictive scoring.** No "this client will churn." The system observes current state and compares facts.

3. **No automated actions.** The system doesn't reassign tasks, move deadlines, or cancel meetings. It presents facts with enough context to decide. Automation comes after detections prove reliable.

4. **No historical trend analysis (yet).** Uses 5-day windows with current data. Once 90+ days of `detection_findings` history exists, trend overlays become a natural Phase 16 evolution.

5. **No Chat-based actions.** The morning brief is informational. Quick actions in Google Chat ("reply 1 to reassign") is Phase 16 scope, after detections prove themselves. The Command Center is the action surface.

6. **No blocked/waiting-on distinction.** The system doesn't know if a task is overdue because it's neglected or because it's waiting on the client. Deadlines are the signal — past due is past due. If the team is routinely marking tasks overdue while waiting for external input, that's a process problem (they should extend the deadline), not a detection system problem.

7. **No Asana micro-sync.** The Asana collector fetches ALL tasks with no filter. Per-entity task refresh is not possible without building a new scoped Asana API method. Task data freshness depends on the 30-minute collection cycle. This is a known limitation — acceptable because task data changes less frequently than calendar data, and the 30-minute cycle covers most scenarios. If this proves insufficient in production, a scoped Asana method (~100 lines) can be added in Phase 16.

---

## Phased Build Plan

### Phase 15a: CalendarSync Expansion + Schema Formalization (1 PR)

**What:** Extend time block generation from 7 to 10 business days. Formalize `time_blocks` in schema.py.

**Files changed:**
- `lib/time_truth/calendar_sync.py`:
  - `ensure_blocks_for_week()` at line 235: change `timedelta(days=6)` to `timedelta(days=13)` (covers 10 business days across 2 calendar weeks)
  - Add weekend-skip logic in `sync_events()` to skip Saturday/Sunday dates
- `lib/schema.py`:
  - Add `TABLES["time_blocks"]` with columns from SCHEMA_ATLAS: `id, date, start_time, end_time, lane, task_id, is_protected, is_buffer, created_at, updated_at`
  - This formalizes a table that already exists at runtime (created by BlockManager) — the migration is safe because `CREATE TABLE IF NOT EXISTS` is idempotent
  - Verify revenue columns (`prior_year_revenue`, `ytd_revenue`, `lifetime_revenue`) at startup — add to schema if not present, with `ALTER TABLE ADD COLUMN IF NOT EXISTS` pattern

**Does NOT touch:** `lib/truth_cycle.py` (dead code — the autonomous loop calls `CalendarSync` directly via `_process_time_truth()` at line 851 of `autonomous_loop.py`).

**Why first:** Collision detection queries `time_blocks` for future days. Without blocks for those days, there's nothing to query.

**Verification:**
- `time_blocks` appears in schema.py with correct columns matching SCHEMA_ATLAS
- After truth cycle run, `time_blocks` table has rows for the next 10 business days
- Weekends are skipped
- Idempotent: running twice doesn't create duplicate blocks (existing check at line 127-130 of `calendar_sync.py`)
- Revenue columns either exist or are added — detector can query them without error

**Estimated size:** ~60 lines changed.

---

### Phase 15b: Three Detectors + Correlator + Findings Table (1 PR)

**What:** Implement CollisionDetector, DriftDetector, BottleneckDetector, the correlator, the findings table, the task weight system, and dry-run preview mode.

**Files created:**
- `lib/detectors/__init__.py` — exports + `run_all_detectors(dry_run=False)` orchestrator
- `lib/detectors/collision.py` — `CollisionDetector` with two paths (Molham via time_blocks, team via events+calendar_attendees)
- `lib/detectors/drift.py` — `DriftDetector` with client tier/revenue (graceful fallback if revenue columns missing)
- `lib/detectors/bottleneck.py` — `BottleneckDetector` with absence exclusion via events+calendar_attendees
- `lib/detectors/correlator.py` — post-detection entity overlap pass, outputs `FindingGroup` list
- `lib/detectors/task_weight.py` — weight derivation from title/project patterns, learning loop storage

**New tables (added to `lib/schema.py`):**

```sql
-- Detection findings (main + preview)
CREATE TABLE detection_findings (
    id              TEXT PRIMARY KEY,
    detector        TEXT NOT NULL,        -- 'collision', 'drift', 'bottleneck'
    entity_type     TEXT NOT NULL,        -- 'day', 'client', 'team_member'
    entity_id       TEXT NOT NULL,        -- date string, client_id, member_name
    finding_type    TEXT NOT NULL,        -- 'collision', 'overdue_drift', 'throughput_bottleneck', 'overdue_bottleneck'
    severity_data   TEXT NOT NULL,        -- JSON: raw numbers (ratio, overdue_count, etc)
    adjacent_data   TEXT NOT NULL,        -- JSON: moveable tasks, assignees, peers, etc
    related_findings TEXT,                -- JSON: [finding_ids] from correlator
    first_detected  TEXT NOT NULL,
    last_detected   TEXT NOT NULL,
    resolved_at     TEXT,
    notified_at     TEXT,
    acknowledged_at TEXT,                 -- "Got it" timestamp
    suppressed_until TEXT                 -- "Expected" expiry date (30 days)
);

CREATE TABLE detection_findings_preview (
    -- identical schema, used during dry-run week
);

-- Task weight rules (learning loop)
CREATE TABLE task_weight_rules (
    id              TEXT PRIMARY KEY,
    pattern         TEXT NOT NULL,        -- keyword or project type
    field           TEXT NOT NULL,        -- 'title' or 'project_type'
    assigned_weight TEXT NOT NULL,        -- 'quick', 'standard', 'heavy'
    confidence      REAL DEFAULT 0.5,
    corrections     INTEGER DEFAULT 0,
    confirmations   INTEGER DEFAULT 0
);

-- Per-task weight overrides (manual corrections)
CREATE TABLE task_weight_overrides (
    task_id         TEXT PRIMARY KEY,
    weight          TEXT NOT NULL,        -- 'quick', 'standard', 'heavy'
    set_by          TEXT NOT NULL,        -- 'system' or 'user'
    set_at          TEXT NOT NULL
);
```

**Detector dataclasses:**

```python
@dataclass
class CollisionFinding:
    date: str
    person: str                          # 'Molham Homsi' or team member name
    available_minutes: int
    tasks_due: int
    weighted_ratio: float
    meetings: list[dict]                 # [{title, start, end}] from events table
    tasks: list[dict]                    # [{id, title, client, project, due_date, weight}]
    moveable_tasks: list[dict]           # subset: due_date > date + 2 days

@dataclass
class DriftFinding:
    client_id: str
    client_name: str
    client_tier: str                     # platinum/gold/silver/bronze
    client_ytd_revenue: float | None     # None if revenue columns don't exist
    overdue_tasks: list[dict]            # [{id, title, assignee, days_past_due}]
    completions_5d: int                  # 0 by definition when drift fires
    assigned_team: list[dict]            # [{name, total_active, client_active, client_overdue}]
    last_completion: dict | None         # {title, completed_by, date}
    days_since_last_meeting: int | None

@dataclass
class BottleneckFinding:
    member_name: str
    active_tasks: int
    completed_5d: int
    overdue_tasks: int
    team_median_active: int
    team_median_completed: int
    team_median_overdue: int
    breakdown_by_client: list[dict]      # [{client_name, task_count}]
    overdue_items: list[dict]            # [{title, client, days_overdue}]
    peers: list[dict]                    # [{name, shared_clients, active, completed_5d}]
    excluded_members: list[dict]         # [{name, reason, since}]

@dataclass
class FindingGroup:
    primary: CollisionFinding | DriftFinding | BottleneckFinding
    subordinates: list                   # related findings folded under primary
    shared_entity: str                   # the entity that links them
```

**Files changed:**
- `lib/autonomous_loop.py` — add DETECTION phase (Phase 1b5) after AUTO-RESOLVE (after line 223), before TRUTH MODULES (line 225). Call `run_all_detectors(dry_run=True)`. Write `detection_last_run` to `sync_state` on success.

**Key implementation notes:**
- All calendar queries use `events` + `calendar_attendees` JOIN, never `calendar_events`
- Task-to-person matching uses `tasks.assignee = team_members.name` (string match, same pattern as existing `command_center.py` line 337)
- Task-to-client linking uses `tasks.project_id` → `projects.client_id` (both in schema.py)
- Revenue queries use `COALESCE` with try/except for missing columns
- Collision Path B (team members): `available_minutes = 480 - meeting_minutes` (8-hour day assumed)

**Dependencies:** Phase 15a (collision needs future time blocks).

**Verification:**
- Run autonomous loop → `detection_findings_preview` populated (dry-run mode for first week)
- Run again with no changes → no duplicate rows, `last_detected` updated
- Collision scenario: tasks due tomorrow, no open blocks → finding with correct weighted ratio
- Collision Path B: team member with meetings filling entire day + tasks due → collision fires
- Drift scenario: client with overdue tasks, 0 completions in 5d → finding with tier and available revenue
- Drift with missing revenue columns: finding still fires, revenue shows as null
- Bottleneck scenario: member with 2x median active AND below median completions → finding fires
- Absence: member with 0 calendar events for 3+ days (via events+calendar_attendees query) → excluded from median, noted in finding
- Correlation: drift client's tasks assigned to bottlenecked member → merged `FindingGroup`
- Task weight: "proposal" in title → derived as heavy, manual correction updates rule confidence

**Estimated size:** ~710 lines new code, ~30 lines changed in autonomous_loop.py.

---

### Phase 15c: API Endpoints + Micro-Sync (calendar & email only) + ADR (1 PR)

**What:** Wire detection findings, week strip, and staleness to the API. Micro-sync for calendar and email data only (Asana excluded — see "What This Design Does Not Do" §7).

**Endpoints:**
- `GET /api/command/week-strip` — 10-day array: `[{date, available_minutes, tasks_due, weighted_ratio, has_collision}]`
- `GET /api/command/findings` — active findings grouped by correlation, with acknowledged/suppressed sections
- `GET /api/command/findings/{id}?refresh=true` — single finding detail with optional on-demand micro-sync for calendar + email data. When `refresh=true`, calls `collect_calendar_for_user()` and `collect_gmail_for_user()` from `all_users_runner.py` directly (bypassing orchestrator). Task data from last scheduled collection.
- `POST /api/command/findings/{id}/acknowledge` — mark "Got it"
- `POST /api/command/findings/{id}/suppress` — mark "Expected" (30-day suppression)
- `GET /api/command/staleness` — `{last_run, is_stale, stale_since}`
- `GET /api/command/weight-review` — pending weight confirmations for the learning loop
- `POST /api/command/weight-review/{task_id}` — confirm or correct a task's weight

**Response shape for `/api/command/findings`:**

```json
{
  "groups": [
    {
      "primary": {
        "id": "...",
        "detector": "bottleneck",
        "entity_name": "Ahmad",
        "summary": "34 active (median: 16), 2 completed in 5d (median: 8)",
        "severity_data": {"active": 34, "completed_5d": 2, "median_active": 16},
        "adjacent_data": {"breakdown": [...], "peers": [...]}
      },
      "subordinates": [
        {"id": "...", "detector": "drift", "entity_name": "Client Flavor", "summary": "4 overdue, 0 completions", "client_tier": "platinum", "ytd_revenue": 180000}
      ],
      "shared_entity": "Ahmad"
    }
  ],
  "acknowledged": [...],
  "suppressed": [...],
  "team_collisions": [...],
  "count": 3,
  "last_detection": "2026-03-03T06:00:00",
  "is_stale": false
}
```

**Micro-sync wiring (~100 lines total: ~60 in all_users_runner.py, ~40 in server.py):**
```python
# New helpers in all_users_runner.py:
def micro_sync_calendar(user_email: str, since: str, until: str, db_path: Path) -> dict:
    """Fetch + transform + store calendar events for one user."""
    raw = collect_calendar_for_user(user_email, since, until, limit=100, db_path=db_path)
    if not raw["ok"] or raw["count"] == 0:
        return raw
    # Re-fetch raw event data (collect_calendar_for_user doesn't return raw events)
    # Instead: instantiate CalendarCollector scoped to this user, call sync()
    from lib.collectors.calendar import CalendarCollector
    collector = CalendarCollector({"user": user_email}, store=StateStore(db_path))
    return collector.sync(since=since, until=until)

def micro_sync_gmail(user_email: str, since: str, until: str, db_path: Path) -> dict:
    """Fetch + transform + store gmail messages for one user."""
    from lib.collectors.gmail import GmailCollector
    collector = GmailCollector({"user": user_email}, store=StateStore(db_path))
    return collector.sync(since=since, until=until)

# In the findings/{id} endpoint (server.py):
from lib.collectors.all_users_runner import micro_sync_calendar, micro_sync_gmail

# For bottleneck findings — refresh member's calendar + email
member_email = finding.entity_id  # or look up from team_members
micro_sync_calendar(member_email, since, until, db_path=store.db_path)
micro_sync_gmail(member_email, since, until, db_path=store.db_path)
```

**Note:** The exact implementation depends on whether `CalendarCollector.sync()` accepts `since`/`until` parameters for scoped pulls. If it doesn't, the sync method needs a minor extension to accept a date range (~10 lines). This is verified during Phase 15c implementation.

**ADR required:** `docs/adr/0013-detection-system.md` — `api/server.py` is modified.

**Dependencies:** Phase 15b.

**Verification:**
- Each endpoint returns correct shape
- No findings → `{"groups": [], "count": 0}`
- Correlated findings → grouped correctly
- Acknowledge → finding moves to acknowledged section
- Suppress → finding moves to suppressed section, reappears after 30 days
- Staleness → returns correct stale flag based on `detection_last_run`
- Micro-sync: `?refresh=true` on a bottleneck finding triggers calendar + email pull for that member
- Micro-sync: `?refresh=true` on a drift finding triggers calendar pull for assigned team members
- Micro-sync does NOT trigger Asana task pull (expected behavior)
- Micro-sync latency: < 3 seconds for calendar + email scoped pull

**Estimated size:** ~270 lines in server.py, ~60 lines in all_users_runner.py (micro-sync helpers + CalendarCollector/GmailCollector scoped sync wiring), ~30 lines ADR.

---

### Phase 15d: Command Center UI Redesign (1 PR)

**What:** Replace three-tab scored layout with single-view design (as shown in layout diagram above).

**Files changed:**
- `time-os-ui/src/pages/CommandCenter.tsx` — full rewrite to single-view layout
- `time-os-ui/src/lib/api.ts` — add fetch functions for all new endpoints
- `time-os-ui/src/lib/hooks.ts` — add hooks for new endpoints

**New components (in CommandCenter.tsx):**
- `StalenessBar` — staleness indicator at top
- `WeekStrip` — 10-day horizontal cards with ratio coloring
- `FindingCard` — single finding with expandable adjacent data, "Got it" and "Expected" buttons. On expand, calls `?refresh=true` endpoint and shows brief "Refreshing calendar & email..." state before rendering detail with fresh data.
- `CorrelatedGroup` — groups related findings, primary + subordinates
- `TeamCollisions` — collapsible section for team member collisions

**Note:** Replace the inline `useFetchCommand()` hook (lines 17-30 of current `CommandCenter.tsx`) with shared hooks from `hooks.ts`.

**Dependencies:** Phase 15c.

**Verification:**
- Renders with staleness bar, week strip, findings, decision queue
- Empty state: "Nothing requires attention" (only when not stale)
- Stale state: yellow warning, no "nothing requires attention"
- Finding cards show adjacent data, expand on click
- "Got it" / "Expected" buttons work via API
- Correlated findings render as grouped cards
- Team collisions in collapsible section
- Week strip days are clickable
- No scored lists or color-coded labels anywhere

**Estimated size:** ~350 lines changed in CommandCenter.tsx, ~80 lines in api.ts/hooks.ts.

---

### Phase 15e: Morning Brief + Staleness Alert (1 PR)

**What:** Daily morning brief via Google Chat. Staleness warning when detection is stale.

**Files created:**
- `lib/detectors/morning_brief.py` — compares current findings against `notified_at`, formats message, sends via GoogleChatChannel. Includes weight review prompt when pending confirmations exist. Gracefully omits revenue figures when not available.

**Files changed:**
- `lib/autonomous_loop.py` — call `morning_brief.send_if_changed()` after detection phase. Add staleness check: if `detection_last_run` is >2 hours old during business hours, send one-time stale warning.
- `config/governance.yaml` — add `morning_brief_hour: 8` setting (avoids quiet hours 23:00-08:00)

**Morning brief includes:**
- New findings (with client tier, revenue if available)
- Worsened findings (acknowledged findings that got worse are un-acknowledged and included)
- Resolved findings
- Weight review prompt (if pending confirmations exist)
- Suppressed findings are excluded entirely

**Timing gate:** `current_hour >= morning_brief_hour` AND `last_brief_sent < today`. Exactly one brief per day.

**Staleness alert:** `NOW() - detection_last_run > 2 hours` AND `within_business_hours(9, 21)` AND `stale_alert_sent_today = False`. Fires once, clears on next successful detection.

**Dependencies:** Phase 15b. Can run in parallel with 15c/15d.

**Verification:**
- New finding → morning brief fires
- Same finding next day, no change → brief says nothing (or doesn't fire)
- Finding resolves → brief includes "Resolved: ..."
- Acknowledged finding worsens → un-acknowledged and included in brief
- Suppressed finding → excluded from brief
- Brief fires exactly once per day
- Detection stale for 2+ hours during business hours → staleness alert fires once
- Detection resumes → staleness clears
- Drift finding with missing revenue → brief shows tier only, no error

**Estimated size:** ~120 lines.

---

### Phase 15f: Retire Scored Views + Fix Broken Calendar Queries (1 PR)

**What:** Remove scoring logic from Command Center views. Fix the broken `calendar_events` queries that exist in the current code.

**Files changed:**
- `lib/command_center.py`:
  - `ClientHealthView.get_client_health()` — remove `health_status`/`health_reason` (lines 146-160). Keep raw data queries.
  - `TeamLoadView.get_team_load()` — remove `load_status`/`load_reason` (lines 359-377). Fix broken `calendar_events` query at line 351: change from `SELECT id FROM calendar_events WHERE subject_email = ?` to `SELECT e.id FROM events e JOIN calendar_attendees ca ON ca.event_id = e.id WHERE ca.email = ? AND date(e.start_time) >= ? AND date(e.start_time) <= ?`
  - `TeamLoadView.get_member_detail()` — fix broken `calendar_events` query at line 461 with same pattern.
- Detail views (`get_client_detail`, `get_member_detail`) otherwise unchanged.

**Dependencies:** Phase 15d.

**Verification:**
- Command Center renders without scored views
- Team load meeting counts now return correct data (previously broken)
- Detail views still work from finding card drill-down
- No scoring labels in API responses
- No references to `calendar_events` table remain in `command_center.py`

**Estimated size:** ~50 lines removed/refactored, ~20 lines added for corrected queries.

---

## Build Sequence

```
15a (CalendarSync + schema) → 15b (Detectors + Correlator + Weights) → 15c (API + micro-sync) → 15d (UI) → 15f (Retire + fix queries)
                                                                       ↘
                                                                        15e (Morning Brief + Staleness)
```

| Phase | What | Size | Depends On |
|-------|------|------|-----------|
| 15a | CalendarSync 10-day + schema formalization | ~60 lines | None |
| 15b | Three detectors + correlator + weights + dry-run | ~740 lines | 15a |
| 15c | API endpoints (8) + micro-sync (calendar/email) + ADR | ~360 lines | 15b |
| 15d | Command Center single-view UI | ~430 lines | 15c |
| 15e | Morning brief + staleness alert | ~120 lines | 15b (parallel with 15c/15d) |
| 15f | Retire scored views + fix broken calendar queries | ~70 lines | 15d |

**Total: 6 PRs, ~1,780 lines net.**

15e can start as soon as 15b merges, independent of the UI work. Phases 15c+15d and 15e run in parallel.

**Dry-run week:** After 15b merges, detectors run in preview mode for 1 week. The executive reviews draft findings daily. Threshold adjustments happen before 15c/15d go live. This means 15b ships first, the preview week runs, and then 15c-15f ship in sequence.

---

## What Changes For the Executive

**Before:** Open Command Center. See 20 clients ranked by color. See 31 team members ranked by color. Click through 3 tabs. Absorb nothing. Close it.

**After:** Open Command Center. See the week strip — Thursday looks tight. See one card: "Ahmad bottlenecked — causing drift on Flavor (platinum, $180K YTD) and Zest (gold, $85K)." See that Reem and Sara could absorb. Hit "Got it," open Asana, reassign 6 tasks. Total time: 90 seconds.

Or: open Command Center. See the week strip — all green. See "Nothing requires attention." Close it. Total time: 5 seconds.

Check your phone at 8 AM. See: "Flavor drifting, Ahmad bottlenecked." Know before the day starts. Or see nothing. Go to the gym.

That's the goal.
