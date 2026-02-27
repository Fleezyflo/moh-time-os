/**
 * issueStyles — Shared issue styling constants and helpers.
 *
 * Extracted from IssueCard.tsx and IssueDrawer.tsx to eliminate duplication.
 * Both components import from here instead of defining inline.
 */

import type { Issue } from '../types/api';
import { priorityLabel } from './priority';

// ─── State styles (v29 + legacy) ─────────────────────────────────────────

export interface StateStyle {
  icon: string;
  color: string;
  bg: string;
  label: string;
}

export const stateStyles: Record<string, StateStyle> = {
  // v29 states
  detected: { icon: '◎', color: 'text-blue-300', bg: 'bg-blue-900/20', label: 'Detected' },
  surfaced: { icon: '○', color: 'text-blue-400', bg: 'bg-blue-900/30', label: 'Surfaced' },
  snoozed: { icon: '◷', color: 'text-amber-400', bg: 'bg-amber-900/30', label: 'Snoozed' },
  acknowledged: {
    icon: '◉',
    color: 'text-purple-400',
    bg: 'bg-purple-900/30',
    label: 'Acknowledged',
  },
  addressing: { icon: '⊕', color: 'text-cyan-400', bg: 'bg-cyan-900/30', label: 'Addressing' },
  awaiting_resolution: {
    icon: '◷',
    color: 'text-amber-400',
    bg: 'bg-amber-900/30',
    label: 'Awaiting Resolution',
  },
  regression_watch: {
    icon: '◎',
    color: 'text-yellow-400',
    bg: 'bg-yellow-900/30',
    label: 'Regression Watch',
  },
  regressed: { icon: '⊘', color: 'text-red-400', bg: 'bg-red-900/30', label: 'Regressed' },
  closed: { icon: '✓', color: 'text-green-400', bg: 'bg-green-900/30', label: 'Closed' },
  // Legacy states
  open: { icon: '○', color: 'text-blue-400', bg: 'bg-blue-900/30', label: 'Open' },
  monitoring: { icon: '◉', color: 'text-purple-400', bg: 'bg-purple-900/30', label: 'Monitoring' },
  awaiting: { icon: '◷', color: 'text-amber-400', bg: 'bg-amber-900/30', label: 'Awaiting' },
  blocked: { icon: '⊘', color: 'text-red-400', bg: 'bg-red-900/30', label: 'Blocked' },
  resolved: { icon: '✓', color: 'text-green-400', bg: 'bg-green-900/30', label: 'Resolved' },
};

export const defaultStateStyle: StateStyle = stateStyles.open;

// ─── Priority colors ─────────────────────────────────────────────────────

export const priorityColors: Record<string, string> = {
  critical: 'text-red-400',
  high: 'text-orange-400',
  medium: 'text-amber-400',
  low: 'text-[var(--grey-light)]',
  info: 'text-[var(--grey-muted)]',
};

// ─── Issue field accessors (v29 + legacy) ────────────────────────────────

/** Convert v29 severity string to numeric priority */
export const severityToPriority = (severity: string | undefined): number => {
  switch (severity) {
    case 'critical':
      return 90;
    case 'high':
      return 70;
    case 'medium':
      return 50;
    case 'low':
      return 30;
    case 'info':
      return 10;
    default:
      return 50;
  }
};

/** Get issue title (v29: title, legacy: headline) */
export const getTitle = (issue: Issue): string => issue.title || issue.headline || '';

/** Get issue type (v29: type, legacy: issue_type) */
export const getType = (issue: Issue): string => issue.type || '';

/** Get numeric priority (v29: severity→number, legacy: priority) */
export const getPriority = (issue: Issue): number =>
  issue.priority ?? severityToPriority(issue.severity);

/** Get created timestamp */
export const getCreatedAt = (issue: Issue): string => issue.created_at || '';

/** Get last activity timestamp (v29: updated_at, legacy: last_activity_at) */
export const getLastActivity = (issue: Issue): string =>
  issue.updated_at || issue.last_activity_at || '';

/** Get priority info (label + color class) from numeric priority */
export function getPriorityInfo(priority: number): { label: string; color: string } {
  const label = priorityLabel(priority);
  return {
    label: label.charAt(0).toUpperCase() + label.slice(1),
    color: priorityColors[label] || priorityColors.medium,
  };
}
