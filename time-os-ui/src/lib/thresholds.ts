// Centralized thresholds for consistency across the app

// Team workload thresholds
export const WORKLOAD_THRESHOLDS = {
  overloaded: 20, // Tasks above this = overloaded
  heavy: 10, // Tasks above this = heavy load
  normal: 5, // Tasks above this = normal
  light: 0, // Below normal = light
} as const;

export function getLoadLevel(taskCount: number): 'overloaded' | 'heavy' | 'normal' | 'light' {
  if (taskCount >= WORKLOAD_THRESHOLDS.overloaded) return 'overloaded';
  if (taskCount >= WORKLOAD_THRESHOLDS.heavy) return 'heavy';
  if (taskCount >= WORKLOAD_THRESHOLDS.normal) return 'normal';
  return 'light';
}

export const LOAD_STYLES = {
  overloaded: { color: 'text-red-400', bg: 'bg-red-900/30', label: 'Overloaded' },
  heavy: { color: 'text-orange-400', bg: 'bg-orange-900/30', label: 'Heavy' },
  normal: { color: 'text-blue-400', bg: 'bg-blue-900/30', label: 'Normal' },
  light: { color: 'text-green-400', bg: 'bg-green-900/30', label: 'Light' },
} as const;

// Priority thresholds (re-export from priority.ts for convenience)
export { PRIORITY_THRESHOLDS } from './priority';

// Coupling strength thresholds
export { COUPLING_THRESHOLDS } from './coupling';

// AR aging thresholds
export const AR_AGING_THRESHOLDS = {
  critical: 90, // Days overdue
  high: 60,
  medium: 30,
  low: 0,
} as const;

// Confidence thresholds for data quality
export const CONFIDENCE_THRESHOLDS = {
  high: 0.8,
  medium: 0.6,
  low: 0.4,
} as const;
