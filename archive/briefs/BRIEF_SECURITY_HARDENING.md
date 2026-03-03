# Brief 13: SECURITY_HARDENING
> **Objective:** Elevate authentication from optional single-token to production-grade: scoped API keys, role-based access, rate limiting, CORS/CSP hardening, and secure credential management.
>
> **Why now:** After Brief 12, the system has a live dashboard and API serving real business intelligence. Auth is currently optional — if `INTEL_API_TOKEN` is unset, all endpoints are open. Before any real user touches this system, access control must be non-negotiable.

## Scope

### What This Brief Does
1. **API key lifecycle** — generation, rotation, expiry, revocation. Per-purpose keys (dashboard, CLI, webhook).
2. **Role-based access** — admin, operator, viewer scopes. Endpoints gated by scope.
3. **Rate limiting** — per-key throttling to prevent abuse and protect SQLite from concurrent overload.
4. **CORS & CSP** — lock dashboard origin, prevent XSS/clickjacking, secure headers.
5. **Credential management** — all secrets in env vars or encrypted config, zero hardcoded tokens.
6. **Session security** — secure cookie handling for dashboard auth, CSRF protection.

### What This Brief Does NOT Do
- Multi-tenant/multi-org isolation (future)
- OAuth2/OIDC federation (future, unless needed sooner)
- Build new features

## Dependencies
- Brief 12 (INTERFACE_EXPERIENCE) complete — dashboard and API serving live data

## Phase Structure

| Phase | Focus | Tasks |
|-------|-------|-------|
| 1 | Foundation | SH-1.1: API key management system |
| 2 | Access Control | SH-2.1: Role-based endpoint scoping |
| 3 | Protection | SH-3.1: Rate limiting + CORS/CSP hardening |
| 4 | Credentials | SH-4.1: Credential audit + secure storage |
| 5 | Validation | SH-5.1: Security validation (pen test checklist) |

## Task Queue

| Seq | Task ID | Title | Status |
|-----|---------|-------|--------|
| 1 | SH-1.1 | API Key Management System | PENDING |
| 2 | SH-2.1 | Role-Based Endpoint Scoping | PENDING |
| 3 | SH-3.1 | Rate Limiting + CORS/CSP Hardening | PENDING |
| 4 | SH-4.1 | Credential Audit & Secure Storage | PENDING |
| 5 | SH-5.1 | Security Validation | PENDING |

## Success Criteria
- No endpoint accessible without valid API key (optional auth eliminated)
- 3 roles enforced: admin (full), operator (write), viewer (read-only)
- Rate limits enforced per key (configurable, default 100 req/min)
- CORS locked to dashboard origin, CSP headers on all responses
- Zero hardcoded secrets in codebase (grep verified)
- Security checklist passes (OWASP API Top 10)
