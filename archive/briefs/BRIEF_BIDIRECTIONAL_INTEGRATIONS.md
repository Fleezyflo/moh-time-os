# Brief 15: BIDIRECTIONAL_INTEGRATIONS
> **Objective:** Transform MOH Time OS from a read-only intelligence system into an action engine — write back to Asana, Gmail, Calendar, and Google Chat. Enable the system to not just detect problems but act on them.
>
> **Why now:** After Brief 14, the system is performant and secure. Intelligence modules detect patterns, scenario modeling projects impact, resolution queue identifies actions. But nothing actually happens — the system can only notify. This brief closes the loop: detect → decide → act.

## Scope

### What This Brief Does
1. **Asana write-back** — create tasks, update status, add comments from resolution queue actions
2. **Gmail drafts** — compose follow-up emails from signal context (invoices, client risk)
3. **Calendar automation** — create review meetings, block focus time, schedule follow-ups
4. **Google Chat interactivity** — slash commands, interactive cards with action buttons, bidirectional conversation
5. **Action execution framework** — typed action system connecting resolution queue to integration writes
6. **Approval workflow** — human-in-the-loop confirmation before destructive/external actions

### What This Brief Does NOT Do
- Change collector read paths (Brief 9)
- Modify intelligence logic (Brief 11)
- Alter UI (Brief 12)

## Dependencies
- Brief 14 (PERFORMANCE_SCALE) complete — system performant under load
- Google API OAuth scopes must be upgraded from readonly to read-write

## Phase Structure

| Phase | Focus | Tasks |
|-------|-------|-------|
| 1 | Framework | BI-1.1: Action execution framework + approval workflow |
| 2 | Project Management | BI-2.1: Asana write-back (create tasks, update, comment) |
| 3 | Communication | BI-3.1: Gmail draft composition + Calendar automation |
| 4 | Chat | BI-4.1: Google Chat interactive cards + slash commands |
| 5 | Validation | BI-5.1: End-to-end action execution validation |

## Task Queue

| Seq | Task ID | Title | Status |
|-----|---------|-------|--------|
| 1 | BI-1.1 | Action Execution Framework | PENDING |
| 2 | BI-2.1 | Asana Write-Back | PENDING |
| 3 | BI-3.1 | Gmail Drafts + Calendar Automation | PENDING |
| 4 | BI-4.1 | Google Chat Interactive Mode | PENDING |
| 5 | BI-5.1 | Action Execution Validation | PENDING |

## Success Criteria
- Resolution queue actions can create Asana tasks automatically
- Invoice follow-up drafts composed in Gmail (not sent — draft only, human reviews)
- Review meetings auto-scheduled for at-risk clients
- Google Chat slash commands return live system data
- Interactive cards allow approve/dismiss actions directly from Chat
- Every external write action has audit log entry
- Human approval required for any action that modifies external systems
