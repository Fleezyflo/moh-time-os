# TASK: Verify NI-3.1 through NI-5.1 (email digest, history/muting, analytics)
> Brief: AUDIT_VERIFICATION | Priority: P3 | Sequence: P3.16 | Status: PENDING

## Context

Notification routing works (NI-1.1 DONE). But three sub-tasks may be incomplete.

## Instructions
1. Read `tasks/TASK_NI_3_1_EMAIL_DIGEST.md` — check if email notification channel exists in `lib/notifier/channels/`. If no email channel, this is NOT DONE.
2. Read `tasks/TASK_NI_4_1_HISTORY_MUTING.md` — check if notification history/muting exists in DB and is exposed via API.
3. Read `tasks/TASK_NI_5_1_ANALYTICS_VALIDATION.md` — check if notification analytics are tracked.
4. `ls lib/notifier/channels/` to see what channels exist
5. `grep -rn 'mute\|dismiss\|history' lib/notifier/` to check muting support

## Acceptance Criteria
- [ ] Report per sub-task: DONE or GAP
