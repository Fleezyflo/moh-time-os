# MOH Time OS — Configuration Discovery (Hard Gate) (v0.1)

> **Goal:** produce a complete, evidence-backed configuration map + impact mapping **before** any execution is enabled.
> Output is a **Config Proposal Bundle** (diff) + a **Discovery Report** (explainable, attributable).

## Principles
- **Deep by default:** enumerate *all* relevant surfaces and parameters; prefer completeness over speed.
- **Attribution:** every inferred config value must cite the evidence that led to it.
- **Uncertainty explicit:** unknowns are first-class; propose safe defaults with assumptions.
- **Conservative actions:** Discovery is read-only; it may draft proposals but never writes to external systems.

---

## What discovery must learn

### 1) Identity & topology
- Which Google account(s) are in scope.
- Which calendars exist (IDs, names, access level, timezone).
- Which Google Tasks lists exist (IDs, names, counts).
- Which channels exist for delegation (email-only unless configured).

### 2) Reality surface baselines (last N days)
Default N=90, configurable.

**Approved rollout:** start with a **14-day deep run** to validate correctness (paging, performance, attribution), then scale to 90 days.

**Email baseline**
- Volume by day, by sender domain, by thread.
- High-sensitivity signal frequency (finance/legal/security keywords + attachments).
- “Directly addressing Moh” detection patterns.

**Calendar baseline**
- Meeting density per weekday.
- Recurring series detection.
- No-meeting windows (natural deep-work windows).
- Typical meeting lengths and clustering.

**Tasks baseline**
- Counts per list.
- Aging distribution (old tasks, overdue tasks).
- Repeated patterns in titles (candidate projects).

**Chat baseline (Google Chat)**
- Mentions/DMs addressing Moh, by space/user.
- Urgency language rate.
- High-sensitivity signal frequency.
- Conversation clusters that suggest project enrollment candidates.

### 3) Lane mapping evidence
- Which lanes appear implicitly (via task list names, keywords, meeting names, sender domains).
- How much work each lane seems to consume (proxy via tasks + meetings + email obligations).

### 4) Priority tier inference (Always urgent / Important / Significant)
- Build a candidate tier model from:
  - frequency of interaction
  - sensitivity rate
  - explicit urgency language
  - external vs internal
  - “directly addressed Moh” rate
- Output as **proposed tiers** + allow manual override.

### 5) Project enrollment candidates
- Candidate projects from:
  - recurring participant clusters
  - recurring threads
  - recurring meeting series
  - repeated task title tokens
- Provide evidence bundles and propose enrollment rule bundles.

### 6) Scheduling window validation
- Validate SEW (default 10:00–20:30) against actual calendar usage.
- Identify natural execution windows.
- Detect systematic overload (AEC shortages).

### 7) Delegation graph validation
- Cross-check delegation roster against observed assignments/threads.
- Propose lane → delegate defaults and escalation paths.

---

## Outputs

### A) Discovery Report (human)
- Executive summary (what the system learned)
- Gaps/unknowns (explicit)
- Proposed config values by domain (A–J)
- Impact map highlights (second-order effects)
- Risk register (where inference could be wrong)

### B) Config Proposal Bundle (machine)
- A single JSON document with:
  - config values
  - evidence pointers
  - assumptions
  - version

### C) Acceptance checks (for discovery)
- All required config domains present (A–J)
- All inferred values have attribution or are marked assumption
- Any missing critical IDs (calendar/task list IDs) blocks Propose/Execute enablement

---

## Safety
- Discovery is **read-only**.
- No emails sent, no calendar edits, no task edits.
- No storage of email bodies unless explicitly enabled; store only metadata by default.
