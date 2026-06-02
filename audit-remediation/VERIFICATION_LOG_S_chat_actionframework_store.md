# Verification Log — fix/chat-actionframework-store

**Session:** chat-actionframework-store (standalone fix)
**Date:** 2026-06-02
**Agent:** Claude Opus 4.8

---

## Pre-Edit Verification

For EVERY method call added or modified, one row. If any cell is "no" or blank, no commit.

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| lib/integrations/chat_commands.py | `get_action_framework()` | api/action_router.py:37 | yes — `() -> ActionFramework`, no args | yes — returns `ActionFramework`, used for `.approve_action`/`.reject_action` | yes — 7 existing callers in api/action_router.py (146,174,205,229,251,272,291) all call it argless |
| lib/integrations/chat_commands.py | `framework.approve_action(action_id, approved_by=sender_email)` | lib/actions/action_framework.py:242 | yes — `approve_action(self, action_id, approved_by, additional_context=None) -> bool` | yes — `bool`, assigned to `success` and branched on | unchanged call signature (only the framework constructor changed) |
| lib/integrations/chat_commands.py | `framework.reject_action(action_id, rejected_by=sender_email, reason=reason)` | lib/actions/action_framework.py:274 | yes — `reject_action(self, action_id, rejected_by, reason) -> bool` | yes — `bool`, assigned to `success` and branched on | unchanged call signature |
| api/chat_webhook_router.py | `get_action_framework()` | api/action_router.py:37 | yes — see above | yes — see above | yes — see above |
| api/chat_webhook_router.py | `framework.approve_action(action_id, approved_by=sender_email)` | lib/actions/action_framework.py:242 | yes | yes | unchanged call signature |
| api/chat_webhook_router.py | `framework.reject_action(action_id, rejected_by=sender_email, reason=reason)` | lib/actions/action_framework.py:274 | yes | yes | unchanged call signature |

**Root cause:** `ActionFramework.__init__(self, store, policy_engine=None, approval_policies=None, dry_run=False)` (action_framework.py:122) requires positional `store`. Four call sites constructed it with no args → `TypeError` at runtime on every Google Chat approve/reject (slash-command path AND interactive-button path).

**Fix:** Replace each `ActionFramework()` with `get_action_framework()` — the existing policy-aware singleton accessor (api/action_router.py:37) that builds `ActionFramework(store=get_store(), policy_engine=PolicyEngine(ApprovalPolicy(DEFAULT_POLICIES)), dry_run=False)`. Chosen over bare `ActionFramework(store=get_store())` because the bare form omits `policy_engine`, diverging from the REST approve/reject behavior that already uses this singleton.

**Import placement:** `from api.action_router import get_action_framework` placed INSIDE each function body (replacing the existing in-body `from lib.actions.action_framework import ActionFramework`), preserving the deferred-import pattern and avoiding any module-level cycle (chat_webhook_router imports chat_commands; api.server imports action_router).

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | "All checks passed!" |
| `ruff format --check` on changed files | PASS | "3 files already formatted" |
| `bandit -r` on changed files | PASS | 0 High, 0 Medium (67 Low are pre-existing assert-in-test, not introduced); exit 0 |
| `pytest` target class (Molham's Mac) | PASS | `TestChatCommandSenderVerification` 4 passed in 0.33s |
| `pytest` action regression suites | PASS (1 pre-existing unrelated fail) | test_auth_and_side_effects + test_action_integration + test_action_schema_fixes all pass; test_action_framework::test_reject_pending_action KeyError 'rejection_reason' is PRE-EXISTING on clean main (A-U1 schema dropped column), unrelated to construction fix |
| mypy strict-only baseline | PASS | "Strict island errors: 0 ... baseline stable" |
| Every method call in changed files resolves to a real `def` | PASS | get_action_framework@api/action_router.py:37, approve_action@action_framework.py:242, reject_action@:274 |
| Verification log included in `git add` | YES | included in commit block below |

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| fix: pass store to ActionFramework in chat approve/reject | lib/integrations/chat_commands.py, api/chat_webhook_router.py, audit-remediation/VERIFICATION_LOG_S_chat_actionframework_store.md | yes — single purpose: the no-arg ActionFramework() crash on the Google Chat approve/reject path (both slash + interactive). Not WS2. |

Single purpose. No unrelated changes.
