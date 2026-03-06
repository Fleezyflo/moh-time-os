# TASK: Wire Notification Intelligence and Suppression
> Brief: AUDIT_REMEDIATION | Priority: P1 | Sequence: P1.5 | Status: PENDING

## Context

Four modules related to notification intelligence exist with real code but zero imports:

1. `lib/notifier/digest.py` (400 lines) — `DigestEngine` class. Batches notifications into periodic digests instead of individual alerts.
2. `lib/intelligence/notification_intelligence.py` — `NotificationIntelligence` class, `NotificationDecision`, `NotificationBatch`, `FatigueState`. Decides whether/how/when to notify (fatigue management, channel selection). Also has `is_work_hours()` and `select_channel()` helpers.
3. `lib/intelligence/attention_tracking.py` — `AttentionTracker` class, `AttentionEvent`, `AttentionDebt`, `AttentionSummary`. Tracks attention debt — which entities haven't been reviewed.
4. `lib/intelligence/signal_suppression.py` — `SignalSuppression` class, `SuppressionRecord`, `SignalDismissStats`. Manages user dismissals and suppression rules.

## Objective

Wire these modules to make the notification system intelligent — batching, fatigue prevention, attention tracking, and suppression.

## Instructions

### 1. Wire `DigestEngine` into `lib/notifier/engine.py`

The `NotificationEngine` currently sends each notification individually. Integrate `DigestEngine` so that non-urgent notifications are batched into periodic digests.

Read `lib/notifier/engine.py` to understand the current send flow, then insert the digest batching logic.

### 2. Wire `NotificationIntelligence` into notification decisions

Before sending, check `NotificationIntelligence` to decide:
- Should this notification be sent now or deferred?
- Which channel (Google Chat, email, etc.)?
- Is the user in fatigue state?

### 3. Wire `SignalSuppression` into signal notification flow

Before notifying about a signal, check if the user has dismissed/suppressed that signal type. Filter out suppressed signals.

### 4. Wire `AttentionTracker` into `_intelligence_phase()`

After entity_memory (if P1-3 is done) or after scoring, compute attention debt per entity. This feeds into notification priority — entities with high attention debt get priority notifications.

### 5. Add API endpoint

- `/api/v2/intelligence/attention-debt` — returns entities sorted by attention debt

## Preconditions
- [ ] None (can be done independently, but benefits from P1-3 system memory)

## Validation
1. Digest batches non-urgent notifications
2. Signal suppression filters dismissed signals
3. Attention debt computed and queryable via API
4. Fatigue state prevents notification floods
5. `ruff check`, `bandit` clean on all touched files
6. `python -m pytest tests/ -x` passes

## Acceptance Criteria
- [ ] `DigestEngine` integrated into `NotificationEngine`
- [ ] `NotificationIntelligence` gates notification sends
- [ ] `SignalSuppression` filters suppressed signals
- [ ] `AttentionTracker` wired into intelligence phase
- [ ] `/api/v2/intelligence/attention-debt` endpoint exists
- [ ] ruff, bandit clean

## Output
- Modified: `lib/notifier/engine.py`, `lib/autonomous_loop.py`, `api/intelligence_router.py`

## Estimate
3 hours

## Branch
`feat/wire-notification-intelligence`
