// API client for Time OS endpoints
// Connects to FastAPI backend at /api/v2/* (spec-compliant)

import type {
  Proposal,
  Issue,
  Client,
  TeamMember,
  Task,
  Coupling,
  Watcher,
  FixData,
  Evidence,
  ApiListResponse,
} from '../types/api';

// API base URL: configurable via env, defaults to /api/v2 for spec-compliant endpoints
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';

// Current actor for mutations - configurable via env or set programmatically
let currentActor = import.meta.env.VITE_ACTOR || 'system';

export function setActor(actor: string) {
  currentActor = actor;
}

export function getActor(): string {
  return currentActor;
}

// Simple in-memory cache for API responses
interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

const cache = new Map<string, CacheEntry<unknown>>();

function getCached<T>(key: string): T | null {
  const entry = cache.get(key) as CacheEntry<T> | undefined;
  if (!entry) return null;
  if (Date.now() - entry.timestamp > entry.ttl) {
    cache.delete(key);
    return null;
  }
  return entry.data;
}

function setCache<T>(key: string, data: T, ttlMs = 30000): void {
  cache.set(key, { data, timestamp: Date.now(), ttl: ttlMs });
}

export function invalidateCache(pattern?: string): void {
  if (!pattern) {
    cache.clear();
    return;
  }
  for (const key of cache.keys()) {
    if (key.includes(pattern)) {
      cache.delete(key);
    }
  }
}

// Custom API Error with status code for granular handling
export class ApiError extends Error {
  status: number;
  statusText: string;
  isNetworkError: boolean;

  constructor(status: number, statusText: string, message?: string) {
    super(message || `API error: ${status} ${statusText}`);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.isNetworkError = false;
  }

  get isUnauthorized() {
    return this.status === 401;
  }
  get isForbidden() {
    return this.status === 403;
  }
  get isNotFound() {
    return this.status === 404;
  }
  get isServerError() {
    return this.status >= 500;
  }
  get isClientError() {
    return this.status >= 400 && this.status < 500;
  }
}

async function fetchJson<T>(url: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url);
  } catch {
    // Network error (offline, CORS, etc.)
    const apiError = new ApiError(0, 'Network Error', 'Unable to connect to server');
    apiError.isNetworkError = true;
    throw apiError;
  }

  if (!res.ok) {
    // Try to get error message from response body
    let message: string | undefined;
    try {
      const body = await res.json();
      message = body.detail || body.error || body.message;
    } catch {
      // Body not JSON or empty
    }
    throw new ApiError(res.status, res.statusText, message);
  }
  return res.json();
}

export async function fetchProposals(
  limit = 7,
  status = 'open',
  days = 7,
  clientId?: string,
  memberId?: string,
  useCache = true
): Promise<ApiListResponse<Proposal>> {
  let url = `${API_BASE}/proposals?limit=${limit}&status=${status}&days=${days}`;
  if (clientId) url += `&client_id=${encodeURIComponent(clientId)}`;
  if (memberId) url += `&member_id=${encodeURIComponent(memberId)}`;

  // Check cache
  if (useCache) {
    const cached = getCached<ApiListResponse<Proposal>>(url);
    if (cached) return cached;
  }

  const result = await fetchJson<ApiListResponse<Proposal>>(url);
  setCache(url, result, 30000); // 30s cache
  return result;
}

export async function fetchIssues(
  limit = 5,
  days = 7,
  clientId?: string,
  memberId?: string
): Promise<ApiListResponse<Issue>> {
  let url = `${API_BASE}/issues?limit=${limit}&days=${days}`;
  if (clientId) url += `&client_id=${encodeURIComponent(clientId)}`;
  if (memberId) url += `&member_id=${encodeURIComponent(memberId)}`;
  return fetchJson(url);
}

export async function fetchWatchers(hours = 24): Promise<ApiListResponse<Watcher>> {
  return fetchJson(`${API_BASE}/watchers?hours=${hours}`);
}

/** Dismiss a watcher */
export async function dismissWatcher(
  watcherId: string
): Promise<{ success: boolean; error?: string }> {
  return postJson(`${API_BASE}/watchers/${watcherId}/dismiss`, { actor: getActor() });
}

/** Snooze a watcher for N hours */
export async function snoozeWatcher(
  watcherId: string,
  hours = 24
): Promise<{ success: boolean; error?: string }> {
  return postJson(`${API_BASE}/watchers/${watcherId}/snooze`, { hours, actor: getActor() });
}

export async function fetchFixData(): Promise<FixData> {
  return fetchJson(`${API_BASE}/fix-data`);
}

export async function fetchCouplings(
  anchorType?: string,
  anchorId?: string
): Promise<ApiListResponse<Coupling>> {
  let url = `${API_BASE}/couplings`;
  if (anchorType && anchorId) {
    url += `?anchor_type=${anchorType}&anchor_id=${anchorId}`;
  }
  return fetchJson(url);
}

export async function fetchClients(): Promise<ApiListResponse<Client>> {
  return fetchJson(`${API_BASE}/clients`);
}

export async function fetchTeam(): Promise<ApiListResponse<TeamMember>> {
  return fetchJson(`${API_BASE}/team`);
}

// Proposals API
export async function fetchProposalDetail(proposalId: string): Promise<ProposalDetailResponse> {
  return fetchJson(`${API_BASE}/proposals/${proposalId}`);
}

export interface ProposalDetailResponse {
  proposal_id: string;
  proposal_type: string;
  scope_level: string;
  scope_name: string;
  client_id: string | null;
  client_name: string | null;
  client_tier: string | null;
  headline: string;
  score: number;
  score_breakdown: Record<string, unknown>;
  signal_summary: Record<string, unknown>;
  worst_signal: string;
  status: string;
  trend: string;
  first_seen_at: string;
  last_seen_at: string;
  signals: ProposalSignalDetail[];
  total_signals: number;
  affected_task_ids: string[];
  issues_url: string;
}

export interface ProposalSignalDetail {
  signal_id: string;
  signal_type: string;
  entity_type: string | null;
  entity_id: string | null;
  description: string;
  task_title: string | null;
  assignee: string | null;
  days_overdue: number | null;
  days_until: number | null;
  severity: string;
  status: string;
  detected_at: string;
  value: Record<string, unknown>;
}

// Tasks API (v2 -- returns {items:[...], total} natively)
export async function fetchTasks(
  _assignee?: string,
  _status?: string,
  _project?: string,
  limit = 50
): Promise<ApiListResponse<Task>> {
  return fetchJson(`${API_BASE}/priorities?limit=${limit}`);
}

export async function fetchEvidence(
  entityType: string,
  entityId: string
): Promise<ApiListResponse<Evidence>> {
  return fetchJson(`${API_BASE}/evidence/${entityType}/${entityId}`);
}

export async function fetchAllCouplings(): Promise<ApiListResponse<Coupling>> {
  return fetchJson(`${API_BASE}/couplings`);
}

// ==== Client Detail Endpoints (spec_router /api/v2/clients*) ====

/** Full client detail from GET /api/v2/clients/{clientId} */
export async function fetchClientDetail(clientId: string): Promise<Record<string, unknown>> {
  return fetchJson(`${API_BASE}/clients/${clientId}`);
}

/** Client team involvement from GET /api/v2/clients/{clientId}/team */
export async function fetchClientTeam(
  clientId: string
): Promise<{ items: Record<string, unknown>[]; total: number }> {
  return fetchJson(`${API_BASE}/clients/${clientId}/team`);
}

/** Client invoices from GET /api/v2/clients/{clientId}/invoices */
export async function fetchClientInvoices(
  clientId: string
): Promise<{ items: Record<string, unknown>[]; total: number }> {
  return fetchJson(`${API_BASE}/clients/${clientId}/invoices`);
}

/** Client AR aging from GET /api/v2/clients/{clientId}/ar-aging */
export async function fetchClientARAging(clientId: string): Promise<Record<string, unknown>> {
  return fetchJson(`${API_BASE}/clients/${clientId}/ar-aging`);
}

// ==== Team Workload Endpoint (server.py /api/team/workload) ====

