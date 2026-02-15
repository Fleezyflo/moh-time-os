/**
 * Intelligence API Client
 * 
 * Typed functions for all intelligence layer endpoints.
 */

const API_BASE = '/api/v2/intelligence';

// =============================================================================
// TYPES
// =============================================================================

export interface ApiResponse<T> {
  status: 'ok' | 'error';
  data: T;
  computed_at: string;
  params?: Record<string, unknown>;
  error?: string;
}

export interface SignalSummary {
  total_active: number;
  by_severity: {
    critical: number;
    warning: number;
    watch: number;
  };
  by_entity_type: {
    client: number;
    project: number;
    person: number;
    portfolio: number;
  };
  new_since_last_check: number;
  escalated_recently: number;
  recently_cleared: number;
}

export interface Signal {
  signal_id: string;
  name: string;
  severity: 'critical' | 'warning' | 'watch';
  entity_type: string;
  entity_id: string;
  entity_name?: string;
  evidence: string;
  implied_action: string;
  detected_at?: string;
}

export interface Pattern {
  pattern_id: string;
  name: string;
  type: string;
  severity: 'structural' | 'operational' | 'informational';
  description: string;
  affected_entities: Array<{ type: string; id: string; name: string }>;
  implied_action: string;
  metrics?: Record<string, number>;
}

export interface Proposal {
  id: string;
  type: string;
  urgency: 'immediate' | 'this_week' | 'monitor';
  headline: string;
  summary: string;
  entity: { type: string; id: string; name: string };
  evidence: Array<{ source: string; source_id: string; description: string; data: Record<string, unknown> }>;
  implied_action: string;
  trend?: string;
  confidence?: string;
  priority_score?: {
    raw_score: number;
    rank: number;
    components: Record<string, number>;
  };
}

export interface BriefingSummary {
  total_proposals: number;
  immediate_count: number;
  this_week_count: number;
  monitor_count: number;
}

export interface Briefing {
  generated_at: string;
  summary: BriefingSummary;
  critical_items: Proposal[];
  attention_items: Proposal[];
  watching: Proposal[];
  portfolio_health: {
    overall_score: number;
    active_structural_patterns: number;
    trend: string;
  };
  top_proposal: string;
}

export interface Scorecard {
  entity_type: string;
  entity_id?: string;
  entity_name?: string;
  composite_score: number;
  dimensions: Record<string, {
    name: string;
    score: number;
    weight: number;
    status: string;
  }>;
  computed_at: string;
}

export interface CriticalItem {
  headline: string;
  entity: { type: string; id: string; name: string };
  implied_action: string;
  evidence_count: number;
  priority_score: number;
}

export interface PortfolioIntelligence {
  generated_at: string;
  portfolio_score: Scorecard;
  signal_summary: SignalSummary;
  structural_patterns: Pattern[];
  top_proposals: Array<{ headline: string; urgency: string; score: number }>;
}

export interface ClientIntelligence {
  client_id: string;
  generated_at: string;
  scorecard: Scorecard;
  active_signals: Signal[];
  signal_history: Signal[];
  trajectory: Record<string, unknown>;
  proposals: Proposal[];
}

export interface PersonIntelligence {
  person_id: string;
  generated_at: string;
  scorecard: Scorecard;
  active_signals: Signal[];
  signal_history: Signal[];
  profile: Record<string, unknown>;
}

// =============================================================================
// OPERATIONAL PROFILE TYPES (from query_engine endpoints)
// =============================================================================

/** Client deep profile from /clients/{id}/profile
 * Based on query_engine.client_deep_profile()
 */
export interface ClientProfile {
  client_id: string;
  client_name: string;
  tier?: string;
  total_invoiced?: number;
  outstanding?: number;
  ytd_revenue?: number;
  project_count?: number;
  total_tasks?: number;
  active_tasks?: number;
  entity_links_count?: number;
  // Projects from v_project_operational_state
  projects: Array<{
    project_id: string;
    project_name: string;
    project_status?: string;
    total_tasks: number;
    open_tasks: number;
    completed_tasks?: number;
    overdue_tasks: number;
    completion_rate_pct?: number;
  }>;
  // People involved (via tasks)
  people_involved: Array<{
    person_id: string;
    person_name: string;
    person_email?: string;
    role?: string;
    tasks_for_client: number;
  }>;
  // Recent invoices
  recent_invoices: Array<{
    invoice_id: string;
    amount: number;
    currency?: string;
    invoice_status: string;
    issue_date: string;
    due_date?: string;
  }>;
}

/** Person operational profile from /team/{id}/profile
 * Based on query_engine.person_operational_profile()
 */
export interface PersonProfile {
  person_id: string;
  person_name: string;
  email?: string;
  role?: string;
  assigned_tasks: number;
  active_tasks: number;
  overdue_tasks?: number;
  project_count?: number;
  // Projects with task counts (field is tasks_on_project from backend)
  projects: Array<{
    project_id: string;
    project_name: string;
    client_name: string;
    tasks_on_project: number;
  }>;
  // Clients with task counts (field is tasks_for_client from backend)
  clients: Array<{
    client_id: string;
    client_name: string;
    tasks_for_client: number;
  }>;
}

/** Project operational state from /projects/{id}/state */
export interface ProjectOperationalState {
  project_id: string;
  project_name: string;
  client_id: string;
  client_name: string;
  total_tasks: number;
  open_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  completion_rate_pct: number;
  health_score: number;
  assigned_people: number;
}

