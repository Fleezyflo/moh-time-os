# Phase A2 (gmail dedupe) — verified findings & decisions

**Session:** executing-plans, 2026-05-31. Worktree `claude/fervent-germain-af8e0f` @ `8642d24` (= latest `main`).
**Status:** verification COMPLETE; `lib/schema.py` edited + verified; live-DB dedupe SQL ready
(`audit-remediation/a2_gmail_dedupe.sql`); live-DB dedupe NOT yet run (Molham's Mac); not yet committed.

## Where work happens (resolved; user: "make the call, stand by it")
Do ALL remediation in this CLEAN worktree. The main checkout `/Users/molhamhomsi/clawd/moh_time_os` is on
branch `fix/portfolio-progressive-render` (10 commits dated 2026-03; HUGE uncommitted tree incl. hundreds of
deletions). It's an abandoned/superseded 2026-03 test-fix branch (main advanced past it via PRs #108-110).
OFF-LIMITS — never edit there. Flagged for Molham.

## Two false starts this session (full honesty, both discarded)
1. I first analyzed `lib/collectors/recorder.py` and reasoned about "delete-before-insert" + an "intentional
   no-UNIQUE note", and attempted `INSERT OR IGNORE` edits there. **Wrong file** — in this worktree
   `recorder.py` is the HTTP cassette record/replay harness; it has nothing to do with gmail. (I had been
   reading the dirty main-checkout's copy.) Those edits never landed. Discarded.
2. My first distinct-key counts (participants 10,092; labels 10,078; attachments 2,891) were CONTAMINATED by
   a second heavy query running against the DB concurrently. Discarded. Clean numbers below.

## Root cause (CONFIRMED in this worktree, by reading the real files)
- Writer: `lib/collectors/gmail.py:655-707` — per thread, `self.store.insert_many("gmail_participants"|
  "gmail_attachments"|"gmail_labels", rows)`. **No delete-before-insert; pure append.**
- `self.store` = `ResilientStore(StateStore(db_path))` (gmail.py).
- `StateStore.insert_many` (state_store.py:93-110, line 103) builds SQL via `safe_sql.insert_or_replace`.
- `safe_sql.insert_or_replace` (safe_sql.py:99-106) → `INSERT OR REPLACE INTO <t> (...) VALUES (...)`.
- The gmail tables had **no UNIQUE natural-key constraint** (only `id INTEGER PK AUTOINCREMENT` + a
  non-unique `idx_<t>_message`). So `INSERT OR REPLACE` never finds a conflict → every re-collection appends.
  This EXACTLY matches the remediation's root-cause claim ("INSERT OR REPLACE degenerates to plain INSERT").

## Authoritative dedupe math (live DB, single quiescent connection, 2026-05-31)
| table | rows | distinct(natural key) | NULLs in key cols | dedupe? |
|---|---|---|---|---|
| gmail_participants | 6,133,839 | 6,823 | 0 / 0 / 0 | YES (~99.9% waste) |
| gmail_labels | 4,103,337 | 4,647 | 0 / 0 | YES (~99.9% waste) |
| gmail_attachments | 3,379,707 | **703 (stable key)** | 0 | YES (~99.98% waste) |

### CORRECTION (2026-06-01): attachments DID need deduping — my first pass got this wrong
My first measurement counted attachments distinct on a key that INCLUDED `attachment_id` and
concluded "zero duplicates, no dedupe needed." That was WRONG. Gmail regenerates
`body.attachmentId` on every fetch (`lib/collectors/gmail.py:530`), so each of ~900 re-collections
of a message produced a NEW attachment_id for the same physical file — making every row look unique.
Distinct on the STABLE key `(message_id, filename, mime_type, size_bytes)` = **703** (only 39 distinct
filenames across 1,247 messages). So attachments were the single biggest bloat (1.83 GB table), not
the "clean" table I first claimed.
Fix (a2_attachments_fix.sql): dropped the wrong 5-col UNIQUE index (it was 1.78 GB and could never
prevent re-bloat), deduped on the 4-col stable key (3,379,707 → 703), created the correct 4-col UNIQUE
index, VACUUMed. `schema.py` attachments `"unique"` is the 4-col stable key (attachment_id stored but
excluded). Final live DB: participants 6,823 / labels 4,647 / attachments 703; **file 3.24 GB → 679 MB**.

Keys (verified against live-DB `.schema`, correcting the remediation's guesses):
- participants: `(message_id, role, email)` — matches remediation. ✓
- labels: `(message_id, label_id)` — remediation guessed a `label` column that DOES NOT EXIST; real columns
  are `label_id` + `label_name`, and `label_name` is functionally determined by `label_id`
  (distinct(msg,label_id) == distinct(msg,label_id,label_name) == 4,647).
- attachments: full tuple `(message_id, filename, mime_type, size_bytes, attachment_id)`; `attachment_id`
  alone is also unique. Either way NOTHING to dedupe — the remediation's "attachments ~3.1M bloated" was wrong.

All three tables have `id INTEGER PRIMARY KEY AUTOINCREMENT` → dedupe on `MIN(id)`.

## Why UNIQUE indexes (not a writer change), and how (Option B)
With a UNIQUE natural-key index in place, the existing `INSERT OR REPLACE` does the right thing (replaces the
conflicting row instead of appending). **No collector/state_store change needed.**

Schema-engine constraints (read in `lib/schema_engine.py`):
- `build_create_table` (382-394) turns a table dict's `"unique": [cols]` into `UNIQUE(cols)` INSIDE CREATE
  TABLE — applies to FRESH DBs / test fixtures only.
- `converge()` Phase 0.5 (466-490) rebuilds a table for constraint drift ONLY when
  `_needs_constraint_rebuild()` is true, which requires a `"constraint_version" > stored` (returns False
  immediately when `constraint_version` is 0/absent). The gmail dicts have NO `constraint_version`.
- The global `INDEXES` loop (542-555, 678-680) hardcodes `CREATE INDEX IF NOT EXISTS` — it CANNOT emit a
  UNIQUE index. So `INDEXES` is not a usable path for uniqueness.

Therefore **Option B**:
1. Add `"unique": [...]` to the 3 gmail `TABLES[...]` dicts (NO `constraint_version`). Effect:
   - FRESH DBs / test fixtures get `UNIQUE(...)` in CREATE TABLE (correct going forward).
   - On the LIVE DB, `converge()` does NOT rebuild (no `constraint_version`) → no crash on existing dupes,
     and no change to the live table from the code path.
2. Protect the LIVE DB with a standalone `CREATE UNIQUE INDEX` created AFTER the dedupe, in
   `a2_gmail_dedupe.sql` (Molham's Mac).
   Net: fresh DBs enforce via table-level `UNIQUE(...)`; the live DB enforces via the named unique index.
   Functionally equivalent; both make `INSERT OR REPLACE` self-correct.

This was chosen over (a) adding a `constraint_version` (would trigger a full table rebuild that copies 6M+
rows through `INSERT OR IGNORE` — slow and risky on the live 3 GB DB) and (b) extending the `INDEXES` tuple
to support a unique flag (touches two loops + the type signature in schema_engine — larger blast radius).

## Edits made (this worktree)
- `lib/schema.py`: added `"unique"` to `TABLES["gmail_participants"]` (~1033), `["gmail_attachments"]`
  (~1049), `["gmail_labels"]` (~1063), each with a one-line comment. Verified: `py_compile` OK; `ruff check`
  passed; `git diff` = +12 lines, schema.py only. (Sandbox `ruff format` wants a trivial whitespace tweak;
  Molham runs the pinned `ruff-format` — do NOT format from the sandbox.)
- `audit-remediation/a2_gmail_dedupe.sql`: the live-DB dedupe + unique-index + VACUUM script.

## Rollout order & protected-file note
- The dedupe SQL (Molham) and the schema.py merge are independent, but BOTH must precede the Phase C daemon
  restart. (Live DB protected by the unique index; fresh DBs by the table `"unique"` key.)
- `lib/schema.py` MAY be an enforcement-protected file (the protected list lives in the private
  `Fleezyflo/enforcement` repo, not readable here; CODEOWNERS only marks `lib/safety/schema.py` +
  `docs/schema.sql`). Editing it in-branch is fine (CI restores blessed; the Enforcement Gate blocks merge if
  it differs). If the Gate fails on the PR, Molham runs the blessing workflow for `lib/schema.py`.

## Hard constraint
Do NOT restart daemon/API until Phase C2 lands. Dedupe + unique indexes must run BEFORE any restart.
