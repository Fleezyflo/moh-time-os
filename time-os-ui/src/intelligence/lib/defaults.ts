/**
 * Smart Defaults for Intelligence Views
 * 
 * Manages default values, filter persistence, and smart initial states.
 */

// Storage keys
const STORAGE_KEYS = {
  SIGNAL_FILTERS: 'intel_signal_filters',
  PROPOSAL_FILTERS: 'intel_proposal_filters',
  LAST_VIEW: 'intel_last_view',
  PREFERENCES: 'intel_preferences',
} as const;

// =============================================================================
// TYPES
// =============================================================================

export interface SignalFilters {
  severity: string;
  entityType: string;
}

export interface ProposalFilters {
  urgency: string;
  limit: number;
}

export interface IntelPreferences {
  autoRefresh: boolean;
  refreshInterval: number; // seconds
  compactMode: boolean;
  showWatchItems: boolean;
}

// =============================================================================
// DEFAULT VALUES
// =============================================================================

export const DEFAULT_SIGNAL_FILTERS: SignalFilters = {
  severity: 'all',
  entityType: 'all',
};

export const DEFAULT_PROPOSAL_FILTERS: ProposalFilters = {
  urgency: '',
  limit: 20,
};

export const DEFAULT_PREFERENCES: IntelPreferences = {
  autoRefresh: false,
  refreshInterval: 60,
  compactMode: false,
  showWatchItems: false,
};

// =============================================================================
// STORAGE HELPERS
// =============================================================================

function getStoredValue<T>(key: string, defaultValue: T): T {
  if (typeof window === 'undefined') return defaultValue;
  
  try {
    const stored = localStorage.getItem(key);
    if (stored) {
      return JSON.parse(stored) as T;
    }
  } catch {
    // Ignore parse errors
  }
  return defaultValue;
}

function setStoredValue<T>(key: string, value: T): void {
  if (typeof window === 'undefined') return;
  
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage errors
  }
}

// =============================================================================
// FILTER MANAGEMENT
// =============================================================================

export function getSignalFilters(): SignalFilters {
  return getStoredValue(STORAGE_KEYS.SIGNAL_FILTERS, DEFAULT_SIGNAL_FILTERS);
}

export function setSignalFilters(filters: SignalFilters): void {
  setStoredValue(STORAGE_KEYS.SIGNAL_FILTERS, filters);
}

export function getProposalFilters(): ProposalFilters {
  return getStoredValue(STORAGE_KEYS.PROPOSAL_FILTERS, DEFAULT_PROPOSAL_FILTERS);
}

export function setProposalFilters(filters: ProposalFilters): void {
  setStoredValue(STORAGE_KEYS.PROPOSAL_FILTERS, filters);
}

// =============================================================================
// PREFERENCES
// =============================================================================

export function getPreferences(): IntelPreferences {
  return getStoredValue(STORAGE_KEYS.PREFERENCES, DEFAULT_PREFERENCES);
}

export function setPreferences(prefs: Partial<IntelPreferences>): void {
  const current = getPreferences();
  setStoredValue(STORAGE_KEYS.PREFERENCES, { ...current, ...prefs });
}

// =============================================================================
// LAST VIEW TRACKING
// =============================================================================

export function getLastView(): string {
  return getStoredValue(STORAGE_KEYS.LAST_VIEW, '/intel');
}

export function setLastView(path: string): void {
  setStoredValue(STORAGE_KEYS.LAST_VIEW, path);
}

// =============================================================================
// SMART DEFAULTS BASED ON DATA
// =============================================================================

/**
 * Suggest initial urgency filter based on proposal counts.
 * If there are critical items, default to showing them.
 */
export function suggestUrgencyFilter(counts: { immediate: number; this_week: number; monitor: number }): string {
  if (counts.immediate > 0) return 'immediate';
  if (counts.this_week > 0) return 'this_week';
  return '';
}

/**
 * Suggest initial severity filter based on signal counts.
 */
export function suggestSeverityFilter(counts: { critical: number; warning: number; watch: number }): string {
  if (counts.critical > 0) return 'critical';
  if (counts.warning > 0) return 'warning';
  return 'all';
}

/**
 * Calculate smart limit based on total items.
 */
export function suggestLimit(total: number): number {
  if (total <= 10) return 10;
  if (total <= 25) return 20;
  if (total <= 50) return 25;
  return 50;
}
