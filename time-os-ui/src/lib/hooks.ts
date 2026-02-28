// React hooks for data fetching from Control Room API
import { useState, useEffect, useCallback } from 'react';
import * as api from './api';

// Generic fetch hook with error recovery
function useFetch<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const doFetch = useCallback(() => {
    setLoading(true);
    return fetcher()
      .then((result) => {
        setData(result);
        setError(null);
        return result;
      })
      .catch((err) => {
        setError(err);
        // Only log once per error in dev mode
        if (retryCount === 0 && import.meta.env.DEV) {
          console.error('Fetch error:', err.message);
        }
        throw err;
      })
      .finally(() => {
        setLoading(false);
      });
  }, [fetcher, retryCount]);

  useEffect(() => {
    // Track if component unmounts during fetch (for future abort implementation)
    const controller = { cancelled: false };
    doFetch().catch(() => {
      // Error already handled in doFetch
      // Future: check controller.cancelled before state updates
    });
    return () => {
      controller.cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps spread is intentional for dynamic dependencies
  }, [...deps, retryCount]);

  // Refetch clears error and retries
  const refetch = useCallback(() => {
    setRetryCount((c) => c + 1);
  }, []);

  // Reset error without refetching (keeps last-good-data if present)
  const resetError = useCallback(() => {
    setError(null);
  }, []);

  return { data, loading, error, refetch, resetError };
}

// Proposals
export function useProposals(
  limit = 7,
  status = 'open',
  days = 7,
  clientId?: string,
  memberId?: string
) {
  return useFetch(
    () => api.fetchProposals(limit, status, days, clientId, memberId),
    [limit, status, days, clientId, memberId]
  );
}

// Issues
export function useIssues(limit = 5, days = 7, clientId?: string, memberId?: string) {
  return useFetch(
    () => api.fetchIssues(limit, days, clientId, memberId),
    [limit, days, clientId, memberId]
  );
}

// Watchers
export function useWatchers(hours = 24) {
  return useFetch(() => api.fetchWatchers(hours), [hours]);
}

// Fix Data
export function useFixData() {
  return useFetch(() => api.fetchFixData(), []);
}

// Couplings for specific anchor
export function useCouplings(anchorType: string, anchorId: string) {
  return useFetch(() => api.fetchCouplings(anchorType, anchorId), [anchorType, anchorId]);
}

// All couplings
export function useAllCouplings() {
  return useFetch(() => api.fetchAllCouplings(), []);
}

// System health
export function useHealth() {
  return useFetch(() => api.checkHealth(), []);
}

// Clients
export function useClients() {
  return useFetch(() => api.fetchClients(), []);
}

// Team
export function useTeam() {
  return useFetch(() => api.fetchTeam(), []);
}

// Tasks with optional filters
export function useTasks(assignee?: string, status?: string, project?: string, limit = 50) {
  return useFetch(
    () => api.fetchTasks(assignee, status, project, limit),
    [assignee, status, project, limit]
  );
}

// Evidence for an entity
export function useEvidence(entityType: string, entityId: string) {
  return useFetch(() => api.fetchEvidence(entityType, entityId), [entityType, entityId]);
}

// Client detail (full detail with nested sections)
export function useClientDetail(clientId: string) {
  return useFetch(() => api.fetchClientDetail(clientId), [clientId]);
}

// Client team involvement
export function useClientTeam(clientId: string) {
  return useFetch(() => api.fetchClientTeam(clientId), [clientId]);
}

// Client invoices
export function useClientInvoices(clientId: string) {
  return useFetch(() => api.fetchClientInvoices(clientId), [clientId]);
}

// Client AR aging
export function useClientARAging(clientId: string) {
  return useFetch(() => api.fetchClientARAging(clientId), [clientId]);
}

// Team workload distribution
export function useTeamWorkload() {
  return useFetch(() => api.fetchTeamWorkload(), []);
}

// Inbox items with filters
export function useInbox(filters: api.InboxFilters = {}) {
  return useFetch(
    () => api.fetchInbox(filters),
    [
      filters.state,
      filters.type,
      filters.severity,
      filters.client_id,
      filters.unread_only,
      filters.sort,
    ]
  );
}

// Inbox counts (cacheable, global scope)
export function useInboxCounts() {
  return useFetch(() => api.fetchInboxCounts(), []);
}

// Recently actioned inbox items
export function useInboxRecent(days = 7, type?: string) {
  return useFetch(() => api.fetchInboxRecent(days, type as api.InboxFilters['type']), [days, type]);
}

// Portfolio overview (tier breakdown, health, totals, overdue AR)
export function usePortfolioOverview() {
  return useFetch(() => api.fetchPortfolioOverview(), []);
}

// At-risk clients by health score threshold
export function usePortfolioRisks(threshold = 50) {
  return useFetch(() => api.fetchPortfolioRisks(threshold), [threshold]);
}

// Client health overview (counts by status)
export function useClientsHealth() {
  return useFetch(() => api.fetchClientsHealth(), []);
}

// ==== Task Management Hooks (Phase 6) ====

// Single task detail
export function useTaskDetail(taskId: string) {
  return useFetch(() => api.fetchTaskDetail(taskId), [taskId]);
}

// Delegations (by me / to me)
export function useDelegations() {
  return useFetch(() => api.fetchDelegations(), []);
}

// Priorities with advanced filtering
export function usePrioritiesAdvanced(filters: api.PriorityAdvancedFilters = {}) {
  return useFetch(
    () => api.fetchPrioritiesAdvanced(filters),
    [
      filters.q,
      filters.due,
      filters.assignee,
      filters.project,
      filters.status,
      filters.min_score,
      filters.max_score,
      filters.tags,
      filters.sort,
      filters.order,
      filters.limit,
      filters.offset,
    ]
  );
}

// Grouped priorities (by project, assignee, etc.)
export function usePrioritiesGrouped(groupBy = 'project', limit = 50) {
  return useFetch(() => api.fetchPrioritiesGrouped(groupBy, limit), [groupBy, limit]);
}

// Bundle detail
export function useBundleDetail(bundleId: string) {
  return useFetch(() => api.fetchBundleDetail(bundleId), [bundleId]);
}
