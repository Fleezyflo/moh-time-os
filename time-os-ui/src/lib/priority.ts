// Priority normalization and utilities
// Canonical priority is a number (0-100 scale, higher = more urgent)

export type PriorityLabel = 'critical' | 'high' | 'medium' | 'low';

export interface PriorityThresholds {
  critical: number;
  high: number;
  medium: number;
}

// Default thresholds (can be overridden via config if needed)
export const PRIORITY_THRESHOLDS: PriorityThresholds = {
  critical: 80,
  high: 60,
  medium: 40
};

// Get human-readable label from numeric priority
export function priorityLabel(priority: number): PriorityLabel {
  if (priority >= PRIORITY_THRESHOLDS.critical) return 'critical';
  if (priority >= PRIORITY_THRESHOLDS.high) return 'high';
  if (priority >= PRIORITY_THRESHOLDS.medium) return 'medium';
  return 'low';
}

// Get CSS class for priority badge
export function priorityBadgeClass(priority: number): string {
  if (priority >= PRIORITY_THRESHOLDS.critical) return 'bg-red-900/30 text-red-400';
  if (priority >= PRIORITY_THRESHOLDS.high) return 'bg-orange-900/30 text-orange-400';
  if (priority >= PRIORITY_THRESHOLDS.medium) return 'bg-yellow-900/30 text-yellow-400';
  return 'bg-slate-700 text-slate-400';
}

// Compare priorities for sorting (descending: higher priority first)
export function comparePriority(a: number, b: number): number {
  return b - a;
}

// Check if priority matches a filter threshold
export function matchesPriorityFilter(priority: number, filter: number | 'all'): boolean {
  if (filter === 'all') return true;
  if (filter >= PRIORITY_THRESHOLDS.critical) return priority >= PRIORITY_THRESHOLDS.critical;
  if (filter >= PRIORITY_THRESHOLDS.high) return priority >= PRIORITY_THRESHOLDS.high && priority < PRIORITY_THRESHOLDS.critical;
  if (filter >= PRIORITY_THRESHOLDS.medium) return priority >= PRIORITY_THRESHOLDS.medium && priority < PRIORITY_THRESHOLDS.high;
  return priority < PRIORITY_THRESHOLDS.medium;
}
