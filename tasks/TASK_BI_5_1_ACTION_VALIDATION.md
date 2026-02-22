# BI-5.1: Action Execution Validation

## Objective
End-to-end validation that the full detect → decide → act loop works: intelligence detects a pattern, resolution queue proposes an action, approval workflow fires, action executes on external system, audit log captures everything.

## Test Scenarios

### 1. Invoice Follow-Up Flow
```
Overdue invoice detected (IE-2.1 pattern)
  → Resolution item created (IE-6.1)
  → Action proposed: draft follow-up email
  → Chat notification with approve/dismiss card
  → User clicks Approve in Chat
  → Gmail draft created in Drafts folder
  → Audit log: action completed, draft_id recorded
```

### 2. Capacity Rebalancing Flow
```
Capacity crisis pattern detected (IE-2.1)
  → Resolution item: reassign tasks
  → Action proposed: create Asana task for project lead
  → User approves via dashboard resolution UI
  → Asana task created in correct project
  → Audit log: action completed, task_gid recorded
```

### 3. Client Risk Review Flow
```
Client risk pattern detected (IE-2.1)
  → Resolution item: schedule review meeting
  → Action proposed: create Calendar event
  → Chat notification with card
  → User approves
  → Calendar event created with correct attendees
  → Audit log: action completed, event_id recorded
```

### 4. Chat Command Flow
```
User types /queue in Google Chat
  → System returns card with top 5 pending items
  → User clicks Approve on item #3
  → Action executes (Asana task created)
  → Confirmation message in Chat
```

### 5. Rejection Flow
```
Action proposed → User clicks Dismiss
  → Action status = REJECTED, reason logged
  → No external write executed
  → Resolution item marked as dismissed
```

## Validation Checklist
- [ ] All 4 integration types execute successfully (Asana, Gmail, Calendar, Chat)
- [ ] Approval workflow blocks execution until approved
- [ ] Rejection prevents execution and logs reason
- [ ] Every external write has audit trail with external system ID
- [ ] Chat interactive cards work (approve/dismiss buttons)
- [ ] Slash commands return live data
- [ ] Rate limiting prevents action flood
- [ ] Failed actions don't leave partial state in external systems
- [ ] OAuth scope upgrades in place for Gmail and Calendar

## Estimated Effort
Medium — systematic testing of all flows, fixing integration issues as found
