# 08_UI_SURFACE_OPPORTUNITIES.md — UI Surface Opportunities by Domain

> Phase F Deliverable | Generated: 2026-02-04

---

## 1. DELIVERY Domain

### 1.1 Project Heatstrip (MAX 25)
- **Required Entities:** projects, tasks
- **Required Metrics:** slip_risk_score, health, completion_pct
- **Freshness:** Per cycle (~5 min)
- **Confidence:** Requires data_integrity gate
- **Drilldown:** project_id → Project Room

### 1.2 First to Break Narrative
- **Required Entities:** projects, tasks, clients
- **Required Metrics:** time_to_consequence_hours, top_driver
- **Freshness:** Per cycle
- **Confidence:** HIGH/MED/LOW indicator required
- **Drilldown:** entity_id → Entity detail

### 1.3 Overdue Tasks List
- **Required Entities:** tasks
- **Required Fields:** title, due_date, assignee, project_id
- **Freshness:** Real-time preferred
- **Confidence:** Reliable if due_date populated
- **Drilldown:** task_id → Task detail

### 1.4 Blocked Tasks Board
- **Required Entities:** tasks
- **Required Fields:** title, blockers, dependencies
- **Freshness:** Per sync
- **Confidence:** Depends on blocker data quality
- **Drilldown:** task_id → Task detail with blocker context

### 1.5 Project Health Trend
- **Required Entities:** projects, client_health_log (repurposed)
- **Required Metrics:** health over time
- **Freshness:** Daily aggregation
- **Confidence:** Requires historical data
- **Drilldown:** date → Day detail

### 1.6 Milestone Timeline
- **Required Entities:** projects
- **Required Fields:** deadline, next_milestone, next_milestone_date
- **Freshness:** On sync
- **Confidence:** Depends on deadline accuracy
- **Drilldown:** project_id → Project Room

### 1.7 Task Completion Velocity
- **Required Entities:** tasks
- **Required Fields:** status transitions over time
- **Freshness:** Daily
- **Confidence:** Requires status history
- **Drilldown:** None (aggregate view)

### 1.8 Owner Workload Distribution
- **Required Entities:** tasks, team_members
- **Required Fields:** assignee_id, duration_min
- **Freshness:** Per cycle
- **Confidence:** Requires team_members populated
- **Drilldown:** team_member_id → Person detail

### 1.9 Project Room (Selected)
- **Required Entities:** projects, tasks, communications
- **Required Fields:** All project fields, related tasks, related comms
- **Freshness:** Real-time
- **Confidence:** Full chain required
- **Drilldown:** Sub-entity details

### 1.10 Dependency Graph
- **Required Entities:** tasks
- **Required Fields:** dependencies, blockers
- **Freshness:** Per sync
- **Confidence:** Low (dependency data sparse)
- **Drilldown:** task_id → Task detail

---

## 2. CLIENTS Domain

### 2.1 Client Portfolio (MAX 25)
- **Required Entities:** clients, projects, invoices
- **Required Metrics:** health_score, ar_outstanding
- **Freshness:** Per cycle
- **Confidence:** Requires client_coverage gate
- **Drilldown:** client_id → Client 360

### 2.2 Client Health Scores
- **Required Entities:** clients
- **Required Metrics:** health_score, sub-scores (delivery, finance, responsiveness, commitments, capacity)
- **Freshness:** Per cycle
- **Confidence:** Depends on data linkage
- **Drilldown:** client_id → Score breakdown

### 2.3 Relationship Trend Indicators
- **Required Entities:** clients, client_health_log
- **Required Fields:** relationship_trend, health_score history
- **Freshness:** Daily
- **Confidence:** Requires historical data
- **Drilldown:** client_id → History view

### 2.4 VIP Alert List
- **Required Entities:** clients, people
- **Required Fields:** tier='A', is_vip=1
- **Freshness:** Real-time
- **Confidence:** Reliable if tier set
- **Drilldown:** client_id/person_id → Detail

