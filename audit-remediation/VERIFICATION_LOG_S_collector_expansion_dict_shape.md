# Verification Log — fix/collector-expansion-dict-shape

**Session:** collector-expansion-dict-shape (autonomous)
**Date:** 2026-06-02
**Agent:** Claude Opus 4.8

---

## Scope

Test-only repair. Update non-Xero `tests/test_*_collector_expansion.py` to assert the
current `CollectorResult.to_dict()` shape instead of the legacy collector result dict.

**Files edited (tests only):**
- `tests/test_chat_collector_expansion.py`
- `tests/test_asana_collector_expansion.py`
- `tests/test_gmail_collector_expansion.py`

**NOT touched:**
- `tests/test_xero_collector_expansion.py` — owned by spawned Chip A
  (memory `moh-chip-owns-xero-expansion-test`); run only as regression.
- `tests/test_calendar_collector_expansion.py` — baseline passes 0 failures; no
  assertions reference sync-result keys (verified by grep). No edit needed.
- All `lib/collectors/*.py` production files — read-only, NOT modified.

---

## Pre-Edit Verification

Source-of-truth interface = `CollectorResult.to_dict()` and each collector's `sync()`.
Every key my new assertions reference was confirmed by reading the source AND by
empirically reproducing each collector's `sync()` return dict.

| File edited | Interface depended on | Defined at (file:line) | Confirmed shape | Empirically reproduced |
|-------------|----------------------|------------------------|-----------------|------------------------|
| test_chat | `CollectorResult.to_dict()` | lib/collectors/result.py:104-142 | top-level: source/status/success/timestamp/collected/transformed/stored/duration_ms; `secondary_tables[name]` = `{"stored": int, "error": str\|None}` | yes |
| test_chat | `ChatCollector.sync()` | lib/collectors/chat.py:344-518 | returns `cr.to_dict()`; secondary keys reactions/attachments/space_metadata/space_members | yes (reactions.stored=5) |
| test_asana | `AsanaCollector.sync()` | lib/collectors/asana.py:477-653 | returns `cr.to_dict()`; emits `stored` (NOT `stored_tasks`); portfolios/goals fetch-fail → PARTIAL | yes (status=partial, stored=5/1) |
| test_asana | `AsanaCollector.collect()` portfolio/goal fetch-error path | lib/collectors/asana.py:141-167, 615-617 | unmocked list_portfolios/list_goals raise → `_secondary_fetch_errors` → secondary failures → escalate_to_partial | yes |
| test_gmail | `GmailCollector.sync()` | lib/collectors/gmail.py:584-746 | returns `result.to_dict()`; emits `stored` (NOT `stored_primary`); secondary in `secondary_tables` (NOT `stored_secondary`) | yes (success/stored=5; partial on RuntimeError) |
| test_gmail | `GmailCollector._transform_labels` | lib/collectors/gmail.py:543 | signature `(self, thread_id, message_id, label_ids)` — 3 positional args; row has thread_id/message_id/label_id/label_name | yes |
| test_gmail | `COLLECTOR_ERRORS` tuple | lib/collectors/resilience.py:35-63 | includes RuntimeError, sqlite3.Error, etc.; does NOT include bare `Exception` → test must raise a member type | yes |

### Key design facts driving the assertion rewrites

1. `to_dict()` `success` is `True` **only** when `status == SUCCESS`. PARTIAL → `success=False`
   by deliberate design (result.py:13-14, 107-114). Tests that previously asserted
   `success is True` on a partial-secondary path are asserting the OLD contract.
2. `to_dict()` serializes `secondary_tables[name]` as a nested dict `{"stored","error"}`,
   not a bare int. Legacy tests indexing `["reactions"] == 5` assume the old flat int.
3. `to_dict()` emits `stored` (primary count). Legacy `stored_tasks` / `stored_primary` /
   `stored_secondary` keys do not exist in the typed shape.
4. `_transform_labels` gained a `message_id` positional param; 2-arg test calls are stale.
5. gmail/asana `sync()` catch `COLLECTOR_ERRORS`, not bare `Exception`. A test raising bare
   `Exception` from a mocked store exercises an unreachable failure mode (real store errors
   are `sqlite3.Error`, which IS in COLLECTOR_ERRORS). Fix is test-only: raise `RuntimeError`
   (already the established pattern — see asana `test_collect_handles_subtask_pull_failures`).

---

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed test files | PASS | `All checks passed!` |
| `ruff format --check` on changed test files | PASS | `3 files already formatted` |
| `bandit -r` on changed test files | PASS | `Medium: 0, High: 0` (261 Low = B101 assert_used, expected in tests) |
| `pytest` 4 non-Xero files | PASS | chat 24, calendar 34, asana 26, gmail 34 → 118 passed |
| `pytest` xero regression (read-only) | PASS | 28 passed; file mtime predates my edits → untouched |
| Every method call in changed files resolves to a real `def` | PASS | `_transform_labels` (gmail.py:543), `sync()` (chat/asana/gmail), all to_dict keys (result.py:104-142) |
| Verification log included in `git add` | YES (in commit block) | |

**Out-of-scope pre-existing failures (NOT touched, NOT fixed here):**
`tests/test_audit_remediation_v4_implementations.py` — 4 failures from
`ImportError: cannot import name 'CollectorStatusEntry' from 'api.response_models'`.
A missing API model, unrelated to collector result-dict shape. Confirmed none of the
3 edited files reference `CollectorStatusEntry`. Left for a separate PR per
"One PR, One Purpose."

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| Single PR: collector-expansion dict-shape test repair | 3 test files + this log | yes |

---