export interface TeamWorkloadMember {
  name: string;
  total: number;
  overdue: number;
  due_today: number;
  avg_priority: number;
  status: 'overloaded' | 'busy' | 'available';
}

/** Team workload distribution from GET /api/team/workload */
export async function fetchTeamWorkload(): Promise<{ team: TeamWorkloadMember[] }> {
  return fetchJson('/api/team/workload');
}

// ==== Inbox Endpoints (spec_router /api/v2/inbox*) ====

import type { InboxResponse, InboxCounts, InboxItemType, Severity } from '../types/spec';

/** Inbox filter options for GET /api/v2/inbox */
export interface InboxFilters {
  state?: 'proposed' | 'snoozed';
  type?: InboxItemType;
  severity?: Severity;
  client_id?: string;
  unread_only?: boolean;
  sort?: 'severity' | 'age' | 'age_desc' | 'client';
}

/** Fetch inbox items with optional filters */
export async function fetchInbox(filters: InboxFilters = {}): Promise<InboxResponse> {
  const params = new URLSearchParams();
  if (filters.state) params.set('state', filters.state);
  if (filters.type) params.set('type', filters.type);
  if (filters.severity) params.set('severity', filters.severity);
  if (filters.client_id) params.set('client_id', filters.client_id);
  if (filters.unread_only) params.set('unread_only', 'true');
  if (filters.sort) params.set('sort', filters.sort);
  const qs = params.toString();
  return fetchJson(`${API_BASE}/inbox${qs ? `?${qs}` : ''}`);
}

/** Fetch inbox counts (cacheable, always global scope) */
export async function fetchInboxCounts(): Promise<InboxCounts> {
  return fetchJson(`${API_BASE}/inbox/counts`);
}

/** Fetch recently actioned inbox items */
export async function fetchInboxRecent(days = 7, type?: InboxItemType): Promise<InboxResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (type) params.set('type', type);
  return fetchJson(`${API_BASE}/inbox/recent?${params.toString()}`);
}

/** Execute action on inbox item */
export async function executeInboxAction(
  itemId: string,
  action: string,
  payload: Record<string, unknown> = {},
  actor = getActor()
): Promise<{ success: boolean; error?: string }> {
  return postJson(`${API_BASE}/inbox/${itemId}/action?actor=${encodeURIComponent(actor)}`, {
    action,
    ...payload,
  });
}

// ==== Portfolio / Client Health Endpoints (server.py) ====

/** Portfolio overview: tier breakdown, health stats, at-risk clients, totals, overdue AR */
export interface PortfolioOverview {
  by_tier: Array<{ tier: string; count: number; total_ar: number; at_risk: number }>;
  by_health: Array<{ health: string; count: number }>;
  at_risk: Array<Record<string, unknown>>;
  totals: { total_clients: number; total_ar: number; total_annual_value: number };
  overdue_ar: { count: number; total: number };
}

export async function fetchPortfolioOverview(): Promise<PortfolioOverview> {
  return fetchJson('/api/clients/portfolio');
}

/** At-risk client from /api/clients/at-risk */
export interface AtRiskClient {
  client_id: string;
  name: string;
  health_score: number;
  trend?: string;
  factors?: Record<string, unknown>;
}

export async function fetchPortfolioRisks(
  threshold = 50
): Promise<{ threshold: number; clients: AtRiskClient[]; total: number }> {
  return fetchJson(`/api/clients/at-risk?threshold=${threshold}`);
}

/** Client health item from /api/clients/health */
export interface ClientHealthItem {
  client_id: string;
  name: string;
  health_score: number;
  tier?: string;
  trend?: string;
  at_risk?: boolean;
  factors?: Record<string, unknown>;
}

export async function fetchClientsHealth(): Promise<{
  clients: ClientHealthItem[];
  total: number;
}> {
  return fetchJson('/api/clients/health');
}

// ==== Mutation Endpoints ====

async function postJson<T>(url: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

/** Tag a proposal to create an Issue */
export async function tagProposal(
  proposalId: string,
  actor = getActor()
): Promise<{ success: boolean; issue?: Issue; error?: string }> {
  const result = await postJson<{ success: boolean; issue?: Issue; error?: string }>(
    `${API_BASE}/issues`,
    { proposal_id: proposalId, actor }
  );
  if (result.success) invalidateCache('proposals');
  return result;
}

/** Snooze a proposal for N days */
export async function snoozeProposal(
  proposalId: string,
  days = 7
): Promise<{ success: boolean; error?: string }> {
  const result = await postJson<{ success: boolean; error?: string }>(
    `${API_BASE}/proposals/${proposalId}/snooze`,
    { days }
  );
  if (result.success) invalidateCache('proposals');
  return result;
}

/** Dismiss a proposal */
export async function dismissProposal(
  proposalId: string,
  reason = 'Dismissed by user'
): Promise<{ success: boolean; error?: string }> {
  const result = await postJson<{ success: boolean; error?: string }>(
    `${API_BASE}/proposals/${proposalId}/dismiss`,
    { reason }
  );
  if (result.success) invalidateCache('proposals');
  return result;
}

/** Resolve a fix-data item */
export async function resolveFixDataItem(
  itemType: 'identity' | 'link',
  itemId: string,
  resolution = 'manually_resolved'
): Promise<{ success: boolean; error?: string }> {
  return postJson(`${API_BASE}/fix-data/${itemType}/${itemId}/resolve`, {
    resolution,
    actor: getActor(),
  });
}

/** Resolve an issue */
export async function resolveIssue(
  issueId: string,
  resolution = 'manually_resolved'
): Promise<{ success: boolean; issue_id?: string; state?: string; error?: string }> {
  return patchJson(`${API_BASE}/issues/${issueId}/resolve`, { resolution, actor: getActor() });
}

/** Change issue state */
export type IssueState = 'open' | 'monitoring' | 'awaiting' | 'blocked' | 'resolved' | 'closed';

export async function changeIssueState(
  issueId: string,
  newState: IssueState,
  reason?: string
): Promise<{ success: boolean; issue_id?: string; state?: string; error?: string }> {
  return patchJson(`${API_BASE}/issues/${issueId}/state`, {
    state: newState,
    reason,
    actor: getActor(),
  });
}

/** Block an issue */
export async function blockIssue(
  issueId: string,
  reason: string
): Promise<{ success: boolean; issue_id?: string; state?: string; error?: string }> {
  return changeIssueState(issueId, 'blocked', reason);
}

/** Unblock an issue (set to open) */
export async function unblockIssue(
  issueId: string
): Promise<{ success: boolean; issue_id?: string; state?: string; error?: string }> {
  return changeIssueState(issueId, 'open', 'Unblocked');
}

/** Start monitoring an issue */
export async function monitorIssue(
  issueId: string
): Promise<{ success: boolean; issue_id?: string; state?: string; error?: string }> {
  return changeIssueState(issueId, 'monitoring');
}

/** Add a note to an issue */
export async function addIssueNote(
  issueId: string,
  text: string
): Promise<{ success: boolean; note_id?: string; error?: string }> {
  return postJson(`${API_BASE}/issues/${issueId}/notes`, { text, actor: getActor() });
}

/** Health check */
export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  timestamp: string;
  database?: {
    connected: boolean;
    signals: number;
    issues: number;
    clients: number;
  };
  error?: string;
}

export async function checkHealth(): Promise<HealthResponse> {
  return fetchJson(`${API_BASE}/health`);
}

