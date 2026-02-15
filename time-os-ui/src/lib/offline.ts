/**
 * Degraded Mode Support
 *
 * Features:
 * - Degraded mode detection and UI patterns
 * - Network status tracking
 */

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

// Note: This is intentionally mutable state for the degraded mode tracking
// eslint-disable-next-line prefer-const
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
// Helpers
// ============================================================================

export function isInDegradedMode(): boolean {
  return degradedState.isOffline || degradedState.failedRequests.length > 0;
}

export function getRetryDelay(attempt: number): number {
  // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
  return Math.min(1000 * Math.pow(2, attempt), 30000);
}
