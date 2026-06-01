# ADR-0024: System-Map Generator — Router Prefix Resolution

## Status
Accepted

## Context
`scripts/generate_system_map.py` is the single source of truth for the system data flow
(collectors → DB tables → API routes → UI routes), consumed by the Drift Detection CI gate.
It produced a semantically wrong `docs/system-map.json`.

`get_api_routes()` recorded only the literal decorator path string and performed no prefix
resolution. For every router-mounted endpoint it ignored both the FastAPI
`app.include_router(prefix=...)` mount (declared in `api/server.py:112-120`) and the router's
own `APIRouter(prefix=...)` (declared inside each router file). Concrete effect:
`@intelligence_router.get("/signals")` was recorded as `/signals` instead of
`/api/v2/intelligence/signals`; `@action_router.post("/{action_id}/approve")` became
`/{action_id}/approve` instead of `/api/actions/{action_id}/approve`. Roughly 130 of ~270
recorded `api_routes` were prefix-stripped and could never match a real URL or a UI fetch,
defeating the drift gate's purpose of catching UI↔API mismatches.

`get_ui_api_calls()` only matched `fetch(...)` and `fetchJson|postJson(\`${API_BASE}...\`)`.
It missed `patchJson` wrappers and literal `/api/...` wrapper calls, and it never resolved
`${API_BASE}` to its value, storing raw fragments such as `/clients${qs ? '?' + qs : ''}`
that were not comparable to `api_routes`.

`scripts/generate_system_map.py` is an ADR-trigger file (`scripts/check_adr_required.sh`)
because its output gates merges; a change to its semantics shifts every recorded path.

## Decision
1. `get_api_routes()` records `mount_prefix + own_prefix + decorator_path` for router
   endpoints. The mount prefix is parsed from `app.include_router(<symbol>, prefix=...)` in
   `api/server.py`, resolving the import-alias chain (the call keys on the imported symbol,
   e.g. `from api.action_router import router as action_router`, not the module name). The
   own prefix is parsed from each router file's `APIRouter(prefix=...)` declaration
   (multi-line aware). `@app.*` routes in `api/server.py` remain absolute.
2. A phantom `/endpoint` route previously emitted from a usage example inside the
   `api/response_models.py` module docstring is no longer recorded: that module declares no
   `APIRouter`, so only `@app.*` decorators are considered there.
3. `get_ui_api_calls()` resolves `${API_BASE}` per file (`time-os-ui/src/lib/api.ts` →
   `/api/v2`, `time-os-ui/src/intelligence/api.ts` → `/api/v2/intelligence`), captures the
   `fetchJson`/`postJson`/`patchJson`/`putJson`/`delJson` wrappers and literal `/api/`
   wrapper calls (including multi-line), and strips query-string template tails while
   preserving path-parameter interpolations (`${clientId}`).
4. `docs/system-map.json` is regenerated from the corrected generator and committed. The
   `--check` drift gate is expected to change its committed baseline (the previous baseline
   matched the buggy output).
5. No `api/server.py` or router file is modified — only the generator and its artifact.

## Consequences
- `api_routes` now hold fully-qualified, request-matchable paths (e.g.
  `/api/v2/intelligence/signals`, `/api/actions/{action_id}/approve`). 129 prefix-stripped
  entries are replaced by their qualified equivalents; the lone net removal is the phantom
  docstring-derived `/endpoint` route (283 → 282 entries).
- `ui_api_calls` now hold comparable `/api*` paths, so future UI↔API drift can actually be
  detected by comparing the two lists.
- The Drift Detection gate's committed `docs/system-map.json` baseline changes in this PR by
  design; subsequent `--check` runs pass against the corrected output.
- The generator's parsing is structural (it reads `include_router`/`APIRouter`/`API_BASE`
  declarations) rather than relying on a hardcoded router-name allowlist, so newly added
  routers are resolved automatically as long as they follow the existing declaration style.
