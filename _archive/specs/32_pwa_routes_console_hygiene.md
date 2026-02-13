# DEFECT PROMPT 032: PWA broken + routes/navigation inconsistent + noisy console

## Scope
You are fixing a **real defect cluster** in Time OS. Treat this as production code: deterministic changes, minimal surface area, no speculative refactors unless required by acceptance criteria.

## Defects covered (source: DEFECT_MANIFEST.md)
- 13.1 PWA icons/manifest paths broken (404 / invalid image)
- 13.2 Service worker (if present) not registered or stale; cache issues
- 13.3 `apple-mobile-web-app-capable` meta deprecated; wrong meta usage
- 14.1 Issues page exists but hidden/not in nav
- 14.2 Deep links break on refresh (missing SPA fallback / base)
- 14.3 Navigation labels mismatch routes; active state unreliable
- 15.1 Console noise: TypeErrors from prod build (e.g., `R.filter is not a function`)
- 15.2 Unhandled promise rejections / fetch errors not surfaced

## Goal
Make navigation coherent, Issues page reachable, PWA assets valid, and eliminate known runtime console errors by fixing root causes (not hiding them).

## Hard constraints
- **No UI stubs**: every button/route/control in this scope must either work end-to-end or be removed + replaced with a clear disabled state and inline explanation.
- Prefer small PR-sized diffs. If a refactor is required, do it as a mechanical split with identical behavior first.
- Add/repair tests where relevant (unit or integration). If not feasible, explain why and add a smoke script.
- All changes must be compatible with the existing stack (Vite + React + TS on UI, FastAPI on API).

## Deterministic plan (execute in order)
1. Fix PWA assets: validate `public/manifest*` and icon files exist, are valid PNGs, and match manifest paths; run `pnpm dev` and confirm no manifest/icon fetch errors.
2. Fix meta tags in `index.html`: replace deprecated `apple-mobile-web-app-capable` with `mobile-web-app-capable` while preserving iOS behavior.
3. Make Issues page discoverable: add it to the primary nav and ensure route exists; confirm it renders with real data and graceful empty state.
4. Harden routing: ensure Vite/SPA fallback works (dev + preview). If `base` is used, make it explicit and consistent.
5. Reproduce and eliminate `R.filter is not a function`: locate `R` import usage (likely Ramda or a util) and fix incorrect import/bundling; add a regression test or a minimal runtime guard.
6. Add global fetch error surfacing: standardized toast/banner and console logging only in dev; prevent silent failures.
7. Verify with a clean browser profile: confirm no residual service worker cache; document how to hard-refresh/clear SW for developers.

## Acceptance criteria (must be demonstrably true)
- No manifest/icon errors in DevTools Network/Console on `pnpm dev` and `pnpm preview`.
- Issues page is reachable from nav and via direct URL; refresh does not 404.
- The `R.filter` runtime error is gone at source (no try/catch masking).
- Unhandled fetch failures show a user-visible error state (not silent).
- Service worker/PWA behavior does not pin users to a stale build.

## Likely files / hotspots
- `time-os-ui/index.html`
- `time-os-ui/public/manifest.json (or equivalent)`
- `time-os-ui/public/pwa-192x192.png`
- `time-os-ui/public/pwa-512x512.png`
- `time-os-ui/src/router.tsx`
- `time-os-ui/src/**/nav*`
- `time-os-ui/vite.config.ts`

## Output
- Commit-ready code changes.
- A short note in `logs/WORKLOG.md` describing what changed and how to verify.