async function patchJson<T>(url: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

async function putJson<T>(url: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

// ==== Task Management Endpoints (server.py /api/tasks*) ====

/** Fetch single task detail from GET /api/tasks/{taskId} */
export async function fetchTaskDetail(taskId: string): Promise<Task> {
  return fetchJson(`/api/tasks/${taskId}`);
}

/** Create a new task via POST /api/tasks */
export interface TaskCreatePayload {
  title: string;
  description?: string;
  project?: string;
  assignee?: string;
  due_date?: string;
  priority?: number;
  tags?: string;
  source?: string;
  status?: string;
}

export async function createTask(
  payload: TaskCreatePayload
): Promise<{ success: boolean; task?: Task; bundle_id?: string; error?: string }> {
  const result = await postJson<{
    success: boolean;
    task?: Task;
    bundle_id?: string;
    error?: string;
  }>('/api/tasks', payload as unknown as Record<string, unknown>);
  if (result.success) invalidateCache('tasks');
  return result;
}

/** Update a task via PUT /api/tasks/{taskId} */
export interface TaskUpdatePayload {
  title?: string;
  description?: string;
  project?: string;
  assignee?: string;
  due_date?: string;
  priority?: number;
  status?: string;
  tags?: string;
}

export interface TaskUpdateResponse {
  success: boolean;
  id: string;
  bundle_id?: string;
  changes?: Array<{ field: string; old: unknown; new: unknown }>;
  updated_fields?: string[];
  signals_resolved?: number;
  requires_approval?: boolean;
  reason?: string;
  decision_id?: string;
  error?: string;
}

export async function updateTask(
  taskId: string,
  payload: TaskUpdatePayload
): Promise<TaskUpdateResponse> {
  const result = await putJson<TaskUpdateResponse>(
    `/api/tasks/${taskId}`,
    payload as unknown as Record<string, unknown>
  );
  if (result.success) invalidateCache('tasks');
  return result;
}

/** Add a note to a task via POST /api/tasks/{taskId}/notes */
export async function addTaskNote(
  taskId: string,
  note: string
): Promise<{ success: boolean; error?: string }> {
  return postJson(`/api/tasks/${taskId}/notes`, { note });
}

/** Delegate a task via POST /api/tasks/{taskId}/delegate */
export interface DelegatePayload {
  to: string;
  note?: string;
  due_date?: string;
}

export interface DelegateResponse {
  success: boolean;
  id?: string;
  delegated_to?: string;
  bundle_id?: string;
  assignee_workload?: number;
  warning?: string;
  requires_approval?: boolean;
  reason?: string;
  decision_id?: string;
  error?: string;
}

export async function delegateTask(
  taskId: string,
  payload: DelegatePayload
): Promise<DelegateResponse> {
  const result = await postJson<DelegateResponse>(
    `/api/tasks/${taskId}/delegate`,
    payload as unknown as Record<string, unknown>
  );
  if (result.success) invalidateCache('tasks');
  return result;
}

/** Escalate a task via POST /api/tasks/{taskId}/escalate */
export interface EscalatePayload {
  to: string;
  reason?: string;
}

export interface EscalateResponse {
  success: boolean;
  id?: string;
  escalated_to?: string;
  bundle_id?: string;
  escalation_level?: number;
  old_priority?: number;
  new_priority?: number;
  new_urgency?: string;
  requires_approval?: boolean;
  reason?: string;
  decision_id?: string;
  error?: string;
}

export async function escalateTask(
  taskId: string,
  payload: EscalatePayload
): Promise<EscalateResponse> {
  const result = await postJson<EscalateResponse>(
    `/api/tasks/${taskId}/escalate`,
    payload as unknown as Record<string, unknown>
  );
  if (result.success) invalidateCache('tasks');
  return result;
}

/** Recall a delegation via POST /api/tasks/{taskId}/recall */
export async function recallTask(
  taskId: string
): Promise<{ success: boolean; id?: string; bundle_id?: string; error?: string }> {
  const result = await postJson<{
    success: boolean;
    id?: string;
    bundle_id?: string;
    error?: string;
  }>(`/api/tasks/${taskId}/recall`, {});
  if (result.success) invalidateCache('tasks');
  return result;
}

/** Fetch delegations from GET /api/delegations */
export interface DelegationsResponse {
  delegated_by_me: Task[];
  delegated_to_me: Task[];
  total: number;
}

export async function fetchDelegations(): Promise<DelegationsResponse> {
  return fetchJson('/api/delegations');
}

/** Fetch priorities (advanced) from GET /api/priorities/advanced */
export interface PriorityAdvancedFilters {
  q?: string;
  due?: string;
  assignee?: string;
  project?: string;
  status?: string;
  min_score?: number;
  max_score?: number;
  tags?: string;
  sort?: 'score' | 'due' | 'title' | 'assignee';
  order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface PriorityItem {
  id: string;
  title: string;
  score: number;
  due: string | null;
  assignee: string | null;
  source: string | null;
  project: string | null;
  reasons: string[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export async function fetchPrioritiesAdvanced(
  filters: PriorityAdvancedFilters = {}
): Promise<PaginatedResponse<PriorityItem>> {
  const params = new URLSearchParams();
  if (filters.q) params.set('q', filters.q);
  if (filters.due) params.set('due', filters.due);
  if (filters.assignee) params.set('assignee', filters.assignee);
  if (filters.project) params.set('project', filters.project);
  if (filters.status) params.set('status', filters.status);
  if (filters.min_score != null) params.set('min_score', String(filters.min_score));
  if (filters.max_score != null) params.set('max_score', String(filters.max_score));
  if (filters.tags) params.set('tags', filters.tags);
  if (filters.sort) params.set('sort', filters.sort);
  if (filters.order) params.set('order', filters.order);
  if (filters.limit != null) params.set('limit', String(filters.limit));
  if (filters.offset != null) params.set('offset', String(filters.offset));
  const qs = params.toString();
  return fetchJson(`/api/priorities/advanced${qs ? `?${qs}` : ''}`);
}

/** Fetch grouped priorities from GET /api/priorities/grouped */
export async function fetchPrioritiesGrouped(
  groupBy = 'project',
  limit = 50
): Promise<Record<string, unknown>> {
  return fetchJson(`/api/priorities/grouped?group_by=${groupBy}&limit=${limit}`);
}

/** Bulk action on priorities via POST /api/priorities/bulk */
export interface BulkActionPayload {
  action: string;
  ids: string[];
  assignee?: string;
  snooze_days?: number;
  priority?: number;
  project?: string;
}

export async function bulkPriorityAction(
  payload: BulkActionPayload
): Promise<{ success: boolean; affected?: number; error?: string }> {
  const result = await postJson<{ success: boolean; affected?: number; error?: string }>(
    '/api/priorities/bulk',
    payload as unknown as Record<string, unknown>
  );
  if (result.success) invalidateCache('priorities');
  return result;
}

/** Fetch bundle detail from GET /api/bundles/{bundleId} */
export async function fetchBundleDetail(bundleId: string): Promise<Record<string, unknown>> {
  return fetchJson(`/api/bundles/${bundleId}`);
}

// ==== Priorities Workspace Endpoints (Phase 7) ====

/** Filters for GET /api/priorities/filtered */
export interface PriorityFilteredParams {
  due?: 'today' | 'week' | 'overdue';
  assignee?: string;
  source?: string;
  project?: string;
  q?: string;
  limit?: number;
}

/** Fetch filtered priorities from GET /api/priorities/filtered */
export async function fetchPrioritiesFiltered(
  filters: PriorityFilteredParams = {}
): Promise<{ items: PriorityItem[]; total: number }> {
  const params = new URLSearchParams();
  if (filters.due) params.set('due', filters.due);
  if (filters.assignee) params.set('assignee', filters.assignee);
  if (filters.source) params.set('source', filters.source);
  if (filters.project) params.set('project', filters.project);
  if (filters.q) params.set('q', filters.q);
  if (filters.limit != null) params.set('limit', String(filters.limit));
  const qs = params.toString();
  return fetchJson(`/api/priorities/filtered${qs ? `?${qs}` : ''}`);
}

/** Saved filter from GET /api/filters */
export interface SavedFilter {
  id?: string;
  name: string;
  filters: Record<string, unknown>;
  created_at?: string;
}

/** Fetch saved filters from GET /api/filters */
export async function fetchSavedFilters(): Promise<{ filters: SavedFilter[] }> {
  return fetchJson('/api/filters');
}

/** Complete a priority item via POST /api/priorities/{itemId}/complete */
export async function completePriority(itemId: string): Promise<{
  success: boolean;
  id?: string;
  bundle_id?: string;
  signals_resolved?: number;
  error?: string;
}> {
  const result = await postJson<{
    success: boolean;
    id?: string;
    bundle_id?: string;
    signals_resolved?: number;
    error?: string;
  }>(`/api/priorities/${itemId}/complete`, {});
  if (result.success) invalidateCache('priorities');
  return result;
}

/** Snooze a priority item via POST /api/priorities/{itemId}/snooze */
export async function snoozePriority(
  itemId: string,
  days = 1
): Promise<{
  success: boolean;
  id?: string;
  new_due_date?: string;
  bundle_id?: string;
  error?: string;
}> {
  const result = await postJson<{
    success: boolean;
    id?: string;
    new_due_date?: string;
    bundle_id?: string;
    error?: string;
  }>(`/api/priorities/${itemId}/snooze?days=${days}`, {});
  if (result.success) invalidateCache('priorities');
  return result;
}

/** Archive stale priorities via POST /api/priorities/archive-stale */
export async function archiveStalePriorities(
  daysThreshold = 14
): Promise<{ success: boolean; archived_count?: number; error?: string }> {
  const result = await postJson<{
    success: boolean;
    archived_count?: number;
    error?: string;
  }>(`/api/priorities/archive-stale?days_threshold=${daysThreshold}`, {});
  if (result.success) invalidateCache('priorities');
  return result;
}

// ==== Time & Capacity Functions (Phase 8) ====

/** Time block from /api/time/blocks */
export interface TimeBlock {
  id: string;
  date: string;
  start_time: string;
  end_time: string;
  lane: string;
  task_id: string | null;
  is_protected: boolean;
  is_buffer: boolean;
  duration_min: number;
  is_available: boolean;
  task_title?: string;
  task_status?: string;
}

/** Response from /api/time/blocks */
export interface TimeBlocksResponse {
  date: string;
  blocks: TimeBlock[];
  total: number;
}

/** Fetch time blocks for a given date and optional lane */
export async function fetchTimeBlocks(date?: string, lane?: string): Promise<TimeBlocksResponse> {
  const params = new URLSearchParams();
  if (date) params.set('date', date);
  if (lane) params.set('lane', lane);
  const qs = params.toString();
  return fetchJson<TimeBlocksResponse>(`/api/time/blocks${qs ? `?${qs}` : ''}`);
}

/** Response from /api/time/summary */
export interface TimeSummaryResponse {
  date: string;
  time: Record<string, unknown>;
  scheduling: Record<string, unknown>;
}

/** Fetch time summary for a date */
export async function fetchTimeSummary(date?: string): Promise<TimeSummaryResponse> {
  const params = date ? `?date=${date}` : '';
  return fetchJson<TimeSummaryResponse>(`/api/time/summary${params}`);
}

/** Schedule a task into a time block */
export async function scheduleTask(
  taskId: string,
  blockId?: string,
  date?: string
): Promise<{ success: boolean; message: string; block_id?: string }> {
  const params = new URLSearchParams({ task_id: taskId });
  if (blockId) params.set('block_id', blockId);
  if (date) params.set('date', date);
  const result = await postJson<{ success: boolean; message: string; block_id?: string }>(
    `/api/time/schedule?${params.toString()}`,
    {}
  );
  if (result.success) {
    invalidateCache('time');
    invalidateCache('blocks');
  }
  return result;
}

/** Unschedule a task from its time block */
export async function unscheduleTask(
  taskId: string
): Promise<{ success: boolean; message: string }> {
  const result = await postJson<{ success: boolean; message: string }>(
    `/api/time/unschedule?task_id=${taskId}`,
    {}
  );
  if (result.success) {
    invalidateCache('time');
    invalidateCache('blocks');
  }
  return result;
}

/** Event from /api/v2/events */
export interface CalendarEvent {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  location?: string;
  status?: string;
  source?: string;
}

/** Fetch events with optional date range */
export async function fetchEvents(
  startDate?: string,
  endDate?: string,
  limit = 50
): Promise<ApiListResponse<CalendarEvent>> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  return fetchJson<ApiListResponse<CalendarEvent>>(`${API_BASE}/events?${params.toString()}`);
}

/** Day view response from /api/day/{date} */
export interface DayViewResponse {
  [key: string]: unknown;
}

/** Fetch day view analysis */
export async function fetchDayView(date?: string): Promise<DayViewResponse> {
  const path = date ? `/api/day/${date}` : '/api/day/';
  return fetchJson<DayViewResponse>(path);
}

/** Week view response from /api/week */
export interface WeekViewResponse {
  [key: string]: unknown;
}

/** Fetch week view analysis */
export async function fetchWeekView(): Promise<WeekViewResponse> {
  return fetchJson<WeekViewResponse>('/api/week');
}

/** Capacity lane from /api/capacity/lanes */
export interface CapacityLane {
  id: string;
  name: string;
  [key: string]: unknown;
}

/** Fetch capacity lanes configuration */
export async function fetchCapacityLanes(): Promise<{ lanes: CapacityLane[] }> {
  return fetchJson<{ lanes: CapacityLane[] }>('/api/capacity/lanes');
}

/** Capacity utilization response */
export interface CapacityUtilizationResponse {
  utilization?: Record<string, unknown>;
  [key: string]: unknown;
}

/** Fetch capacity utilization metrics */
export async function fetchCapacityUtilization(
  laneId?: string,
  targetDate?: string
): Promise<CapacityUtilizationResponse> {
  const params = new URLSearchParams();
  if (laneId) params.set('lane_id', laneId);
  if (targetDate) params.set('target_date', targetDate);
  const qs = params.toString();
  return fetchJson<CapacityUtilizationResponse>(`/api/capacity/utilization${qs ? `?${qs}` : ''}`);
}

/** Forecast entry from /api/capacity/forecast */
export interface ForecastEntry {
  date: string;
  [key: string]: unknown;
}

/** Capacity forecast response */
export interface CapacityForecastResponse {
  lane_id: string;
  days: number;
  forecasts: ForecastEntry[];
}

/** Fetch capacity forecast for upcoming days */
export async function fetchCapacityForecast(
  laneId = 'default',
  days = 7
): Promise<CapacityForecastResponse> {
  const params = new URLSearchParams({
    lane_id: laneId,
    days: String(days),
  });
  return fetchJson<CapacityForecastResponse>(`/api/capacity/forecast?${params.toString()}`);
}

/** Capacity debt response */
export interface CapacityDebtResponse {
  [key: string]: unknown;
}

/** Fetch capacity debt report */
export async function fetchCapacityDebt(lane?: string): Promise<CapacityDebtResponse> {
  const params = lane ? `?lane=${lane}` : '';
  return fetchJson<CapacityDebtResponse>(`/api/capacity/debt${params}`);
}

// ==== Commitments (Phase 9) ====

/** Commitment from /api/commitments */
export interface Commitment {
  id: string;
  text: string;
  due_date: string | null;
  status: string;
  task_id: string | null;
  source_type: string;
  owner: string | null;
  confidence: number;
  created_at: string;
}

/** Commitments list response */
export interface CommitmentsResponse {
  commitments: Commitment[];
  total: number;
}

/** Commitments summary response from /api/commitments/summary */
export interface CommitmentsSummaryResponse {
  [key: string]: unknown;
}

/** Fetch all commitments, optionally filtered by status */
export async function fetchCommitments(status?: string, limit = 50): Promise<CommitmentsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set('status', status);
  return fetchJson<CommitmentsResponse>(`/api/commitments?${params.toString()}`);
}

/** Fetch untracked commitments (not linked to tasks) */
export async function fetchUntrackedCommitments(limit = 50): Promise<CommitmentsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return fetchJson<CommitmentsResponse>(`/api/commitments/untracked?${params.toString()}`);
}

/** Fetch commitments due by a date */
export async function fetchCommitmentsDue(
  date?: string
): Promise<CommitmentsResponse & { date: string }> {
  const params = date ? `?date=${date}` : '';
  return fetchJson<CommitmentsResponse & { date: string }>(`/api/commitments/due${params}`);
}

/** Fetch commitments summary statistics */
export async function fetchCommitmentsSummary(): Promise<CommitmentsSummaryResponse> {
  return fetchJson<CommitmentsSummaryResponse>('/api/commitments/summary');
}

/** Link a commitment to a task */
export async function linkCommitment(
  commitmentId: string,
  taskId: string
): Promise<{ success: boolean; commitment_id: string; task_id: string }> {
  const result = await postJson<{
    success: boolean;
    commitment_id: string;
    task_id: string;
  }>(`/api/commitments/${commitmentId}/link?task_id=${taskId}`, {});
  if (result.success) {
    invalidateCache('commitments');
  }
  return result;
}

/** Mark a commitment as done */
export async function markCommitmentDone(
  commitmentId: string
): Promise<{ success: boolean; commitment_id: string }> {
  const result = await postJson<{ success: boolean; commitment_id: string }>(
    `/api/commitments/${commitmentId}/done`,
    {}
  );
  if (result.success) {
    invalidateCache('commitments');
  }
  return result;
}

// ==== Notifications (Phase 10) ====

/** Notification from /api/notifications */
export interface Notification {
  id: string;
  type: string;
  message: string;
  task_id: string | null;
  target_id: string | null;
  dismissed: number;
  dismissed_at: string | null;
  created_at: string;
}

/** Notifications list response */
export interface NotificationsResponse {
  notifications: Notification[];
  total: number;
}

/** Notification stats response from /api/notifications/stats */
export interface NotificationStatsResponse {
  total: number;
  unread: number;
}

/** Fetch notifications, optionally including dismissed */
export async function fetchNotifications(
  includeDismissed = false,
  limit = 50
): Promise<NotificationsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (includeDismissed) params.set('include_dismissed', 'true');
  return fetchJson<NotificationsResponse>(`/api/notifications?${params.toString()}`);
}

/** Fetch notification stats (total + unread) */
export async function fetchNotificationStats(): Promise<NotificationStatsResponse> {
  return fetchJson<NotificationStatsResponse>('/api/notifications/stats');
}

/** Dismiss a single notification */
export async function dismissNotification(
  notifId: string
): Promise<{ success: boolean; id: string }> {
  const result = await postJson<{ success: boolean; id: string }>(
    `/api/notifications/${notifId}/dismiss`,
    {}
  );
  if (result.success) {
    invalidateCache('notifications');
  }
  return result;
}

/** Dismiss all notifications */
export async function dismissAllNotifications(): Promise<{
  success: boolean;
  dismissed_count: number;
}> {
  const result = await postJson<{ success: boolean; dismissed_count: number }>(
    '/api/notifications/dismiss-all',
    {}
  );
  if (result.success) {
    invalidateCache('notifications');
  }
  return result;
}

// ==== Weekly Digest (Phase 10) ====

/** Weekly digest response from /api/digest/weekly */
export interface WeeklyDigestResponse {
  period: { start: string; end: string };
  completed: {
    count: number;
    items: Array<{ id: string; title: string; completed_at: string }>;
  };
  slipped: {
    count: number;
    items: Array<{ id: string; title: string; due: string; assignee: string | null }>;
  };
  archived: number;
}

/** Fetch weekly digest */
export async function fetchWeeklyDigest(): Promise<WeeklyDigestResponse> {
  return fetchJson<WeeklyDigestResponse>('/api/digest/weekly');
}

// ==== Emails / Email Triage (Phase 10) ====

/** Email from /api/emails (communications table) */
export interface EmailItem {
  id: string;
  subject: string | null;
  sender: string | null;
  recipient: string | null;
  body: string | null;
  received_at: string | null;
  actionable: number;
  processed: number;
  type: string;
  [key: string]: unknown;
}

/** Emails list response */
export interface EmailsResponse {
  emails: EmailItem[];
  total: number;
}

/** Fetch emails with optional filters */
export async function fetchEmails(
  actionableOnly = false,
  unreadOnly = false,
  limit = 30
): Promise<EmailsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (actionableOnly) params.set('actionable_only', 'true');
  if (unreadOnly) params.set('unread_only', 'true');
  return fetchJson<EmailsResponse>(`/api/emails?${params.toString()}`);
}