### 2.5 Client 360 View
- **Required Entities:** clients, brands, projects, tasks, communications, invoices, commitments
- **Required Metrics:** All sub-scores, recent_change
- **Freshness:** Per cycle
- **Confidence:** Full chain required
- **Drilldown:** All sub-entities

### 2.6 Brand Breakdown
- **Required Entities:** clients, brands, projects
- **Required Fields:** brand_id, project counts
- **Freshness:** Per cycle
- **Confidence:** Reliable
- **Drilldown:** brand_id → Brand projects

### 2.7 Contact Frequency Tracker
- **Required Entities:** clients, communications
- **Required Fields:** last_interaction, contact_frequency_days
- **Freshness:** Per comm sync
- **Confidence:** Depends on comm linkage (12%)
- **Drilldown:** client_id → Comms history

### 2.8 Churn Risk Ladder
- **Required Entities:** clients
- **Required Metrics:** health_score decline, ar aging
- **Freshness:** Per cycle
- **Confidence:** MED (composite)
- **Drilldown:** client_id → Risk factors

### 2.9 Client Actions Panel
- **Required Entities:** clients
- **Required Fields:** Derived from top_driver
- **Freshness:** Per cycle
- **Confidence:** Depends on data completeness
- **Drilldown:** action → Execute flow

### 2.10 Recent Client Activity Feed
- **Required Entities:** tasks, communications, invoices
- **Required Fields:** recent changes per client
- **Freshness:** Real-time
- **Confidence:** Reliable
- **Drilldown:** activity → Source entity

---

## 3. CASH Domain

### 3.1 AR Waterfall Chart
- **Required Entities:** invoices
- **Required Fields:** amount, aging_bucket
- **Freshness:** Per Xero sync (5 min)
- **Confidence:** Requires finance_ar_coverage
- **Drilldown:** bucket → Invoice list

### 3.2 Total AR Tile
- **Required Entities:** invoices
- **Required Metrics:** total_ar
- **Freshness:** Per sync
- **Confidence:** Reliable if Xero syncing
- **Drilldown:** → AR detail view

### 3.3 Debtors Board (MAX 25)
- **Required Entities:** invoices, clients
- **Required Fields:** client_name, total_owed, aging
- **Freshness:** Per sync
- **Confidence:** Reliable
- **Drilldown:** client_id → Client AR detail

### 3.4 Collection Moves (MAX 7)
- **Required Entities:** invoices, clients
- **Required Fields:** Derived collection actions
- **Freshness:** Per cycle
- **Confidence:** Reliable
- **Drilldown:** move → Execute flow

### 3.5 Invoice Status Pipeline
- **Required Entities:** invoices
- **Required Fields:** status distribution
- **Freshness:** Per sync
- **Confidence:** Reliable
- **Drilldown:** status → Invoice list

### 3.6 Client AR Detail
- **Required Entities:** invoices, clients
- **Required Fields:** Per-client invoice breakdown
- **Freshness:** Per sync
- **Confidence:** Reliable
- **Drilldown:** invoice_id → Invoice detail

### 3.7 Payment Pattern Analysis
- **Required Entities:** invoices (paid), clients
- **Required Fields:** paid_date, issue_date
- **Freshness:** Historical
- **Confidence:** Requires paid invoice history
- **Drilldown:** client_id → Payment history

### 3.8 AR by Client Tier
- **Required Entities:** invoices, clients
- **Required Fields:** AR grouped by client.tier
- **Freshness:** Per sync
- **Confidence:** Reliable
- **Drilldown:** tier → Client list

### 3.9 Severe AR Alert
- **Required Entities:** invoices
- **Required Fields:** aging_bucket IN ('61-90','90+')
- **Freshness:** Real-time
- **Confidence:** Reliable
- **Drilldown:** invoice_id → Action options

