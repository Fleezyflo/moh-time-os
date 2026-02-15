/**
 * Filter Hooks with Persistence
 * 
 * React hooks that persist filter state to localStorage.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  getSignalFilters,
  setSignalFilters,
  getProposalFilters,
  setProposalFilters,
  type SignalFilters,
  type ProposalFilters,
} from './defaults';

// =============================================================================
// SIGNAL FILTERS HOOK
// =============================================================================

export function useSignalFilters() {
  const [filters, setFilters] = useState<SignalFilters>(getSignalFilters);
  
  const updateFilters = useCallback((updates: Partial<SignalFilters>) => {
    setFilters(prev => {
      const next = { ...prev, ...updates };
      setSignalFilters(next);
      return next;
    });
  }, []);
  
  const resetFilters = useCallback(() => {
    const defaults = { severity: 'all', entityType: 'all' };
    setFilters(defaults);
    setSignalFilters(defaults);
  }, []);
  
  return {
    filters,
    updateFilters,
    resetFilters,
    severity: filters.severity,
    entityType: filters.entityType,
    setSeverity: (v: string) => updateFilters({ severity: v }),
    setEntityType: (v: string) => updateFilters({ entityType: v }),
  };
}

// =============================================================================
// PROPOSAL FILTERS HOOK
// =============================================================================

export function useProposalFilters() {
  const [filters, setFilters] = useState<ProposalFilters>(getProposalFilters);
  
  const updateFilters = useCallback((updates: Partial<ProposalFilters>) => {
    setFilters(prev => {
      const next = { ...prev, ...updates };
      setProposalFilters(next);
      return next;
    });
  }, []);
  
  const resetFilters = useCallback(() => {
    const defaults = { urgency: '', limit: 20 };
    setFilters(defaults);
    setProposalFilters(defaults);
  }, []);
  
  return {
    filters,
    updateFilters,
    resetFilters,
    urgency: filters.urgency,
    limit: filters.limit,
    setUrgency: (v: string) => updateFilters({ urgency: v }),
    setLimit: (v: number) => updateFilters({ limit: v }),
  };
}

// =============================================================================
// AUTO-REFRESH HOOK
// =============================================================================

export function useAutoRefresh(
  refetchFn: () => void,
  enabled: boolean = false,
  intervalSeconds: number = 60
) {
  useEffect(() => {
    if (!enabled) return;
    
    const interval = setInterval(refetchFn, intervalSeconds * 1000);
    return () => clearInterval(interval);
  }, [enabled, intervalSeconds, refetchFn]);
}
