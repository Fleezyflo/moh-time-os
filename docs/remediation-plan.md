# Remediation Execution Plan

Source of truth: `docs/closure-audit.md` (47 validated bug rows, gate split confirmed)

Audit completeness: **PASS**
Remediation readiness: **BLOCKED** (pending RU-1 decision)

---

## 1. Blockers

### BLOCKER-1: RU-1 — entity_links PK strategy

**Why it blocks:** PR1 must sync `entity_links` in schema.py with the migration schema (D4). The migration uses `link_id TEXT PRIMARY KEY`. schema.py has `id INTEGER PRIMARY KEY`. `converge()` can add columns but cannot rename or retype a PK. Without a decision, schema.py cannot be written.

**Bug rows dependent:** EL-1, EL-2, EL-3, EL-4, EL-5, EL-6, EL-7, EL-8, EL-9, EL-10, EL-11 (all 11 entity_links bugs). Also blocks SF-1, INS-1, N-U1, N-U2, N-S1, N-S2 indirectly because they share PR1.

**Decision required — two options:**

Option A: Add-alongside. Keep `id INTEGER PRIMARY KEY`. Add `link_id TEXT UNIQUE NOT NULL`, `confidence_reasons TEXT`, `status TEXT NOT NULL DEFAULT 'proposed'`, `updated_at TEXT`, `confirmed_by TEXT`, `confirmed_at TEXT`. Backfill `link_id` from existing rows if any. V4 code uses `link_id` as application PK. server.py:5179 (EL-6) switches from `WHERE id=?` to `WHERE link_id=?`.
- Pro: No data loss. converge() handles it.
- Con: Vestigial `id INTEGER` column remains forever.

Option B: Drop-and-recreate. Delete the `entity_links` table definition from schema.py entirely. Add new definition matching migration (12 columns, `link_id TEXT PRIMARY KEY`). converge() sees a new table and creates it. Old data is lost.
- Pro: Clean schema. No vestigial column.
- Con: Loses existing entity_links rows. Only safe if `SELECT count(*) FROM entity_links` is 0.

**Minimum action to unblock:** Molham picks A or B (or a variant). If B, confirm row count is 0.

### BLOCKER-2: RU-7 — notification `message` vs `title` (non-blocking for PR1, blocks PR3 frontend contract)

**Why it blocks PR3:** N-I1..5 fix requires deciding whether the notification INSERT dict includes a `message` field (aliased from `title`) or the frontend Notification interface changes `message` to `title`. Without this, the PR3 handler fixes cannot guarantee the frontend contract is satisfied.

**Bug rows dependent:** N-I1, N-I2, N-I3, N-I4, N-I5 (handler fixes in PR3), plus frontend contract G1.

**Decision required:** (a) Backend aliases `title AS message` in GET /api/notifications response, or (b) frontend renames `message` to `title` in api.ts Notification interface.

**Minimum action to unblock:** Molham picks (a) or (b).

### BLOCKER-3: RU-8 — Evidence interface `excerpt_text` / `context_json` (non-blocking for PR1, blocks PR4 frontend contract)

**Why it blocks PR4:** IH-1 fix rewrites the evidence endpoint to query `artifacts` + `entity_links`. Neither table has `excerpt_text` or `context_json`. The frontend Evidence interface declares these fields. Without removing them from the TS interface, the contract is broken by design.

**Bug rows dependent:** IH-1 (endpoint rewrite in PR4), plus frontend contract G3.

**Decision required:** Remove `excerpt_text` and `context_json` from Evidence TypeScript interface (no alternative data source exists).

**Minimum action to unblock:** Confirm removal is acceptable.

---

## 2. Fix Batches

### Batch A: Schema expansion (PR1)

**Row IDs (6 schema changes, unblocking 17 bug rows):**
- Direct: SF-1, INS-1, INS-2, N-U1, N-U2, N-S1, N-S2
- Unblocked downstream: EL-1..11 (all become fixable once schema syncs)

**Why together:** All are schema.py-only changes. No handler code. Single SCHEMA_VERSION bump. converge() applies all at once on next startup.

**Files touched:** `lib/schema.py`

**Schema changes:**
- Add `saved_filters` table (D3) — unblocks SF-1
- Add `severity TEXT` to insights (D2) — unblocks INS-1
- Add `dismissed INTEGER DEFAULT 0`, `dismissed_at TEXT` to notifications (D1) — unblocks N-U1, N-U2, N-S1, N-S2
- Add `task_id TEXT`, `recipient_id TEXT` to notifications (D8) — unblocks N-I1..5 handler fixes
- Add `couplings` table (D5) — unblocks CP-1
- Sync entity_links to migration schema (D4) — **BLOCKED by RU-1**
- Bump SCHEMA_VERSION

**Migration impact:** converge() runs ALTER TABLE ADD COLUMN for new columns on existing tables. New tables created fresh. entity_links sync depends on RU-1 decision.

