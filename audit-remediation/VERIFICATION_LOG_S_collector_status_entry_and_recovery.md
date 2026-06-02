# Verification Log — feat/collector-status-entry-and-recovery

**Session:** collector-status-entry-and-recovery
**Date:** 2026-06-02
**Agent:** Opus 4.8 (1M)

---

## Task framing correction

The originating task said: "tests fail with `ImportError: cannot import name 'CollectorStatusEntry'`
— add the model, that fixes the 4 tests." That diagnosis was wrong. Direct `pytest` run of the
4 named tests shows **four different root causes**:

| Named test | Actual error | Root cause |
|-----------|-------------|-----------|
| `TestSyncHealthSurfacing::test_B_collector_status_entry_model` | `ImportError: CollectorStatusEntry` | model missing |
| `TestSyncHealthSurfacing::test_B_get_status_surfaces_init_failed_collectors` | `AssertionError: assert 'xero' in {}` | `get_status()` ignores `init_failures` |
| `TestOrchestratorRecoveryLifecycle::test_B_reinit_clears_recovered_collector` | `AttributeError: no attribute 'reinit_failed_collectors'` | method missing |
| `TestOrchestratorRecoveryLifecycle::test_B_reinit_keeps_still_failing_collector` | `AttributeError: no attribute 'reinit_failed_collectors'` | method missing |

An earlier log (`VERIFICATION_LOG_S_collector_expansion_dict_shape.md:74-79`) mislabeled all 4 as the
same ImportError. Molham approved the full feature fix (all 7 tests in both classes). Scope = the
whole "sync-health surfacing + collector recovery" feature, NOT just the model.

The other 8 failures in the file (`TestStateStoreTransaction` ×5 → `StateStore.execute_write`/`transaction`
missing; `TestSchemaOwnership`/`TestEntityLinksSchemaAlignment` → `DETERMINISM VIOLATION` live-DB access)
are SEPARATE concerns, NOT in this scope, left untouched.

## Protected-files check

`api/response_models.py` and `lib/collectors/orchestrator.py` checked against
`enforcement.disconnected-20260601/protected-files.txt` (16 entries: CI workflows, scripts/, Makefile,
.pre-commit-config.yaml, pyproject.toml). Neither file is protected. Clear to edit.

---

## Pre-Edit Verification

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| api/response_models.py | `BaseModel`, `Field` | pydantic (external) | yes — same import already used at response_models.py:16 for 14 existing models | n/a | new model, no callers besides test:518/528 |
| lib/collectors/orchestrator.py (get_status) | `self.init_failures.items()` | dict attr set in `_init_collectors`/`__init__` (this change) | yes — `dict[str,str]` name→error | iterated for surfacing | producer = `_init_collectors`; consumers = get_status, tests:464/487/154 |
| lib/collectors/orchestrator.py (get_status) | `getattr(collector, "circuit_breaker", None)` | base.py:39 sets `circuit_breaker` on real collectors; test fakes (test:485 `type("Fake",(),{"sync_interval":300})`) lack it | yes — guarded with getattr, default state "closed" | n/a | callers of get_status: tests:467/503/158/169, server sync/status |
| lib/collectors/orchestrator.py (reinit_failed_collectors) | `collector_class(source_config, self.store)` | matches existing init at orchestrator.py:105 and `_FakeCollectorOK.__init__(self, config, store)` test:38 | yes — (config_dict, store) | returns collector instance | mirrors `_init_collectors`:104-108 |
| lib/collectors/orchestrator.py (_sync_impl) | `self.reinit_failed_collectors()` | orchestrator.py (this change) | yes — no args, returns still-failing dict | called for side effect | test_B_sync_impl_triggers_recovery test:192 |

### Interface facts confirmed by reading source/tests before editing

- `_init_collectors` builds collectors via `collector_map[name](source_config, self.store)` (orchestrator.py:102-108). On failure it currently only logs (line 108) — discards the error. Fix: record into `self.init_failures`.
- `collector_map` is local to `_init_collectors` (orchestrator.py:66-75). `reinit_failed_collectors` needs the same map → extract to a method/module constant so both share it (no name-guessing; building it inline in both is duplication, so I will add a `_collector_map()` helper).
- `_FakeCollectorOK.__init__(self, config, store)` (test:38), `.sync_interval` set from config (test:39); has `sync()` and `health_check()`; **no `circuit_breaker`**.
- `_FakeCollectorFail.__init__` raises `ConnectionError` (test:52). `ConnectionError` ∈ `COLLECTOR_ERRORS`? Must confirm — see below.
- `get_status()` healthy-path reads `collector.circuit_breaker.state` (orchestrator.py:295) and `collector.sync_interval` (313). Test fakes at test:485 and recovered `_FakeCollectorOK` lack `circuit_breaker` → must use `getattr`.
- Test `test_B_get_status_mixed` asserts a fake with only `sync_interval` resolves `healthy is True` (test:506) — so missing circuit_breaker must be treated as "closed".

