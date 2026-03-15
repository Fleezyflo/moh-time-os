# Codebase Audit & Remediation Report — 2026-03-10

## Scan 1: httpx Calls Missing `timeout=`

9 httpx calls across 4 files have no `timeout=` parameter. A hung connection blocks the caller indefinitely.

| Severity | File | Lines | Calls |
|----------|------|-------|-------|
| **HIGH** | `lib/integrations/chat_interactive.py` | 106, 183, 261, 318, 382, 455 | 6 × `httpx.post/patch/delete` |
| **HIGH** | `engine/xero_client.py` | 68, 105 | `httpx.post` (token refresh), `httpx.get` (API) |
| **HIGH** | `lib/observability/tracing.py` | 264 | `httpx.post` (trace export) |
| **MEDIUM** | `lib/notifier/channels/google_chat.py` | 30, 59 | `AsyncClient()` (no timeout kwarg), `httpx.post` |

**Fix:** Add `timeout=30` (or appropriate value) to every call. The Xero token refresh at line 68 should use a shorter timeout (10s).

---

## Scan 2: `return {}` / `return []` on Failure Paths

20 locations return empty containers on failure, hiding errors as "no data." Most are in collectors and integrations.

| Severity | File | Lines | Pattern |
|----------|------|-------|---------|
| **HIGH** | `lib/collectors/chat.py` | 143, 154, 163, 293 | 4 empty returns — silent data loss during sync |
| **HIGH** | `lib/collectors/calendar.py` | 214 | `return []` — calendar events silently lost |
| **HIGH** | `lib/store.py` | 204 | `return {}` — store lookup silently fails |
| **MEDIUM** | `lib/collectors/asana.py` | 70 | `return []` — already in try/except but hides cause |
| **MEDIUM** | `lib/collectors/all_users_runner.py` | 58, 954 | `return []` and `return {}` |
| **MEDIUM** | `lib/xero_ops.py` | 69, 137 | `return []` — financial data silently lost |
| **MEDIUM** | `lib/contacts.py` | 96, 149 | `return []` and `return {}` |
| **LOW** | `lib/analyzers/attendance.py` | 470 | `return {}` |
| **LOW** | `lib/analyzers/priority.py` | 52 | `return {}` |
| **LOW** | `lib/backup.py` | 61 | `return []` |
| **LOW** | `lib/command_center.py` | 61, 284 | `return []` |
| **LOW** | `lib/intelligence/signals.py` | 764 | `return {}` |
| **LOW** | `lib/intelligence/temporal.py` | 149 | `return {}` |

**Fix:** Replace with logged errors and typed error results (or raise). Prioritize collectors first — silent data loss during sync is the worst case.

---

## Scan 3: f-string SQL in Migrations

7 migration files use f-string interpolation for ALTER TABLE / DROP VIEW. These are internal DDL with hardcoded column names (not user input), but they violate the codebase rule and aren't routed through `lib/safe_sql.py`.

| Severity | File | Line | Statement |
|----------|------|------|-----------|
| **MEDIUM** | `lib/migrations/v29_spec_alignment.py` | 164 | `f"ALTER TABLE issues_v5 ADD COLUMN {col_name} {col_type}"` |
| **MEDIUM** | `lib/migrations/v32_signal_lifecycle.py` | 93 | `f"ALTER TABLE signal_state ADD COLUMN {col_name} {col_type}"` |
| **MEDIUM** | `lib/migrations/v29_inbox_schema.py` | 70 | `f"ALTER TABLE inbox_items ADD COLUMN {col_name} {col_type}"` |
| **MEDIUM** | `lib/migrations/v4_milestone1_truth_proof.py` | 229 | `f"ALTER TABLE {table} ADD COLUMN {column} {column_def}"` |
| **MEDIUM** | `lib/migrations/add_communications_columns.py` | 47 | `f"ALTER TABLE communications ADD COLUMN {col_name} {col_type}"` |
| **LOW** | `lib/migrations/rebuild_schema_v12.py` | 364 | `f"DROP VIEW IF EXISTS {view}"` |
| **LOW** | `lib/migrations/migrate_to_spec_v12.py` | 52 | `f"DROP VIEW IF EXISTS {v}"` |

Also: `lib/safety/migrations.py` lines 124, 142, 158 use `f"DROP TRIGGER IF EXISTS {trigger_name}"` — same pattern.

**Fix:** Route through `safe_sql.py` add_column / drop_view helpers, or at minimum validate identifiers with `_validate()`.

---

## Scan 4: CI Job Gaps

| Severity | Location | Issue |
|----------|----------|-------|
| **HIGH** | `ci.yml:468-469` | `pip-audit` has `\|\| true` + `continue-on-error: true` — dependency vulns never block merges |
| **HIGH** | `ci.yml:481-482` | `pnpm audit` has `\|\| true` + `continue-on-error: true` — same for JS deps |
| **MEDIUM** | `ci.yml:492` | SBOM generation uses `\|\| true` — silent failure means stale SBOM |
| **LOW** | `ci.yml:544,550,565` | `kill $API_PID \|\| true` — expected cleanup, not a gap |
| **LOW** | `ci.yml:118` | `bandit --skip B101,B608` — B101 (assert) skip is fine, B608 skip means `safe_sql.py` findings are suppressed at CI level |

