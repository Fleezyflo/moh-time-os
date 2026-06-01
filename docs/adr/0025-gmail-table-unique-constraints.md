# ADR-0025: Gmail Relation Table UNIQUE Constraints

## Status
Accepted

## Context
The Gmail collector writes three relation tables — `gmail_participants`, `gmail_attachments`, and `gmail_labels` — via `state_store.insert_many`, which emits `INSERT OR REPLACE`. `INSERT OR REPLACE` only replaces an existing row when the new row conflicts on a PRIMARY KEY or UNIQUE constraint. These tables were originally declared with only a synthetic `id INTEGER PRIMARY KEY AUTOINCREMENT` and no natural-key UNIQUE constraint, so every re-collection of an already-seen message produced a fresh `id` and appended a duplicate row instead of replacing the prior one. Because the daemon re-collects messages on each cycle, the relation tables grew without bound: live data accumulated ~6.1M `gmail_participants` rows for ~6.8k distinct participants and ~4.1M `gmail_labels` rows for ~4.6k distinct labels.

The fix landed in code (`lib/schema.py`, commit `afeab3a`, "fix: add UNIQUE keys to gmail relation tables (anti-bloat)") by adding a `"unique"` natural key to each table definition, which `lib/schema_engine._build_create_sql` renders as a table-level `UNIQUE(...)` clause. The schema-building code is the source of truth; `docs/schema.sql` is a generated artifact exported from `lib/schema.TABLES` by `scripts/export_schema.py`. That artifact was not re-exported when the constraints were added, so CI Drift Detection (`scripts/export_schema.py --check`) failed on `main` (run 26744462175) reporting `docs/schema.sql` stale.

`docs/schema.sql` is an ADR-trigger file (`scripts/check_adr_required.sh`), and adding UNIQUE constraints is a schema-semantics change, so the artifact regeneration requires this ADR.

## Decision
1. Adopt the following natural-key UNIQUE constraints on the Gmail relation tables, as already declared in `lib/schema.py`:
   - `gmail_participants`: `UNIQUE(message_id, role, email)` — one row per (message, role, address).
   - `gmail_attachments`: `UNIQUE(message_id, filename, mime_type, size_bytes, attachment_id)` — the full attachment identity per message.
   - `gmail_labels`: `UNIQUE(message_id, label_id)` — one row per (message, label); `label_name` is functionally determined by `label_id`.
2. Regenerate `docs/schema.sql` from `lib/schema.TABLES` via `scripts/export_schema.py` so the published artifact reflects code truth. No collector code or schema-building code is changed by this ADR — the constraints already exist in code; only the generated artifact and this decision record are added.

## Consequences
- The Gmail collector's `INSERT OR REPLACE` now conflicts on the natural key and replaces the prior row instead of appending, making re-collection idempotent and bounding the relation tables at their distinct-row counts.
- `docs/schema.sql` matches `lib/schema.TABLES`; CI Drift Detection passes again.
- A freshly created or converged database gets the `UNIQUE(...)` clause in the table's `CREATE` statement, so idempotency holds from the first collection cycle. These three tables do not declare a `constraint_version`, so `lib/schema_engine.converge`'s constraint-drift rebuild path (gated on `constraint_version`) does not automatically rebuild a pre-existing, over-bloated copy of these tables; reclaiming the historical duplicate rows on an already-bloated database is a separate one-time cleanup, out of scope for this artifact regeneration.
- Future schema-semantics changes in `lib/schema.py` must re-run `scripts/export_schema.py` in the same change so the artifact never drifts from code.