/** Mark an email as actionable */
export async function markEmailActionable(
  emailId: string
): Promise<{ success: boolean; id: string }> {
  const result = await postJson<{ success: boolean; id: string }>(
    `/api/emails/${emailId}/mark-actionable`,
    {}
  );
  if (result.success) {
    invalidateCache('emails');
  }
  return result;
}

/** Dismiss an email (mark as processed) */
export async function dismissEmail(emailId: string): Promise<{ success: boolean; id: string }> {
  const result = await postJson<{ success: boolean; id: string }>(
    `/api/emails/${emailId}/dismiss`,
    {}
  );
  if (result.success) {
    invalidateCache('emails');
  }
  return result;
}

// ==== Governance & Admin (Phase 11) ====

/** Helper: DELETE JSON requests */
async function deleteJson<T>(url: string): Promise<T> {
  const res = await fetch(url, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

// ---- Governance Config (/api/governance) ----

/** Domain configuration from /api/governance */
export interface GovernanceDomain {
  domain: string;
  mode: string;
  confidence_threshold: number;
  [key: string]: unknown;
}

/** Governance status response from GET /api/governance */
export interface GovernanceResponse {
  domains: GovernanceDomain[];
  emergency_brake: boolean;
  summary: Record<string, unknown>;
}

/** Fetch governance status (config, domains, brake) */
export async function fetchGovernance(): Promise<GovernanceResponse> {
  return fetchJson<GovernanceResponse>('/api/governance');
}

/** Set governance mode for a domain */
export async function setGovernanceMode(
  domain: string,
  mode: string
): Promise<{ domain: string; mode: string; status: string }> {
  const result = await putJson<{ domain: string; mode: string; status: string }>(
    `/api/governance/${domain}`,
    { mode }
  );
  invalidateCache('governance');
  return result;
}

/** Set confidence threshold for a domain */
export async function setGovernanceThreshold(
  domain: string,
  threshold: number
): Promise<{ domain: string; threshold: number; status: string }> {
  const result = await putJson<{ domain: string; threshold: number; status: string }>(
    `/api/governance/${domain}/threshold`,
    { threshold }
  );
  invalidateCache('governance');
  return result;
}

/** Governance history entry */
export interface GovernanceHistoryEntry {
  id: string;
  action: string;
  domain: string;
  timestamp: string;
  actor: string;
  details: Record<string, unknown>;
}

/** Governance history response from GET /api/governance/history */
export interface GovernanceHistoryResponse {
  history: GovernanceHistoryEntry[];
  total: number;
}

/** Fetch governance action history */
export async function fetchGovernanceHistory(limit = 50): Promise<GovernanceHistoryResponse> {
  return fetchJson<GovernanceHistoryResponse>(`/api/governance/history?limit=${limit}`);
}

/** Activate emergency brake */
export async function activateEmergencyBrake(
  reason: string
): Promise<{ success: boolean; active: boolean; reason: string }> {
  const result = await postJson<{ success: boolean; active: boolean; reason: string }>(
    `/api/governance/emergency-brake?reason=${encodeURIComponent(reason)}`,
    {}
  );
  invalidateCache('governance');
  return result;
}

/** Release emergency brake */
export async function releaseEmergencyBrake(): Promise<{
  success: boolean;
  active: boolean;
}> {
  const result = await deleteJson<{ success: boolean; active: boolean }>(
    '/api/governance/emergency-brake'
  );
  invalidateCache('governance');
  return result;
}

// ---- Calibration (/api/calibration) ----

/** Calibration result */
export interface CalibrationResponse {
  [key: string]: unknown;
}

/** Fetch last calibration result */
export async function fetchCalibration(): Promise<CalibrationResponse> {
  return fetchJson<CalibrationResponse>('/api/calibration');
}

/** Run calibration */
export async function runCalibration(): Promise<CalibrationResponse> {
  return postJson<CalibrationResponse>('/api/calibration/run', {});
}

// ---- Bundles (/api/bundles) ----

/** Bundle from /api/bundles */
export interface Bundle {
  bundle_id: string;
  domain: string;
  status: string;
  description: string;
  created_at: string;
  applied_at: string | null;
  rolled_back_at: string | null;
  [key: string]: unknown;
}

/** Bundles list response */
export interface BundlesResponse {
  bundles: Bundle[];
  total: number;
}

/** Bundle summary response from /api/bundles/summary */
export interface BundleSummaryResponse {
  by_status: Record<string, number>;
  by_domain: Record<string, number>;
  total_bundles: number;
  recent_applied: Bundle[];
  rollbackable_count: number;
}

/** Fetch bundles with optional filters */
export async function fetchBundles(
  status?: string,
  domain?: string,
  limit = 50
): Promise<BundlesResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set('status', status);
  if (domain) params.set('domain', domain);
  return fetchJson<BundlesResponse>(`/api/bundles?${params.toString()}`);
}

/** Fetch rollbackable bundles */
export async function fetchRollbackable(): Promise<BundlesResponse> {
  return fetchJson<BundlesResponse>('/api/bundles/rollbackable');
}

/** Fetch bundle summary */
export async function fetchBundleSummary(): Promise<BundleSummaryResponse> {
  return fetchJson<BundleSummaryResponse>('/api/bundles/summary');
}

/** Rollback a specific bundle */
export async function rollbackBundle(
  bundleId: string
): Promise<{ success: boolean; bundle: Bundle }> {
  const result = await postJson<{ success: boolean; bundle: Bundle }>(
    `/api/bundles/${bundleId}/rollback`,
    {}
  );
  if (result.success) {
    invalidateCache('bundles');
    invalidateCache('governance');
  }
  return result;
}

/** Rollback the last applied bundle */
export async function rollbackLastBundle(
  domain?: string
): Promise<{ success: boolean; bundle_id: string; description: string; rolled_back_at: string }> {
  const params = domain ? `?domain=${domain}` : '';
  const result = await postJson<{
    success: boolean;
    bundle_id: string;
    description: string;
    rolled_back_at: string;
  }>(`/api/bundles/rollback-last${params}`, {});
  if (result.success) {
    invalidateCache('bundles');
    invalidateCache('governance');
  }
  return result;
}

// ---- Approvals (/api/approvals) ----

/** Approval from /api/approvals */
export interface Approval {
  decision_id: string;
  action_type: string;
  description: string;
  target_entity: string;
  target_id: string;
  payload: Record<string, unknown>;
  risk_level: string;
  source: string;
  created_at: string;
  [key: string]: unknown;
}

/** Approvals list response */
export interface ApprovalsResponse {
  approvals: Approval[];
  total: number;
}

/** Fetch pending approvals */
export async function fetchApprovals(): Promise<ApprovalsResponse> {
  return fetchJson<ApprovalsResponse>('/api/approvals');
}

/** Process an approval (approve or reject) */
export async function processApproval(
  decisionId: string,
  action: 'approve' | 'reject'
): Promise<{ status: string; decision_id: string }> {
  const result = await postJson<{ status: string; decision_id: string }>(
    `/api/approvals/${decisionId}`,
    { action }
  );
  invalidateCache('approvals');
  return result;
}

/** Modify and approve a decision */
export async function modifyApproval(
  decisionId: string,
  modifications: Record<string, unknown>
): Promise<{ success: boolean; id: string; modified: boolean }> {
  const result = await postJson<{ success: boolean; id: string; modified: boolean }>(
    `/api/approvals/${decisionId}/modify`,
    { modifications }
  );
  invalidateCache('approvals');
  return result;
}

// ---- Decisions (/api/decisions) ----

/** Process a decision with side effects */
export async function processDecision(
  decisionId: string,
  action: 'approve' | 'reject'
): Promise<{ status: string; decision_id: string }> {
  const result = await postJson<{ status: string; decision_id: string }>(
    `/api/decisions/${decisionId}`,
    { action }
  );
  invalidateCache('approvals');
  invalidateCache('governance');
  return result;
}

// ---- Data Quality (/api/data-quality) ----

/** Data quality issue */
export interface DataQualityIssue {
  id?: string;
  title?: string;
  count: number;
  items: Array<Record<string, unknown>>;
}

/** Data quality response from GET /api/data-quality */
export interface DataQualityResponse {
  health_score: number;
  total_active_tasks: number;
  issues: {
    stale_tasks: DataQualityIssue;
    ancient_tasks: DataQualityIssue;
    inactive_tasks: DataQualityIssue;
  };
  metrics: {
    priority_distribution: Record<string, number>;
    due_distribution: Record<string, number>;
    priority_inflation_ratio: number;
    stale_ratio: number;
  };
  suggestions: Array<{
    type: string;
    severity: string;
    message: string;
    action: string;
  }>;
}

/** Fetch data quality health score, issues, and suggestions */
export async function fetchDataQuality(): Promise<DataQualityResponse> {
  return fetchJson<DataQualityResponse>('/api/data-quality');
}

/** Cleanup preview response from GET /api/data-quality/preview/{type} */
export interface CleanupPreviewResponse {
  type: string;
  count: number;
  sample: Array<Record<string, unknown>>;
  confirm_endpoint: string;
}

/** Fetch cleanup preview for a type */
export async function fetchCleanupPreview(cleanupType: string): Promise<CleanupPreviewResponse> {
  return fetchJson<CleanupPreviewResponse>(`/api/data-quality/preview/${cleanupType}`);
}

/** Execute a cleanup action (with confirm=true) */
export async function executeCleanup(
  cleanupType: 'ancient' | 'stale' | 'legacy-signals'
): Promise<{ success: boolean; archived_count: number; bundle_id: string }> {
  const result = await postJson<{
    success: boolean;
    archived_count: number;
    bundle_id: string;
  }>(`/api/data-quality/cleanup/${cleanupType}?confirm=true`, {});
  if (result.success) {
    invalidateCache('data-quality');
    invalidateCache('bundles');
  }
  return result;
}

/** Recalculate all priorities */
export async function recalculatePriorities(): Promise<{
  success: boolean;
  recalculated: number;
}> {
  const result = await postJson<{ success: boolean; recalculated: number }>(
    '/api/data-quality/recalculate-priorities',
    {}
  );
  if (result.success) {
    invalidateCache('priorities');
    invalidateCache('data-quality');
  }
  return result;
}

// ---- Search (/api/v2/search) ----

/** Search result from /api/v2/search */
export interface SearchResult {
  id: string;
  type: 'task' | 'project' | 'client' | 'issue' | 'person';
  title: string;
  subtitle?: string;
  score: number;
}

/** Search response */
export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

/** Full-text search across entities */
export async function fetchSearch(
  q: string,
  types?: string[],
  limit = 20
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  if (types?.length) params.set('types', types.join(','));
  return fetchJson<SearchResponse>(`${API_BASE}/search?${params.toString()}`);
}

// ---- Actions (/api/actions) ----

/** Action proposal from /api/actions/pending */
export interface ActionProposal {
  action_id: string;
  action_type: string;
  target_entity: string;
  target_id: string;
  payload: Record<string, unknown>;
  risk_level: string;
  source: string;
  confidence_score: number;
  status: string;
  created_at: string;
}

/** Actions list response */
export interface ActionsListResponse {
  count: number;
  actions: ActionProposal[];
}

/** Fetch pending actions */
export async function fetchPendingActions(
  actionType?: string,
  limit = 50
): Promise<ActionsListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (actionType) params.set('action_type', actionType);
  return fetchJson<ActionsListResponse>(`/api/actions/pending?${params.toString()}`);
}

