// React hooks for data fetching from Control Room API
import { useState, useEffect } from 'react';
import * as api from './api';

// Generic fetch hook
function useFetch<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetcher()
      .then(result => {
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err);
          console.error('Fetch error:', err);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, deps);

  return { data, loading, error, refetch: () => fetcher().then(setData) };
}

// Proposals
export function useProposals(limit = 7, status = 'open') {
  return useFetch(() => api.fetchProposals(limit, status), [limit, status]);
}

// Issues
export function useIssues(limit = 5) {
  return useFetch(() => api.fetchIssues(limit), [limit]);
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
  return useFetch(
    () => api.fetchCouplings(anchorType, anchorId), 
    [anchorType, anchorId]
  );
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

// Evidence for an entity
export function useEvidence(entityType: string, entityId: string) {
  return useFetch(
    () => api.fetchEvidence(entityType, entityId),
    [entityType, entityId]
  );
}
