# BRIEF 7: Pipeline Hardening
> Status: PENDING (starts after Brief 6: Test Remediation)
> Branch: `brief/pipeline-hardening`
> Trigger: Investigation uncovered 6 pipeline-blocking issues, missing tables, schema misalignments, and code quality violations

---

## Problem Statement

After Data Foundation (Brief 5) and Test Remediation (Brief 6), the data layer is solid and tests are green. But the **pipeline cycle** — collect → normalize → commitment_extraction → lane_assignment → gates → resolution_queue — cannot run end-to-end due to:

1. **Schema misalignments**: Code queries columns/tables that don't exist in the DB
2. **Missing tables**: `resolution_queue` and `client_identities` defined in migration code but never created
3. **Column name drift**: `lane` vs `lane_id` across 3 modules
4. **Missing columns**: `from_domain`, `client_id`, `link_status` missing from `communications`
5. **Gate data gaps**: `brand_id` populated for only 40/354 projects, blocking `project_brand_required` gate
6. **Code quality violations**: f-string SQL, hardcoded config, silent error suppression

## Root Causes

| # | Issue | Where | Impact |
|---|-------|-------|--------|
| 1 | `t.lane` queried but column is `lane_id` | lane_assigner.py:194, capacity_command_page7.py:506+ | Lane assignment + snapshot crash |
| 2 | `from_domain`, `client_id`, `link_status` missing from communications | normalizer.py:232-320 | Normalizer can't link communications to clients |
| 3 | `client_identities` table doesn't exist | normalizer.py:256 (JOIN), spec_schema_migration.py:209 | Identity matching fails |
| 4 | `resolution_queue` table doesn't exist | resolution_queue.py:46-139, spec_schema_migration.py:288 | Resolution pipeline stage crashes |
| 5 | `brand_id` only on 40/354 projects | gates.py:71-73, normalizer.py:134-215 | `project_brand_required` gate fails for 89% |
| 6 | f-string SQL in 11 files | lib/store.py, lib/entities.py, lib/items.py, etc. | SQL injection risk, code quality violation |

## Approach

- **Phase 1 — Schema Alignment**: Fix column names and add missing columns via `ALTER TABLE`
- **Phase 2 — Missing Tables**: Run the existing migration functions to create `client_identities` and `resolution_queue`
- **Phase 3 — Data Population**: Populate `brand_id` from Asana/Xero data, derive `from_domain` from `from_email`
- **Phase 4 — Code Quality**: Fix f-string SQL, hardcoded config, silent error suppression
- **Phase 5 — Pipeline Validation**: Run each pipeline stage end-to-end, verify no crashes

## Tasks

| Seq | Task File | Title | Phase |
|-----|-----------|-------|-------|
| 1.1 | `tasks/TASK_PH_1_1_FIX_LANE_COLUMN_ALIGNMENT.md` | Fix lane vs lane_id column alignment | 1 |
| 1.2 | `tasks/TASK_PH_1_2_ADD_COMMUNICATIONS_COLUMNS.md` | Add missing communications columns | 1 |
| 2.1 | `tasks/TASK_PH_2_1_CREATE_MISSING_TABLES.md` | Create client_identities + resolution_queue tables | 2 |
| 3.1 | `tasks/TASK_PH_3_1_POPULATE_BRAND_IDS.md` | Populate project brand_ids from Asana data | 3 |
| 3.2 | `tasks/TASK_PH_3_2_DERIVE_COMM_DOMAINS.md` | Derive from_domain and seed client identities | 3 |
| 4.1 | `tasks/TASK_PH_4_1_FIX_FSTRING_SQL.md` | Replace f-string SQL with parameterized queries | 4 |
| 4.2 | `tasks/TASK_PH_4_2_FIX_HARDCODED_CONFIG.md` | Extract hardcoded values to config | 4 |
| 5.1 | `tasks/TASK_PH_5_1_PIPELINE_VALIDATION.md` | End-to-end pipeline validation | 5 |

## Constraints

- All DB changes via `ALTER TABLE` or migration scripts — no DROP TABLE
- Protected files (GUARDRAILS.md list) must not be modified
- All fixes must pass existing test suite (0 regressions)
- f-string SQL fixes: only convert identifier interpolation, leave parameterized queries alone
- `--no-verify` on all git operations per CLAUDE.md

## Success Criteria

- All 5 pipeline stages run without crash on live data
- `communications` fully linked (from_domain derived, client_id populated where possible)
- `brand_id` populated for ≥90% of active projects
- Zero f-string SQL in lib/ directory
- Full test suite still passes
