# ADR-0018: Phase C Intelligence Expansion

## Status
Accepted

## Context
Phase C of audit remediation expands MOH Time OS intelligence capabilities
across four areas: adaptive thresholds, notification delivery, bidirectional
integration, and manual validation planning.

This ADR is required because `api/spec_router.py` and `api/intelligence_router.py`
are modified with new endpoints, and `lib/schema.py` adds two new tables
(notification_mutes, notification_analytics), triggering schema version increment.

## Decision

### Adaptive Thresholds (GAP-10-01 to GAP-10-04)
- ThresholdAdjuster with effectiveness-based adjustment (+-30% cap, cooldown,
  oscillation detection with freeze after 3 flip-flops)
- Seasonal modifiers driven by BusinessCalendar (Ramadan, Q4, summer)
- CalibrationReporter combining CalibrationEngine + ThresholdAdjuster output
- Two new API endpoints: /calibration/report and /calibration/briefing

### Notification Delivery (GAP-10-05 to GAP-10-07)
- EmailChannel using GmailWriter with async/sync send and HTML formatting
- Entity-level notification muting with API endpoints (mute/unmute/list)
- Delivery analytics tracking with summary endpoint
- Schema v15 -> v16: notification_mutes table, notification_analytics table

### Bidirectional Integration (GAP-10-08, GAP-10-09, GAP-10-12, GAP-10-13)
- CalendarWriter wired into CalendarHandler for Google Calendar API
- AsanaActionHandler mapping proposals to AsanaWriter calls
- sig_client_comm_gap signal with proactive email draft generation
- End-to-end integration tests for propose -> approve -> execute chain

### Manual Validation (GAP-10-11, GAP-10-14)
- CI-4.1 conversational intelligence validation test plan
- PI-5.1 contextual surfaces validation test plan

## Consequences
- Schema version increments from 15 to 16
- Two new tables added to schema: notification_mutes, notification_analytics
- New API endpoints on intelligence_router require auth token
- Seasonal modifiers are configurable via thresholds.yaml
- All external integrations (Gmail, Calendar, Asana) use lazy initialization
  and graceful degradation when credentials are unavailable