/** Fetch action history */
export async function fetchActionHistory(
  entityId?: string,
  actionType?: string,
  limit = 50
): Promise<ActionsListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (entityId) params.set('entity_id', entityId);
  if (actionType) params.set('action_type', actionType);
  return fetchJson<ActionsListResponse>(`/api/actions/history?${params.toString()}`);
}

/** Approve an action */
export async function approveAction(
  actionId: string,
  approvedBy: string
): Promise<{ action_id: string; status: string }> {
  const result = await postJson<{ action_id: string; status: string }>(
    `/api/actions/${actionId}/approve`,
    { approved_by: approvedBy }
  );
  invalidateCache('actions');
  invalidateCache('approvals');
  return result;
}

/** Reject an action */
export async function rejectAction(
  actionId: string,
  rejectedBy: string,
  reason: string
): Promise<{ action_id: string; status: string }> {
  const result = await postJson<{ action_id: string; status: string }>(
    `/api/actions/${actionId}/reject`,
    { rejected_by: rejectedBy, reason }
  );
  invalidateCache('actions');
  invalidateCache('approvals');
  return result;
}

/** Execute an approved action */
export async function executeAction(
  actionId: string,
  dryRun = false
): Promise<{
  action_id: string;
  success: boolean;
  error: string | null;
  execution_time_ms: number | null;
  result_data: unknown;
}> {
  const result = await postJson<{
    action_id: string;
    success: boolean;
    error: string | null;
    execution_time_ms: number | null;
    result_data: unknown;
  }>(`/api/actions/${actionId}/execute`, { dry_run: dryRun });
  if (result.success) {
    invalidateCache('actions');
  }
  return result;
}

