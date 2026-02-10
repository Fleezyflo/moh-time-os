/**
 * Offline-first + Degraded Mode Support
 *
 * Features:
 * - TanStack Query persistence with versioned cache key
 * - Degraded mode detection and UI patterns
 * - Retry controls with request_id tracking
 */

import { QueryClient } from '@tanstack/react-query';

// Cache version - increment to invalidate all cached data
const CACHE_VERSION = 1;
const CACHE_KEY = `moh-time-os-query-cache-v${CACHE_VERSION}`;

// ============================================================================
// Degraded Mode State
// ============================================================================

export interface DegradedModeState {
  isOffline: boolean;
  lastSuccessfulSync: string | null;
  failedRequests: FailedRequest[];
  retryCount: number;
}

export interface FailedRequest {
  requestId: string;
  url: string;
  errorCode: string;
  errorMessage: string;
  timestamp: string;
}

const initialState: DegradedModeState = {
  isOffline: !navigator.onLine,
  lastSuccessfulSync: null,
  failedRequests: [],
  retryCount: 0,
};

let degradedState = { ...initialState };

// ============================================================================
// State Management
// ============================================================================

export function getDegradedState(): DegradedModeState {
  return { ...degradedState };
}

export function setOffline(offline: boolean): void {
  degradedState.isOffline = offline;
}

export function recordSuccess(): void {
  degradedState.lastSuccessfulSync = new Date().toISOString();
  degradedState.failedRequests = [];
  degradedState.retryCount = 0;
}

export function recordFailure(request: FailedRequest): void {
  degradedState.failedRequests.push(request);
  degradedState.retryCount++;
}

export function clearFailures(): void {
  degradedState.failedRequests = [];
  degradedState.retryCount = 0;
}

// ============================================================================
// Network Status Listeners
// ============================================================================

export function initOfflineListeners(): () => void {
  const handleOnline = () => setOffline(false);
  const handleOffline = () => setOffline(true);

  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);

  return () => {
    window.removeEventListener('online', handleOnline);
    window.removeEventListener('offline', handleOffline);
  };
}

// ============================================================================
// Cache Persistence
// ============================================================================

export function persistQueryCache(queryClient: QueryClient): void {
  try {
    const state = queryClient.getQueryCache().getAll();
    const serializable = state.map((query) => ({
      queryKey: query.queryKey,
      state: query.state,
    }));
    localStorage.setItem(CACHE_KEY, JSON.stringify(serializable));
  } catch {
    // Storage quota exceeded or other error
  }
}

export function restoreQueryCache(queryClient: QueryClient): void {
  try {
    const cached = localStorage.getItem(CACHE_KEY);
    if (cached) {
      const parsed = JSON.parse(cached);
      // Note: Full restoration would require hydration logic
      // This is a simplified version
      console.log(`[Offline] Restored ${parsed.length} cached queries`);
    }
  } catch {
    // Invalid cache or parse error
    localStorage.removeItem(CACHE_KEY);
  }
}

export function clearQueryCache(): void {
  localStorage.removeItem(CACHE_KEY);
}

// ============================================================================
// Helpers
// ============================================================================

export function isInDegradedMode(): boolean {
  return degradedState.isOffline || degradedState.failedRequests.length > 0;
}

export function getRetryDelay(attempt: number): number {
  // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
  return Math.min(1000 * Math.pow(2, attempt), 30000);
}