/** Trajectory data from trajectory endpoints */
export interface TrajectoryData {
  entity_id: string;
  entity_type: string;
  windows: Array<{
    start: string;
    end: string;
    metrics: Record<string, number>;
  }>;
  trends: Record<string, {
    direction: 'increasing' | 'stable' | 'declining';
    change_pct: number;
  }>;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

async function fetchJson<T>(url: string): Promise<ApiResponse<T>> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

// Primary Endpoints

export async function fetchCriticalItems(): Promise<ApiResponse<CriticalItem[]>> {
  return fetchJson(`${API_BASE}/critical`);
}

export async function fetchBriefing(): Promise<ApiResponse<Briefing>> {
  return fetchJson(`${API_BASE}/briefing`);
}

// Signals

export async function fetchSignals(quick = true): Promise<ApiResponse<{ signals: Signal[]; total_signals: number }>> {
  return fetchJson(`${API_BASE}/signals?quick=${quick}`);
}

export async function fetchSignalSummary(): Promise<ApiResponse<SignalSummary>> {
  return fetchJson(`${API_BASE}/signals/summary`);
}

export async function fetchActiveSignals(entityType?: string, entityId?: string): Promise<ApiResponse<Signal[]>> {
  const params = new URLSearchParams();
  if (entityType) params.append('entity_type', entityType);
  if (entityId) params.append('entity_id', entityId);
  const query = params.toString() ? `?${params}` : '';
  return fetchJson(`${API_BASE}/signals/active${query}`);
}

export async function fetchSignalHistory(entityType: string, entityId: string, limit = 50): Promise<ApiResponse<Signal[]>> {
  return fetchJson(`${API_BASE}/signals/history?entity_type=${entityType}&entity_id=${entityId}&limit=${limit}`);
}

// Patterns

export async function fetchPatterns(): Promise<ApiResponse<{ patterns: Pattern[]; total_detected: number }>> {
  return fetchJson(`${API_BASE}/patterns`);
}

export async function fetchPatternCatalog(): Promise<ApiResponse<Array<{
  id: string;
  name: string;
  type: string;
  severity: string;
  description: string;
  implied_action: string;
}>>> {
  return fetchJson(`${API_BASE}/patterns/catalog`);
}

// Proposals

export async function fetchProposals(limit = 20, urgency?: string): Promise<ApiResponse<Proposal[]>> {
  const params = new URLSearchParams();
  params.append('limit', String(limit));
  if (urgency) params.append('urgency', urgency);
  return fetchJson(`${API_BASE}/proposals?${params}`);
}

// Scores

export async function fetchClientScore(clientId: string): Promise<ApiResponse<Scorecard>> {
  return fetchJson(`${API_BASE}/scores/client/${clientId}`);
}

export async function fetchProjectScore(projectId: string): Promise<ApiResponse<Scorecard>> {
  return fetchJson(`${API_BASE}/scores/project/${projectId}`);
}

export async function fetchPersonScore(personId: string): Promise<ApiResponse<Scorecard>> {
  return fetchJson(`${API_BASE}/scores/person/${personId}`);
}

export async function fetchPortfolioScore(): Promise<ApiResponse<Scorecard>> {
  return fetchJson(`${API_BASE}/scores/portfolio`);
}

// Entity Intelligence (Deep Dive)

export async function fetchClientIntelligence(clientId: string): Promise<ApiResponse<ClientIntelligence>> {
  return fetchJson(`${API_BASE}/entity/client/${clientId}`);
}

export async function fetchPersonIntelligence(personId: string): Promise<ApiResponse<PersonIntelligence>> {
  return fetchJson(`${API_BASE}/entity/person/${personId}`);
}

export async function fetchPortfolioIntelligence(): Promise<ApiResponse<PortfolioIntelligence>> {
  return fetchJson(`${API_BASE}/entity/portfolio`);
}

// Entity Detail (Full Profile)
// Uses entity intelligence endpoints for full scorecard + signals + trajectory

export async function fetchClientDetail(clientId: string | number): Promise<ApiResponse<ClientIntelligence>> {
  return fetchJson(`${API_BASE}/entity/client/${clientId}`);
}

export async function fetchPersonDetail(personId: string | number): Promise<ApiResponse<PersonIntelligence>> {
  return fetchJson(`${API_BASE}/entity/person/${personId}`);
}

export async function fetchProjectDetail(projectId: string | number): Promise<ApiResponse<ProjectOperationalState>> {
  return fetchJson(`${API_BASE}/projects/${projectId}/state`);
}

// Client operational profile (lighter than full intelligence)
export async function fetchClientProfile(clientId: string | number): Promise<ApiResponse<ClientProfile>> {
  return fetchJson(`${API_BASE}/clients/${clientId}/profile`);
}

// Person operational profile (lighter than full intelligence)
export async function fetchPersonProfile(personId: string | number): Promise<ApiResponse<PersonProfile>> {
  return fetchJson(`${API_BASE}/team/${personId}/profile`);
}

// Client trajectory
export async function fetchClientTrajectory(clientId: string | number, windowDays = 30, numWindows = 6): Promise<ApiResponse<TrajectoryData>> {
  return fetchJson(`${API_BASE}/clients/${clientId}/trajectory?window_days=${windowDays}&num_windows=${numWindows}`);
}

// Person trajectory
export async function fetchPersonTrajectory(personId: string | number, windowDays = 30, numWindows = 6): Promise<ApiResponse<TrajectoryData>> {
  return fetchJson(`${API_BASE}/team/${personId}/trajectory?window_days=${windowDays}&num_windows=${numWindows}`);
}