**Fix:** Remove `continue-on-error` from `pip-audit` and `pnpm audit`. These should block PRs if known vulnerabilities exist. If they're too noisy today, add an allowlist for known-accepted CVEs instead of blanket suppression.

---

## Scan 5: Test Coverage Gaps

### Collectors without tests (7 files)

| File | Risk | Notes |
|------|------|-------|
| `lib/collectors/base.py` | **HIGH** | Base class — all collectors inherit from it |
| `lib/collectors/orchestrator.py` | **HIGH** | Coordinates all collectors |
| `lib/collectors/all_users_runner.py` | **MEDIUM** | CLI multi-service runner |
| `lib/collectors/contacts.py` | **MEDIUM** | Contact sync |
| `lib/collectors/drive.py` | **MEDIUM** | Drive sync |
| `lib/collectors/recorder.py` | **LOW** | Sync recording |
| `lib/collectors/watchdog.py` | **LOW** | Health monitoring |

### Engine without tests (11 files — zero coverage)

| File | Risk |
|------|------|
| `engine/asana_client.py` | **HIGH** — just added rate limiting + 429 retry, untested |
| `engine/xero_client.py` | **HIGH** — financial API, no timeout, untested |
| `engine/discovery.py` | **MEDIUM** |
| `engine/tasks_discovery.py` | **MEDIUM** |
| `engine/chat_discovery.py` | **MEDIUM** |
| `engine/financial_pulse.py` | **MEDIUM** |
| `engine/heartbeat_pulse.py` | **MEDIUM** |
| `engine/calibration.py` | **LOW** |
| `engine/gogcli.py` | **LOW** |
| `engine/knowledge_base.py` | **LOW** |
| `engine/rules_store.py` | **LOW** |

**Fix:** Prioritize `base.py`, `orchestrator.py`, `asana_client.py`, `xero_client.py`.

---

## Scan 6: `noqa` / Suppression Audit

30 `noqa` comments found. Breakdown:

| Category | Count | Verdict |
|----------|-------|---------|
| `E402` conditional imports (signals.py, patterns.py, etc.) | 16 | **Acceptable** — conditional import pattern is deliberate |
| `PLW0603` global in db.py | 2 | **Acceptable** — migration flag pattern |
| `S311` random in resilience.py | 1 | **Acceptable** — jitter, not crypto |
| `S105` token in auth.py | 1 | **Acceptable** — localhost passthrough, documented |
| `S608` entire safe_sql.py | 1 (file-level) | **Review** — `_validate()` exists but bandit still flags 7 functions |
| `B904` entire server.py | 1 (file-level) | **Review** — suppresses "raise from" across all 149 routes |
| `E402` late imports in server.py | 4 | **Acceptable** — after middleware setup |

**Action items:**
- `api/server.py` `ruff: noqa: B904` is a blanket suppression of bare `raise` without `from`. Should be fixed per-route or the exception chains should use `raise X from e`.
- `lib/safe_sql.py` `ruff: noqa: S608` — the `_validate()` function is the mitigation, but a comment explaining the security model would be better than blanket suppression.

---

## Scan 7: B008 — Mutable Default Arguments

7 instances of `function-call-in-default-argument` (Bugbear B008). These create shared mutable defaults.

**Fix:** Replace `def f(x=SomeClass())` with `def f(x=None); if x is None: x = SomeClass()`.

---

## Scan 8: Ruff Line-Length (E501)

459 lines exceed the configured max length. These are pre-existing and not blocking CI (E501 appears to be in the ignore list or warn-only). Low priority but contributes to readability debt.

---

## Priority Actions

### Critical (blocks production reliability)

1. **Add `timeout=` to all 9 httpx calls** — `chat_interactive.py`, `xero_client.py`, `tracing.py`, `google_chat.py`. A hung external service will freeze the sync loop or notifier indefinitely.

### High (causes silent failures)

2. **Fix `return {}` / `return []` in collectors** — `chat.py` (4 locations), `calendar.py`, `store.py`. Silent data loss during sync is invisible until someone notices missing records.
3. **Remove `continue-on-error` from `pip-audit` and `pnpm audit`** — dependency vulns should block, not be silently ignored.
4. **Add tests for `base.py`, `orchestrator.py`, `asana_client.py`, `xero_client.py`** — core infrastructure and financial API with zero test coverage.

### Medium (causes friction or technical debt)

5. **Route migration f-string SQL through `safe_sql.py`** — 10 locations across 8 files.
6. **Fix `api/server.py` blanket `noqa: B904`** — add proper exception chaining per-route.
7. **Add tests for remaining engine files** — 11 files with zero coverage.

### Low (cleanup)

8. **459 E501 line-length violations** — batch cleanup when convenient.
9. **S603 subprocess findings** — 3 locations, all using list args (no `shell=True`), benign false positives but worth documenting.
