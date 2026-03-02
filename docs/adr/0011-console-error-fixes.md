# ADR-0011: Console Error Fixes (Post-Buildout)

## Status
Accepted

## Context
After the full buildout (Phases -1 through 14), the dev console shows 6 errors: a 500 on `/api/notifications/stats` (wrong column name in WHERE clause), manifest.webmanifest syntax error in dev (VitePWA not serving manifest in dev mode), service worker registration failure in dev (no sw.js in dev), deprecated `apple-mobile-web-app-capable` meta tag, and 404s on endpoints that require a server restart.

## Decision
1. Fix `server.py` notification stats endpoint: change `dismissed = 0 OR dismissed IS NULL` to `read_at IS NULL` — the `notifications` table has `read_at`, not `dismissed`
2. Add `devOptions: { enabled: true }` to VitePWA config so manifest.webmanifest is served in dev mode
3. Guard service worker registration with `import.meta.env.PROD` — VitePWA handles SW in dev when devOptions is enabled
4. Replace deprecated `apple-mobile-web-app-capable` with `mobile-web-app-capable` in index.html

## Consequences
- Notification stats endpoint returns correct counts instead of 500
- No more manifest syntax errors in dev console
- No more SW registration failures in dev console
- No deprecation warning for meta tag
- 404s for financial/detail and asana-context resolve with server restart (no code change needed)
