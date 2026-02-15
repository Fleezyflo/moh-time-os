/**
 * Formatters — intelligence-specific formatting utilities
 *
 * For general formatting, use:
 * - lib/format.ts: formatCurrency, formatNumber, formatPercent, formatCompact
 * - lib/datetime.ts: formatDate, formatRelative, formatDateTime
 */

// Re-export commonly used formatters for convenience
export { formatCurrency, formatPercent } from '../../lib/format';
export { formatDate, formatRelative as formatTimeAgo } from '../../lib/datetime';

/**
 * Format a dimension key to a display label.
 * 'task_health' → 'Task Health'
 */
export function formatDimensionLabel(key: string | null | undefined): string {
  if (!key) return '—';
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Format a number as a percentage.
 * null → '—'
 * 53.3 → '53%'
 */
export function formatPercentage(value: number | null | undefined): string {
  if (value == null) return '—';
  return `${Math.round(value)}%`;
}

/**
 * Classify a health score into a named tier.
 */
export function classifyScore(score: number | null | undefined): string | null {
  if (score == null) return null;
  if (score <= 30) return 'CRITICAL';
  if (score <= 50) return 'AT_RISK';
  if (score <= 70) return 'STABLE';
  if (score <= 90) return 'HEALTHY';
  return 'STRONG';
}

/**
 * Classify a load score into a named tier (inverted — high load = bad).
 */
export function classifyLoad(loadScore: number | null | undefined): string | null {
  if (loadScore == null) return null;
  if (loadScore >= 85) return 'CRITICAL';
  if (loadScore >= 70) return 'AT_RISK';
  if (loadScore >= 50) return 'STABLE';
  if (loadScore >= 30) return 'HEALTHY';
  return 'STRONG';
}
