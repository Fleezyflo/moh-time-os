# Endpoint Fix Audit — Verified and Complete

**Verified**: 2026-03-11 — Every finding below was read line-by-line against source code and cross-referenced against `lib/schema.py` (the source of truth) and `docs/schema.sql` (documentation snapshot).

---

## Scope

Every instance where:
1. A handler queries columns that don't exist on the actual table
2. A handler queries a table that doesn't exist or uses the wrong table name
3. Inline `CREATE TABLE IF NOT EXISTS` creates tables with schemas conflicting with `lib/schema.py`
4. A handler calls engine methods that don't exist

The 23 smoke-test failures (GET endpoints) were the starting point. Extended scan found 13 additional bugs in POST/PUT/DELETE handlers and conditional GET paths.

---

## Category A: Column Mismatches (18 total)

### A1–A4: paginated_router.py

| # | Endpoint | Line | Wrong | Correct | Table | Status |
|---|---|---|---|---|---|---|
| A1 | `GET /api/v2/paginated/tasks` | 88 | `due_at` | `due_date` | tasks | FIXED in working tree |
| A2 | `GET /api/v2/paginated/signals` | 96 | `id, description, resolved` | `signal_id, signal_type, entity_ref_type, entity_ref_id, value, status, detected_at, resolved_at, created_at` | signals | FIXED in working tree |
| A3 | `GET /api/v2/paginated/clients` | 107 | `c.status` | `c.tier` | clients | FIXED in working tree |
| A4 | `GET /api/v2/paginated/invoices` | 134 | `invoice_number` | `external_id` | invoices | NOT FIXED |

**Note**: A4 — `due_at` in the invoices query is correct (invoices table has `due_at`). Only `invoice_number` → `external_id`.

### A5–A7: server.py GET endpoints

| # | Endpoint | Line | Wrong | Correct | Table |
|---|---|---|---|---|---|
| A5 | `GET /api/anomalies` | 2997 | `ORDER BY severity DESC` | `severity` doesn't exist on insights | insights |
| A6 | `GET /api/notifications` | 3008 | `dismissed = 0` | `dismissed` doesn't exist on notifications | notifications |
| A7 | `GET /api/emails` | 2942–2945 | `type = 'email'`, `actionable = 1` | `source` not `type`; `requires_response` not `actionable` | communications |

**Schema.py proof:**
- `insights` (line 703): columns are `id, type, domain, title, description, confidence, data, actionable, action_taken, created_at, expires_at` — NO `severity`, NO `category`
- `notifications` (line 740): columns are `id, type, priority, title, body, action_url, action_data, channels, sent_at, read_at, acted_on_at, created_at` — NO `dismissed`, NO `dismissed_at`
- `communications` (schema.sql:175): has `source` (not `type`), `requires_response` (not `actionable`)

### A8–A9: spec_router.py / query_engine.py

| # | Endpoint | Line | Wrong | Correct | Table |
|---|---|---|---|---|---|
| A8 | `GET /api/v2/clients/{id}/team` | spec_router.py:728 | `tm.role` (doesn't exist), `tm.client_id` (doesn't exist), `t.completed` (should be `t.status`) | team_members has: `id, name, email, asana_gid, default_lane` | team_members, tasks |
| A9 | `GET /api/v2/team/{id}/calendar-detail` | query_engine.py:1131 | `e.assignee_id` | events table has no `assignee_id` — need to join through `calendar_attendees.email` via `people.id` | events |

**Schema.py proof:**
- `team_members` (schema.sql:266): `id, name, email, asana_gid, default_lane, created_at, updated_at` — NO `role`, NO `client_id`
- `events` (schema.sql:146): NO `assignee_id` column. Tasks has `assignee_id` but events does not.

### A10–A18: Extended scan — POST endpoints and conditional paths

| # | Endpoint | Line | Wrong | Correct | Table | Why not caught by smoke test |
|---|---|---|---|---|---|---|
| A10 | `POST /api/emails/{id}/mark-actionable` | server.py:2966 | `actionable` | `requires_response` | communications | POST not tested |
| A11 | `POST /api/notifications/{id}/dismiss` | server.py:3042 | `dismissed`, `dismissed_at` | neither exists | notifications | POST not tested |
| A12 | `POST /api/notifications/dismiss-all` | server.py:3052–3056 | `dismissed` (in SELECT + UPDATE) | doesn't exist | notifications | POST not tested |
| A13 | `GET /api/insights?category=X` | server.py:2978 | `category = ?` | insights has `type` and `domain`, not `category` | insights | Only fails with `?category=` param |
| A14 | `GET /api/control-room/clients` | server.py:5303 | `financial_ar_total`, `financial_ar_aging_bucket` | `financial_ar_outstanding`, `financial_ar_aging` | clients | May not fail if no rows match WHERE |
| A15 | `POST /api/v2/fix-data/{type}/{id}/resolve` (link) | spec_router.py:2286 | `status`, `confirmed_by`, `confirmed_at`, `link_id` (4 wrong columns) | none exist on entity_links | entity_links | POST not tested |
| A16 | `POST /api/v2/fix-data/{type}/{id}/resolve` (identity) | spec_router.py:2281 | queries `identities` | table is `client_identities`; no `confidence_score` | client_identities | POST not tested |
| A17 | `POST /api/control-room/fix-data/resolve` (identity) | server.py:5233 | `canonical_id`, `confidence_score`, `updated_at` on `identities` | table is `client_identities`; none of these columns exist | client_identities | POST not tested |
| A18 | `POST /api/control-room/fix-data/resolve` (link) | server.py:5247 | `entity_links.updated_at` | doesn't exist (only has `created_at`) | entity_links | POST not tested |

---

## Category B: Wrong Table Names (8 total)

| # | Endpoint | Line | Wrong table | Correct table | Column issues too? |
|---|---|---|---|---|---|
| B1 | `GET /api/governance/history` | server.py:3183 | `governance_history` | `governance_audit_log` | Columns match enough for SELECT * |
| B2 | `GET /api/control-room/evidence/{type}/{id}` | server.py:5359 | `excerpts` | doesn't exist — no excerpts table anywhere | YES — also uses `entity_links.entity_id` and `entity_links.linked_id` (neither exists) |
| B3 | `GET /api/v2/evidence/{type}/{id}` | spec_router.py:2505 | `item_history` | doesn't exist in schema.py | Different approach — uses `item_history.item_type` and `item_history.item_id` |
| B4 | `GET /api/v2/fix-data` | spec_router.py:1560 | `identities` | `client_identities` (completely different schema) | YES — queries `display_name`, `source`, `confidence_score` (none exist on client_identities) |
| B5 | `GET /api/filters` | server.py:2738 | `saved_filters` | not in schema.py — needs to be added | N/A — table doesn't exist at all |
| B6 | `POST /api/control-room/fix-data/resolve` | server.py:5260 | `governance_history` (INSERT) | `governance_audit_log` | YES — INSERT uses `decision_id, type, target_id, processed_by` but audit_log has `timestamp, actor, subject_identifier, details` |
| B7 | `POST /api/v2/fix-data/{type}/{id}/resolve` | spec_router.py:2281 | `identities` (UPDATE) | `client_identities` | YES — `confidence_score` doesn't exist |
| B8 | `POST /api/decisions/{id}` | server.py:2315 | `governance_history` (INSERT) | `governance_audit_log` | YES — same wrong columns as B6: `decision_id, action, type, target_id, processed_by, side_effects` vs actual `timestamp, actor, subject_identifier, details` |

