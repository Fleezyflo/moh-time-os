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

// Clients
export function useClients() {
  return useFetch(() => api.fetchClients(), []);
}

// Team
export function useTeam() {
  return useFetch(() => api.fetchTeam(), []);
}

// Tasks for a specific assignee
export function useTasks(assignee?: string, status?: string, limit = 20) {
  return useFetch(() => api.fetchTasks(assignee, status, limit), [assignee, status, limit]);
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