### 3.10 Cash Flow Projection
- **Required Entities:** invoices
- **Required Fields:** due_date, amount
- **Freshness:** Per sync
- **Confidence:** LOW (no payment probability)
- **Drilldown:** date → Expected payments

---

## 4. CAPACITY Domain

### 4.1 Lane Allocation Map
- **Required Entities:** capacity_lanes, tasks
- **Required Fields:** weekly_hours, task durations by lane
- **Freshness:** Per cycle
- **Confidence:** Requires capacity_baseline gate
- **Drilldown:** lane_id → Lane tasks

### 4.2 Capacity Gap Indicator
- **Required Entities:** capacity_lanes, tasks
- **Required Metrics:** hours_needed vs hours_available
- **Freshness:** Per cycle
- **Confidence:** LOW (no real time tracking)
- **Drilldown:** lane_id → Gap breakdown

### 4.3 Person Utilization Grid
- **Required Entities:** team_members, tasks
- **Required Fields:** task assignments, durations
- **Freshness:** Per cycle
- **Confidence:** MED (estimated durations)
- **Drilldown:** team_member_id → Task list

### 4.4 Overload Alerts
- **Required Entities:** team_members, tasks
- **Required Metrics:** utilization > 100%
- **Freshness:** Per cycle
- **Confidence:** MED
- **Drilldown:** person → Reassign flow

### 4.5 Time Block Calendar (Placeholder)
- **Required Entities:** time_blocks
- **Required Fields:** date, start_time, end_time, task_id
- **Freshness:** Real-time
- **Confidence:** N/A (table empty)
- **Drilldown:** block_id → Edit block

### 4.6 Time Debt Tracker (Placeholder)
- **Required Entities:** time_debt
- **Required Fields:** lane, amount_min, reason
- **Freshness:** Per cycle
- **Confidence:** N/A (table empty)
- **Drilldown:** debt_id → Resolve flow

### 4.7 Capacity Moves (MAX 7)
- **Required Entities:** team_members, tasks
- **Required Fields:** Reassignment suggestions
- **Freshness:** Per cycle
- **Confidence:** MED
- **Drilldown:** move → Execute

### 4.8 Lane Weekly Summary
- **Required Entities:** capacity_lanes, tasks
- **Required Fields:** Weekly aggregates
- **Freshness:** Daily
- **Confidence:** MED
- **Drilldown:** lane_id → Week detail

### 4.9 Team Calendar Overlay
- **Required Entities:** events, team_events
- **Required Fields:** Event times per person
- **Freshness:** Per calendar sync
- **Confidence:** Reliable for meetings
- **Drilldown:** event_id → Event detail

### 4.10 Available Hours Finder
- **Required Entities:** events, time_blocks
- **Required Fields:** Free time slots
- **Freshness:** Real-time
- **Confidence:** LOW (no time blocks)
- **Drilldown:** slot → Schedule task

---

## 5. COMMS Domain

### 5.1 Thread Console (MAX 25)
- **Required Entities:** communications
- **Required Fields:** subject, from_email, received_at, client_id
- **Freshness:** Per Gmail sync (2 min)
- **Confidence:** Reliable for emails
- **Drilldown:** comm_id → Thread detail

### 5.2 Response Needed List
- **Required Entities:** communications
- **Required Fields:** requires_response=1
- **Freshness:** Per sync
- **Confidence:** LOW (response detection weak)
- **Drilldown:** comm_id → Reply flow

### 5.3 SLA Breach Alerts
- **Required Entities:** communications
- **Required Fields:** expected_response_by, received_at
- **Freshness:** Real-time
- **Confidence:** LOW (SLA data sparse)
- **Drilldown:** comm_id → Respond

### 5.4 Commitment Tracker
- **Required Entities:** commitments
- **Required Fields:** text, type, status, deadline
- **Freshness:** Per extraction
- **Confidence:** LOW (only 3 commitments)
- **Drilldown:** commitment_id → Update status

