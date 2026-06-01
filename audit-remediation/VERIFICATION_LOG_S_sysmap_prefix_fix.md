# Verification Log — fix/system-map-prefix-resolution

**Session:** system-map prefix fix (ad-hoc task)
**Date:** 2026-06-01
**Agent:** Opus 4.8 (1M context)

---

## Pre-Edit Verification

Only `scripts/generate_system_map.py` was edited. The code it parses (api/server.py,
router files, UI api.ts) was READ to derive the parsing rules but NOT modified. No
runtime function calls were added to production code; the edits are self-contained
regex/string logic. Functions referenced below are the ones the new generator logic
relies on the *structure of*, verified by reading the source.

| File edited | Method/structure relied on | Defined/declared at (file:line) | Confirmed | Matches usage | Callers checked |
|-------------|----------------------------|--------------------------------|-----------|---------------|-----------------|
| scripts/generate_system_map.py | `app.include_router(symbol, prefix=...)` mounts | api/server.py:112-120 | yes | yes (mount prefixes parsed) | N/A (generator reads, does not call) |
| scripts/generate_system_map.py | `from api.X import Y [as Z]` alias imports | api/server.py:103-110 | yes | yes (alias→module map) | N/A |
| scripts/generate_system_map.py | `router = APIRouter(prefix="/actions")` | api/action_router.py:31 | yes | yes (own prefix + local var `router`) | N/A |
| scripts/generate_system_map.py | `router = APIRouter(prefix="/chat")` | api/chat_webhook_router.py:25 | yes | yes | N/A |
| scripts/generate_system_map.py | `intelligence_router = APIRouter(tags=...)` (no prefix) | api/intelligence_router.py:31 | yes | yes (own prefix "") | N/A |
| scripts/generate_system_map.py | `governance_router = APIRouter(prefix="/api/governance")` multi-line | api/governance_router.py:23-26 | yes | yes (multi-line span scan) | N/A |
| scripts/generate_system_map.py | `export_router = APIRouter(prefix="/api/governance")` multi-line | api/export_router.py:25-28 | yes | yes | N/A |
| scripts/generate_system_map.py | `spec_router`/`sse_router`/`paginated_router = APIRouter(tags=...)` | api/spec_router.py:68, sse_router.py:36, paginated_router.py:32 | yes | yes (own prefix "") | N/A |
| scripts/generate_system_map.py | `const API_BASE = ENV \|\| '/api/v2'` | time-os-ui/src/lib/api.ts:18 | yes | yes (resolve to fallback literal) | N/A |
| scripts/generate_system_map.py | `const API_BASE = '/api/v2/intelligence'` | time-os-ui/src/intelligence/api.ts:7 | yes | yes (resolve to literal) | N/A |
| scripts/generate_system_map.py | `patchJson(\`${API_BASE}/issues/${id}/resolve\`)` wrapper | time-os-ui/src/lib/api.ts:497,508 | yes | yes (verb added to regex) | N/A |
| scripts/generate_system_map.py | literal `/api/...` wrapper calls | time-os-ui/src/lib/api.ts:405,593,664,809,817,843,870 | yes | yes (absolute path branch) | N/A |
| scripts/generate_system_map.py | `@router.get("/endpoint")` is a DOCSTRING example, not a route | api/response_models.py:1-12 | yes | yes (no APIRouter → correctly ignored) | N/A |

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed file | PASS | "All checks passed!" |
| `ruff format --check` on changed file | PASS | "1 file already formatted" (ruff 0.15.1, matches pre-commit pin) |
| `bandit -r` on changed file | PASS | no findings ("BANDIT CLEAN") |
| `pytest` (3751 collected; 0 reference system-map) | PASS | no test asserts against generator output |
| `check_mypy_baseline.py --strict-only` | PASS | "Strict island errors: 0 ... baseline stable" |
| full `pre-commit run --files` (both staged) | PASS | "Sync system map ... Passed" |
| Every method call in changed file resolves | PASS | only stdlib (re, json, pathlib, argparse, sys); no new prod-interface calls |
| `generate_system_map.py --check` after regen | PASS | "docs/system-map.json is up to date" |

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| Fix system-map prefix resolution | scripts/generate_system_map.py, docs/system-map.json | yes — one purpose, generator + its regenerated artifact only |

Single concern (generator semantics + artifact). No router/server.py changes. No bundling.

---

## Result summary

- api_routes: 283 buggy rows → 282 correct rows. 129 prefix-stripped paths replaced by
  fully-qualified equivalents; 1 phantom docstring route (`/endpoint`) correctly dropped.
- Bug targets confirmed present: `/api/v2/intelligence/signals`,
  `/api/actions/{action_id}/{approve,reject,execute}`.
- 0 non-`/api` stragglers remain in api_routes (excluding `/` and `/{path:path}` SPA catch-all).
- ui_api_calls: now resolves `${API_BASE}` per file, captures `patchJson` + literal `/api/`
  wrapper calls, strips query tails. All 54 entries are fully-qualified `/api*` paths.
