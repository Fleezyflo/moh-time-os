# HANDOFF — TaskFlow

## What Just Happened

Session 4 completed tasks T1-T3 of Phase 02 (Authentication):
- User model and Alembic migration created
- Password hashing with argon2 implemented and tested
- Login/register API endpoints created with integration tests
- PR #6 created, all CI checks passing, auto-merge enabled

## What's Next

**Phase 02, Task T4: JWT Token Generation** (BLOCKED)

Before implementing T4, a decision is needed on token expiry strategy:
- Option A: Short-lived access tokens (15 min) + refresh tokens (7 days) — more secure, more complex
- Option B: Long-lived tokens (24 hours) — simpler, worse for token compromise

This decision affects T4 implementation, T5 (auth middleware), and later frontend storage.

**Recommendation:** Option A (short-lived + refresh). Industry standard for auth systems, especially with localStorage.

Once decided, implement:
- `backend/lib/tokens.py` — `generate_jwt()` and `decode_jwt()`
- `backend/tests/unit/test_tokens.py` — valid, expired, tampered token tests

If T4 completes, start T5 (auth middleware).

## Blockers

- BL-002: JWT token expiry strategy decision required (blocks T4)
- BL-001: Password complexity validation missing (high severity, not blocking)

## Key Rules

- Use pytest fixtures for test DB isolation (session 4 lesson)
- Always use ORM queries, never f-string SQL
- Argon2 hashing is ~100ms per call — acceptable at current scale

## Documents to Read

- `plan/phase-02.yaml` — Full task specs for Phase 02
- `sessions/session-004.yaml` — Session 4 record with discoveries and lessons
