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
export async function fetchProposalDetailLegacy(proposalId: string): Promise<unknown> {
  // LEGACY: backend-only endpoint; migrate to /api/v2 when available
  return fetchJson(`/api/control-room/proposals/${proposalId}`);
}

// Tasks API (uses /api/tasks)
export async function fetchTasks(
  assignee?: string,
  status?: string,
  limit = 20
): Promise<ApiListResponse<Task>> {
  let url = `/api/tasks?limit=${limit}`;
  if (assignee) url += `&assignee=${encodeURIComponent(assignee)}`;
  if (status) url += `&status=${encodeURIComponent(status)}`;
  return fetchJson(url);
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
  status: 'healthy' | 'unhealthy';
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