### 5.5 Relationship Moves (MAX 7)
- **Required Entities:** communications, clients
- **Required Fields:** Follow-up suggestions
- **Freshness:** Per cycle
- **Confidence:** MED
- **Drilldown:** move → Execute

### 5.6 Client Communication History
- **Required Entities:** communications
- **Required Fields:** Filtered by client_id
- **Freshness:** Per sync
- **Confidence:** LIMITED (12% linked)
- **Drilldown:** comm_id → Detail

### 5.7 Unlinked Communications
- **Required Entities:** communications
- **Required Fields:** link_status='unlinked'
- **Freshness:** Per cycle
- **Confidence:** Reliable
- **Drilldown:** comm_id → Link flow

### 5.8 VIP Inbox
- **Required Entities:** communications, clients
- **Required Fields:** client.tier='A' or is_vip=1
- **Freshness:** Per sync
- **Confidence:** Depends on linkage
- **Drilldown:** comm_id → Priority response

### 5.9 Commitment Breakdown by Client
- **Required Entities:** commitments, clients
- **Required Fields:** Grouped by client_id
- **Freshness:** Per extraction
- **Confidence:** LOW (sparse data)
- **Drilldown:** client_id → Commitments

### 5.10 Promise vs Request Ratio
- **Required Entities:** commitments
- **Required Fields:** type distribution
- **Freshness:** Per extraction
- **Confidence:** LOW
- **Drilldown:** type → List

---

## 6. GOVERNANCE Domain

### 6.1 Resolution Queue (MAX 50)
- **Required Entities:** resolution_queue
- **Required Fields:** entity_type, issue_type, priority
- **Freshness:** Per cycle
- **Confidence:** Reliable
- **Drilldown:** item_id → Resolve flow

### 6.2 Pending Actions List
- **Required Entities:** pending_actions
- **Required Fields:** action_type, risk_level, status
- **Freshness:** Real-time
- **Confidence:** Reliable
- **Drilldown:** action_id → Approve/Reject

### 6.3 Decision Audit Log
- **Required Entities:** decisions
- **Required Fields:** decision_type, rationale, outcome
- **Freshness:** On decision
- **Confidence:** Reliable
- **Drilldown:** decision_id → Detail

### 6.4 Data Quality Dashboard
- **Required Entities:** All gates
- **Required Fields:** Gate pass/fail, coverage %
- **Freshness:** Per cycle
- **Confidence:** Reliable
- **Drilldown:** gate → Detail

### 6.5 Sync State Monitor
- **Required Entities:** sync_state
- **Required Fields:** source, last_sync, error
- **Freshness:** Per sync
- **Confidence:** Reliable
- **Drilldown:** source → Force sync

### 6.6 Notification History
- **Required Entities:** notifications
- **Required Fields:** type, title, sent_at, read_at
- **Freshness:** Real-time
- **Confidence:** Reliable
- **Drilldown:** notification_id → Detail

### 6.7 Cycle Performance Log
- **Required Entities:** cycle_logs
- **Required Fields:** duration_ms, phase
- **Freshness:** Per cycle
- **Confidence:** Reliable
- **Drilldown:** cycle_id → Phase breakdown

### 6.8 Trust Strip
- **Required Entities:** Gates, sync_state
- **Required Fields:** Gate status, coverage, freshness
- **Freshness:** Per cycle
- **Confidence:** N/A (meta)
- **Drilldown:** gate → Detail

### 6.9 Mode Selector
- **Required Entities:** None (config)
- **Required Fields:** Current mode
- **Freshness:** N/A
- **Confidence:** N/A
- **Drilldown:** None

### 6.10 Horizon Selector
- **Required Entities:** None (config)
- **Required Fields:** Current horizon
- **Freshness:** N/A
- **Confidence:** N/A
- **Drilldown:** None

---

*End of 08_UI_SURFACE_OPPORTUNITIES.md*