---

## Category C: Wrong Table Structure (3 total)

All three are the same root cause: the `/api/v2/couplings` endpoint and fix-data endpoints query `entity_links` using column names from the `couplings` table.

| # | Endpoint | Line | Queries these columns from entity_links | Actual entity_links columns (schema.py:1526) |
|---|---|---|---|---|
| C1 | `GET /api/v2/couplings` | spec_router.py:1507 | `coupling_id, anchor_ref_type, anchor_ref_id, entity_refs, coupling_type, strength, why, confidence` | `id, from_artifact_id, to_entity_type, to_entity_id, confidence, method, created_at` — only `confidence` overlaps |
| C2 | `GET /api/v2/fix-data` | spec_router.py:1569 | `link_id` | `id` (INTEGER PK, not `link_id` TEXT) |
| C3 | `GET /api/control-room/fix-data` | server.py:4996 | `link_id` | `id` |

**Root cause**: `/api/control-room/couplings` (server.py:5279) correctly uses `CouplingService`. The v2 endpoint does NOT — it raw-queries `entity_links` with `couplings` column names. Fix: wire v2 to `CouplingService` too.

---

## Category D: Inline CREATE TABLE Conflicts (6 total)

| # | File:Line | Table | What inline creates | What schema.py defines | Severity |
|---|---|---|---|---|---|
| D1 | server.py:4963–4970 | `identities` | `(id, display_name, source, canonical_id, confidence_score)` | Not in schema.py. `client_identities` exists with `(id, client_id, identity_type, identity_value, created_at)` | HIGH — creates ghost table that doesn't match real data model |
| D2 | server.py:4972–4983 | `entity_links` | `(link_id TEXT PK, from_artifact_type, from_artifact_id, to_entity_type, to_entity_id, method, confidence, status)` | `(id INTEGER PK, from_artifact_id, to_entity_type, to_entity_id, confidence, method, created_at)` — PK type mismatch, extra columns, missing `created_at` | HIGH — if inline runs first, `id` column gets wrong type |
| D3 | key_manager.py:78 | `api_keys` | Has NOT NULL + UNIQUE + CHECK constraints on 4 columns | Schema.py:1234 declares same columns but nullable/unconstrained | MEDIUM — constraint mismatch, `converge()` would lose constraints |
| D4 | audit_log.py:63 | `governance_audit_log` | NOT NULL on `timestamp, action, actor, subject_identifier, details, created_at` (6 columns) | Schema.py:1221 declares all nullable | MEDIUM — constraint mismatch |
| D5 | coupling_service.py:43 | `couplings` | Full schema with CHECK constraints | Not in schema.py at all | HIGH — table only exists because inline creates it |
| D6 | notifications.py:84 | `notification_queue` | `(id INTEGER PK AUTOINCREMENT, notification_id, type, priority, title, body, entity_type, entity_id, data_json, created_at)` | Not in schema.py at all | MEDIUM — separate queue table, inline creation is fragile |

---

## Category E: Missing Engine Methods (2 total)

| # | Endpoint | Line | Calls | Actually exists? | Fix |
|---|---|---|---|---|---|
| E1 | `GET /api/governance` | server.py:3125 | `governance.get_all_domains()` | NO — governance_engine.py has `get_mode()`, `set_mode()`, `get_status()`, `get_summary()` but NOT `get_all_domains()` | Use `governance.get_status()` which returns domain info |
| E2 | `GET /api/governance` | server.py:3126 | `governance.is_emergency_brake_active()` | NO — has `emergency_brake()`, `release_brake()` but NOT `is_emergency_brake_active()` | Use `governance.get_status()` which has brake state |

---

## Category F: Schema Registration Gaps

| # | Table | In schema.py? | Created by | Risk |
|---|---|---|---|---|
| F1 | `saved_filters` | NO | Nothing — queried but never created | HIGH — always fails |
| F2 | `couplings` | NO | `coupling_service.py:43` inline CREATE | MEDIUM — fragile |
| F3 | `notification_queue` | NO | `notifications.py:84` inline CREATE | MEDIUM — fragile |

`notification_mutes` and `notification_analytics` ARE in schema.py — confirmed.

**52+ additional tables** exist only via inline CREATE (intelligence layer tables, V4 service tables, collector tables). These are not handler bugs but are architectural debt.

---

## Category G: Notification INSERT Column Bugs (1 pattern, 5 locations)

**Pattern**: All notification INSERT calls include `recipient_id` in the data dict, but `notifications` table has no `recipient_id` column. Every notification INSERT crashes with `sqlite3.OperationalError: table notifications has no column named recipient_id`.

| # | Endpoint | Line | Insert includes | Actual columns |
|---|---|---|---|---|
| G1a | `POST /api/tasks/{id}/delegate` | server.py:1132 | `recipient_id, task_id, dismissed` | none of these exist (PR1 adds `task_id`, `dismissed`) |
| G1b | `POST /api/tasks/{id}/escalate` | server.py:1308 | `recipient_id, task_id, dismissed` | same |
| G1c | `POST /api/tasks/{id}/escalate` (original assignee notif) | server.py:1327 | `recipient_id, task_id, dismissed` | same |
| G1d | `POST /api/decisions/{id}` (delegation side-effect) | server.py:2250 | `recipient_id, task_id, dismissed` | same |
| G1e | `POST /api/decisions/{id}` (escalation side-effect) | server.py:2282 | `recipient_id, task_id, dismissed` | same |

**Impact**: Every delegation and escalation action fails to create a notification. The INSERT crashes, but each is wrapped in try/except so the parent action succeeds — the notification just silently doesn't get created. Users never get notified of delegations or escalations.

**Fix**: Add `recipient_id TEXT` to notifications table in PR1. This column stores who should receive the notification (a person/team ID), which is semantically different from `target_id` (the entity the notification references, e.g. a task).

---

## Impact Summary (VERIFIED)

| Category | Count | Critical | Details |
|---|---|---|---|
| Column mismatches | 18 (A1–A18) | A1–A3 already fixed, A4–A18 remain | 3 fixed in working tree, 15 still broken |
| Wrong table names | 8 (B1–B8) | All still broken | 5 also have column issues |
| Wrong table structure | 3 (C1–C3) | All still broken | Root: v2 couplings queries wrong table |
| Inline CREATE conflicts | 6 (D1–D6) | D1–D2 most critical | Ghost tables with wrong schemas |
| Missing engine methods | 2 (E1–E2) | Both still broken | Governance endpoint dead |
| Schema registration gaps | 3 (F1–F3) | F1 critical | saved_filters never created |
| Notification INSERT bugs | 1 pattern, 5 locations (G1a–G1e) | All crash at runtime | Every delegation/escalation notification fails silently |

