# Brief 24: Prepared Intelligence & Contextual Readiness

## Status: DESIGNED
## Priority: P1 — The core interaction model for the system
## Dependencies: Brief 17 (Intelligence Wiring — events, persistence), Brief 18 (Intelligence Depth — entity profiles, narratives, outcome tracking), Brief 22 (Strategic Memory — decision journal, behavioral patterns), Brief 15 (Bidirectional Integrations — write-back infrastructure), Brief 23 (Predictive Foresight)

## What Brief 17/18 Provide

Brief 17 wires intelligence into the daemon cycle and creates the event system. The preparation engine (PI-1.1) consumes `intelligence_events` — when a critical signal fires, the event is written to the events table, and the preparation engine reads unconsumed events to trigger action preparation. Without Brief 17, there's no mechanism for the preparation engine to know when something happened.

Brief 18 creates entity intelligence profiles with narratives, attention levels, and recommended actions. The preparation engine uses these profiles to fill context into drafts — instead of the drafting engine having to re-query every data source, it reads the entity profile (already synthesized) and uses the narrative + recommended_actions to inform draft content and tone. Without Brief 18, every draft would need to re-aggregate data from scratch, and the contextual surfaces would have no synthesized intelligence to display.

Brief 22 provides the decision journal that captures approve/modify/dismiss decisions and feeds behavioral patterns back into preparation rules. Without Brief 22, dismissed actions can't inform future preparation.

## Problem Statement

The system collects data, detects signals, computes trajectories, and models scenarios — but all of this intelligence sits behind pages you have to navigate to and interpret yourself. When you know you need to follow up with a client, you still have to open Gmail, recall the context, and write the email from scratch. When you know a project is slipping, you still have to go to Asana and manually create or update tasks. The system tells you what's happening but doesn't prepare what you should do about it.

The right model: the system continuously observes, analyzes, and **prepares actions** — email drafts, Asana task updates, calendar event proposals, Chat messages — and presents them **in context** where they're relevant. Not in a queue. Not autonomously. In the moment you need them, ready for your approval, modification, or dismissal. Nothing dispatches without your explicit say-so.

## Success Criteria

- **Asana layer**: watch tasks in real time, surface overdue/blocked/stale items, prepare task creation and status updates, analyze project velocity — all from within MOH Time OS
- **Email drafting**: context-aware email drafts that draw on client health, payment status, communication history, and relationship tone — staged for review, never auto-sent
- **Calendar intelligence**: propose meetings based on availability patterns, suggest reschedules when conflicts arise, prepare event creation — all queued for approval
- **Chat preparation**: draft Google Chat messages for follow-ups, alerts, or team coordination — ready for review and dispatch
- **Daily intelligence briefing**: morning view that synthesizes overnight changes, predicted concerns for the week, and the 3-5 highest-priority prepared items
- **Contextual surfaces**: when viewing any entity (client, project), prepared actions relevant to that entity are visible and actionable
- **Human-in-the-loop dispatch**: every prepared action requires explicit approval (one tap to send, one tap to edit first, one tap to dismiss)
- **Preparation triggers**: system prepares actions based on signals (client gone silent → draft follow-up), predictions (deadline slipping → draft Asana update), and schedules (pre-meeting → prepare briefing)

## Scope

### Phase 1: Preparation Engine & Action Registry (PI-1.1)
Build the core engine that watches triggers (signals raised, predictions generated, schedule events) and prepares actions in a staging area. Each prepared action has: type (email/task/event/message), context (why it was prepared), content (the draft), target entity, priority, and expiry. Actions sit in staging until approved, modified, or dismissed. Dismissals feed back into the decision journal (Brief 22). Define the preparation trigger rules.

### Phase 2: Asana Intelligence Layer (PI-2.1)
Build a unified Asana interface within MOH Time OS. Not a mirror of Asana — an intelligent overlay. Surface tasks that are overdue, blocked, or stale. Show project velocity with trajectory data. Prepare task creation drafts when the system detects a need (e.g., prediction says milestone will be missed → draft a task to address the blocker). Prepare status updates when conditions change. Allow on-demand: "create a task for..." which the system drafts with full context pre-filled.

