/**
 * Intelligence Data Hooks
 *
 * React hooks for fetching intelligence data with loading/error states.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import * as api from './api';
import type {
  CriticalItem,
  Briefing,
  Signal,
  SignalSummary,
  Pattern,
  Proposal,
  Scorecard,
  PortfolioIntelligence,
  ClientIntelligence,
  PersonIntelligence,
  ClientProfile,
  PersonProfile,
  ProjectOperationalState,
  TrajectoryData,
} from './api';

// =============================================================================
// HOOK TYPES
// =============================================================================

interface UseDataResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

// =============================================================================
// HOOK OPTIONS
// =============================================================================

interface UseDataOptions {
  /** When false, the hook does NOT fetch data. Defaults to true. */
  enabled?: boolean;
}

// =============================================================================
// GENERIC HOOK FACTORY
// =============================================================================

function useData<T>(
  fetchFn: () => Promise<{ data: T }>,
  deps: unknown[] = [],
  options: UseDataOptions = {}
): UseDataResult<T> {
  const { enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<Error | null>(null);

  // Memoize fetchFn with its deps to create a stable reference
  // This avoids the spread dependency array pattern that ESLint can't verify
  const depsKey = JSON.stringify(deps);
  const stableFetchFn = useMemo(() => fetchFn, [depsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = useCallback(async () => {
    if (!enabled) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await stableFetchFn();
      setData(result.data);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, [stableFetchFn, enabled]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    if (enabled) {
      fetchData();
    }
  }, [enabled, fetchData]);

  return { data, loading, error, refetch };
}

// =============================================================================
// PRIMARY HOOKS
// =============================================================================

export function useCriticalItems(): UseDataResult<CriticalItem[]> {
  return useData(() => api.fetchCriticalItems(), []);
}

export function useBriefing(): UseDataResult<Briefing> {
  return useData(() => api.fetchBriefing(), []);
}

// =============================================================================
// SIGNAL HOOKS
// =============================================================================

export function useSignals(
  quick = true
): UseDataResult<{ signals: Signal[]; total_signals: number }> {
  return useData(() => api.fetchSignals(quick), [quick]);
}

export function useSignalSummary(): UseDataResult<SignalSummary> {
  return useData(() => api.fetchSignalSummary(), []);
}

export function useActiveSignals(entityType?: string, entityId?: string): UseDataResult<Signal[]> {
  return useData(() => api.fetchActiveSignals(entityType, entityId), [entityType, entityId]);
}

export function useSignalHistory(
  entityType: string,
  entityId: string,
  limit = 50
): UseDataResult<Signal[]> {
  return useData(
    () => api.fetchSignalHistory(entityType, entityId, limit),
    [entityType, entityId, limit]
  );
}

// =============================================================================
// PATTERN HOOKS
// =============================================================================

export function usePatterns(): UseDataResult<{ patterns: Pattern[]; total_detected: number }> {
  return useData(() => api.fetchPatterns(), []);
}

export function usePatternCatalog(): UseDataResult<
  Array<{
    id: string;
    name: string;
    type: string;
    severity: string;
    description: string;
    implied_action: string;
  }>
> {
  return useData(() => api.fetchPatternCatalog(), []);
}

// =============================================================================
// PROPOSAL HOOKS
// =============================================================================

export function useProposals(limit = 20, urgency?: string): UseDataResult<Proposal[]> {
  return useData(() => api.fetchProposals(limit, urgency), [limit, urgency]);
}

// =============================================================================
// SCORE HOOKS
// =============================================================================

export function useClientScore(clientId: string): UseDataResult<Scorecard> {
  return useData(() => api.fetchClientScore(clientId), [clientId]);
}

export function useProjectScore(projectId: string): UseDataResult<Scorecard> {
  return useData(() => api.fetchProjectScore(projectId), [projectId]);
}

export function usePersonScore(personId: string): UseDataResult<Scorecard> {
  return useData(() => api.fetchPersonScore(personId), [personId]);
}

export function usePortfolioScore(): UseDataResult<Scorecard> {
  return useData(() => api.fetchPortfolioScore(), []);
}

// =============================================================================
// ENTITY INTELLIGENCE HOOKS
// =============================================================================

export function useClientIntelligence(clientId: string): UseDataResult<ClientIntelligence> {
  return useData(() => api.fetchClientIntelligence(clientId), [clientId]);
}

export function usePersonIntelligence(personId: string): UseDataResult<PersonIntelligence> {
  return useData(() => api.fetchPersonIntelligence(personId), [personId]);
}

export function usePortfolioIntelligence(): UseDataResult<PortfolioIntelligence> {
  return useData(() => api.fetchPortfolioIntelligence(), []);
}

// =============================================================================
// ENTITY DETAIL HOOKS
// =============================================================================

/**
 * Fetch full intelligence for a client (scorecard + signals + trajectory).
 * Hook does NOT fetch if clientId is null/undefined/empty.
 */
export function useClientDetail(
  clientId: string | number | null | undefined
): UseDataResult<ClientIntelligence> {
  const enabled = clientId != null && clientId !== '';
  return useData(() => api.fetchClientDetail(clientId!), [clientId], { enabled });
}

/**
 * Fetch full intelligence for a person (scorecard + signals + profile).
 * Hook does NOT fetch if personId is null/undefined/empty.
 */
export function usePersonDetail(
  personId: string | number | null | undefined
): UseDataResult<PersonIntelligence> {
  const enabled = personId != null && personId !== '';
  return useData(() => api.fetchPersonDetail(personId!), [personId], { enabled });
}

/**
 * Fetch operational state for a project.
 * Hook does NOT fetch if projectId is null/undefined/empty.
 */
export function useProjectDetail(
  projectId: string | number | null | undefined
): UseDataResult<ProjectOperationalState> {
  const enabled = projectId != null && projectId !== '';
  return useData(() => api.fetchProjectDetail(projectId!), [projectId], { enabled });
}

/**
 * Fetch operational profile for a client (lighter than full intelligence).
 */
export function useClientProfile(
  clientId: string | number | null | undefined
): UseDataResult<ClientProfile> {
  const enabled = clientId != null && clientId !== '';
  return useData(() => api.fetchClientProfile(clientId!), [clientId], { enabled });
}

/**
 * Fetch operational profile for a person (lighter than full intelligence).
 */
export function usePersonProfile(
  personId: string | number | null | undefined
): UseDataResult<PersonProfile> {
  const enabled = personId != null && personId !== '';
  return useData(() => api.fetchPersonProfile(personId!), [personId], { enabled });
}

/**
 * Fetch trajectory data for a client.
 */
export function useClientTrajectory(
  clientId: string | number | null | undefined,
  windowDays = 30,
  numWindows = 6
): UseDataResult<TrajectoryData> {
  const enabled = clientId != null && clientId !== '';
  return useData(
    () => api.fetchClientTrajectory(clientId!, windowDays, numWindows),
    [clientId, windowDays, numWindows],
    { enabled }
  );
}

/**
 * Fetch trajectory data for a person.
 */
export function usePersonTrajectory(
  personId: string | number | null | undefined,
  windowDays = 30,
  numWindows = 6
): UseDataResult<TrajectoryData> {
  const enabled = personId != null && personId !== '';
  return useData(
    () => api.fetchPersonTrajectory(personId!, windowDays, numWindows),
    [personId, windowDays, numWindows],
    { enabled }
  );
}