**API contract impact:** None — schema changes alone don't change API responses. Endpoints using new columns still need handler fixes (PR3/PR4).

**Regression risk:** Low. converge() is additive. Existing queries are unaffected by new columns. Risk: if SCHEMA_VERSION bump triggers unexpected behavior in a code path that checks version.

**Can ship independently:** YES (except entity_links sync portion, which is blocked).

**Note:** PR1 can ship without entity_links sync. Split into PR1a (everything except entity_links) and PR1b (entity_links sync after RU-1 decision). This unblocks Batch B and parts of Batch C immediately.

---

### Batch B: server.py handler fixes (PR3)

**Row IDs (22 bug rows):**
- Notifications: N-I1, N-I2, N-I3, N-I4, N-I5, N-U1, N-U2, N-S1, N-S2
- Decisions: D-I1, D-I2, D-I3, D-U1, D-U2
- Governance: G-1, G-2, G-3
- Identities (v1): ID-1, ID-2, ID-3
- Entity links (v1): EL-6
- Insights: INS-1

**Why together:** All are in `api/server.py` (or server.py calling into engine.py). Same file, same review surface. The notification, decision, governance, and identity fixes are independent code paths within server.py — no cross-contamination.

**Files touched:** `api/server.py`, `lib/notifier/engine.py` (if any engine-side changes needed for notification INSERT pattern)

**Schema changes:** None (depends on Batch A landing first for N-U1, N-U2, N-S1, N-S2, INS-1, EL-6).

**Handler/query changes:**
- N-I1..5: Remove `recipient_id`, `task_id`, `dismissed` from INSERT dicts. After PR1 lands, add back `task_id` and `recipient_id` using correct schema columns.
- N-U1..2, N-S1..2: Migration-dependent — these work once PR1 adds `dismissed`/`dismissed_at`.
- D-I1..3: Replace `type`→`decision_type`, remove `target_id`/`proposed_changes`/`reason`, add `domain` (NOT NULL).
- D-U1: Remove `processed_by` from UPDATE dict.
- D-U2: Remove `modifications` from UPDATE dict.
- G-1..3: Change table name `governance_history`→`governance_audit_log`. Remap columns: `decision_id`→`subject_identifier`, `type`→`action`, remove `target_id`/`processed_by`/`side_effects`, add `actor`/`details`.
- ID-1: Remove inline `CREATE TABLE IF NOT EXISTS identities`. Query `client_identities` instead.
- ID-2: Rewrite SELECT to use `client_identities` with correct columns.
- ID-3: Rewrite UPDATE to use `client_identities` with correct columns.
- EL-6: Change `WHERE id=?` to `WHERE link_id=?`, remove `updated_at` (or keep if PR1b landed).
- INS-1: ORDER BY `severity` — works once PR1 adds the column.

**API contract impact:** Notification responses gain `task_id`, `recipient_id`. Governance history response changes column shape. Fix-data identity_conflicts changes column shape. RU-7 decision affects whether `title` is aliased to `message`.

