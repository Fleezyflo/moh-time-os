# Phase C: Intelligence Expansion

**Priority:** Ship third — new intelligence capabilities that don't exist yet.
**Estimated PRs:** 3-4 (natural splits: thresholds, notifications, bidirectional, proactive)

---

## Scope

New feature work. Every item here requires building something that doesn't exist. Depends on Phase B being complete (especially ConversationalIntelligence wiring for CI-4.1 validation).

## Work Items

### Adaptive Thresholds

**Threshold adjustment engine (GAP-10-01)**
`calibration.py` analyzes feedback but doesn't adjust `thresholds.yaml`. Build `ThresholdAdjuster`: score signal effectiveness (true positive rate, action rate), propose changes with +-30% cap per cycle, cooldown between adjustments, oscillation detection, adjustment history storage.

Files: `lib/intelligence/threshold_adjuster.py` (create) or extend `lib/calibration.py`

**Seasonal/contextual modifiers (GAP-10-02)**
BusinessCalendar knows Ramadan/Q4/summer but thresholds don't change. Create modifier functions driven by `BusinessCalendar.get_season()`. Ramadan: relax response time. Q4: tighten financials. Summer: relax activity.

Files: `lib/intelligence/threshold_adjuster.py`, `lib/intelligence/signals.py`

**Calibration reporting (GAP-10-03)**
CalibrationReporter with weekly/effectiveness/history reports. API endpoint for reports. `format_for_briefing()` for morning brief integration. Depends on GAP-10-01 and GAP-10-02.

Files: `lib/intelligence/calibration_reporter.py` (create), `api/intelligence_router.py`

**Adaptive threshold tests (GAP-10-04)**
Test suite covering: adjustment engine, seasonal modifiers, calibration reports, end-to-end signal->effectiveness->adjustment. Depends on GAP-10-01 through GAP-10-03.

Files: `tests/test_adaptive_thresholds.py` (create)

### Notifications

**Email notification channel (GAP-10-05)**
DigestEngine batches notifications but only delivers via Google Chat. Create `EmailChannel` using existing GmailWriter. Wire into NotificationEngine. Route digest-mode notifications to email.

Files: `lib/notifier/channels/email.py` (create), `lib/notifier/engine.py`, `lib/intelligence/notification_intelligence.py`

**Notification muting (GAP-10-06)**
Add notification_mutes table (entity_id, mute_until, mute_reason). Mute/unmute API endpoints. Check mute status before delivery.

Files: `lib/schema.py`, `lib/notifier/engine.py`, `api/spec_router.py`

**Notification analytics (GAP-10-07)**
Track delivery outcomes (delivered, failed, opened, acted_on). Analytics queries: delivery rate by channel, action rate by type. API endpoint.

Files: `lib/schema.py`, `lib/notifier/engine.py`, `api/intelligence_router.py`

### Bidirectional Integration

**Calendar write-back (GAP-10-08)**
No CalendarWriter exists. Create using Google Calendar API (service account delegation, same pattern as GmailWriter). Support create/update/delete events. Dry_run mode. Wire into action framework.

Files: `lib/integrations/calendar_writer.py` (create), `lib/executor/handlers/calendar.py` (create), `lib/actions/action_framework.py`

**Proposal-to-Asana pipeline (GAP-10-12)**
AsanaWriter and action_framework exist separately but aren't connected. Create AsanaActionHandler mapping proposal implied_actions (create_task, add_comment, update_status) to AsanaWriter calls. Register in action_framework.

Files: `lib/executor/handlers/asana.py` (create), `lib/actions/action_framework.py`

**Proactive email drafts (GAP-10-13)**
No intelligence trigger for "you haven't emailed Client X in 2 weeks." Add communication gap signal. Generate proposals with `implied_action="draft_email"`. EmailHandler creates drafts with context from entity profile.

Files: `lib/intelligence/signals.py`, `lib/intelligence/proposals.py`, `lib/executor/handlers/email.py`

**End-to-end action validation test (GAP-10-09)**
Integration test exercising propose -> approve -> execute -> verify across Asana/Gmail handlers in dry_run mode.

Files: `tests/test_action_integration.py` (create)

### Manual Validation (blocked on above)

**CI-4.1 conversational validation (GAP-10-11)**
After Phase B wires ConversationalIntelligence: test ambiguous queries, error responses, multi-turn context. Document results.

**PI-5.1 contextual surfaces validation (GAP-10-14)**
After proposal-to-Asana and email drafts work: verify proposals in inbox, Asana tasks created, email drafts contextually relevant. Document results.

## Verification

- [ ] Thresholds adjust based on signal effectiveness
- [ ] Seasonal modifiers apply during Ramadan, Q4, summer
- [ ] Calibration report generates with real data
- [ ] Email notifications deliver via GmailWriter
- [ ] Notification muting suppresses delivery for muted entities
- [ ] Calendar events can be created programmatically
- [ ] Proposals auto-create Asana tasks via approval flow
- [ ] Communication gaps trigger email draft proposals
- [ ] Action integration test passes end-to-end
- [ ] Conversational UI handles ambiguity and multi-turn
- [ ] All existing tests pass
