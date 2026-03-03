# BRIEF 8: User Readiness
> Status: PENDING (starts after Brief 7: Pipeline Hardening)
> Branch: `brief/user-readiness`
> Trigger: Pipeline hardened; now remove dead weight, complete truth modules, unify aggregation, and prove production readiness

---

## Problem Statement

After Brief 7, the data layer and pipeline are solid. But the system carries dead-weight architecture and has gaps between its modules and the live API surface:

1. **Tier gating is dead code** — `feature_flags.yaml` defines Tiers 0-4 with "7 stable days" unlock criteria that nothing tracks. It's complexity for nothing. The tier system, morning brief, and Clawdbot channel must be removed entirely.

2. **Three competing aggregation systems** — `agency_snapshot.json`, `snapshot.json` (aggregator), and V5 `HealthDashboard` compute overlapping data independently. No unified output.

3. **Agency snapshot uses minimal builders** — Pages 0, 1, 7, 10, 11, 12 use stub implementations pending schema fixes (which Brief 7 completes).

4. **Truth modules exist but aren't wired** — `client_truth`, `capacity_truth`, `time_truth`, `commitment_truth` all have real implementations but no orchestrated cycle activates them together.

5. **Notifications route through Clawdbot** — must be replaced with direct Google Chat webhook delivery.

6. **Daemon never ran** — `TimeOSDaemon.run_once()` has a broken `PROJECT_ROOT` import and has never completed a cycle.

7. **Intelligence endpoints return real data** — but nobody's verified the full chain from DB → intelligence engine → API response on current data.

## Goal

`python -m lib.daemon run-once` produces a complete, validated agency snapshot using all truth modules and unified aggregation. Google Chat receives a structured notification. The API serves real intelligence data. Zero stubs, zero dead code, zero infantile abstractions.

## Approach

- **Phase 1 — Excise Dead Code**: Remove tier gating, morning brief, Clawdbot channel. Clean surgical removal with no regressions.
- **Phase 2 — Complete Truth Module Wiring**: Initialize time blocks, seed commitments, verify client health calculator, wire all 4 truth modules into a single orchestrated cycle.
- **Phase 3 — Upgrade Agency Snapshot**: Replace minimal builders with full implementations now that schema is aligned. Unify aggregator output into agency snapshot.
- **Phase 4 — Google Chat Notifications**: Build direct Google Chat webhook channel, wire into notifier engine, test delivery.
- **Phase 5 — Daemon Activation**: Fix daemon imports, wire truth cycle + snapshot + notification into run-once, execute first successful cycle.
- **Phase 6 — API Verification & End-to-End Validation**: Verify every intelligence endpoint returns real data. Full production readiness proof.

## Tasks

| Seq | Task File | Title | Phase |
|-----|-----------|-------|-------|
| 1.1 | `tasks/TASK_UR_1_1_EXCISE_TIER_SYSTEM.md` | Remove tier gating + feature_flags.yaml | 1 |
| 1.2 | `tasks/TASK_UR_1_2_EXCISE_MORNING_BRIEF.md` | Remove morning brief + Clawdbot channel | 1 |
| 2.1 | `tasks/TASK_UR_2_1_WIRE_TRUTH_MODULES.md` | Wire all 4 truth modules into orchestrated cycle | 2 |
| 2.2 | `tasks/TASK_UR_2_2_INITIALIZE_TIME_BLOCKS.md` | Initialize time blocks from calendar data | 2 |
| 2.3 | `tasks/TASK_UR_2_3_SEED_COMMITMENTS.md` | Seed commitments from existing communications | 2 |
| 3.1 | `tasks/TASK_UR_3_1_UPGRADE_SNAPSHOT_BUILDERS.md` | Replace minimal builders with full implementations | 3 |
| 3.2 | `tasks/TASK_UR_3_2_UNIFY_AGGREGATION.md` | Consolidate aggregator into agency snapshot output | 3 |
| 4.1 | `tasks/TASK_UR_4_1_GOOGLE_CHAT_NOTIFICATIONS.md` | Build Google Chat webhook notification channel | 4 |
| 5.1 | `tasks/TASK_UR_5_1_DAEMON_FIRST_CYCLE.md` | Fix daemon and run first complete cycle | 5 |
| 6.1 | `tasks/TASK_UR_6_1_API_VERIFICATION.md` | Verify all intelligence endpoints return real data | 6 |
| 6.2 | `tasks/TASK_UR_6_2_PRODUCTION_READINESS.md` | End-to-end production readiness validation | 6 |

## Constraints

- Protected files must not be modified
- All deletions require "Deletion rationale:" in commit body (per CLAUDE.md, 20+ lines)
- Tests must pass after each phase — no "we'll fix it later"
- Google Chat webhook must support dry-run mode before live delivery
- Agency snapshot must still validate against existing contracts (predicates, invariants, thresholds, schema)

## Success Criteria

- Zero references to tier gating, morning brief, or Clawdbot in codebase
- `python -m lib.daemon run-once` completes without error
- Agency snapshot passes all 4 validation gates with real data
- Google Chat receives structured notification (or dry-run log proves delivery format)
- All intelligence API endpoints return non-empty real data
- Full test suite passes (≥706 tests, 0 failures)
- Test count may decrease from removed test files — that's expected and documented