**Total: 41 handler bugs (15 column mismatches remaining + 8 wrong tables + 3 wrong structure + 6 inline conflicts + 2 missing methods + 3 registration gaps + 5 notification INSERT crashes). Note: G1a-G1e are counted as 5 locations but 1 root cause (missing `recipient_id` column).**

---

## Implementation Plan (Revised — Best Practice)

### Design Decisions

Before listing PRs, three architectural questions that the original plan got wrong:

**1. Notifications: dismissed vs read**
Investigation found: `read_at` exists in schema but NO code ever writes it. The UI tracks only `dismissed`. The stats endpoint counts `read_at IS NULL` (always true — dead code). The product today treats "dismissed" as the only state transition. The V29 `inbox_items` model has both `read_at` and `dismissed_at` as separate states. **Decision**: Add `dismissed INTEGER DEFAULT 0` and `dismissed_at TEXT` to notifications schema. Keep `read_at` for future use. Handler code for A6/A11/A12 is correct once the schema has the columns — no handler changes needed for dismiss logic. Fix the stats endpoint to also count dismissed.

**2. Identity resolution: wire to IdentityService, not client_identities**
Investigation found TWO parallel identity systems:
- `client_identities` — simple domain→client lookup table (production, in schema.py)
- `identity_profiles/claims/operations` — full resolution system with confidence, merge/split, audit trail (V4 migration, `lib/v4/identity_service.py`)
- `identities` (server.py inline) — ephemeral ghost table that duplicates neither

The fix-data endpoints want identity RESOLUTION (confidence scores, canonical mapping, conflict detection). That's `IdentityService`, not `client_identities`. **Decision**: Wire fix-data identity handlers to `IdentityService.resolve_identity()` and `IdentityService.merge_profiles()`. Register `identity_profiles`, `identity_claims`, `identity_operations` in schema.py. Delete inline `identities` CREATE.

**3. Evidence endpoints: use artifact_excerpts + artifacts, not excerpts/item_history**
Investigation found: `artifacts` has `artifact_id, type, source, occurred_at, created_at` (schema.py:1516). `artifact_excerpts` has `excerpt_id, artifact_id, excerpt_text, anchor_type, anchor_start, anchor_end, excerpt_hash, redaction_status, created_at` (migration only — NOT in schema.py). `entity_links` connects artifacts to entities. `excerpts` and `item_history` don't exist. **Decision**: Register `artifact_excerpts` in schema.py. Evidence query only needs existing artifacts columns (`source`, `type`, `occurred_at`), so additional migration columns (`source_id`, `actor_person_id`, `payload_ref`, `content_hash`, `visibility_tags`) are deferred to a separate V4 schema PR. Evidence query: `artifact_excerpts JOIN artifacts ON artifact_id JOIN entity_links ON from_artifact_id`.