### Phase 3: Email & Communication Drafting (PI-3.1)
Build context-aware email drafting that uses everything the system knows. When a client's health drops and they haven't responded in 10 days, the system drafts a follow-up email that references the right project, uses an appropriate tone (based on communication history analysis), and addresses the actual concern. When an invoice is overdue, draft a gentle reminder that knows the client's payment pattern. When a meeting just happened, draft a follow-up summary. All on-demand or trigger-based. Calendar event proposals and Google Chat message drafts live here too.

### Phase 4: Daily Intelligence Briefing (PI-4.1)
Build the morning view. When you open the system, you see: what changed since you last looked (new signals, resolved issues, payments received), what's predicted to need attention this week (from Brief 23), and the highest-priority prepared actions ready for your review. This is your 5-minute morning scan. Each prepared action is a card: expand to see full context, one tap to approve, one tap to edit, one tap to dismiss. The briefing adapts based on your behavior (Brief 22) — things you always dismiss stop appearing.

### Phase 5: Contextual Surfaces & Pre-Meeting Briefs (PI-5.1)
Wire prepared actions into entity pages. When you view Client X, you see any pending prepared actions (draft email, suggested task). When you're about to enter a meeting (detected via calendar), the system surfaces a pre-meeting brief: client status, recent communication, outstanding items, relationship history, and any prepared talking points. Build the dispatch mechanism: approve sends via the appropriate writer (GmailWriter, AsanaWriter, CalendarWriter, ChatWriter from Brief 15). Validate end-to-end: trigger → prepare → present → approve → dispatch.

## Architecture

```
Preparation Engine:
  preparation_triggers
    ├─ signal_raised → evaluate preparation rules
    ├─ prediction_generated → evaluate preparation rules
    ├─ schedule_event → pre-meeting brief, post-meeting follow-up
    ├─ on_demand → user requests preparation
    └─ time_based → periodic check for stale items needing follow-up

  prepared_actions table
    ├─ id, created_at, expires_at
    ├─ action_type: 'email_draft' | 'asana_task' | 'asana_update' | 'calendar_event' | 'chat_message'
    ├─ trigger_type, trigger_id (what caused this to be prepared)
    ├─ entity_type, entity_id (what it's about)
    ├─ priority: 'urgent' | 'high' | 'normal' | 'low'
    ├─ status: 'staged' | 'approved' | 'modified' | 'dismissed' | 'dispatched' | 'expired'
    ├─ content JSON (the actual draft — subject, body, recipients, etc.)
    ├─ context JSON (why this was prepared — signals, predictions, history)
    ├─ dispatched_at, dispatch_result
    └─ feeds into decision_log (Brief 22) on any state change

Dispatch Layer:
  Uses existing Brief 15 writers:
    ├─ GmailWriter → send email drafts
    ├─ AsanaWriter → create/update tasks
    ├─ CalendarWriter → create events
    └─ ChatWriter → send messages

Integration Points:
  Brief 22 (Memory) → enriches prepared action context with history
  Brief 23 (Foresight) → generates prediction-based preparation triggers
  Brief 21 (Notifications) → delivers alerts about urgent prepared items
  Brief 15 (Write-back) → actual dispatch execution
```

## Task Files
- `tasks/TASK_PI_1_1_PREPARATION_ENGINE.md`
- `tasks/TASK_PI_2_1_ASANA_INTELLIGENCE.md`
- `tasks/TASK_PI_3_1_EMAIL_COMMUNICATION_DRAFTING.md`
- `tasks/TASK_PI_4_1_DAILY_INTELLIGENCE_BRIEFING.md`
- `tasks/TASK_PI_5_1_CONTEXTUAL_SURFACES_VALIDATION.md`

## Estimated Effort
Very Large — 5 tasks, ~4,000 lines total. Core preparation engine, 4 integration layers, daily briefing UI, contextual surfaces, dispatch mechanism.
