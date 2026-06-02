# Verification Log — fix/ws4-data-freshness

**Session:** WS4 (resume after WS1–WS3 merged; HEAD bf60dc1 → branched off origin/main 104c679 which includes Chip D #126)
**Date:** 2026-06-02
**Agent:** Claude Opus 4.8 (1M) — implementer (I implement with TDD; a separate read-only Workflow verifies)

---

## Working model

- **Isolation:** WS4 is implemented in a dedicated git worktree at `/Users/molhamhomsi/clawd/ws4-worktree` on branch `fix/ws4-data-freshness`, branched off `origin/main` (104c679). The MAIN checkout (`/Users/molhamhomsi/clawd/moh_time_os`) is left on `fix/tasks-collector-propagation-test` with the in-flight spawned-chip working-tree edits UNTOUCHED — the live daemon runs from it. This keeps WS4 from colliding with Chips A/C/E (and Chip D, now merged as #126).
- **Interpreter:** tests run with the main checkout's venv by absolute path: `/Users/molhamhomsi/clawd/moh_time_os/.venv/bin/python3 -m pytest`. Verified: first-party source resolves from the worktree, third-party deps from the main `.venv` (ruff 0.15.1 == pinned, pytest 9.0.2, bandit 1.9.3).
- **Xero scope decision (best-practice, per operator):** Chip B never started (no Xero commits on origin/main; `list_invoices` still single-page; no `replace_source_rows`; xero.py:374 standalone DELETE). WS4 already owns the Xero token-cache (S4.5) and InvoiceID (S4.7d) work. Folding Chip B's two extra audit findings — `list_invoices` pagination and atomic DELETE+reinsert — INTO WS4 as a final task, so all Xero code lands in one coherent PR. Salvage patches (`audit-remediation/salvage/*.patch`) used as reference, every interface re-verified live.

---

## Pre-Edit Verification

For EVERY method call added or modified, one row. Filled BEFORE each edit.

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| _(filled per task below)_ | | | | | |

### Task 1 — S4.1 credential contract (test-only; no source edit)

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| tests/test_ws4_credentials_smoke.py | `engine.xero_client.load_credentials` | engine/xero_client.py:64 | yes — no-arg, returns XeroCredentials; raises RuntimeError("Xero credentials not found") xero_client.py:75-78 | yes (`.client_id`,`.tenant_id`) | n/a (test) |
| tests/test_ws4_credentials_smoke.py | `engine.xero_client._CONFIG_PATH` / `xc.os.path.exists` | xero_client.py:18 / stdlib | yes — module attr; `_load_from_env` reads os.path.exists at :46 | yes | n/a |
| tests/test_ws4_credentials_smoke.py | `engine.asana_client.load_pat` | engine/asana_client.py:31 | yes — no-arg→str; raises RuntimeError("Asana PAT not found") asana_client.py:41-43 | yes | n/a |

### Task 2 — S4.2 freshness wiring

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| data_freshness.py (new `record_collection_for_source`) | `self.record_collection` | data_freshness.py:128-135 (`entity_type,entity_id,source,collected_at=None,record_count=1`) | yes — called with exactly those kwargs | returns None | wrapper is sole new caller; existing callers unaffected (added method, no signature change) |
| orchestrator.py `_sync_one` + new `_record_freshness` | `DataFreshnessTracker(db_path=…)` | data_freshness.py:97-101 (`db_path: Path`) | yes | constructs tracker | n/a |
| orchestrator.py `_record_freshness` | `paths.db_path()` | lib/paths.py:41 → Path | yes (import lib.paths at orchestrator.py:15) | yes | n/a |
| orchestrator.py `_record_freshness` | `tracker.record_collection_for_source(source, record_count=)` | data_freshness.py (new, this PR) | yes | None | sole caller |
| orchestrator.py `_sync_one` | `result.get("stored", 0)` | dict from `collector.sync()` (CollectorResult.to_dict carries `stored`) | yes — `or 0` guards None | int | unchanged success/except structure (lines 136-150 → +1 line) |
| autonomous_loop.py:682 | `freshness_dashboard.get("avg_freshness_by_source", {})` | data_freshness.py:322 (dashboard key) | yes — key exists; old `"sources"` never existed (bug) | dict→len | this is the only consumer of that result var (loop-local) |

---

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | "All checks passed!" on all 13 source + 7 test files |
| `ruff format --check` on changed files | PASS | reformatted tasks.py/state_store.py/test_ws4_task_tombstoning.py (Mac, pinned 0.15.1), re-staged |
| `bandit -r` on changed files | PASS | pre-commit hook uses `-ll --skip B101,B608`; first commit attempt FAILED on B108 hardcoded_tmp_directory at test_ws4_task_tombstoning.py:56,95 (`store.db_path="/tmp/ignored.db"`); root-cause fixed → `str(tmp_path/"ignored.db")` (no suppression). Re-run: "No issues identified." |
| `pytest` | PASS | full WS4+regression surface 161 passed; regression-free vs base 104c679 (−2 failures, +35 passed, +0 errors) |
| Every method call in changed files resolves to a real `def` | PASS | all interfaces read+cited in Pre-Edit table above |
| Verification log included in `git add` | PASS | this file staged with the commit |

**Pre-commit env note:** the worktree lacks `time-os-ui/node_modules` (gitignored, not shared into worktrees), so the `sync-ui-types`/`sync-system-map` hooks failed (`openapi-typescript not found`). Fixed by symlinking the worktree's `time-os-ui/node_modules` → the main checkout's existing install (read-only use, not a fresh `pnpm install` — sandbox-compliant on this Mac).

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| WS4 (one PR per plan) | _(WS4 plan files only)_ | |

---

## Per-task evidence (fail→pass observed)

### S4.1 (test-only, locks current correct contract)
- `tests/test_ws4_credentials_smoke.py` → **4 passed** (no fail stage: these assert the *current* correct error behavior; regression guard for operator credential restoration). Asana already live (ASANA_PAT wired); Xero live sync BLOCKED on operator OAuth.

### S4.2 freshness wiring
- Step 2 FAIL: `record_collection_for_source` → `AttributeError: 'DataFreshnessTracker' object has no attribute 'record_collection_for_source'` (2 failed).
- Step 4 PASS after adding wrapper (2 passed).
- Step 6 FAIL: `test_sync_one_records_freshness_on_success` → `assert 0 == 1 where 0 = len([])` (no freshness write).
- Step 8 PASS after wiring `_record_freshness` into `_sync_one` (3 passed).
- Step 10 PASS: `test_dashboard_has_no_sources_key_but_has_avg_by_source` (pins existing dashboard contract; 1 passed).
- Step 12: ruff clean; `tests/test_ws4_freshness_wiring.py tests/test_data_freshness.py` → **22 passed** (4 new + 18 regression).
- Files: lib/intelligence/data_freshness.py, lib/collectors/orchestrator.py, lib/autonomous_loop.py, tests/test_ws4_freshness_wiring.py.

### S4.4 capacity repoint
- **Plan correction (TDD surfaced 2 real plan bugs):** (1) class is `CapacityCommandPage7Engine` (capacity_command_page7.py:132), NOT `CapacityCommandPage7` as the plan's test wrote — fixed the test. (2) the plan's test used fixed `2026-06-01` event dates; with `Horizon.THIS_WEEK` the window is `[today 00:00, today+7d]`, so on any run after 2026-06-01 those events fall out-of-window and the test false-negatives. Rewrote the test to anchor event times to `date.today()` so they're always in-window. Both corrections preserve the test's intent.
- Pre-Edit confirmed: ctor `(db_path=None, mode, horizon)` :199; `_query_one/_query_all` swallow OperationalError→None/[] :240-248,230-238; `_load_calendar_events`→`tuple[float,float,float,int,int]` :536-583; consumers `event.get("is_focus_block")` :571 + `_compute_largest_contiguous_focus` :596 (derived 0/1 column preserves both).
- Step 2 FAIL: `meeting_count == 0` (calendar_events query swallowed→zeroed) and `calendar_last_sync_at == None`.
- Step 5 PASS after repoint (synced_at→updated_at on `events`; is_focus_block derived from `event_type='focusTime'`). 2 passed.
- Step 6 grep: NO live SQL reader of calendar_events/gmail_messages remains in lib/api/scripts. Remaining hits are Python var/param names (command_center.py already reads `FROM events`; priority_engine param), retention config keys (data_lifecycle/cron_tasks), docstrings/comments (calendar.py, bottleneck.py, collision.py). One stale **diagnostic script** `scripts/entity_relationship_map.py:23` maps `"Calendar":"calendar_events"` — out of plan file-set, flagged for commit body (will break only if run post-DROP).
- Step 7 ruff clean. `-k capacity` → 24 passed (incl. my 2). 3 ERRORS in `tests/test_missed_surface_closure.py` are PRE-EXISTING on the 104c679 base (61 errors in isolation: "DETERMINISM VIOLATION: live DB path probed" — that file doesn't use fixture_db). NOT a WS4 file, NOT my regression.
- Files: lib/agency_snapshot/capacity_command_page7.py, tests/test_ws4_capacity_repoint.py. **DROP TABLE remains a deferred operator [DECISION].**

### S4.5 Xero token caching
- Pre-Edit confirmed (engine/xero_client.py): `save_tokens(access_token, refresh_token)`:99 wrote `{"access_token":…}` only :110; `get_access_token()`:156 always refreshed :161; `refresh_access_token(creds)`:131; `TOKEN_CACHE_PATH`:19; `Any` imported :12; no module-level `time` (added it).
- Minor deviation from plan (idiomatic): added `import time` at module level (after `import os`) instead of 3 scattered local `import time` — behavior identical, cleaner.
- Step 2 FAIL: `reuses_unexpired_cache` → returns MagicMock (always refreshes); `save_tokens_writes_expires_at` → `KeyError: 'expires_at'`. (`refreshes_when_expired` passed pre-fix — current code always refreshes.)
- Step 6 PASS after adding TTL/skew constants + `_read_token_cache`/`_cached_access_token_if_valid`, `save_tokens` expires_at, `get_access_token` cache-reuse. 3 passed.
- Step 7 regression: `test_xero_collector.py` clean. `test_xero_collector_expansion.py` → 3 FAILED (`invoices_stored` key). PROVEN pre-existing: stashed my engine/xero_client.py change, the 3 still fail identically → they are **Chip A's stale tests** ([[moh-chip-owns-xero-expansion-test]]), NOT my regression, NOT my file to edit.
- Step 8 ruff clean; bandit clean.
- Files: engine/xero_client.py, tests/test_ws4_xero_token_cache.py.

### S4.6 tombstoning
- Pre-Edit confirmed: `lib.db.validate_identifier`:36 (raises ValueError); `TasksCollector(config, store=None)`:36, `collect()`→`{"tasks":…,"lists":…}`:123, `transform` emits `id=f"gtask_{id}"`,`source="google_tasks"`, skips completed:140-146; `AsanaCollector.sync` success path :544-632, `cr.status`:626, tasks use `gid`:567; base `sync()` :92-211; `lib.safe_sql.delete`/`in_placeholders`/`in_clause` :118/164/198.
- **No-Bypass-Rule win:** plan hand-rolled an f-string DELETE + new `# noqa: S608`. Instead built SQL via `lib.safe_sql` (validated identifier + the codebase's SINGLE file-level approved S608 suppression at safe_sql.py:17). **No new noqa added.** bandit clean on reconcile.py.
- **TDD caught my bug:** first impl used `safe_sql.in_clause` → `id IN (...)` (deletes the SEEN rows — inverted). Test `test_tombstone_deletes_rows_not_in_seen_set` FAILED `{'gtask_b','asana_x'} == {'gtask_a','asana_x'}`. Fixed to `id NOT IN (placeholders)`. PASS.
- **Plan/test inconsistency resolved:** the plan's TasksCollector test stubs `collect→{tasks:[]}` (empty) + `transform→2 rows`, asserting seen=={gtask_a,gtask_b}. Plan's prose impl built `seen` from `collect()["tasks"]` (would be empty → test fails). Implemented correctly by deriving seen from the TRANSFORMED rows' `id` (canonical row id, completed already filtered) — matches test AND avoids a 2nd raw parse. Asana derives from `raw_data["tasks"]` gid (matches its test).
- Step 4 helper PASS (2); Step 8 TasksCollector PASS (1); Asana reconcile PASS (1) → 4/4 tombstone tests pass. `test_asana_collector.py` clean.
- 10 `test_tasks_collector.py` failures are PRE-EXISTING (naive−aware TypeError, fixed next in S4.7a) — proven by stashing my edits → `10 failed, 11 passed` identical. NOT my regression.
- Step 13 ruff clean; bandit clean (no S608).
- Files: lib/collectors/reconcile.py, lib/collectors/tasks.py, lib/collectors/asana.py, tests/test_ws4_task_tombstoning.py.

### S4.7a silent swallows
- Pre-Edit confirmed: `_compute_priority` naive `strptime` − aware `now(UTC)` at tasks.py:216-217, guard only `ValueError`:229; `get_internal_users` returns `[]` on missing DB at all_users_runner.py:64 (+ no try/finally on conn); 4 un-logged cursor-parse `except ValueError: pass` at 281/398/550/715 (all have `user`+`stored_cursor` in scope via `get_cursor(...)` at 265/380/534/699). Site 629 is `filtered_count += 1` (deliberate, commented) — left untouched.
- tasks fix: `.replace(tzinfo=timezone.utc)` + `except (ValueError, TypeError) as e: logger.debug(...)`. `test_tasks_collector.py` → 21 passed (was 10 failed pre-fix; this is the previously-red `test_overdue_high_priority` + 9 transform tests that hit the same path).
- get_internal_users: Step 5 FAIL "DID NOT RAISE FileNotFoundError"; Step 6 raise + try/finally → PASS. 2 robustness tests pass.
- 4 cursor swallows → `logger.debug("<svc> cursor parse failed for %s (%r): %s", user, stored_cursor, e)`. import OK; no bare cursor-pass remains.
- Step 9 ruff clean (S110/S112 gone); bandit clean.
- Files: lib/collectors/tasks.py, lib/collectors/all_users_runner.py, tests/test_ws4_ingestion_robustness.py.

### S4.7b all_users lock + WAL
- Pre-Edit confirmed: `CollectorLock` (collector_registry.py:29) — `__init__(name="global")`:54, `self.acquired`:57, `__enter__`:180 sets acquired, `__exit__`:191, `break_lock`:156, TTL_SECONDS=60/HEARTBEAT_INTERVAL=20 :51-52; 7 bare `sqlite3.connect(str(db_path))` sites (88/99/124/140/154/164/176); `run_all_users(since,until,limit_users=None,limit_per_user=50,dry_run=False,services=None)`:936 body opens `db_path=paths.db_path();ensure_tables`:948 with an inner `dry_run` `return {}` and final `return report`:1125.
- Step 2/6 FAIL: `_connect` ImportError; `CollectorLock` AttributeError on module.
- Added `_DB_TIMEOUT_SECONDS=30.0` + `_connect(db_path)` (timeout+WAL); routed all 7 sites via replace_all (helper at :51 unchanged). Step 4 WAL test PASS.
- Wrapped `run_all_users` in `CollectorLock("all_users")`: not-acquired → `{"skipped": True}`; else delegate to extracted `_run_all_users_locked` (whole body incl. dry_run early-return moved in, indentation preserved). Step 8 lock test PASS. 4/4 robustness tests pass.
- Regression: import OK; only caller is module `main()`:1201 (signature unchanged); `test_all_users_sweep_cursor.py` → 8 passed.
- Step 9 ruff clean; bandit clean.
- Files: lib/collectors/all_users_runner.py, tests/test_ws4_ingestion_robustness.py.

### S4.7c registry drift
- Pre-Edit confirmed: `CollectorSpec.enabled`:209 + `.sync_interval_seconds`:210; `COLLECTOR_REGISTRY` 8 sources (cal=60,gmail=120,drive=600,contacts=600,rest=300) all enabled :215-277; `get_collector_map()`→{name:class} for 8 :285, imports classes INSIDE the fn (so orchestrator top-level class imports become removable). Registry intervals == orchestrator's old hardcoded → no behavior drift.
- Step 2 FAIL: `_core_sources_from_registry` ImportError; disable test shows xero force-enabled despite enabled:false.
- Removed orchestrator class-imports (22-29) → single `from lib.collector_registry import COLLECTOR_REGISTRY, CollectorLock, get_collector_map`; added `_core_sources_from_registry()`; rewrote `_init_collectors` to derive from registry + `setdefault` interval (no longer FORCES enabled=True → explicit enabled:false honored).
- Step 4 PASS (2); Step 5 import OK, prints 8 sources.
- **Regression rigor:** broad `-k "orchestrator or registry"` shows 17 failures in test_audit_remediation_v3_behavioral/v4_implementations — PROVEN pre-existing & NOT mine: stashing my orchestrator.py gives 40 failed/26 passed (WORSE) vs 17 failed/40 passed WITH my change (my lazy `get_collector_map()` import actually fixes ~23 of them). The 17 residual all trip conftest `DETERMINISM VIOLATION: live DB probed` at `StateStore.__init__`→run_startup_migrations→`db_path.exists()` (lib/db.py:180) — a pre-existing TEST-HARNESS issue (those files don't use fixture_db), independent of WS4.
- All 23 WS4 new tests pass together. ruff clean.
- Files: lib/collectors/orchestrator.py, tests/test_ws4_ingestion_robustness.py.
- **FLAG for handoff:** multiple existing test files (test_missed_surface_closure.py, test_audit_remediation_v3/v4) fail under the conftest determinism guard because they construct StateStore against the live DB path instead of fixture_db. Pre-existing tech-debt, out of WS4 scope. (Spawn-task filed.)

### S4.7d magic constants
- Pre-Edit confirmed: `_run_inbox_enrichment` `run_enrichment_batch(use_llm=True, limit=20)`:249 (orchestrator); `os` NOT imported (added); xero.py `inv_number`:390, `inv_id` .replace chain:432, `store.insert("invoices",{"id":inv_id,...})`:436-454, `external_id`=inv_number:441, `list_invoices` imported INSIDE sync:268-272 (called PAID:281 + AUTHORISED:284), XeroCollector ctor`(config,store=None)`:58, WS3 ACCREC-empty guard already present:302-329; credential_paths `google_sa_file` hardcoded `sa-bW9saGFtQGhybW55LmNv.json`:39.
- **Deviation from plan (import-time-capture trap):** plan defined `DEFAULT_INBOX_ENRICH_LIMIT = int(os.environ.get("MOH_INBOX_ENRICH_LIMIT","20"))` at MODULE level — frozen at import, so the test (sets env after import) would get 20, FAIL. Implemented: module const `DEFAULT_INBOX_ENRICH_LIMIT=20` + read env AT CALL TIME inside `_run_inbox_enrichment`. Step 2 FAIL `20==75`; Step 4 PASS.
- Xero InvoiceID: `inv_guid = inv.get("InvoiceID")` + `inv_id = f"xero_{inv_guid}"` (fallback to sanitized number). Test PASS. **Mutation-proved** (reverted to old .replace → test FAILED `{'xero_INV_1'}=set(['xero_INV_1','xero_INV_1'])` → test couples to fix). NOTE: the `git checkout` I used to undo the mutation ALSO reverted my uncommitted real edits — re-applied them. Lesson: never `git checkout <file>` to undo a mutation on a file with uncommitted edits.
- SA filename: `os.environ.get("GOOGLE_SA_FILENAME", "service-account.json")` + genericized docstring. Leaked base64 fully removed from lib/. 2 SA tests PASS.
- Regression: `test_xero_collector.py` 20 passed; `test_credential_audit.py` 47 passed (did NOT pin old name); `test_credential_paths.py` 2 passed. The `xero_INV-001` literals in test_xero_collector_expansion.py:282-341 are `_transform_line_items` inputs, not inv_id-derivation assertions.
- Step 13 ruff clean; bandit clean.
- Files: lib/collectors/orchestrator.py, lib/collectors/xero.py, lib/credential_paths.py, tests/test_ws4_ingestion_robustness.py.
- **[DECISION] for Molham (SA file resolution changes):** default SA filename changes `sa-bW9saGFtQGhybW55LmNv.json` → `service-account.json`. The live daemon resolves the SA file via this path. Molham must EITHER (a) `export GOOGLE_SA_FILE=<full path to existing SA file>` (preferred, explicit) in the daemon plist, OR (b) `export GOOGLE_SA_FILENAME=sa-bW9saGFtQGhybW55LmNv.json` to keep the current on-disk name, OR (c) rename the on-disk file to `service-account.json`. Without one, Google collectors (gmail/calendar/chat/drive/tasks/contacts) won't find the SA file. Goes in the PR handoff note.

### S4.7e watchdog decision (Option A — document + lean on lock TTL)
- Pre-Edit confirmed: `WatchdogTimer` class docstring :26-34 (watchdog.py); orchestrator `_sync_impl` ThreadPoolExecutor(max_workers=5):199 + `for future in as_completed(futures):`:204; `CollectorLock.TTL_SECONDS=60`/`HEARTBEAT_INTERVAL=20`:51-52.
- Step 2 PASS (pins existing TTL=60≤120, heartbeat=20<60 — documentation contract, no fail stage).
- Documented SIGALRM/main-thread limitation in WatchdogTimer docstring + added explanatory comment above the as_completed loop (lock-TTL safety net). No runtime behavior change (Option A).
- imports OK; ruff clean; all 11 ingestion_robustness tests pass.
- Files: lib/collectors/watchdog.py, lib/collectors/orchestrator.py, tests/test_ws4_ingestion_robustness.py.

### FOLD-IN — Xero pagination + atomic DELETE+reinsert (Chip B's 2 findings, Chip B never started)
- **Why folded:** verification-log lines 134-135 recorded these as out-of-scope real data-loss bugs; WS4 already owns all Xero code (S4.5/S4.7d). One coherent Xero PR > split. Salvage `state_store_replace_source_rows.patch` used as reference; every interface re-verified.
- **Xero pagination contract (Context7 /xeroapi/xero-python):** Accounting Invoices endpoint returns ≤100/page; supports `page=N`; loop until a short page. Implemented `list_invoices` to loop `page=1..N` via `xero_get`, accumulate, stop when `len(batch) < XERO_PAGE_SIZE(=100)`. Pre-Edit confirmed: old `list_invoices`:246 single `xero_get`; `xero_get`:207; collector calls it PAID:281+AUTHORISED:284 then `all_invoices=paid+authorised`:286.
  - 2 pagination tests (patch `xero_get`): FAIL `100==102` (truncated) → PASS (102, paged [1,2], no page 3). Single-short-page: 1 request only.
- **Atomicity — StateStore.replace_source_rows:** Pre-Edit confirmed `_get_conn()` contextmanager commits-on-clean-exit/closes-in-finally:59-75; `insert_many`:93; `safe_sql.insert_or_replace`:99 + `safe_sql.delete`:118; `db_module.validate_identifier`. Added `replace_source_rows(table, source_column, source_value, rows)` — DELETE+INSERT in ONE txn, `except Exception: conn.rollback(); raise` (re-raise, NOT a swallow → ruff/bandit/CLAUDE.md compliant; precedent: it's the only `except Exception` in state_store.py:155).
  - 3 atomic tests (via `object.__new__(StateStore)` to bypass `__init__`'s ensure_migrations which trips the conftest determinism guard): mid-insert NOT NULL failure → rolls back (prior xero+asana rows retained); success → old xero gone/asana kept; empty → clears source. FAIL (AttributeError) → PASS.
- **Collector rewire:** removed standalone `DELETE FROM invoices WHERE source='xero'`:374 + per-row `store.insert`:448; now accumulate `invoice_rows` in the loop → ONE `store.replace_source_rows("invoices","source","xero",invoice_rows)` after the loop, with a typed FAILED+STALE-retain error path. AR aggregation unchanged (dict-build can't raise, so the old per-row try/except COLLECTOR_ERRORS was dropped). WS3 ACCREC-empty guard:302-329 still prevents empty-wipe upstream.
- **Latent FK bug fixed:** the SECOND inv_id derivation in the line_items block (xero.py:560) still used the old `.replace()` chain → line_items `invoice_id` would orphan from the GUID-keyed invoice rows. Updated to the same GUID-or-fallback. (Missed by the S4.7d plan, which only cited line 392.)
- **S4.7d test updated:** `test_xero_invoice_id_uses_guid_not_number` captured from `store.insert` (now unused for invoices) → updated to capture from `store.replace_source_rows`. PASS.
- Regression: `test_xero_collector.py` 20 passed; full xero surface 29 passed. ruff clean; bandit clean (exit 0).
- Files: engine/xero_client.py, lib/state_store.py, lib/collectors/xero.py, tests/test_ws4_xero_pagination_atomic.py, tests/test_ws4_ingestion_robustness.py.

---

## Adversarial verify Workflow round 1 (workflow w38722kb0, 36 read-only agents) — 5 of 9 tasks REFUTED → fixed

Independent verify (re-run + mutation-proof) + 3 skeptics (correctness/data-safety/spec-completeness) per committed task, read-only against the worktree. Verify-stage `mutation_proved=true` for all 9 (tests genuinely couple to fixes). Skeptic outcomes:

| Task | verify | skeptics | outcome |
|------|--------|----------|---------|
| S4.2 freshness wiring | pass | 3/3 refute | core sound; refuted on CO-BUNDLED defects (contract + silent-failures regressions, tasks tombstone) → fixed |
| S4.4 capacity repoint | pass | 2/3 refute | repoint correct; refuted on tz-aware/naive crashes exposed by reading live `events` → fixed |
| S4.5 xero token cache | pass | 1/3 | DONE (airtight; lone refute = co-bundled tombstone, fixed) |
| S4.6 tombstoning | pass | 3/3 refute | reconcile primitive sound; refuted on tasks double-fetch data-loss + asana flip → fixed |
| S4.7a silent swallows | pass | 1/3 | DONE (lone refute = co-bundled tombstone, fixed) |
| S4.7b all_users lock | pass | 1/3 | DONE (lone refute = co-bundled tombstone, fixed) |
| S4.7c registry drift | pass | 3/3 refute | runtime correct; refuted on 3 tests/contract/ regressions → fixed |
| S4.7d magic constants | pass | 2/3 refute | trio correct; refuted on co-bundled regressions + fallback FK divergence → fixed |
| FOLD xero pagination+atomic | pass | 2/3 refute | pagination+atomicity correct; refuted on FakeStore regression + line_items append-only → fixed |

**Real in-scope defects the skeptics caught (all genuine — this is why the model exists):**

- **FIX-1 (DATA LOSS, ~8 skeptics + PoC):** `TasksCollector.sync` built the tombstone seen-set from a SECOND `collect()`; a partial 2nd fetch (collect swallows per-list errors) tombstoned just-stored live rows. Fixed: added `BaseCollector._last_synced_rows` (set in `sync()` after `insert_many`), and `TasksCollector.sync` derives the seen-set from THOSE stored rows — one fetch, no divergence. Docstring corrected. Tombstone moved into its own try (cleanup error can't flip the result). New regression test: 2nd fetch returns fewer rows → fetch-1 rows NOT deleted, `collect()` called exactly once.
- **FIX-2 (CI-BLOCKING):** S4.7c removed orchestrator's 8 module-level collector imports → `tests/contract/test_collector_paths.py` (`mock.patch orchestrator.AsanaCollector` ×2) + `test_collector_registry.py::test_orchestrator_has_all_collectors` (greps source for class names) failed; CI runs `tests/contract/` (ci.yml:105). Fixed: re-added the 8 imports + `__all__` re-export (runtime still uses `get_collector_map()`; ruff clean via `__all__`). `tests/contract/` → 79 passed.
- **FIX-3 (REGRESSION):** `tests/test_collector_silent_failures.py` FakeStore lacked `replace_source_rows`+`db_path` → new calls raised AttributeError (∈ COLLECTOR_ERRORS) → PARTIAL flipped to FAILED. NOT chip-owned. Fixed: added both to FakeStore (atomic delete-by-source + reinsert, honors `_fail_on_table`). 46 passed.
- **FIX-4 (result corruption):** Asana tombstone was inside the result-determining try → a `db_path`/tombstone failure reclassified a real SUCCESS/PARTIAL to FAILED. Fixed: own try (log+continue), and seen-set derived from `transformed_tasks` (the STORED rows) so a transform-failure PARTIAL (transformed=[]) → empty-guard, no wipe.
- **FIX-5 (live crash, reproduced):** repointing to live `events` (tz-aware timestamps) exposed `_compute_reality_gap_confidence` (aware−naive TypeError → always "invalid") and `_compute_largest_contiguous_focus` (aware vs naive compare → crash). Fixed: `_parse_event_dt` normalizes all event datetimes to naive; sync-time normalized to aware UTC. 2 new tz-aware regression tests.
- **FIX-6 (FK + data hygiene):** (a) `reconcile.py` added `PRAGMA foreign_keys=ON` (tombstoning a task no longer orphans `time_blocks.task_id`). (b) `xero_line_items` was append-only (AUTOINCREMENT PK, no id in rows) → unbounded duplicates each sync; fixed by clearing the (xero-only) table before reinsert. (c) extracted `_xero_invoice_row_id(inv)` (deterministic GUID-first, no mutable counter) used by BOTH the invoice loop and the line_items loop → fallback FK no longer diverges. New regression: line_items cleared each sync + FK == invoice id.

**Re-verification after round-1 fixes:** full WS4+regression+contract+silent-failures surface = **292 passed**. Full suite delta vs base 104c679: failures **244→237 (−7)**, passed **3366→3410 (+44)**, errors **189→189 (0)** — regression-free, fixes 7 pre-existing failures. ruff clean; bandit clean.

## Adversarial verify Workflow round 2 (workflow wu6govlhi, 36 read-only agents) — caught 3 MORE real defects

Round 1's 5 failures dropped to: S4.5 FAILED (2/3), all others ≤1/3 (aggregate pass). But two ≤1/3 lenses + the S4.5 2/3 carried **genuine reproduced defects** (engineering correctness is not a majority vote — a lens with a working PoC wins):

- **FIX-8 (DATA LOSS, PoC reproduced):** a PARTIAL upstream fetch (asana per-project / google_tasks per-list failure swallowed + `continue`) leaves `cr.status=SUCCESS` (the per-unit failure only increments a log counter, never escalates), so the tombstone fired with an INCOMPLETE seen-set → deleted still-live rows from the failed unit. (Round-1's FIX-1/FIX-4 fixed the 2nd-fetch divergence + the result-flip, but not the silently-partial SINGLE fetch.) PoC: project A `list_tasks` raises ConnectionError, B succeeds → status=success, `asana_LIVE_A` permanently tombstoned. Fix: `collect()` now returns `_primary_fetch_complete` (False if any per-unit fetch failed); `BaseCollector` exposes `_last_raw_data`; both tombstones run ONLY when `_primary_fetch_complete`. + 2 partial-fetch regression tests (tombstone skipped).
- **FIX-9 (half-clear data loss):** round-1 FIX-6 cleared `xero_line_items` via `store.query("DELETE...") + store.insert_many()` — two connections, non-atomic; an insert failure mid-loop committed the DELETE standalone → table emptied. Fixed: added `StateStore.replace_all_rows(table, rows)` (full-table DELETE+reinsert in ONE txn, rollback on failure, via `safe_sql.delete(table, where="1=1")` — no f-string SQL/noqa); xero line_items routed through it; FakeStore got `replace_all_rows`. + atomic-rollback regression test.
- **FIX-10 (S4.5 spec gap):** `cli/xero_auth.py` + `cli/xero_auth_auto.py` wrote `{"access_token":…}` with no `expires_at` → a just-minted OAuth token was immediately rejected by `_cached_access_token_if_valid` (no expires_at → None) and refreshed. Fixed: both CLIs now write `expires_at = time.time() + XERO_TOKEN_TTL_SECONDS` (the engine two-field contract). Neither CLI is in ci.yml's protected set; change is the token-cache WRITE shape, not the OAuth consent flow.
- **FK-pragma reverted (round-2 S4.6 DEFECT 2):** round-1 FIX-6 added `PRAGMA foreign_keys=ON` to `reconcile.py`, but `time_blocks.task_id REFERENCES tasks(id)` (no ON DELETE) → the pragma ABORTS the tombstone DELETE whenever a tombstoned task has a scheduled block (breaks the feature). Reverted the pragma (matches the rest of the codebase's delete paths, which don't enforce it); the dependent-`time_blocks` cleanup is filed as a separate spawn-task.

**Re-verification after round-2 fixes:** full WS4+regression+contract+silent-failures surface = **295 passed**. Full suite delta vs base 104c679: failures **244→237 (−7)**, passed **3366→3413 (+47)**, errors **189→189 (0)** — regression-free. ruff clean; bandit clean ("No issues identified", exact hook args).

## Adversarial verify Workflow round 3 (workflow wmskilbq1, 36 read-only agents) — 8/9 pass; FOLD caught 1 MORE real defect

S4.2/S4.5/S4.7a/b/c/d at 0/3, S4.4/S4.6 at 1/3 (aggregate pass). **FOLD failed** (verify mut=False + 1/3): the data-safety skeptic reproduced a **CI-reliability defect** (and the verifier's mutation #2 was a methodology artifact, not a real gap):

- **FIX-11 (test isolation — reproduced):** under full-suite ordering, my fold-in tests `test_xero_line_items_cleared_before_reinsert_and_fk_matches` + `test_xero_invoice_id_uses_guid_not_number` failed with `RuntimeError: Xero credentials not found`. Root cause (deep Python import-machinery bug): `test_collector_silent_failures.py::test_xero_real_boundary_api_failure` pops `engine.xero_client` from sys.modules and re-imports, but **never re-bound the parent package attribute `engine.xero_client`** — and `from engine.xero_client import X` resolves via the PARENT ATTRIBUTE, not sys.modules. So `engine.xero_client` (parent attr) pointed at the popped/un-patched object while sys.modules held the restored one; the collector's lazy import read the stale parent-attr object, bypassing my patch → real `list_invoices` → load_credentials → RuntimeError. Confirmed via `getattr(engine,'xero_client') is sys.modules['engine.xero_client'] == False`. Fixed: both teardowns in that file now (a) capture the real module first, (b) re-import if absent, and (c) **rebind `engine.xero_client = sys.modules['engine.xero_client']`**. My fold-in tests also switched to string-target `monkeypatch.setattr("engine.xero_client.list_invoices", ...)` (belt-and-suspenders). Repro now passes.
- **Verifier mutation #2 (NOT a defect):** the verifier deleted only the explicit `try/except conn.rollback()` from replace_source_rows and the atomicity test still passed — because `_get_conn`'s contextmanager skips `commit()` on exception and SQLite auto-rolls-back on close. So atomicity is guaranteed by the contextmanager; the explicit rollback is redundant belt-and-suspenders. The fix IS atomic (multiple probes confirmed prior rows survive a mid-batch failure) — the verifier just picked a mutation a redundant safety layer absorbs.
- **FIX-9 follow-up (staleness):** `replace_all_rows` for xero_line_items was gated by `if line_items_rows:`, so a zero-line-item sync left stale rows. Now always replaces (past the ACCREC guard, an empty set genuinely means "none this cycle"). (No FK + INNER JOIN reader means this was staleness, not corruption — but tightened anyway.)

**Re-verification after round-3 fixes:** full WS4+regression+contract+silent-failures surface = **295 passed**. Full suite delta vs base 104c679: failures **244→235 (−9)**, passed **3366→3415 (+49)**, errors **189→189 (0)** — regression-free, fixes 9 pre-existing failures (incl. 2 more the sys.modules rebind un-broke). ruff clean; bandit clean.

## Adversarial verify Workflow round 4 (workflow wp0l28wzy) — all 9 verifiers PASS, 0 refutes

All 9 tasks: `verify=pass`, `mutation_proved=True`, 0/3 refute — including FOLD, whose round-3 verifier `mut=False` (the redundant-rollback methodology artifact) is now resolved (this round's verifier proved both pagination AND atomicity mutations kill their tests). The skeptic stage hit a harness infrastructure flake (many agents "completed without calling StructuredOutput" — a token/protocol starvation, NOT findings; subagent_tokens collapsed to 1.2M vs ~3.6M in prior rounds), so skeptic coverage this round was partial; every skeptic that DID return (S4.5 3/3, S4.7c 2/2, S4.7b 1/1) came back NOT-refuted. Convergent signal across all rounds: round-3 gave full skeptic coverage at ≤1/3 on 8/9 (FOLD's lone real defect = FIX-11, fixed); round-4 verifiers confirm all 9 mutation-proof-pass with the fixes in place. Implementer then directly re-ran the 11 data-safety-critical scenarios the skeptics probed (partial-fetch tombstone skip ×2, stored-rows seen-set, empty-guard, replace_source_rows + replace_all_rows atomic rollback, pagination, tz-aware capacity, Xero+Asana secondary-fetch→PARTIAL) → **11 passed**. WS4 verified sound; proceeding to rebase + PR.

**Two BLOCKED operator actions remain (NOT faked):** Xero OAuth (`.venv/bin/python -m cli.xero_auth` browser consent — populates the refresh token, len 0 today) and GCP SA-key rotation (`config/.credentials.json` leaked key → `docs/runbooks/rotate-sheets-to-xero-sa-key.md` → set `CREDENTIALS_JSON_FILE`). **[DECISION]s for the PR:** GOOGLE_SA_FILENAME resolution (set `GOOGLE_SA_FILE` or `GOOGLE_SA_FILENAME` or rename the on-disk SA file); `DROP TABLE gmail_messages/calendar_events` deferred to operator after the repoint merges. The Asana fix (ASANA_PAT) is already live — verify a live sync.
