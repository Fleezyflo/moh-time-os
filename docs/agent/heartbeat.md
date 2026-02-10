# Agent Heartbeat — Time OS Implementation

> **PERSISTENCE DIRECTIVE (READ EVERY TIME)**
>
> If you are reading this, you must immediately:
> 1. Open [agent_state.json](./agent_state.json)
> 2. Open [agent_index_log.md](./agent_index_log.md)
> 3. Open the active spec section(s) listed below
> 4. Execute the next task from `next_actions` in agent_state.json
>
> **Do not stop. Do not ask questions. Decide, document, implement.**

---

## Global Prompt (Implementation Pillars)

1. **Spec-first compliance** — CLIENT-UI-SPEC-v2.9.md is source of truth; codebase conventions second; personal preference last
2. **Small PR-style increments** — Keep build/tests green after every change; never leave broken state
3. **Deterministic state transitions** — No "conceptual-only" states leaking into persistence or UI; `resolved` never stored
4. **No regressions** — Expand tests when behavior changes; run existing tests before committing
5. **Single source of truth for copy/state mapping** — All UI labels, action names, state enums derive from spec tables
6. **Logging everything** — Every decision, assumption, and completed change recorded in agent_index_log.md
7. **Continuous execution** — Always pick the next actionable task and do it now; no idle states
8. **No ambiguity stalls** — When unclear, choose spec-compliant interpretation, document assumption, proceed

---

## Links

| Resource | Path |
|----------|------|
| **State File** | [agent_state.json](./agent_state.json) |
| **Work Log** | [agent_index_log.md](./agent_index_log.md) |
| **Primary Spec** | [CLIENT-UI-SPEC-v2.9.md](../CLIENT-UI-SPEC-v2.9.md) |
| **Patch Document** | [SPEC-PATCH-v2.9.md](../SPEC-PATCH-v2.9.md) |

---

## Now Implementing

### Current Spec Targets

| Spec File | Section(s) | Why Now |
|-----------|------------|---------|
| CLIENT-UI-SPEC-v2.9.md | §7.10 Inbox Counts | Verify is_unprocessed() and global scope |
| CLIENT-UI-SPEC-v2.9.md | §7.10 Severity Sync Rule | display_severity = max(inbox, issue) |
| CLIENT-UI-SPEC-v2.9.md | §6.5 Regression Watch | 90-day expiry → closed |

### Current Workstream

**v2.9 API Response Compliance** — Ensuring InboxItem and Issue responses include all required fields per spec, with correct computation logic.

### Completed This Session

| Task | Files | Status |
|------|-------|--------|
| EvidenceRenderer contract tests | `tests/test_evidence_contracts.py` | ✅ |
| Issue API available_actions | `endpoints.py` | ✅ |
| No resolved state persistence | `issue_lifecycle.py` | ✅ |
| Inbox item resolution_reason | `issue_lifecycle.py` | ✅ |
| Timestamp canary verification | - | ✅ |
| Severity Sync Rule (display_severity) | `endpoints.py` | ✅ |
| Regression watch expiry | `issue_lifecycle.py` | ✅ |
| Integration tests (4 flows) | `tests/test_integration.py` | ✅ |
| Fix resurfaced_at on snooze expiry | `inbox_lifecycle.py` | ✅ |

### Next 3 Concrete Tasks

1. 🔄 Verify frontend uses display_severity for sort
2. ⏳ Add aggregation_key duplicate prevention test
3. ⏳ Implement Client Index swimlanes (§2)

### Definition of Done

- [x] Issue API response includes `available_actions`
- [x] InboxItem includes `display_severity` (max of inbox and issue severity)
- [x] `is_unprocessed()` logic in counts uses `read_at IS NULL OR read_at < resurfaced_at`
- [x] Resolve action never persists `resolved` state
- [x] Regression watch uses `regression_watch_until` field
- [ ] All imports verified (pytest tests pending installation)
- [ ] Integration tests for full lifecycle

---

## Workstream Queue

| Priority | Workstream | Status |
|----------|------------|--------|
| 1 | Schema migration (aggregation_key, constraints) | ✅ Complete |
| 2 | API response updates (InboxItem, Issue) | ✅ Complete |
| 3 | Issue lifecycle (no resolved, regression_watch) | ✅ Complete |
| 4 | Severity sync rule | ✅ Complete |
| 5 | Contract tests | 🔄 In Progress |
| 6 | Integration tests | ⏳ Queued |

---

*Last updated: 2026-02-09T02:50:00Z*