**Regression risk:** Medium. server.py is large (5000+ lines). Each fix is isolated to its endpoint function, but the governance column remap (G-1..3) touches the approval flow which has partial-mutation risk (G-1 fires AFTER D-U1's UPDATE).

**Can ship independently:** YES, after Batch A. Migration-dependent rows (N-U1, N-U2, N-S1, N-S2, INS-1) require the schema columns to exist.

---

### Batch C: spec_router.py handler fixes (PR4)

**Row IDs (4 bug rows):**
- Identities (v2): ID-4, ID-5
- Couplings: CP-1
- Item History: IH-1

**Why together:** All are in `api/spec_router.py` — the v2 API router. Independent endpoints.

**Files touched:** `api/spec_router.py`

**Schema changes:** None (depends on Batch A for couplings table).

**Handler/query changes:**
- ID-4: Rewrite `SELECT FROM identities` to `SELECT FROM client_identities` with correct columns.
- ID-5: Rewrite `UPDATE identities` to `UPDATE client_identities` with correct columns.
- CP-1: Replace `SELECT ... FROM entity_links` with call to `CouplingService.get_couplings()` or direct query on `couplings` table.
- IH-1: Rewrite evidence query from `SELECT artifact_id, excerpt_text, context_json, item_type FROM item_history` to `SELECT` from `artifacts` + `entity_links` join.

**API contract impact:** Fix-data v2 identity_conflicts changes shape (same as Batch B for v1). Evidence response shape changes — **BLOCKED by RU-8** for frontend contract. Couplings response now returns real data from couplings table.

**Regression risk:** Medium. Evidence endpoint rewrite (IH-1) is the most complex — changing the source table entirely. CP-1 is a table swap. ID-4/ID-5 mirror Batch B's ID-1..3.

**Can ship independently:** YES, after Batch A (needs couplings table). IH-1 frontend contract portion blocked by RU-8.

---

### Batch D: entity_links service layer (PR-entity-links)

**Row IDs (9 bug rows):**
- EL-1, EL-2, EL-3, EL-4, EL-7, EL-8, EL-9, EL-10, EL-11

**Why together:** All are in `lib/v4/entity_link_service.py`, `lib/entity_link_confirmer.py`, or `scripts/validate_data_foundation.py`. All caused by the same root issue: schema.py doesn't match the migration schema. Once PR1 (or PR1b) syncs entity_links in schema.py, all 9 bugs are resolved without any code changes to these files — the columns will exist.

**Files touched:** None (resolved by Batch A's schema sync). Verification-only batch.

**Schema changes:** None in this batch (dependency on Batch A / PR1b).

**Handler/query changes:** None. EL-1..4 and EL-7..11 all reference columns that the migration defines. Once schema.py matches, converge() creates them.

**API contract impact:** V4 entity link operations become functional (create, update confidence, confirm, reject, batch confirm, query).

**Regression risk:** Low. No code changes — purely a schema-unblock. Risk: if converge() column addition order matters (it doesn't — ALTER TABLE ADD COLUMN is independent).

**Can ship independently:** NO. Entirely dependent on Batch A's entity_links sync (PR1b), which is **BLOCKED by RU-1**.

**Note:** EL-5 (spec_router.py:2286) is in Batch C. EL-6 (server.py:5179) is in Batch B. The remaining 9 are this batch.

---

### Batch E: action handler fixes (PR-actions)

**Row IDs (5 bug rows):**
- A-I1, A-I2, A-I3, A-U1, A-S1

**Why together:** All are in `lib/` action-layer files. A-I1 and A-I2 are copy-paste clones (same `_log_action()` pattern). A-I3, A-U1, A-S1 are in `action_framework.py`. Schema decision D7 says fix code, not schema.

**Files touched:** `lib/executor/handlers/notification.py`, `lib/executor/handlers/delegation.py`, `lib/actions/action_framework.py`

**Schema changes:** None. D7 explicitly says do not add phantom columns to actions.

**Handler/query changes:**
- A-I1 (notification.py:142): Rewrite `_log_action()` INSERT. Replace `domain`→`type`, `action_type`→(remove), `target_id`→`target_system`, `data`→`payload`. Add `type` and `payload` (both NOT NULL).
- A-I2 (delegation.py:267): Same fix as A-I1 (copy-paste clone).
- A-I3 (action_framework.py:464): Rewrite `_store_proposal()` INSERT. Remove `target_entity`, `target_id`, `risk_level`, `source`, `confidence_score`. Keep `id`, `type`, `payload`, `requires_approval`, `status`, `approved_by`, `approved_at`, `created_at`.
- A-U1 (action_framework.py:282): Rewrite `reject_action()` UPDATE. Remove `rejected_by`, `rejection_reason`. Use `status` (exists), add rejection info to `result` or `error` field.
- A-S1 (action_framework.py:450): Rewrite `get_action_history()` WHERE clause. Remove `target_id`. Use `target_system` or remove the filter.

**API contract impact:** None directly — these are background/lib paths, not endpoint handlers. POST /api/propose (A-I3) will start actually persisting proposals.

**Regression risk:** Low-medium. A-I3 fix means proposals will now be stored (currently silently failing). This is a behavior change — proposals that were invisible will become visible. Verify the proposal query path handles the new data.

**Can ship independently:** YES. No schema dependency. No dependency on other batches.

---

### Batch F: test fixes (PR6)

**Row IDs (4 bug rows):**
- CL-T1, CL-T2, CL-T3, CL-T4

**Why together:** All in same file, same bug pattern (wrong column names in test INSERTs).

**Files touched:** `tests/test_sync_schedule.py`

**Schema changes:** None.

**Handler/query changes:** Replace `source`, `status`, `completed_at` with `cycle_number`/`phase`/`data`/`duration_ms`/`created_at` (actual cycle_logs columns). Tests must use real SQLite via `create_fixture_db()`, not Mock.

**API contract impact:** None.

**Regression risk:** Very low. Test-only changes. May reveal that the tests were testing nothing (if they pass with wrong columns via Mock, the tests are theater).

**Can ship independently:** YES. No dependency on any other batch.

---

## 3. Recommended Execution Order

### Step 1: Batch F (PR6) — test fixes
- **Dependency reason:** None. Independent.
- **Blast-radius:** Zero production impact. Test code only.
- **Testability:** Run `pytest tests/test_sync_schedule.py` — tests should pass with corrected columns on real SQLite.
- **Rollback:** Revert single test file.
- **Ship immediately.**

### Step 2: Batch E (PR-actions) — action handler fixes
- **Dependency reason:** None. Independent of schema changes.
- **Blast-radius:** Background action logging and proposal storage. No endpoint response shape changes. POST /api/propose starts working (was silently broken).
- **Testability:** Write fixture-DB tests for each of A-I1, A-I2, A-I3, A-U1, A-S1 with real SQLite. Verify INSERT succeeds with corrected columns.
- **Rollback:** Revert lib/ handler files. Proposals revert to silent failure.
- **Ship after Step 1 or in parallel.**

### Step 3: Resolve RU-1 (decision, not code)
- **Dependency reason:** Unblocks Batch A entity_links sync → unblocks Batch D entirely.
- **Blast-radius:** Decision only — no code change yet.
- **Action:** `SELECT count(*) FROM entity_links` on production/staging DB. If 0 → Option B (drop-recreate). If >0 → Option A (add-alongside).
- **This is a Molham decision point.**

### Step 4: Batch A (PR1 or PR1a+PR1b) — schema expansion
- **Dependency reason:** Unblocks Batches B, C, D (all depend on new columns/tables).
- **Blast-radius:** Schema-only. converge() runs on next startup. No handler behavior changes. Existing queries unaffected.
- **Testability:** Verify converge() adds all expected columns. `PRAGMA table_info(notifications)` should show dismissed, dismissed_at, task_id, recipient_id. Same for insights.severity, saved_filters table, couplings table, entity_links sync.
- **Rollback:** Revert schema.py, bump version back. converge() won't remove columns (additive only), but handlers revert to old behavior.
- **If RU-1 is not yet decided:** Ship PR1a (everything except entity_links sync). Ship PR1b after decision.

### Step 5: Batch B (PR3) — server.py handler fixes
- **Dependency reason:** Requires Batch A for migration-dependent rows (N-U1, N-U2, N-S1, N-S2, INS-1, EL-6).
- **Blast-radius:** Largest batch — 22 bug rows across 6 families in server.py. Endpoint response shapes change for governance history, fix-data identities, anomalies.
- **Testability:** Endpoint regression tests for every affected route. Fixture-DB tests for every INSERT/UPDATE. Contract-shape tests comparing JSON response to TS interface.
- **Rollback:** Revert server.py. Endpoints revert to crashing behavior (which is the current state, so rollback = no regression).
- **Blocked by RU-7** for notification frontend contract portion. Can ship handler fixes without the alias decision — just don't claim contract compliance until RU-7 is resolved.

### Step 6: Batch C (PR4) — spec_router.py handler fixes
- **Dependency reason:** Requires Batch A for couplings table (CP-1). IH-1 rewrite needs artifacts+entity_links join (entity_links must be synced).
- **Blast-radius:** 4 bug rows in v2 API. Evidence endpoint gets entirely new source tables. Couplings endpoint gets real data.
- **Testability:** Same pattern as Step 5. Evidence rewrite needs careful contract-shape testing. Blocked by RU-8 for frontend TS interface cleanup.
- **Rollback:** Revert spec_router.py.

### Step 7: Batch D (PR-entity-links) — verification only
- **Dependency reason:** Requires Batch A entity_links sync (PR1b, blocked by RU-1).
- **Blast-radius:** Zero code changes. Verification that 9 V4 service methods now work against synced schema.
- **Testability:** Integration tests calling each entity_link_service method against real SQLite with synced schema. Verify INSERT, UPDATE, SELECT all succeed.
- **Rollback:** N/A — no code changes to revert.

---

## 4. PR Plan

### PR1a: Schema expansion (excluding entity_links)

**Title:** `feat: add missing tables and columns for 6 schema decisions`

**Files:** `lib/schema.py`

**Schema changes:**
- TABLES["saved_filters"] = new table (D3)
- TABLES["notifications"]: add dismissed, dismissed_at, task_id, recipient_id (D1, D8)
- TABLES["insights"]: add severity (D2)
- TABLES["couplings"] = new table (D5)
- SCHEMA_VERSION bump

**Handler/query changes:** None.

**Frontend contract:** No immediate impact. Enables downstream handler fixes.

**Tests to add:**
- `test_schema_convergence.py`: verify converge() adds all new columns on existing DB
- `test_schema_tables.py`: verify saved_filters and couplings tables exist after converge()
- Verify PRAGMA table_info for each modified table

**Acceptance criteria:**
- [ ] `PRAGMA table_info(notifications)` includes dismissed, dismissed_at, task_id, recipient_id
- [ ] `PRAGMA table_info(insights)` includes severity
- [ ] `SELECT name FROM sqlite_master WHERE type='table'` includes saved_filters, couplings
- [ ] converge() succeeds on fresh DB and on DB with pre-existing tables
- [ ] SCHEMA_VERSION incremented
- Traces to: SF-1, INS-1, INS-2, N-U1, N-U2, N-S1, N-S2 (unblocked), N-I1..5 (partially unblocked)

---

### PR1b: entity_links schema sync — BLOCKED by RU-1

**Title:** `feat: sync entity_links schema with V4 migration`

**Files:** `lib/schema.py`

**Schema changes (Option A):**
- TABLES["entity_links"]: add link_id TEXT UNIQUE NOT NULL, confidence_reasons TEXT, status TEXT NOT NULL DEFAULT 'proposed', updated_at TEXT, confirmed_by TEXT, confirmed_at TEXT
- Keep id INTEGER PRIMARY KEY

**Schema changes (Option B):**
- Replace TABLES["entity_links"] with 12-column migration schema (link_id TEXT PRIMARY KEY)

**Handler/query changes:** None.

**Frontend contract:** Enables V4 entity link operations.

**Tests to add:**
- `test_entity_links_schema.py`: verify all 12 columns present after converge()
- If Option A: verify link_id UNIQUE constraint, verify backfill if rows exist
- If Option B: verify fresh table creation matches migration

**Acceptance criteria:**
- [ ] All columns from migration (link_id, confidence_reasons, status, updated_at, confirmed_by, confirmed_at) exist
- [ ] PK strategy matches Molham's decision (Option A or B)
- [ ] converge() handles existing data correctly
- Traces to: EL-1..11 (all unblocked)

---

### PR3: server.py handler fixes

**Title:** `fix: correct 22 handler bugs across notifications, decisions, governance, identities, entity_links`

**Files:** `api/server.py`

**Schema changes:** None.

**Handler/query changes:**
- Lines ~863, ~1083, ~1257: D-I1..3 — rewrite decisions INSERT dicts
- Lines ~1127, ~1303, ~1322, ~2245, ~2277: N-I1..5 — rewrite notification INSERT dicts
- Lines ~2202: D-U1 — remove processed_by from UPDATE
- Lines ~2314: G-1 — governance_history → governance_audit_log + column remap
- Lines ~3008, ~3039, ~3052, ~3056: N-S1, N-U1, N-S2, N-U2 — migration-dependent (work once PR1a lands)
- Lines ~3105: D-U2 — remove modifications from UPDATE
- Lines ~3183: G-2 — governance_history → governance_audit_log
- Lines ~4950, ~4988, ~5167: ID-1..3 — remove inline CREATE, rewrite to client_identities
- Line ~5179: EL-6 — fix WHERE clause + remove updated_at
- Lines ~5260: G-3 — governance_history → governance_audit_log
- Line ~2997: INS-1 — ORDER BY severity (migration-dependent)

**Frontend contract considerations:**
- Notification response shape gains task_id, recipient_id (matches G1 after PR1a)
- RU-7 decision affects whether title is aliased to message
- Governance history response changes column shape (G5)
- Fix-data identity_conflicts response changes (G4)

**Tests to add/update:**
- Fixture-DB INSERT tests for each of N-I1..5, D-I1..3, G-1, G-3
- Fixture-DB UPDATE tests for D-U1, D-U2, N-U1, N-U2
- Fixture-DB SELECT tests for N-S1, N-S2, G-2, INS-1
- Endpoint regression: POST /api/tasks/{id}, POST /api/tasks/{id}/delegate, POST /api/tasks/{id}/escalate
- Endpoint regression: POST /api/decisions/{id}, POST /api/approvals/{id}/modify
- Endpoint regression: GET /api/governance/history, GET /api/notifications, POST /api/notifications/dismiss*
- Endpoint regression: GET /api/control-room/fix-data, POST /api/control-room/fix-data/{type}/{id}/resolve
- Contract-shape test: GET /api/anomalies response includes severity field

**Acceptance criteria:**
- [ ] N-I1..5: notification INSERT succeeds with correct columns on real SQLite
- [ ] N-U1..2: dismiss UPDATE succeeds (after PR1a)
- [ ] N-S1..2: notification SELECT with dismissed filter succeeds (after PR1a)
- [ ] D-I1..3: decisions INSERT includes domain (NOT NULL), uses decision_type not type
- [ ] D-U1: UPDATE does not reference processed_by
- [ ] D-U2: UPDATE does not reference modifications
- [ ] G-1..3: all reference governance_audit_log, column names match schema
- [ ] ID-1: no inline CREATE TABLE in server.py
- [ ] ID-2..3: queries use client_identities with correct columns
- [ ] EL-6: WHERE uses link_id (not id), no updated_at reference (unless PR1b landed)
- [ ] INS-1: ORDER BY severity succeeds (after PR1a)
- [ ] No `governance_history` string anywhere in server.py after fix
- [ ] No `CREATE TABLE IF NOT EXISTS identities` in server.py after fix

---

### PR4: spec_router.py handler fixes

**Title:** `fix: correct 4 v2 endpoint bugs — identities, couplings, evidence`

**Files:** `api/spec_router.py`

**Schema changes:** None.

**Handler/query changes:**
- Line ~1507: CP-1 — replace entity_links query with couplings table query or CouplingService call
- Line ~1561: ID-4 — rewrite SELECT from identities to client_identities
- Line ~2281: ID-5 — rewrite UPDATE identities to client_identities
- Line ~2503: IH-1 — rewrite evidence query from item_history to artifacts+entity_links join

**Frontend contract considerations:**
- Evidence response shape changes entirely (RU-8 blocks TS interface cleanup)
- Couplings endpoint returns real data instead of crashing
- Fix-data v2 mirrors v1 identity fix

**Tests to add:**
- Fixture-DB tests for CP-1 (couplings query returns correct columns)
- Fixture-DB tests for ID-4, ID-5 (client_identities operations)
- Fixture-DB tests for IH-1 (artifacts+entity_links join)
- Endpoint regression: GET /api/v2/couplings, GET /api/v2/fix-data, POST /api/v2/fix-data/{type}/{id}/resolve, GET /api/v2/evidence/{type}/{id}
- Contract-shape test: evidence response matches updated Evidence interface (after RU-8)

**Acceptance criteria:**
- [ ] CP-1: GET /api/v2/couplings queries couplings table, not entity_links
- [ ] ID-4: SELECT uses client_identities with correct columns
- [ ] ID-5: UPDATE uses client_identities with correct columns
- [ ] IH-1: evidence query uses artifacts+entity_links join, returns valid data
- [ ] No `FROM identities` (bare) in spec_router.py after fix
- [ ] No `FROM entity_links` in get_couplings() after fix

---

### PR-actions: lib/ action handler fixes

**Title:** `fix: correct 5 action-layer bugs — _log_action, _store_proposal, reject_action, get_action_history`

**Files:** `lib/executor/handlers/notification.py`, `lib/executor/handlers/delegation.py`, `lib/actions/action_framework.py`

**Schema changes:** None. D7: fix code, not schema.

**Handler/query changes:**
- notification.py:142 (A-I1): rewrite _log_action() INSERT — use type, target_system, payload
- delegation.py:267 (A-I2): same fix (clone)
- action_framework.py:464 (A-I3): rewrite _store_proposal() INSERT — remove 5 phantom columns
- action_framework.py:282 (A-U1): rewrite reject_action() UPDATE — remove rejected_by, rejection_reason
- action_framework.py:450 (A-S1): fix get_action_history() WHERE — remove target_id

**Frontend contract:** None directly. POST /api/propose starts persisting proposals.

**Tests to add:**
- Fixture-DB INSERT test for _log_action() in notification.py
- Fixture-DB INSERT test for _log_action() in delegation.py
- Fixture-DB INSERT test for _store_proposal()
- Fixture-DB UPDATE test for reject_action()
- Fixture-DB SELECT test for get_action_history()
- Integration test: POST /api/propose → verify proposal stored in actions table

**Acceptance criteria:**
- [ ] A-I1: _log_action() INSERT succeeds on real SQLite with actions schema
- [ ] A-I2: same for delegation.py clone
- [ ] A-I3: _store_proposal() INSERT succeeds — only schema-valid columns
- [ ] A-U1: reject_action() UPDATE succeeds — no rejected_by/rejection_reason
- [ ] A-S1: get_action_history() SELECT succeeds — no WHERE target_id
- [ ] POST /api/propose stores a retrievable row in actions table

---

### PR6: test fixes

**Title:** `fix: correct 4 test_sync_schedule.py column mismatches`

**Files:** `tests/test_sync_schedule.py`

**Schema changes:** None.

**Handler/query changes:** Replace phantom columns (source, status, completed_at) with real cycle_logs columns (cycle_number, phase, data, duration_ms, created_at). Migrate from Mock to fixture DB.

**Tests:** The file IS the tests. Verify all 4 tests pass with real SQLite.

**Acceptance criteria:**
- [ ] CL-T1..4: all 4 tests pass using create_fixture_db() with real SQLite
- [ ] No Mock objects used for database operations in this file
- [ ] INSERT columns match PRAGMA table_info(cycle_logs)

---

### PR-entity-links: verification (no code changes)

**Title:** `test: verify 9 entity_link operations work after schema sync`

**Files:** Tests only (new test file or additions to existing).

**Schema changes:** None (depends on PR1b).

**Tests to add:**
- Integration tests for entity_link_service: create_link(), update_confidence(), confirm_link(), reject_link(), get_links_for_entity(), get_unconfirmed_links(), get_links_by_method()
- Integration test for entity_link_confirmer: batch_confirm()
- Integration test for validate_data_foundation: validate()

**Acceptance criteria:**
- [ ] EL-1: create_link() INSERT succeeds with all columns
- [ ] EL-2: update_confidence() UPDATE succeeds
- [ ] EL-3: confirm_link() UPDATE succeeds
- [ ] EL-4: reject_link() UPDATE succeeds
- [ ] EL-7: batch_confirm() UPDATE succeeds
- [ ] EL-8: get_links_for_entity() SELECT returns link_id, status
- [ ] EL-9: get_unconfirmed_links() SELECT returns confidence_reasons, status
- [ ] EL-10: get_links_by_method() SELECT returns confidence_reasons, status
- [ ] EL-11: validate() WHERE status='confirmed' succeeds
- **BLOCKED by RU-1 / PR1b**

---

## 5. Test Strategy

All tests derived from validated bug rows. Test type per row based on runtime classification.

### 5a. Migration tests (verify schema changes took effect)

| Test | Validates | Row IDs |
|---|---|---|
| notifications has dismissed, dismissed_at, task_id, recipient_id | D1, D8 columns exist | N-U1, N-U2, N-S1, N-S2, N-I1..5 |
| insights has severity | D2 column exists | INS-1 |
| saved_filters table exists | D3 table created | SF-1 |
| couplings table exists | D5 table created | CP-1 |
| entity_links has all 12 migration columns | D4 sync complete | EL-1..11 |
| converge() on fresh DB creates all tables | Full schema | All |
| converge() on existing DB adds missing columns | ALTER TABLE path | All |

### 5b. Endpoint regression tests (verify handler fixes)

| Endpoint | Method | Test | Row IDs |
|---|---|---|---|
| /api/tasks/{id} | PUT | Returns 200 when governance blocks auto-exec | D-I1 |
| /api/tasks/{id}/delegate | POST | Returns 200, notification created, decision created | D-I2, N-I1 |
| /api/tasks/{id}/escalate | POST | Returns 200, both notifications created, decision created | D-I3, N-I2, N-I3 |
| /api/decisions/{id} | POST | Approval succeeds, audit log written to governance_audit_log | D-U1, G-1, N-I4, N-I5 |
| /api/approvals/{id}/modify | POST | Modify succeeds without modifications column | D-U2 |
| /api/notifications | GET | Returns notifications with dismissed filter | N-S1 |
| /api/notifications/{id}/dismiss | POST | Dismiss succeeds | N-U1 |
| /api/notifications/dismiss-all | POST | Fetch + update succeeds | N-U2, N-S2 |
| /api/governance/history | GET | Returns rows from governance_audit_log | G-2 |
| /api/anomalies | GET | Returns ordered by severity | INS-1 |
| /api/control-room | GET | .get("severity") returns value or None without crash | INS-2 |
| /api/control-room/fix-data | GET | No inline CREATE, queries client_identities | ID-1, ID-2 |
| /api/control-room/fix-data/{type}/{id}/resolve | POST | Updates client_identities, writes to governance_audit_log | ID-3, G-3, EL-6 |
| /api/filters | GET | Returns saved filters (after table creation) | SF-1 |
| /api/v2/couplings | GET | Queries couplings table | CP-1 |
| /api/v2/fix-data | GET | Queries client_identities | ID-4 |
| /api/v2/fix-data/{type}/{id}/resolve | POST | Updates client_identities | ID-5 |
| /api/v2/evidence/{type}/{id} | GET | Queries artifacts+entity_links | IH-1 |

### 5c. Runtime failure-path tests (verify crash/degraded behavior is fixed)

| Scenario | Expected before fix | Expected after fix | Row IDs |
|---|---|---|---|
| delegate_task() with valid task | HTTP 500 (re-raised OperationalError) | HTTP 200 + notification + decision | N-I1, D-I2 |
| escalate_task() with valid task | HTTP 500 | HTTP 200 + 2 notifications + decision | N-I2, N-I3, D-I3 |
| api_decision() approval | HTTP 500 (re-raised) | HTTP 200 + audit log | D-U1, G-1 |
| api_decision() delegation side-effect | Notification silently lost | Notification persisted | N-I4 |
| api_decision() escalation side-effect | Notification silently lost | Notification persisted | N-I5 |
| _store_proposal() via POST /api/propose | Silent failure (caught exception) | Proposal stored in actions table | A-I3 |
| _log_action() in notification handler | Silent failure | Action logged | A-I1 |
| _log_action() in delegation handler | Silent failure | Action logged | A-I2 |

### 5d. Contract-shape tests (verify API response matches TS interface)

| Interface | Endpoint | Fields to verify | Row IDs | Blocked? |
|---|---|---|---|---|
| Notification (api.ts:1197) | GET /api/notifications | id, type, message OR title, task_id, dismissed, dismissed_at, created_at | N-I1..5, N-S1 | RU-7 (message vs title) |
| GovernanceResponse (api.ts:1371) | GET /api/governance/overview | domains, emergency_brake, summary | G-2 | No |
| FixData (types/api.ts:240) | GET /api/control-room/fix-data | identity_conflicts, ambiguous_links, missing_mappings, total | ID-1..3 | No |
| Evidence (types/api.ts:259) | GET /api/v2/evidence/{type}/{id} | artifact_id, created_at, source, artifact_type, occurred_at | IH-1 | RU-8 (excerpt_text, context_json removal) |

### 5e. Background/async path tests

| Path | Test | Row IDs |
|---|---|---|
| NotificationHandler._log_action() | INSERT into actions with correct columns | A-I1 |
| DelegationHandler._log_action() | INSERT into actions with correct columns | A-I2 |
| entity_link_confirmer.batch_confirm() | UPDATE entity_links with status, confirmed_by, confirmed_at | EL-7 |

### 5f. Call-order / bootstrap tests

| Scenario | Test | Row IDs |
|---|---|---|
| Fresh DB, call GET /api/v2/fix-data before v1 | No crash (identities shadow table eliminated) | ID-4 |
| Fresh DB, call POST /api/v2/fix-data/resolve before v1 | No crash | ID-5 |
| validate_data_foundation.py on fresh DB | WHERE status='confirmed' succeeds (after schema sync) | EL-11 |

---

## 6. Fastest Path to De-risk Production

The highest-risk production failures are endpoints that crash with HTTP 500 on normal user actions. Ranked by user-facing impact:

### Tier 1: Ship immediately (no schema dependency)

**PR-actions (Batch E): 5 rows — A-I1, A-I2, A-I3, A-U1, A-S1**
- POST /api/propose is silently broken for all users. Every proposal is lost.
- Background action logging is silently broken — no audit trail for notification/delegation actions.
- Zero dependency on schema changes. Ship today.

**PR6 (Batch F): 4 rows — CL-T1..4**
- Test fixes. No production impact but eliminates false confidence in test suite.
- Ship in parallel with PR-actions.

### Tier 2: Ship after PR1a (schema only, no RU-1 dependency)

**PR1a (Batch A minus entity_links): unblocks 7 rows directly**
- Enables dismissed/dismissed_at columns → GET /api/notifications stops crashing (N-S1).
- Enables severity column → GET /api/anomalies stops crashing (INS-1).
- Creates saved_filters table → GET /api/filters stops crashing (SF-1).

### Tier 3: Ship after PR1a (handler fixes)

**PR3 partial (D-I1..3, D-U1, D-U2, G-1..3, ID-1..3): 14 rows**
- These server.py fixes have no schema dependency (they fix phantom columns, wrong table names, wrong column names).
- PUT /api/tasks/{id}, POST /api/tasks/{id}/delegate, POST /api/tasks/{id}/escalate stop crashing.
- POST /api/decisions/{id} approval stops crashing.
- GET /api/governance/history stops crashing.
- Fix-data stops creating shadow tables.
- Can ship the non-migration-dependent portion of PR3 as PR3a.

**Combined Tier 1-3 impact: 30 of 47 bug rows resolved without any blocker decision.**

### Tier 4: After RU-1 decision

**PR1b + PR-entity-links (Batch D): 11 rows — EL-1..11**
- All V4 entity link operations become functional.
- Currently all 11 crash — but V4 features may not be user-facing yet.

---

## 7. Deferred / Optional Cleanup

These improvements are NOT required to resolve the 47 validated bug rows. They appear in the audit as residual uncertainty, architectural debt, or quality improvements.

| Item | Source | Why deferred | When to do |
|---|---|---|---|
| RU-2: ~25 files with inline CREATE TABLE outside schema.py | closure-audit.md §H | Architectural debt. Does not cause any of the 47 bugs. converge() doesn't manage these tables but they work independently. | After all PRs merged. Registration sweep as separate task. |
| RU-4: Test suite Mock audit | closure-audit.md §H | CL-T1..4 hint at broader test-schema mismatch. Other tests may use Mock incorrectly. | After PR6 lands. Sweep tests/ for INSERT/UPDATE with column names and compare against schema.py. |
| RU-5: Communications table exhaustive sweep | closure-audit.md §H | ~50 columns, only email WHERE checked. Other SELECTs may have phantom conditions. | Low priority. Most code uses store.get() or SELECT *. |
| G-C2: Redundant inline DDL in audit_log.py:63 | closure-audit.md §4b | `CREATE TABLE IF NOT EXISTS governance_audit_log` duplicates schema.py. Not a bug — just redundant. | Cleanup when touching audit_log.py. |
| RU-3 fragility: entity_link_service.py hardcoded DB_PATH | closure-audit.md §H | Resolves to same DB today by coincidence. If default changes, services diverge. | After entity_links PRs merged. Centralize DB path config. |
| 35 unvalidated clean rows | closure-audit.md §L | 10 of 45 clean rows spot-checked. Remaining 35 carry schema-match confidence but not trace-level proof. | Optional hostile validation pass if Molham wants full coverage. |
