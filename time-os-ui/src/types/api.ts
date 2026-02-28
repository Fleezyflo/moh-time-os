// API Types - Derived from actual backend responses
// Source of truth: /api/v2/* endpoints (spec-compliant)

export interface Proposal {
  proposal_id: string;
  proposal_type: 'risk' | 'opportunity' | 'request' | 'decision_needed' | 'anomaly' | 'compliance';
  primary_ref_type: string;
  primary_ref_id: string;
  headline: string;
  impact: {
    severity: 'critical' | 'high' | 'medium' | 'low';
    signal_count: number;
    entity_type: string;
    worst_signal?: string;
  };
  score: number;
  occurrence_count: number;
  trend: 'worsening' | 'improving' | 'flat';
  status: 'open' | 'snoozed' | 'dismissed' | 'accepted';
  ui_exposure_level: string;
  first_seen_at: string;
  last_seen_at: string;
  // New hierarchy fields
  scope_level?: 'project' | 'client' | 'brand';
  scope_name?: string;
  client_id?: string;
  client_name?: string;
  client_tier?: 'A' | 'B' | 'C' | null;
  engagement_type?: 'project' | 'retainer';
  // Signal aggregation
  signal_summary?: {
    total: number;
    by_category: {
      overdue: number;
      approaching: number;
      blocked: number;
      health: number;
      financial: number;
      process: number;
      other: number;
    };
    assignee_distribution?: Record<string, number>;
    worst_urgency?: number;
  };
  score_breakdown?: {
    urgency: number;
    breadth: number;
    diversity: number;
    impact_multiplier: number;
  };
  worst_signal?: string;
  signal_count?: number;
  remaining_count?: number;
}

export interface Issue {
  // v29 format (spec-compliant)
  id: string;
  type: 'financial' | 'schedule_delivery' | 'communication' | 'risk';
  state: // v29 states
    | 'detected'
    | 'surfaced'
    | 'snoozed'
    | 'acknowledged'
    | 'addressing'
    | 'awaiting_resolution'
    | 'regression_watch'
    | 'closed'
    | 'regressed'
    // Legacy states
    | 'open'
    | 'monitoring'
    | 'awaiting'
    | 'blocked'
    | 'resolved';
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  client_id: string;
  title: string;
  evidence: string;
  created_at: string;
  updated_at: string;
  available_actions?: string[];
  // Optional fields
  brand_id?: string;
  engagement_id?: string;
  assigned_to?: string;
  suppressed?: number;
  // Legacy aliases for compatibility
  issue_id?: string;
  headline?: string;
  priority?: number;
  last_activity_at?: string;
}

export interface Client {
  id: string;
  name: string;
  tier: 'A' | 'B' | 'C' | null;
  type: string | null;
  // Financial AR fields (as returned by API)
  financial_ar_total: number | null;
  financial_ar_aging_bucket: 'current' | '30' | '60' | '90+' | null;
  // Revenue fields
  financial_annual_value: number | null;
  prior_year_revenue: number | null;
  ytd_revenue: number | null;
  lifetime_revenue: number | null;
  // Legacy field names (deprecated, use the above)
  financial_ar_outstanding?: number | null;
  financial_ar_aging?: string | null;
  // Relationship fields (static from DB)
  relationship_health: 'excellent' | 'good' | 'fair' | 'poor' | 'critical' | null;
  relationship_trend: 'improving' | 'stable' | 'declining' | null;
  relationship_last_interaction: string | null;
  created_at: string;
  updated_at: string;
  // COMPUTED health (from HealthCalculator)
  health_score: number | null; // 0-100 computed score
  health_trend: 'improving' | 'stable' | 'declining' | null;
  health_factors: {
    completion_rate?: number;
    overdue_count?: number;
    activity_score?: number;
    commitment_score?: number;
  } | null;
  computed_at_risk: boolean;
  // Task counts
  project_count?: number;
  open_task_count?: number;
  overdue_task_count?: number;
  // Legacy optional fields
  risk_level?: 'low' | 'medium' | 'high';
  posture?: string;
  open_issues?: number;
  active_projects?: number;
}

export interface TeamMember {
  id: string;
  name: string;
  email: string | null;
  role: string | null;
  department: string | null;
  company: string | null;
  type: 'internal' | 'external';
  is_internal: number; // deprecated, use type
  // Workload metrics
  open_tasks: number;
  overdue_tasks: number;
  due_today: number;
  completed_this_week: number;
  // Relationship attributes
  relationship_trust: 'unknown' | 'low' | 'medium' | 'high' | null;
  relationship_responsiveness: 'unknown' | 'slow' | 'normal' | 'fast' | null;
  // Client associations
  client_id: string | null;
  client_name: string | null;
}

export interface Task {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  priority: number;
  urgency?: string | null;
  assignee: string | null;
  assignee_id?: string | null;
  project?: string | null;
  project_id: string | null;
  client_id: string | null;
  due_date: string | null;
  source?: string | null;
  tags?: string | null;
  notes?: string | null;
  // Delegation fields
  delegated_by?: string | null;
  delegated_at?: string | null;
  delegated_note?: string | null;
  delegation_status?: string | null;
  // Escalation fields
  escalated_to?: string | null;
  escalated_to_id?: string | null;
  escalated_at?: string | null;
  escalation_reason?: string | null;
  escalation_level?: number | null;
  escalation_history?: string | null;
  // Timestamps
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  recalled_at?: string | null;
}

export interface CouplingWhy {
  shared_tasks?: number;
  shared_projects?: number;
  shared_meetings?: number;
  communication_frequency?: number;
  ar_exposure?: number;
  delivery_dependency?: number;
  [key: string]: unknown; // Allow additional fields
}

export interface Coupling {
  coupling_id: string;
  anchor_ref_type: string;
  anchor_ref_id: string;
  entity_refs: Array<{ ref_type: string; ref_id: string; label?: string }>;
  coupling_type: string;
  strength: number;
  why: CouplingWhy;
  confidence: number;
  // UI-derived fields (may not exist in API)
  coupled_type?: string;
  coupled_id?: string;
  coupled_label?: string;
  why_signals?: Array<{ signal_type: string; description: string }>;
}

export type WatcherType =
  | 'no_reply_by'
  | 'no_status_change_by'
  | 'blocker_age_exceeds'
  | 'deadline_approach'
  | 'meeting_imminent'
  | 'invoice_overdue_change';

export interface Watcher {
  issue_id: string;
  watcher_id: string;
  issue_title: string;
  watch_type: WatcherType | string; // string fallback for new types
  triggered_at: string | null;
  trigger_count: number;
  state: string;
  priority: number;
}

export interface FixData {
  identity_conflicts: Array<{
    id: string;
    display_name: string;
    source: string;
    confidence_score: number;
  }>;
  ambiguous_links: Array<{
    id: string;
    entity_type: string;
    entity_id: string;
    linked_type: string;
    linked_id: string;
    confidence: number;
  }>;
  missing_mappings: unknown[];
  total: number;
}

export interface Evidence {
  id: string;
  artifact_id: string;
  excerpt_text: string;
  context_json: string | null;
  created_at: string;
  source: string;
  artifact_type: string;
  occurred_at: string;
}

// API Response wrappers
export interface ApiListResponse<T> {
  items: T[];
  total: number;
  error?: string;
}
