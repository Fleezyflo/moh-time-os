# ADR 0026: Idempotency guards on the two destructive v12 migrations

- Status: Accepted
- Date: 2026-06-01
- Workstream: WS3 (Data-Loss Guards), step S3.2
- Finding: destructive-migrations-no-idempotency-guard (high)

## Context

`lib/migrations/migrate_to_spec_v12.py` (DROP TABLE at 167, 298, 404, 464,
513, 567, 603, 681) and `lib/migrations/rebuild_schema_v12.py:422`
unconditionally DROP TABLE + rename + INSERT...SELECT on every invocation.
A second run drops the already-migrated table and copies from the renamed
schema, which is a data-loss path. A backup is taken but recovery is manual.

The repo has a schema-version triple-mismatch (WS7.S7.1): the live DB has
`PRAGMA user_version = 23` (matching `lib/schema.py:20 SCHEMA_VERSION`), while
an orphaned `_schema_version` table holds `{3, 4001, 4004}` (written only by
the v4 milestone migrations). The two sources disagree.

## Decision

Add a self-skip guard at the top of each `run_migration()` driver that reads
`PRAGMA user_version` and returns `{"skipped": True, "reason": "already at
schema version"}` without taking a backup or touching any table when
`user_version >= schema.SCHEMA_VERSION`.

`PRAGMA user_version` is the source of truth. The `_schema_version` table is
explicitly NOT read by these guards, because it is orphaned and its values do
not reflect the real schema state. This is consistent with how
`lib/schema_engine.py:618,701` and `lib/db.py:125-129` stamp and read the
version.

## Consequences

- Re-running either migration on a current DB is now a safe no-op.
- The guard is conservative: it skips only when the DB is at or above the
  target version, so a genuine upgrade from an older version still runs.
- These migrations remain manual, developer-invoked tools (run via
  `python -m lib.migrations.migrate_to_spec_v12`); the runtime convergence
  path is `schema_engine.converge()`, which is unaffected.
- No change to the orphaned `_schema_version` table here; reconciling it is
  WS7.S7.1's job (a separate ADR).

## Addendum (S3.6): v32 ALTER+backfill made atomic

`lib/migrations/v32_signal_lifecycle.py::migrate()` added lifecycle columns
(`first_detected_at`, `initial_severity`, `peak_severity`) via `ALTER TABLE ADD
COLUMN`, committed mid-migration, then backfilled. A backfill failure left the
columns added-but-unbackfilled.

The original WS3 plan proposed simply deleting the mid-migration `conn.commit()`.
That does NOT work: under sqlite3's default deferred isolation, DDL (`ALTER`)
implicitly commits any pending transaction *before* it executes, so the column
adds are committed regardless of the mid-migration commit, and the except
handler's `conn.rollback()` cannot undo them (verified empirically: the column
survives a rollback).

The real fix: open the connection with `isolation_level=None` and wrap the
ALTER loop + backfill in a single explicit `BEGIN`/`COMMIT`, with `ROLLBACK`
(guarded for the no-active-transaction case) in the except. With an explicit
transaction the ALTERs participate in it, so a backfill failure rolls back the
column adds (verified). The optional `CREATE TABLE IF NOT EXISTS` setup commits
on its own before the `BEGIN`. The entry point is `migrate(db_path)` (there is
no `run_migration` in this module). No version-stamp change.
