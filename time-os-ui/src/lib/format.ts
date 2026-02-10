// Number formatting utilities for consistent display

/**
 * Format a number with thousands separators
 */
export function formatNumber(value: number | undefined | null): string {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString();
}

/**
 * Format a score (0-100 scale) with 1 decimal place
 */
export function formatScore(score: number | undefined | null): string {
  if (score === null || score === undefined) return '—';
  return score.toFixed(1);
}

/**
 * Format a percentage (0-1 or 0-100 input, output includes % symbol)
 * @param value - Value to format
 * @param isDecimal - If true, multiply by 100 (e.g., 0.85 -> 85%)
 * @param decimals - Number of decimal places (default 0)
 */
export function formatPercent(
  value: number | undefined | null,
  isDecimal = true,
  decimals = 0
): string {
  if (value === null || value === undefined) return '—';
  const pct = isDecimal ? value * 100 : value;
  return `${pct.toFixed(decimals)}%`;
}

/**
 * Format a count with compact notation for large numbers
 * e.g., 1,234 -> 1.2K, 1,234,567 -> 1.2M
 */
export function formatCompact(value: number | undefined | null): string {
  if (value === null || value === undefined) return '—';
  if (value < 1000) return value.toString();
  if (value < 1000000) return `${(value / 1000).toFixed(1)}K`;
  return `${(value / 1000000).toFixed(1)}M`;
}

/**
 * Format a confidence/strength value (0-1)
 */
export function formatConfidence(value: number | undefined | null): string {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(0)}%`;
}

/**
 * Format currency (USD by default)
 */
export function formatCurrency(
  value: number | undefined | null,
  currency = 'USD',
  locale = 'en-US'
): string {
  if (value === null || value === undefined) return '—';
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `$${formatNumber(value)}`;
  }
}

/**
 * Format AR outstanding with aging indicator
 */
export function formatAROutstanding(amount: number | null, aging?: string | null): string {
  if (amount === null || amount === undefined || amount === 0) return '—';
  const formatted = formatCurrency(amount);
  if (aging) {
    return `${formatted} (${aging})`;
  }
  return formatted;
}

/**
 * Format a score consistently (1 decimal for display)
 */
export function formatDisplayScore(score: number | undefined | null): string {
  if (score === null || score === undefined) return '—';
  return score.toFixed(1);
}