## Drift correction (mid-session)

`lib/collectors/orchestrator.py` was refactored on disk between my first read and my
first edit (worktree drift): inline `collector_map` was already extracted to
`get_collector_map()` (collector_registry.py:285), plus a new `_core_sources_from_registry`,
`__all__`, and registry import. Re-read the whole file before editing. I did NOT need to
extract a map — instead I added `_resolve_collector_map()` (orchestrator.py:74) that takes
the registry KEY set but the class OBJECT from this module's globals, so tests patching
`lib.collectors.orchestrator.<Class>` are honored by both `_init_collectors` and
`reinit_failed_collectors`. This also fixed a latent patch-bug in `_init_collectors`.

`ConnectionError` confirmed in COLLECTOR_ERRORS (resilience.py:40) — the `_FakeCollectorFail`
init raise is caught by the `except COLLECTOR_ERRORS` clauses.

## What was actually built (full feature, Molham approved)

1. `CollectorStatusEntry` model — api/response_models.py (12 fields, healthy + init-failed states).
2. `self.init_failures` dict — initialized in `__init__`; `_init_collectors` records failures and
   clears recovered names; defensive `hasattr` guard so direct `_init_collectors()` calls (tests
   bypassing `__init__`) don't AttributeError.
3. `reinit_failed_collectors()` — retries failed collectors via `_resolve_collector_map`, moves
   recovered into self.collectors, returns still-failing dict.
4. `get_status()` — appends init-failed entries (init_failed=True/init_error); healthy entries get
   init_failed=False; `getattr` guards for missing circuit_breaker / sync_interval / init_failures
   (test doubles lack them; real collectors always have them).
5. `_sync_impl()` — calls reinit before sync-all; surfaces remaining failures under reserved
   `_init_failures` key (shape `{name: {success: False, error: msg}}`), omitted when none.
6. Test fixture repair — `test_B_get_status_mixed_healthy_and_failed` used a hardcoded 2026-03-13
   `last_success` that rotted into a staleness failure by today (2026-06-02). Replaced with a
   `datetime.now(timezone.utc)` timestamp so the "healthy = fresh data" assertion is deterministic.

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` |
| `ruff format --check` on changed files | PASS | `3 files already formatted` (wrapped 2 long Field() lines by hand to match pinned 0.15.1; did NOT run the sandbox formatter) |
| `bandit -r` on changed source files | PASS | `No issues identified. Total lines of code: 510. nosec: 0` |
| mypy strict-island baseline | PASS | `Strict island errors: 0 … baseline stable` (changed files outside strict islands) |
| `pytest` 21 relevant tests | PASS | 8 v4 target + 9 v3 contract + 3 get_status regression + 1 ws4 ex-regression → `21 passed` |
| Full v4 file | EXPECTED-PARTIAL | `7 failed, 32 passed` — 7 remaining are SEPARATE concerns (StateStore.transaction ×5, live-DB determinism ×2), NOT in scope |
| Regression sweep (10 consumer files) | PASS | baseline 61 fail → after 55 fail; set-diff regressions = EMPTY; fixed 6 pre-existing v3 tests |
| Every method call in changed files resolves to a real `def` | PASS | get_collector_map (registry:285), _core_sources_from_registry (orch:61), _resolve_collector_map (orch:74), reinit_failed_collectors (orch:158), get_sync_states (state_store:376), COLLECTOR_ERRORS (resilience:63) |
| Verification log included in `git add` | YES (in commit block) | |

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| Single PR: collector status-entry model + sync-health surfacing + recovery | api/response_models.py, lib/collectors/orchestrator.py, tests/test_audit_remediation_v4_implementations.py, this log | yes — one logical feature (v4 "Group 5 + Group 1" AND the pre-existing v3 `TestOrchestratorInitFailure` contract, which is the same feature) |

**Out of scope, NOT touched:** StateStore.transaction/execute_write (TestStateStoreTransaction ×5),
live-DB determinism violations (TestSchemaOwnership, TestEntityLinksSchemaAlignment, plus pre-existing
failures in test_autonomous_loop / test_daemon_intelligence / test_background_tasks). These were red
at baseline and remain red — different tasks.

---
