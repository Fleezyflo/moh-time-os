// Spec Types — CLIENT-UI-SPEC-v2.9.md
// Source of truth: /api/v2/* endpoints

// ==== Inbox Types (§7.10) ====

export type InboxItemType = 'issue' | 'flagged_signal' | 'orphan' | 'ambiguous';
export type InboxItemState = 'proposed' | 'snoozed' | 'linked_to_issue' | 'dismissed';
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export interface InboxItem {
  id: string;
  type: InboxItemType;
  state: InboxItemState;
  severity: Severity;
  display_severity: Severity;  // max(inbox.severity, issue.severity)
  proposed_at: string;
  resurfaced_at: string | null;
  attention_age_start_at: string;  // resurfaced_at ?? proposed_at
  read_at: string | null;
  resolved_at: string | null;
  snooze_until: string | null;
  snoozed_by: string | null;
  snoozed_at: string | null;
  snooze_reason: string | null;
  title: string;
  client: {
    id: string;
    name: string;
    status?: string;
  } | null;
  brand: {
    id: string;
    name: string;
  } | null;
  engagement: {
    id: string;
    name: string;
  } | null;
  evidence: Evidence;
  available_actions: string[];
  // Issue-specific fields (when type = 'issue')
  issue_category?: string;
  issue_state?: string;
  issue_assignee?: {
    id: string;
    name: string;
  };
  underlying_issue_id?: string;
  underlying_signal_id?: string;
}

export interface InboxCounts {
  scope: 'global';
  needs_attention: number;
  snoozed: number;
  snoozed_returning_soon: number;
  recently_actioned: number;
  unprocessed: number;
  unprocessed_scope: 'proposed';
  by_severity?: Record<Severity, number>;
  by_type?: Record<InboxItemType, number>;
}

export interface InboxResponse {
  counts: InboxCounts;
  items: InboxItem[];
}

// ==== Issue Types (§6.5, §7.6) ====

export type IssueState =
  | 'detected'
  | 'surfaced'
  | 'snoozed'
  | 'acknowledged'
  | 'addressing'
  | 'awaiting_resolution'
  | 'resolved'
  | 'regression_watch'
  | 'closed'
  | 'regressed';

export type IssueType = 'financial' | 'schedule_delivery' | 'communication' | 'risk';

export interface Issue {
  id: string;
  type: IssueType;
  state: IssueState;
  severity: Severity;
  client_id: string;
  brand_id: string | null;
  engagement_id: string | null;
  title: string;
  evidence: Evidence;
  evidence_version: string;
  // Timestamps
  created_at: string;
  updated_at: string;
  // Snooze fields
  snoozed_until: string | null;
  snoozed_by: string | null;
  snoozed_at: string | null;
  snooze_reason: string | null;
  // Assignment fields
  tagged_by_user_id: string | null;
  tagged_at: string | null;
  assigned_to: string | null;
  assigned_at: string | null;
  assigned_by: string | null;
  // Suppression fields
  suppressed: boolean;
  suppressed_at: string | null;
  suppressed_by: string | null;
  // Escalation fields
  escalated: boolean;
  escalated_at: string | null;
  escalated_by: string | null;
  // Regression watch
  regression_watch_until: string | null;
  // Aggregation
  aggregation_key: string;
  // Actions
  available_actions: string[];
}

// ==== Evidence Types (§6.16) ====

export type EvidenceKind =
  | 'invoice'
  | 'asana_task'
  | 'gmail_thread'
  | 'calendar_event'
  | 'minutes_analysis'
  | 'gchat_message'
  | 'xero_contact';

export interface Evidence {
  version: string;
  kind: EvidenceKind;
  url: string | null;
  display_text: string;
  source_system: string;
  source_id: string;
  payload: Record<string, unknown>;
}

export interface EvidenceLink {
  can_render_link: boolean;
  link_url: string | null;
  link_text: string;
  is_plain_text: boolean;
  additional_links: Array<{
    url: string;
    text: string;
  }>;
}

// ==== Client Types (§7.1-7.3) ====

export type ClientStatus = 'active' | 'recently_active' | 'cold';
export type Tier = 'platinum' | 'gold' | 'silver' | 'bronze' | 'none';

export interface ClientCard {
  id: string;
  name: string;
  tier: Tier;
  status: ClientStatus;
  last_invoice_date: string | null;
  first_invoice_date: string | null;
  // Active client fields
  health_score?: number;
  health_label?: string;
  issued_ytd?: number;
  issued_year?: number;
  paid_ytd?: number;
  paid_year?: number;
  ar_outstanding?: number;
  ar_overdue?: number;
  ar_overdue_pct?: number;
  open_issues_high_critical?: number;
  // Recently active fields
  issued_last_12m?: number;
  issued_prev_12m?: number;
  paid_last_12m?: number;
  paid_prev_12m?: number;
  issued_lifetime?: number;
  paid_lifetime?: number;
}

export interface ClientIndexResponse {
  active: ClientCard[];
  recently_active: ClientCard[];
  cold: ClientCard[];
  counts: {
    active: number;
    recently_active: number;
    cold: number;
  };
}

// ==== Health Types (§6.6) ====

export interface HealthScore {
  score: number | null;  // 0-100 or null if gated
  label: 'Poor' | 'Fair' | 'Good' | 'N/A';
  gating_reason: string | null;  // 'no_tasks' | 'task_linking_incomplete' | null
}

// ==== Action Request Types ====

export interface InboxActionRequest {
  action: 'tag' | 'assign' | 'snooze' | 'dismiss' | 'link' | 'create' | 'select';
  assign_to?: string;
  snooze_days?: number;
  link_engagement_id?: string;
  select_candidate_id?: string;
  note?: string;
}

export interface IssueTransitionRequest {
  action: 'acknowledge' | 'assign' | 'snooze' | 'unsnooze' | 'resolve' | 'escalate' | 'mark_awaiting';
  assigned_to?: string;
  snooze_days?: number;
  note?: string;
}

// ==== API Response Wrappers ====

export interface ApiError {
  error: string;
  message: string;
  details?: Record<string, unknown>;
}