**4. entity_links schema gap**
Investigation found: schema.py has 7 columns (`id INTEGER PK, from_artifact_id, to_entity_type, to_entity_id, confidence, method, created_at`). The V4 migration has 11 columns (using `link_id TEXT PK` plus `confidence_reasons, status, confirmed_by, confirmed_at, updated_at`). The handlers need `status`, `confirmed_by`, `confirmed_at` for fix-data resolve. **Decision**: Add `status TEXT DEFAULT 'proposed'`, `confirmed_by TEXT`, `confirmed_at TEXT`, `updated_at TEXT`, `confidence_reasons TEXT` to entity_links in schema.py. Keep `id INTEGER PK` (schema.py wins over migration's `link_id TEXT PK`). Fix all handler references from `link_id` to `id`.

---

### PR 1: Schema Evolution (lib/schema.py)
**Purpose**: Register missing tables and add missing columns so the declarative schema matches what the system actually needs.

**New tables to add:**
1. `saved_filters` — `(id TEXT PK, name TEXT NOT NULL, filters TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')))`
2. `couplings` — copy from `coupling_service.py:44-55`: `(coupling_id TEXT PK, anchor_ref_type TEXT NOT NULL, anchor_ref_id TEXT NOT NULL, entity_refs TEXT NOT NULL, coupling_type TEXT NOT NULL, strength REAL NOT NULL, why TEXT NOT NULL, investigation_path TEXT NOT NULL, confidence REAL NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')))`
3. `notification_queue` — copy from `notifications.py:84-95`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, notification_id TEXT NOT NULL, type TEXT NOT NULL, priority TEXT NOT NULL, title TEXT NOT NULL, body TEXT, entity_type TEXT, entity_id TEXT, data_json TEXT, created_at TEXT NOT NULL, delivered_at TEXT)` + `"unique": [("notification_id",)]`
4. `artifact_excerpts` — copy from migration:78-88: `(excerpt_id TEXT PK, artifact_id TEXT NOT NULL, anchor_type TEXT NOT NULL, anchor_start TEXT NOT NULL, anchor_end TEXT NOT NULL, excerpt_text TEXT NOT NULL, excerpt_hash TEXT NOT NULL, redaction_status TEXT DEFAULT 'none', created_at TEXT NOT NULL DEFAULT (datetime('now')))`
5. `identity_profiles` — copy from migration:122-132: `(profile_id TEXT PK, profile_type TEXT NOT NULL, canonical_name TEXT NOT NULL, canonical_email TEXT, canonical_domain TEXT, status TEXT NOT NULL DEFAULT 'active', metadata TEXT DEFAULT '{}', created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')))`
6. `identity_claims` — copy from migration:142-154: `(claim_id TEXT PK, profile_id TEXT NOT NULL, claim_type TEXT NOT NULL, claim_value TEXT NOT NULL, claim_value_normalized TEXT NOT NULL, source TEXT NOT NULL, source_artifact_id TEXT, confidence REAL NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL DEFAULT (datetime('now')))`
7. `identity_operations` — copy from migration:165-174: `(op_id TEXT PK, op_type TEXT NOT NULL, from_profile_ids TEXT NOT NULL, to_profile_ids TEXT NOT NULL, reason TEXT NOT NULL, evidence_artifact_ids TEXT DEFAULT '[]', actor TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')))`
~~8. `fix_data_queue`~~ — DEFERRED. Used by V4 services (entity_link_service, collector_hooks, anomaly_detector) and CLI, but zero API handlers reference it. None of the 36 fixes need it. Add in a separate "V4 schema registration" PR to avoid scope bloat.

**Columns to add to existing tables:**
1. ~~`insights`: add `severity TEXT`~~ — REMOVED. Anomalies already store severity as `priority` (100=critical, 80=high, 50=medium, 20=low) via `anomaly.py:424`. The A5 handler fix uses `ORDER BY priority DESC` instead. No new column needed.
2. `notifications`: add `dismissed INTEGER DEFAULT 0`, `dismissed_at TEXT`, `task_id TEXT`, `target_id TEXT`, `recipient_id TEXT`
   - `task_id` and `target_id` complete the UI contract (`api.ts:1197`). Currently notification creation (`autonomous_loop.py:1547`) stores related entity data in `action_data` JSON but not in dedicated columns. Adding the columns now means they're NULL until the creation code is updated — but the columns exist honestly in the schema, not as NULL aliases hiding a gap. Follow-up task: update `_create_notification()` to populate `task_id`/`target_id` from the `data` dict when applicable.
   - `recipient_id` is used by ALL 5 notification INSERT locations (delegation/escalation handlers at server.py:1132, 1308, 1327, 2250, 2282). Without this column, every notification INSERT crashes with `OperationalError`. Semantically different from `target_id`: `recipient_id` = who receives the notification (person/team), `target_id` = what the notification references (task/entity).
3. `entity_links`: add `status TEXT DEFAULT 'proposed'`, `confirmed_by TEXT`, `confirmed_at TEXT`, `updated_at TEXT`, `confidence_reasons TEXT`
4. `communications`: add `channel TEXT DEFAULT 'email'`
   - UI `EmailItem.type` (`api.ts:1288`) expects the communication *channel* ("email", "chat", "call"). The `source` column stores the *provider* ("gmail", "outlook"). These are different concepts. `source AS type` would return "gmail" where UI displays the channel — wrong data. Adding a `channel` column with default "email" is accurate (only gmail collector exists today) and extensible (future non-email collectors set their own channel value).
~~5. `artifacts`: add `source_id TEXT`, `actor_person_id TEXT`, `payload_ref TEXT`, `content_hash TEXT`, `visibility_tags TEXT DEFAULT '[]'`~~ — DEFERRED. The evidence endpoint query uses only existing artifact columns (`source`, `type`, `occurred_at`). None of the 5 new columns are referenced by any of the 36 handler fixes. Add in a separate "V4 schema registration" PR.

**Indexes to add to `INDEXES` list:**
1. `couplings`: `idx_couplings_anchor` on `(anchor_ref_type, anchor_ref_id)`, `idx_couplings_type` on `(coupling_type)`, `idx_couplings_strength` on `(strength DESC)`
2. `notification_queue`: `idx_notification_type` on `(type)`, `idx_notification_priority` on `(priority)`, `idx_notification_created` on `(created_at)`, `idx_notification_delivered` on `(delivered_at)`

**CHECK constraints to preserve in schema.py column defs:**
- `couplings.strength`: `REAL NOT NULL CHECK (strength >= 0 AND strength <= 1)`
- `couplings.confidence`: `REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1)`

Note: `schema_engine.make_alter_safe()` strips CHECK constraints for ALTER TABLE ADD COLUMN (so adding them won't break existing tables), but CREATE TABLE preserves them (so new databases get constraint enforcement).

**Bump** `SCHEMA_VERSION` to 19.

**PK rebuild risk (entity_links)**: `schema_engine.py` Phase 0 (lines 148-179) detects PK type mismatches and drops+recreates the table. If an existing database has `entity_links` with `link_id TEXT PRIMARY KEY` (from server.py's inline CREATE), registering `id INTEGER PRIMARY KEY` in schema.py triggers a DROP+RECREATE. This loses any entity_links rows created by the inline handler. Acceptable because: (a) that data was created with a wrong schema (wrong PK, wrong columns), (b) schema_engine-created entity_links data (correct schema) would have `id INTEGER PK` and Phase 0 won't touch it. Document this in the PR description as a known migration behavior.

**UI contract preservation**: All SQL alias changes MUST match the TypeScript interfaces in `FixDataCard.tsx:50-60` and `types/api.ts`. The identity conflict shape is `{id, display_name, source, confidence_score}`. The ambiguous link shape is `{id, entity_type, entity_id, linked_type, linked_id, confidence}`. Every handler rewrite must produce these exact field names via SQL AS aliases.

**Verification**: `python -c "from lib.schema import TABLES, SCHEMA_VERSION; print(SCHEMA_VERSION); [print(t) for t in TABLES]"` — confirm all new tables appear, version is 19.

---

### PR 2: Fix paginated_router.py (A4)
**Purpose**: Fix the last column mismatch. Commit A1–A3 fixes already in working tree.

Line 134: `invoice_number` → `external_id`

**Verification**: `ruff check api/paginated_router.py`

---

### PR 3: Fix server.py handlers
**Purpose**: Fix all server.py handler bugs.

**Findings addressed**: A5, A7, A10, A13, A14, A17, A18, B1, B2, B5, B6, B8, D1, D2, E1, E2, G1a–G1e + CouplingService path fix (server.py:5283) + email/notification SELECT alias fixes
**Findings fixed by PR1 schema change (handler change still needed)**: A6, A11, A12 (dismissed columns now exist, but notifications SELECT needs aliases — see UI Contract section)
**Findings fixed by PR1 schema change (no handler change needed)**: G1a–G1e (recipient_id column added — all 5 notification INSERTs will work once column exists)

**CouplingService DB path fix (pre-existing bug):**
- Line 5283: `CouplingService()` → `CouplingService(store.db_path)` — bare `CouplingService()` defaults to `<repo>/data/moh_time_os.db` while `store` uses `~/.moh_time_os/data/moh_time_os.db`. Different databases.

**Column fixes:**
1. **A5** (line 2997): `ORDER BY severity DESC` → `ORDER BY priority DESC, created_at DESC` (anomaly detector maps severity→priority via `anomaly.py:424`: critical=100, high=80, medium=50, low=20)
2. **A7** (lines 2942–2945): `type = 'email'` → `from_email IS NOT NULL`; `actionable = 1` → `requires_response = 1`. **ALSO** replace `SELECT *` with explicit column list + aliases to match UI contract (see UI Contract Compatibility section below):
   ```sql
   SELECT id, subject, from_email AS sender, to_emails AS recipient,
          body_text AS body, received_at, requires_response AS actionable,
          processed, channel AS type
   FROM communications
   WHERE from_email IS NOT NULL ...
   ```
   Note: `channel` column added in PR1 with `DEFAULT 'email'`. No `source AS type` — `source` is the provider ("gmail"), `channel` is the communication type ("email"). Different semantics.
3. **A10** (line 2966): `actionable` → `requires_response`
4. **A13** (line 2978): `category = ?` → `domain = ?`
5. **A14** (line 5303): `financial_ar_total` → `financial_ar_outstanding`; `financial_ar_aging_bucket` → `financial_ar_aging`
6. **A18** (line 5247): entity_links UPDATE — keep `updated_at = ?` (PR1 adds this column)

**Identity resolution rewrite (A17, D1):**
- Delete inline CREATE TABLE identities (lines 4963–4970)
- Rewrite GET handler (lines 4986–4991): import `IdentityService`, query `identity_claims` for low-confidence claims:
  ```python
  from lib.v4.identity_service import IdentityService
  svc = IdentityService(store.db_path)  # takes db_path string, NOT store object
  # Low-confidence identity claims
  conflicts = store.query("""
      SELECT ic.claim_id as id, ip.canonical_name as display_name,
             ic.source, ic.confidence as confidence_score,
             ip.profile_id, ip.profile_type
      FROM identity_claims ic
      JOIN identity_profiles ip ON ic.profile_id = ip.profile_id
      WHERE ic.confidence < 0.8 AND ic.status = 'active'
      LIMIT 20
  """)
  ```
- Rewrite POST resolve (lines 5229–5240): For identity type, update claim confidence:
  ```python
  # Resolve = confirm this identity claim is correct
  conn.execute("UPDATE identity_claims SET confidence = 1.0 WHERE claim_id = ?", (item_id,))
  ```
  **NOTE**: `ResolveFixDataRequest` model (line 5213) only has `resolution: str` and `actor: str`. It does NOT have `target_id`. The original plan called `svc.merge_profiles(to_profile_id=body.target_id)` — that would crash with `AttributeError`. For simple resolve (confirm identity), updating claim confidence is correct and matches the current handler's intent. Profile merging would need a separate endpoint or an expanded request model — defer to a follow-up.

**Entity links rewrite (D2):**
- Delete inline CREATE TABLE entity_links (lines 4972–4983)
- Fix GET handler (lines 4994–5001): `link_id` → `id` (schema.py uses `id INTEGER PK`). Keep UI-contract aliases: `to_entity_type as entity_type`, `to_entity_id as entity_id`, `from_artifact_id as linked_id`, `method as linked_type`
- Fix POST resolve (lines 5243–5250): `entity_links.updated_at` now valid (PR1 adds it); also set `status = 'confirmed'`, `confirmed_by`, `confirmed_at`

**Wrong table fixes:**
1. **B1** (line 3183): `governance_history` → `governance_audit_log`
2. **B6** (lines 5258–5264): `governance_history` → `governance_audit_log`; fix column mapping: use `actor` (not `processed_by`), `subject_identifier` (not `target_id`), `details` (JSON with resolution info), add `timestamp`
3. **B8** (line 2315): `governance_history` → `governance_audit_log` in `POST /api/decisions/{id}` handler; same column mapping fix as B6: `processed_by` → `actor`, `target_id` → `subject_identifier`, add `timestamp`, pack `decision_id`, `type`, `side_effects` into `details` JSON

**Notification stats fix (related to A6):**
- Line 3029: `store.count("notifications", "read_at IS NULL")` counts unread, but ignores dismissed. After PR1 adds `dismissed`, stats should report both:
  ```python
  total = store.count("notifications")
  unread = store.count("notifications", "read_at IS NULL")
  undismissed = store.count("notifications", "dismissed = 0 OR dismissed IS NULL")
  return {"total": total, "unread": unread, "undismissed": undismissed}
  ```
  UI `NotificationStatsResponse` (`api.ts:1215`) expects `{total, unread}`. Adding `undismissed` is additive (won't break UI), but the badge count likely should use `undismissed` not `unread` since `read_at` is never written.

**Notifications SELECT alias fix (A6):**
- Lines 3011–3016: Replace `safe_sql.select("notifications", ...)` with explicit column list to match UI `Notification` interface (`api.ts:1197`):
  ```sql
  SELECT id, type, body AS message, task_id, target_id,
         dismissed, dismissed_at, created_at
  FROM notifications
  WHERE ...
  ```
  - `body AS message`: legitimate rename — same data, different name. `_create_notification()` stores text as `body`, UI displays it as `message`.
  - `task_id`, `target_id`: real columns added in PR1. Initially NULL (notification creation code doesn't populate them yet — follow-up task). No NULL aliases hiding missing columns.

**Evidence endpoint rewrite (B2):**
- Lines 5354–5367: Replace `excerpts` query with:
  ```sql
  SELECT ae.excerpt_id as id, ae.artifact_id, ae.excerpt_text,
         ae.anchor_type, ae.anchor_start, ae.anchor_end,
         ae.created_at,
         a.source, a.type as artifact_type, a.occurred_at
  FROM artifact_excerpts ae
  JOIN artifacts a ON ae.artifact_id = a.artifact_id
  JOIN entity_links el ON el.from_artifact_id = a.artifact_id
  WHERE el.to_entity_type = ? AND el.to_entity_id = ?
  ORDER BY a.occurred_at DESC
  LIMIT 50
  ```
  Then construct `context_json` in Python:
  ```python
  import json
  for row in rows:
      row["context_json"] = json.dumps({
          "anchor_type": row.pop("anchor_type", None),
          "anchor_start": row.pop("anchor_start", None),
          "anchor_end": row.pop("anchor_end", None),
      })
  ```
  - **Why Python, not SQL**: System SQLite is 3.37.2 (Ubuntu 22.04) — `json_object()` is NOT available (needs 3.38+). SQL string concatenation (`'{"key":"' || val || '"}'`) returns NULL if any operand is NULL (SQLite || propagates NULL), and doesn't escape quotes in values. Python `json.dumps()` handles both correctly.
  - Also fix entity_links column references: `el.entity_id` → `el.to_entity_id`, `el.linked_id` → `el.from_artifact_id`
  - Also fix parameter order: current handler at line 5366 passes `(entity_id, entity_type)` but WHERE references them as `entity_id = ?` first, then `entity_type = ?` — parameters were SWAPPED. Plan's rewrite has `WHERE el.to_entity_type = ? AND el.to_entity_id = ?` with params `(entity_type, entity_id)` — correct order.
  - Rewrite should use `store.query()` instead of raw `sqlite3.connect()` (current handler at line 5350 opens raw connection — legacy pattern, unnecessary since `store` exists)

**Missing engine methods (E1+E2):**
- Lines 3124–3127: Replace with:
  ```python
  status = governance.get_status()
  # CRITICAL: get_status() returns domains as a dict: {"scheduling": {"mode": "observe", "auto_threshold": 0.8}}
  # UI expects an ARRAY of GovernanceDomain[]: [{domain, mode, confidence_threshold}]
  # Also: engine uses "auto_threshold", UI uses "confidence_threshold"
  domains_list = [
      {"domain": name, "mode": cfg.get("mode", "observe"), "confidence_threshold": cfg.get("auto_threshold", 0.8)}
      for name, cfg in status.get("domains", {}).items()
  ]
  return {
      "domains": domains_list,
      "emergency_brake": status.get("emergency_brake", False),
      "summary": governance.get_summary(),
  }
  ```
  **Verified**: `get_status()` (governance_engine.py:227) returns `{"emergency_brake": bool, "domains": {name: {mode, auto_threshold}}, "rate_limits": dict, "current_counts": dict}`.
  **Verified**: `get_summary()` (governance_engine.py:242) returns `{"ok": bool, "counts": {...}, "updated_at": str|None, "notes": list}`.
  **Verified**: UI `GovernanceDomain` (`api.ts:738`) expects `{domain: string, mode: string, confidence_threshold: number}`.

**Verification**: `ruff check api/server.py && bandit -r api/server.py` + `python -m pytest tests/test_stub_endpoints.py -x`

---

### PR 4: Fix spec_router.py handlers
**Purpose**: Fix all spec_router.py handler bugs.

**Findings addressed**: A8, A15, A16, B3, B4, B7, C1, C2, C3

**Column fixes:**
1. **A8** (lines 726–736): Rewrite client team query:
   ```sql
   SELECT DISTINCT tm.id, tm.name, tm.default_lane, tm.email,
          COUNT(CASE WHEN t.status NOT IN ('completed', 'done') THEN 1 END) as open_tasks,
          COUNT(CASE WHEN t.status NOT IN ('completed', 'done') AND t.due_date < date('now') THEN 1 END) as overdue_tasks
   FROM team_members tm
   JOIN tasks t ON t.assignee_id = tm.id
   WHERE t.client_id = ?
   GROUP BY tm.id
   ORDER BY tm.name
   ```
   Changes: `tm.role` → `tm.default_lane`; `t.completed = 0` → `t.status NOT IN ('completed', 'done')`; removed `WHERE tm.client_id = ?` (column doesn't exist); changed LEFT JOIN to JOIN since we only want team members with tasks for this client. Handler row access: `row[2]` is now `default_lane` (was `role`) — handler code at line 746 uses `row[2] or "Team Member"` which still works.
   **Imports needed for spec_router.py**: Add `from lib.v4.coupling_service import CouplingService` and `from lib.v4.identity_service import IdentityService` to the import block (currently neither is imported).

2. **A15** (line 2286): entity_links UPDATE — change `link_id` → `id`; `status`, `confirmed_by`, `confirmed_at` now valid (PR1 adds them)
3. **A16** + **B7** (line 2281): Change `UPDATE identities SET confidence_score = 1.0 WHERE id = ?` to `UPDATE identity_claims SET confidence = 1.0 WHERE claim_id = ?`. Table `identities` doesn't exist; `identity_claims` (registered in PR1) is the correct table. Column is `confidence` not `confidence_score`, PK is `claim_id` not `id`.
   **NOTE**: `IdentityService` import is still needed for the GET handler (fix-data identity conflicts query at B4). But the POST resolve does NOT need `merge_profiles()` — `FixDataResolveRequest` (line 2134) has no `target_id` field. Simple claim confidence update is the correct behavior. Same finding as PR3 A17.

**Coupling endpoint rewrite (C1):**
- Lines 1505–1516: Replace raw SQL with `CouplingService`:
  ```python
  from lib.v4.coupling_service import CouplingService
  svc = CouplingService(str(DB_PATH))  # MUST pass DB_PATH — default is <repo>/data/ but spec_router uses ~/.moh_time_os/data/
  if anchor_type and anchor_id:
      items = svc.get_couplings_for_entity(anchor_type, anchor_id)
  else:
      items = svc.get_strongest_couplings(limit=50)
  return {"items": items, "total": len(items)}
  ```
  NOTE: `server.py:5283` uses bare `CouplingService()` which is a pre-existing DB path mismatch bug. PR3 should also fix that to `CouplingService(store.db_path)`. Added to PR3 scope.

**Fix-data rewrite (B4, C2, C3):**
- Lines 1558–1576: Wire to `IdentityService` for identity conflicts + correct entity_links columns:
  ```python
  # Identity conflicts via identity_claims
  conflicts = conn.execute("""
      SELECT ic.claim_id as id, ip.canonical_name as display_name,
             ic.source, ic.confidence as confidence_score
      FROM identity_claims ic
      JOIN identity_profiles ip ON ic.profile_id = ip.profile_id
      WHERE ic.confidence < 0.8 AND ic.status = 'active'
      LIMIT 20
  """).fetchall()
  # Ambiguous links using correct entity_links columns
  # IMPORTANT: alias must match UI contract in FixDataCard.tsx:50-60
  # entity_type/entity_id = target entity, linked_type/linked_id = linking artifact+method
  links = conn.execute("""
      SELECT el.id, el.to_entity_type as entity_type, el.to_entity_id as entity_id,
             el.from_artifact_id as linked_id, el.method as linked_type,
             el.confidence
      FROM entity_links el
      WHERE el.confidence < 0.7 AND el.status = 'proposed'
      LIMIT 20
  """).fetchall()
  ```

**Evidence endpoint rewrite (B3):**
- Lines 2501–2512: Replace `item_history` with `artifact_excerpts` + `artifacts` + `entity_links`:
  ```sql
  SELECT ae.excerpt_id as id, ae.artifact_id, ae.excerpt_text,
         ae.anchor_type, ae.anchor_start, ae.anchor_end,
         ae.created_at,
         a.source, a.type as artifact_type, a.occurred_at
  FROM artifact_excerpts ae
  JOIN artifacts a ON ae.artifact_id = a.artifact_id
  JOIN entity_links el ON el.from_artifact_id = a.artifact_id
  WHERE el.to_entity_type = ? AND el.to_entity_id = ?
  ORDER BY ae.created_at DESC
  LIMIT 20
  ```
  Construct `context_json` in Python (same pattern as PR3 evidence endpoint — `json.dumps()` from anchor columns). SQLite 3.37.2 — `json_object()` unavailable.

**Imports to add to spec_router.py:**
- `import json` (NOT currently imported — needed for `json.dumps()` in evidence endpoint context_json construction)
- `from lib.v4.coupling_service import CouplingService` (needed for C1 coupling rewrite)
- `from lib.v4.identity_service import IdentityService` (needed for A16/B7 identity resolve)

**Verification**: `ruff check api/spec_router.py && bandit -r api/spec_router.py` + `python -m pytest tests/test_stub_endpoints.py -x`

---

### PR 5: Fix query_engine.py (A9)
**Purpose**: Fix calendar detail query — events.assignee_id doesn't exist.

**Fix** (query_engine.py:1125–1150):
- Current: `WHERE e.assignee_id = ?` (person_id)
- Events has no `assignee_id`. The person_id is a people table ID.
- Fix: look up person's email, join through `calendar_attendees.email`:
  ```sql
  SELECT ca.event_id, ca.email, ca.display_name,
         ca.response_status, ca.organizer
  FROM calendar_attendees ca
  JOIN events e ON ca.event_id = e.id
  WHERE LOWER(ca.email) = LOWER((SELECT email FROM people WHERE id = ?))
  ORDER BY e.start_time DESC
  ```
  LOWER() needed because: `calendar.py:311` stores `attendee.get("email", "")` without lowercasing. `people.email` also stored as-is. Google Calendar usually returns lowercase but it's not guaranteed. `delegation_graph.py:133` already uses `.lower()` for email comparison — follow that pattern.
- Same fix for recurrence query (lines 1136–1143) — apply LOWER() to both sides.

**Verification**: `ruff check lib/query_engine.py`

---

### PR 6: Housekeeping — Remove inline CREATE TABLE from non-handler code
**Purpose**: Consolidate table creation into schema_engine.

**Approach**: Keep `CREATE TABLE IF NOT EXISTS` as defense-in-depth, do NOT replace with `ensure_migrations()`. Reason: V4 services (`lib/v4/*.py`) use `<repo>/data/moh_time_os.db` as their default DB path, while `lib.db.ensure_migrations()` converges `~/.moh_time_os/data/moh_time_os.db` (from `paths.db_path()`). These are different paths. Delegating to `ensure_migrations()` would converge the wrong database when services use their default path.

The `CREATE TABLE IF NOT EXISTS` pattern is safe because:
- It's idempotent — no-op when schema_engine already created the table
- It works regardless of which DB path is in use
- 8 services use this pattern across the codebase — consistency matters

**What PR6 does instead**: Add a comment noting schema.py as canonical, and ensure the inline schema matches schema.py exactly (sync any divergence). This eliminates the *conflict* risk (D1–D2 ghosts with wrong schemas) while preserving *defense-in-depth*.

1. **D3** (key_manager.py:78): Sync inline `api_keys` CREATE to match schema.py column defs exactly. Add comment: `# Canonical schema in lib/schema.py — keep in sync`.
   - Constraint gap: inline has NOT NULL + UNIQUE + CHECK; schema.py has nullable. Add constraints to schema.py column defs (same approach as couplings CHECK constraints in PR1).
2. **D4** (audit_log.py:63): Sync inline `governance_audit_log` CREATE to match schema.py. Add canonical comment.
   - Constraint gap: inline has NOT NULL on 6 columns; schema.py nullable. Add NOT NULL + DEFAULT to schema.py for the 6 columns.
3. **D5** (coupling_service.py:43): Already synced by PR1 (schema.py gets the exact same column defs + CHECK constraints). Add canonical comment.
4. **D6** (notifications.py:84): Already synced by PR1 (schema.py gets exact defs + UNIQUE + indexes). Add canonical comment.
5. Commit `scripts/smoke_test_endpoints.py`
6. Fix `cron_recommended.txt` line 22 (references deleted `cli_v4.py cycle`)

**Verification**: `ruff check` on all changed files; re-run `scripts/smoke_test_endpoints.py` to confirm all 23+ endpoints pass.

---

## PR Dependency Chain

```
PR1 (schema) ──→ PR2 (paginated_router) ──→ PR3 (server.py) ──→ PR4 (spec_router) ──→ PR5 (query_engine) ──→ PR6 (housekeeping)
```

- PR1 MUST land first — adds columns/tables that PR3-PR6 depend on
- PR2 is independent but goes first (smallest, simplest, proves schema works)
- PR3 and PR4 both depend on PR1's entity_links columns and identity tables
- PR5 is independent of PR3/PR4 but sequential is cleaner
- PR6 goes last — removes inline CREATEs only after schema.py has them

**Total handler fixes**: 41 bugs across 17 endpoints in 4 files + 3 UI contract fixes + 1 pre-existing CouplingService path fix + governance domains shape transform
**Total schema additions**: 7 new tables, 11 new columns on 3 existing tables (notifications: 5 — dismissed, dismissed_at, task_id, target_id, recipient_id; entity_links: 5; communications: 1 — channel)
**Total inline CREATE syncs**: 4 (D3–D6 in PR6, synced to match schema.py) + 2 ghost table deletions (D1–D2 in PR3)

---

## UI Contract Compatibility

**Problem**: Several broken endpoints currently return 500. The UI has TypeScript interfaces defining the expected response shapes. When we fix the SQL to return 200, we unmask field name mismatches between schema column names and UI interface field names. Returning 200 with wrong field names is worse than 500 — it's silent data corruption.

**Rule**: Every handler rewrite MUST produce field names matching the TypeScript interface. Use SQL `AS` aliases where column names differ.

### Email endpoint (`/api/emails`)
| UI field (`api.ts:1288`) | Schema column (`communications`) | Fix type | Action |
|---|---|---|---|
| `sender` | `from_email` | Rename alias | `from_email AS sender` — same data, different name |
| `recipient` | `to_emails` | Rename alias | `to_emails AS recipient` — same data, different name |
| `body` | `body_text` | Rename alias | `body_text AS body` — same data, different name |
| `actionable` | `requires_response` | Rename alias | `requires_response AS actionable` — same semantic (INTEGER 0/1 flag) |
| `type` | `channel` (PR1 adds) | **New column** | `channel AS type` — `source` stores provider ("gmail"), `channel` stores communication type ("email"). Different concepts. Band-aid `source AS type` returns wrong data. |
| `subject` | `subject` | ✓ matches | — |
| `received_at` | `received_at` | ✓ matches | — |
| `processed` | `processed` | ✓ matches | — |

**Fix**: PR1 adds `channel` column. PR3 replaces `SELECT *` with explicit column list using rename aliases (same-data renames) and `channel AS type` (real column).

### Notification endpoint (`/api/notifications`)
| UI field (`api.ts:1197`) | Schema column (`notifications`) | Fix type | Action |
|---|---|---|---|
| `message` | `body` | Rename alias | `body AS message` — same data (notification text), different name |
| `task_id` | `task_id` (PR1 adds) | **New column** | Real column, initially NULL. Follow-up: wire `_create_notification()` to populate it. |
| `target_id` | `target_id` (PR1 adds) | **New column** | Real column, initially NULL. Follow-up: wire `_create_notification()` to populate it. |
| `dismissed` | `dismissed` (PR1 adds) | **New column** | ✓ matches after PR1 |
| `dismissed_at` | `dismissed_at` (PR1 adds) | **New column** | ✓ matches after PR1 |
| `type` | `type` | ✓ matches | — |
| `created_at` | `created_at` | ✓ matches | — |

**Fix**: PR1 adds `task_id`, `target_id`, `dismissed`, `dismissed_at` columns. PR3 replaces `SELECT *` with explicit column list. Only rename alias is `body AS message`. No NULL aliases — every field maps to a real column.

### Evidence endpoints (`/api/control-room/evidence`, `/api/v2/evidence`)
| UI field (`types/api.ts:259`) | Plan provides | Fix type | Action |
|---|---|---|---|
| `excerpt_text` | `ae.excerpt_text` | ✓ matches | — |
| `context_json` | Python `json.dumps()` from anchor columns | **Constructed from real data** | `artifact_excerpts` stores context as 3 columns (`anchor_type`, `anchor_start`, `anchor_end`). SELECT returns raw columns, Python assembles JSON. Handles NULLs and special chars correctly. SQLite 3.37.2 — `json_object()` unavailable, SQL `||` propagates NULL. |
| `source` | `a.source` | ✓ matches | — |
| `artifact_type` | `a.type as artifact_type` | Rename alias | Same data |
| `occurred_at` | `a.occurred_at` | ✓ matches | — |

**Fix**: Evidence SELECT constructs `context_json` from real anchor data. No NULL aliases.

### Fix-data endpoints — aliases correct, envelope must be preserved
Plan uses SQL aliases matching `FixDataCard.tsx:50-60`: `{id, display_name, source, confidence_score}` for identity conflicts, `{id, entity_type, entity_id, linked_type, linked_id, confidence}` for ambiguous links. ✓

**IMPORTANT**: The response envelope must include all 4 fields from `FixData` (types/api.ts:240): `identity_conflicts`, `ambiguous_links`, `missing_mappings` (empty array `[]` for now), and `total` (sum of all three arrays). The existing handler at server.py:5006-5011 and spec_router returns this shape — the rewrite must preserve it exactly.

### Couplings endpoint — already correct
Plan wires to `CouplingService` which returns objects with `coupling_id, anchor_ref_type, anchor_ref_id, entity_refs, coupling_type, strength, why, confidence` matching `types/api.ts:205-219`. ✓

### Governance endpoint — FIXED (was wrong)
`get_status()` returns `domains` as a dict `{name: {mode, auto_threshold}}`. UI expects an array `[{domain, mode, confidence_threshold}]`. Also `auto_threshold` → `confidence_threshold` rename needed. Plan's E1+E2 fix now includes the dict→array transformation.

---

## Test Strategy

**Current coverage gap**: The plan's only verification is `ruff check` + GET-only smoke test. 13 POST handler fixes have zero automated verification. Complex rewrites (identity resolution, evidence, couplings) have no unit tests.

### Minimum test plan per PR:

**PR1 (Schema)**: No handler changes — verify with `python -c` import check + converge() log inspection.

**PR2 (paginated_router A4)**: Already covered by smoke test (GET endpoint).

**PR3 (server.py — 15+ findings)**:
- Extend `tests/test_stub_endpoints.py` with new test class using existing `TestClient` + `create_fixture_db()` pattern:
  - `test_get_emails_returns_aliased_fields` — verify response has `sender`, `body`, `actionable` (not `from_email`, `body_text`, `requires_response`)
  - `test_get_notifications_returns_aliased_fields` — verify response has `message` (not `body`)
  - `test_dismiss_notification` — POST, then GET with `include_dismissed=true`, verify dismissed=1
  - `test_get_evidence_returns_items` — verify response has `excerpt_text`, `context_json`, `source`
  - `test_get_governance_returns_structure` — verify `domains`, `emergency_brake`, `summary` keys exist
  - `test_fix_data_resolve_identity` — POST resolve, verify 200
  - `test_fix_data_resolve_link` — POST resolve, verify 200
- Seed data: add rows to `communications`, `notifications`, `artifacts`, `artifact_excerpts`, `entity_links`, `identity_profiles`, `identity_claims` in `golden_seed.json`

**PR4 (spec_router — 9 findings)**:
- Similar test class pattern, but spec_router uses its own `get_db()` → need to monkeypatch `lib.paths.db_path` (same as existing test pattern)
  - `test_get_couplings_via_service` — verify CouplingService is called with correct db_path
  - `test_get_fix_data_identity_conflicts` — verify response shape matches UI contract
  - `test_get_evidence_v2` — verify response shape
  - `test_client_team_query` — verify team members linked through tasks

**PR5 (query_engine A9)**: Unit test `person_calendar_detail()` with fixture data containing `calendar_attendees` rows.

**PR6 (Housekeeping)**: Smoke test re-run only.

### Test infrastructure changes needed:
1. **`tests/fixtures/golden_seed.json`**: Add seed rows for `communications` (with `from_email`, `body_text`, `requires_response`, `source`, `channel` — current seed only has `id, subject, received_at`), `notifications`, `artifact_excerpts`, `artifacts`, `entity_links`, `identity_profiles`, `identity_claims`, `couplings`
2. **`tests/fixtures/fixture_db.py`**: **MUST be updated.** Currently `_seed_tables()` only inserts `(id, subject, received_at)` for communications (line 358-365). Must expand to insert all columns the email endpoint needs: `from_email`, `body_text`, `requires_response`, `source`, `channel`. Same issue for other new seed tables — `_seed_tables()` has no insert blocks for `notifications`, `artifact_excerpts`, `identity_profiles`, `identity_claims`, `couplings`. These must be added.
3. Schema tables will auto-create: `create_fixture_db()` calls `schema_engine.create_fresh()` which reads `lib/schema.py` — so PR1's new tables will automatically be created in fixture DBs.

---

## PR Merge Strategy

**PR1/PR6 conflict risk**: LOW. PR1 appends new tables after line 1697 of schema.py. PR6 modifies existing column defs at lines 1221-1246 (api_keys, governance_audit_log). Different file regions — git auto-resolves.

**Recommended merge order**: PR1 → PR2 → PR3 → PR4 → PR5 → PR6 (sequential, each depends on prior)

---

## Function Signature Verification Receipts

Every function the plan calls has been read and verified. Discrepancies with the plan are marked FIXED.

| Function | File:Line | Signature | Return type | Plan matches? |
|---|---|---|---|---|
| `governance.get_status()` | governance_engine.py:227 | `(self) -> dict` | `{"emergency_brake": bool, "domains": {name: {mode, auto_threshold}}, ...}` | **FIXED** — domains is dict not array; auto_threshold not confidence_threshold |
| `governance.get_summary()` | governance_engine.py:242 | `(self) -> dict` | `{"ok": bool, "counts": {...}, "updated_at": str\|None, "notes": list}` | ✓ |
| `CouplingService.get_couplings_for_entity()` | coupling_service.py:192 | `(self, entity_type: str, entity_id: str) -> list[dict]` | List of coupling dicts with parsed JSON fields | ✓ |
| `CouplingService.get_strongest_couplings()` | coupling_service.py:227 | `(self, limit: int = 20) -> list[dict]` | Same as above minus investigation_path | ✓ |
| `IdentityService.merge_profiles()` | identity_service.py:468 | `(self, from_profile_ids: list[str], to_profile_id: str, reason: str, actor: str) -> dict` | `{"status": "success", "op_id": ..., "merged_count": ..., "target_profile_id": ...}` or `{"status": "error", "error": ...}` | ✓ |
| `IdentityService.resolve_identity()` | identity_service.py:340 | `(self, claim_type: str, claim_value: str, create_if_missing: bool = False, source: str = "system") -> dict\|None` | Profile dict or None | ✓ (not directly called by plan) |
| `store.update()` | state_store.py:123 | `(self, table: str, id: str, data: dict) -> bool` | True if row updated | ✓ |
| `store.query()` | state_store.py:149 | `(self, sql: str, params: list = None) -> list[dict]` | List of row dicts | ✓ |
| `store.count()` | state_store.py:155 | `(self, table: str, where: str = None, params: list = None) -> int` | Row count | ✓ |
| `safe_sql.select()` | safe_sql.py:60 | `(table, columns="*", where=None, order_by=None, suffix="") -> str` | SQL string | ✓ |
| `safe_sql.where_and()` | safe_sql.py:171 | `(conditions: list[str]) -> str` | Joined conditions or "" | ✓ |
