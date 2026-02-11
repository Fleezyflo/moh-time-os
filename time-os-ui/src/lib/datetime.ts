// DateTime utilities for consistent date handling
// Policy: Store/transport ISO strings, display in browser local time

/**
 * Parse an ISO date string to a Date object
 * Explicit parsing to avoid ambiguous Date constructor behavior
 */
export function parseISO(isoString: string | undefined | null): Date | null {
  if (!isoString) return null;
  const date = new Date(isoString);
  return isNaN(date.getTime()) ? null : date;
}

/**
 * Format a date for display (local time)
 */
export function formatDate(date: Date | string | undefined | null): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  if (!d) return '—';
  return d.toLocaleDateString();
}

/**
 * Format a date with time for display (local time)
 */
export function formatDateTime(date: Date | string | undefined | null): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  if (!d) return '—';
  return d.toLocaleString();
}

/**
 * Format relative time (e.g., "2 hours ago", "3 days ago")
 */
export function formatRelative(date: Date | string | undefined | null): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  if (!d) return '—';

  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 30) return formatDate(d);
  if (diffDays > 1) return `${diffDays} days ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffHours > 1) return `${diffHours} hours ago`;
  if (diffHours === 1) return '1 hour ago';
  if (diffMins > 1) return `${diffMins} minutes ago`;
  if (diffMins === 1) return '1 minute ago';
  return 'Just now';
}

/**
 * Get start of day in ISO format (for filtering)
 */
export function startOfDay(date: Date = new Date()): string {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

/**
 * Get date N days ago in ISO format (for filtering)
 */
export function daysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

/**
 * Get the user's timezone abbreviation (e.g., "GST", "EST")
 */
export function getTimezoneAbbr(): string {
  try {
    return (
      new Intl.DateTimeFormat('en', { timeZoneName: 'short' })
        .formatToParts(new Date())
        .find((part) => part.type === 'timeZoneName')?.value || ''
    );
  } catch {
    return '';
  }
}

/**
 * Format date with timezone indicator
 */
export function formatDateTimeWithTZ(date: Date | string | undefined | null): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  if (!d) return '—';
  const tz = getTimezoneAbbr();
  return `${d.toLocaleString()}${tz ? ` ${tz}` : ''}`;
}

/**
 * Check if a date string is valid ISO format
 */
export function isValidISODate(str: string | undefined | null): boolean {
  if (!str) return false;
  const date = parseISO(str);
  return date !== null;
}

/**
 * Format duration in human readable form
 */
export function formatDuration(ms: number): string {
  const hours = Math.floor(ms / (1000 * 60 * 60));
  const mins = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60));
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}