// ==== Project Enrollment (Phase 12) ====

/** Candidate project from /api/projects/candidates */
export interface ProjectCandidate {
  id: string;
  name: string;
  client_id: string | null;
  client_name: string | null;
  enrollment_status: 'candidate' | 'proposed';
  involvement_type: string | null;
  proposed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCandidatesResponse {
  items: ProjectCandidate[];
  total: number;
  proposed: number;
  candidate: number;
}

/** Enrolled project from /api/projects/enrolled */
export interface EnrolledProject {
  id: string;
  name: string;
  client_id: string | null;
  client_name: string | null;
  client_tier: string | null;
  involvement_type: string;
  enrollment_status: 'enrolled';
  enrolled_at: string | null;
  open_tasks: number;
  overdue_tasks: number;
  created_at: string;
  updated_at: string;
}

export interface EnrolledProjectsResponse {
  retainers: EnrolledProject[];
  projects: EnrolledProject[];
  total: number;
}

/** Detected project from /api/projects/detect */
export interface DetectedProject {
  name: string;
  task_count: number;
}

export interface DetectedProjectsResponse {
  detected: DetectedProject[];
  total: number;
}

/** Project detail from /api/projects/{id} */
export interface ProjectDetailResponse {
  project: Record<string, unknown>;
  client: Record<string, unknown> | null;
  tasks: Record<string, unknown>[];
  overdue_count: number;
}

/** Linking stats from /api/clients/linking-stats */
export interface LinkingStatsResponse {
  total_projects: number;
  linked_projects: number;
  unlinked_projects: number;
  link_rate: number;
  total_clients: number;
  clients_with_projects: number;
}

/** Enrollment action payload */
export interface EnrollmentPayload {
  action: 'enroll' | 'reject' | 'snooze' | 'mark_internal';
  reason?: string;
  client_id?: string;
  involvement_type?: string;
  snooze_days?: number;
}

/** Bulk link payload */
export interface BulkLinkPayload {
  links: Array<{
    task_id: string;
    project_id?: string;
    client_id?: string;
  }>;
}

export interface BulkLinkResponse {
  total: number;
  succeeded: number;
  results: Array<{
    task_id: string;
    success: boolean;
    linked?: string;
    error?: string;
  }>;
}

/** Propose project payload */
export interface ProposeProjectPayload {
  name: string;
  client_id?: string;
  type?: string;
}

/** Fetch project candidates (candidate + proposed) */
export async function fetchProjectCandidates(): Promise<ProjectCandidatesResponse> {
  return fetchJson<ProjectCandidatesResponse>('/api/projects/candidates');
}

/** Fetch enrolled projects with client info and task counts */
export async function fetchProjectsEnrolled(): Promise<EnrolledProjectsResponse> {
  return fetchJson<EnrolledProjectsResponse>('/api/projects/enrolled');
}

/** Detect new projects from tasks not yet in projects table */
export async function fetchDetectedProjects(force = false): Promise<DetectedProjectsResponse> {
  const params = force ? '?force=true' : '';
  return fetchJson<DetectedProjectsResponse>(`/api/projects/detect${params}`);
}

/** Fetch project detail */
export async function fetchProjectDetail(projectId: string): Promise<ProjectDetailResponse> {
  return fetchJson<ProjectDetailResponse>(`/api/projects/${projectId}`);
}

/** Fetch linking stats */
export async function fetchLinkingStats(): Promise<LinkingStatsResponse> {
  return fetchJson<LinkingStatsResponse>('/api/clients/linking-stats');
}

/** Process enrollment action (enroll/reject/snooze/mark_internal) */
export async function processEnrollment(
  projectId: string,
  payload: EnrollmentPayload
): Promise<{ success: boolean; status: string; id: string }> {
  const result = await postJson<{ success: boolean; status: string; id: string }>(
    `/api/projects/${projectId}/enrollment`,
    { ...payload }
  );
  invalidateCache('projects');
  invalidateCache('candidates');
  invalidateCache('enrolled');
  return result;
}

/** Bulk link tasks to projects/clients */
export async function bulkLinkTasks(payload: BulkLinkPayload): Promise<BulkLinkResponse> {
  const result = await postJson<BulkLinkResponse>('/api/tasks/link', { ...payload });
  invalidateCache('tasks');
  invalidateCache('projects');
  return result;
}

/** Sync Xero data */
export async function syncXero(): Promise<Record<string, unknown>> {
  const result = await postJson<Record<string, unknown>>('/api/sync/xero', {});
  invalidateCache('projects');
  invalidateCache('clients');
  return result;
}

/** Propose a new project */
export async function proposeProject(
  payload: ProposeProjectPayload
): Promise<{ success: boolean; project: Record<string, unknown> }> {
  const params = new URLSearchParams({ name: payload.name });
  if (payload.client_id) params.set('client_id', payload.client_id);
  if (payload.type) params.set('type', payload.type);
  const result = await postJson<{ success: boolean; project: Record<string, unknown> }>(
    `/api/projects/propose?${params.toString()}`,
    {}
  );
  invalidateCache('projects');
  invalidateCache('candidates');
  return result;
}

// ==== Collector Data Depth Types & Functions (Phase 13) ====

export interface EmailParticipant {
  email: string;
  name: string | null;
  role: string;
  message_count: number;
}

export interface EmailLabel {
  label_name: string;
  message_count: number;
}

export interface ClientEmailParticipantsResponse {
  participants: EmailParticipant[];
  labels: EmailLabel[];
  total_participants: number;
  total_labels: number;
}

export interface Attachment {
  filename: string;
  mime_type: string | null;
  size_bytes: number | null;
  message_id: string;
  created_at: string;
}

export interface ClientAttachmentsResponse {
  attachments: Attachment[];
  total: number;
  total_size_bytes: number;
}

export interface InvoiceLineItem {
  invoice_id: string;
  description: string | null;
  quantity: number | null;
  unit_amount: number | null;
  line_amount: number | null;
  tax_type: string | null;
  tax_amount: number | null;
  account_code: string | null;
  tracking_category: string | null;
  tracking_option: string | null;
}

export interface CreditNote {
  id: string;
  contact_id: string | null;
  date: string | null;
  status: string | null;
  total: number | null;
  currency_code: string | null;
  remaining_credit: number | null;
  allocated_amount: number | null;
}

export interface ClientInvoiceDetailResponse {
  line_items: InvoiceLineItem[];
  credit_notes: CreditNote[];
  total_line_items: number;
  total_credit_notes: number;
}

export interface CalendarAttendee {
  event_id: string;
  email: string;
  display_name: string | null;
  response_status: string | null;
  organizer: number;
}

export interface RecurrenceRule {
  event_id: string;
  rrule: string;
}

export interface PersonCalendarDetailResponse {
  attendees: CalendarAttendee[];
  recurrence: RecurrenceRule[];
  total_attendees: number;
  total_recurrence: number;
}

export interface AsanaCustomField {
  field_name: string;
  field_type: string;
  text_value: string | null;
  number_value: number | null;
  enum_value: string | null;
  date_value: string | null;
}

export interface AsanaSubtask {
  id: string;
  name: string;
  assignee_name: string | null;
  completed: number;
  due_on: string | null;
}

export interface AsanaStory {
  id: string;
  type: string;
  text: string | null;
  created_by: string | null;
  created_at: string;
}

export interface AsanaAttachment {
  id: string;
  name: string;
  download_url: string | null;
  host: string | null;
  size_bytes: number | null;
}

export interface TaskAsanaDetailResponse {
  custom_fields: AsanaCustomField[];
  subtasks: AsanaSubtask[];
  stories: AsanaStory[];
  dependencies: { depends_on_task_id: string }[];
  attachments: AsanaAttachment[];
}

export interface ChatSpace {
  space_id: string;
  display_name: string | null;
  space_type: string | null;
  threaded: number;
  member_count: number | null;
  created_time: string | null;
  last_synced: string | null;
}

export interface ChatAnalyticsResponse {
  spaces: ChatSpace[];
  reactions: { emoji: string; count: number }[];
  attachments: { content_type: string; count: number }[];
  total_spaces: number;
  total_reactions: number;
  total_attachments: number;
}

export interface XeroContact {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  is_supplier: number;
  is_customer: number;
  default_currency: string | null;
  outstanding_balance: number | null;
  overdue_balance: number | null;
}

export interface BankTransaction {
  id: string;
  type: string | null;
  contact_id: string | null;
  date: string | null;
  status: string | null;
  total: number | null;
  currency_code: string | null;
  reference: string | null;
}

export interface TaxRate {
  name: string;
  tax_type: string | null;
  effective_rate: number | null;
  status: string | null;
}

export interface FinancialDetailResponse {
  contacts: XeroContact[];
  transactions: BankTransaction[];
  tax_rates: TaxRate[];
  total_contacts: number;
  total_transactions: number;
}

export interface AsanaPortfolio {
  id: string;
  name: string;
  owner_id: string | null;
  owner_name: string | null;
}

export interface AsanaGoal {
  id: string;
  name: string;
  owner_id: string | null;
  owner_name: string | null;
  status: string | null;
  due_on: string | null;
}

export interface AsanaPortfolioContextResponse {
  portfolios: AsanaPortfolio[];
  goals: AsanaGoal[];
  total_portfolios: number;
  total_goals: number;
}

/** Fetch email participants for a client */
export async function fetchClientEmailParticipants(
  clientId: string
): Promise<ClientEmailParticipantsResponse> {
  return fetchJson<ClientEmailParticipantsResponse>(
    `/api/v2/clients/${clientId}/email-participants`
  );
}

/** Fetch email attachments for a client */
export async function fetchClientAttachments(clientId: string): Promise<ClientAttachmentsResponse> {
  return fetchJson<ClientAttachmentsResponse>(`/api/v2/clients/${clientId}/attachments`);
}

/** Fetch invoice line items and credit notes for a client */
export async function fetchClientInvoiceDetail(
  clientId: string
): Promise<ClientInvoiceDetailResponse> {
  return fetchJson<ClientInvoiceDetailResponse>(`/api/v2/clients/${clientId}/invoice-detail`);
}

/** Fetch calendar attendees and recurrence for a person */
export async function fetchPersonCalendarDetail(
  personId: string
): Promise<PersonCalendarDetailResponse> {
  return fetchJson<PersonCalendarDetailResponse>(`/api/v2/team/${personId}/calendar-detail`);
}

/** Fetch Asana detail for a task */
export async function fetchTaskAsanaDetail(taskId: string): Promise<TaskAsanaDetailResponse> {
  return fetchJson<TaskAsanaDetailResponse>(`/api/v2/tasks/${taskId}/asana-detail`);
}

/** Fetch chat analytics */
export async function fetchChatAnalytics(): Promise<ChatAnalyticsResponse> {
  return fetchJson<ChatAnalyticsResponse>('/api/v2/chat/analytics');
}

/** Fetch financial detail (contacts, transactions, tax rates) */
export async function fetchFinancialDetail(): Promise<FinancialDetailResponse> {
  return fetchJson<FinancialDetailResponse>('/api/v2/financial/detail');
}

/** Fetch Asana portfolio context (portfolios and goals) */
export async function fetchAsanaPortfolioContext(): Promise<AsanaPortfolioContextResponse> {
  return fetchJson<AsanaPortfolioContextResponse>('/api/v2/projects/asana-context');
}

// ==== Detection System Endpoints (Phase 15d) ====

/** Week strip day entry: one of 10 business days with collision data */
export interface WeekStripDay {
  date: string;
  available_minutes: number;
  tasks_due: number;
  weighted_ratio: number;
  has_collision: boolean;
}

/** Single detection finding */
export interface DetectionFinding {
  id: string;
  detector: 'collision' | 'drift' | 'bottleneck';
  entity_name: string;
  summary: string;
  severity_data: Record<string, unknown>;
  adjacent_data: Record<string, unknown>;
  client_tier?: string;
  ytd_revenue?: number;
  acknowledged_at?: string | null;
  suppressed_until?: string | null;
}

/** Correlated finding group: primary + subordinates */
export interface FindingGroup {
  primary: DetectionFinding;
  subordinates: DetectionFinding[];
  shared_entity: string;
}

/** Response shape for GET /api/command/findings */
export interface FindingsResponse {
  groups: FindingGroup[];
  acknowledged: DetectionFinding[];
  suppressed: DetectionFinding[];
  team_collisions: DetectionFinding[];
  count: number;
  last_detection: string;
  is_stale: boolean;
}

/** Single finding detail (with optional refreshed data) */
export interface FindingDetailResponse {
  finding: DetectionFinding;
  refreshed: boolean;
  refresh_time_ms?: number;
}

/** Staleness status */
export interface StalenessResponse {
  last_run: string;
  is_stale: boolean;
  stale_since?: string | null;
}

/** Weight review item for the learning loop */
export interface WeightReviewItem {
  task_id: string;
  task_title: string;
  derived_weight: number;
  weight_label: 'quick' | 'standard' | 'heavy';
  confidence: number;
  project_name?: string;
  client_name?: string;
}

/** Response shape for GET /api/command/weight-review */
export interface WeightReviewResponse {
  items: WeightReviewItem[];
  count: number;
}

/** Fetch 10-day week strip with collision data */
export async function fetchWeekStrip(): Promise<WeekStripDay[]> {
  return fetchJson<WeekStripDay[]>('/api/command/week-strip');
}

/** Fetch active findings grouped by correlation */
export async function fetchFindings(): Promise<FindingsResponse> {
  return fetchJson<FindingsResponse>('/api/command/findings');
}

/** Fetch single finding detail, optionally triggering micro-sync */
export async function fetchFinding(
  findingId: string,
  refresh = false
): Promise<FindingDetailResponse> {
  const url = `/api/command/findings/${encodeURIComponent(findingId)}${refresh ? '?refresh=true' : ''}`;
  return fetchJson<FindingDetailResponse>(url);
}

/** Acknowledge a finding ("Got it") */
export async function acknowledgeFinding(findingId: string): Promise<{ success: boolean }> {
  return postJson<{ success: boolean }>(
    `/api/command/findings/${encodeURIComponent(findingId)}/acknowledge`,
    {}
  );
}

/** Suppress a finding ("Expected" -- 30-day suppression) */
export async function suppressFinding(findingId: string): Promise<{ success: boolean }> {
  return postJson<{ success: boolean }>(
    `/api/command/findings/${encodeURIComponent(findingId)}/suppress`,
    {}
  );
}

/** Fetch staleness status */
export async function fetchStaleness(): Promise<StalenessResponse> {
  return fetchJson<StalenessResponse>('/api/command/staleness');
}

/** Fetch pending weight review items */
export async function fetchWeightReview(): Promise<WeightReviewResponse> {
  return fetchJson<WeightReviewResponse>('/api/command/weight-review');
}

/** Submit weight correction for a task */
export async function submitWeightReview(
  taskId: string,
  correctedWeight: number,
  correctedLabel: 'quick' | 'standard' | 'heavy'
): Promise<{ success: boolean }> {
  return postJson<{ success: boolean }>(
    `/api/command/weight-review/${encodeURIComponent(taskId)}`,
    { weight: correctedWeight, label: correctedLabel }
  );
}
