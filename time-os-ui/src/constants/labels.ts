// UI Label Constants — Spec §0.3, §0.4
// Centralized mapping from API values to UI display text

import type { Severity, InboxItemType, InboxItemState, IssueState, IssueType } from '../types/spec';

// ==== §0.3 UI Label Mapping ====

// Issue State → UI Label (Spec §0.3)
export const ISSUE_STATE_LABELS: Record<IssueState, string> = {
  detected: 'Detected',
  surfaced: 'Surfaced',
  snoozed: 'Snoozed',
  acknowledged: 'Acknowledged',
  addressing: 'Addressing',
  awaiting_resolution: 'Awaiting Resolution',
  resolved: 'Resolved', // Note: Never persisted per spec
  regression_watch: 'Resolved (watching)',
  closed: 'Closed',
  regressed: 'Regressed',
};

// Inbox State → UI Label (Spec §0.3)
export const INBOX_STATE_LABELS: Record<InboxItemState, string> = {
  proposed: 'Needs Attention',
  snoozed: 'Snoozed',
  linked_to_issue: 'Linked',
  dismissed: 'Dismissed',
};

// Severity → UI Label (Spec §0.3)
export const SEVERITY_LABELS: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
};

// Inbox Item Type → UI Label
export const INBOX_TYPE_LABELS: Record<InboxItemType, string> = {
  issue: 'Issue',
  flagged_signal: 'Flagged Signal',
  orphan: 'Orphan',
  ambiguous: 'Ambiguous',
};

// Issue Type → UI Label
export const ISSUE_TYPE_LABELS: Record<IssueType, string> = {
  financial: 'Financial',
  schedule_delivery: 'Schedule / Delivery',
  communication: 'Communication',
  risk: 'Risk',
};

// Client Status → UI Label
export const CLIENT_STATUS_LABELS = {
  active: 'Active',
  recently_active: 'Recently Active',
  cold: 'Cold',
} as const;

// Engagement State → UI Label (Spec §6.7)
export const ENGAGEMENT_STATE_LABELS = {
  planned: 'Planned',
  active: 'Active',
  blocked: 'Blocked',
  paused: 'Paused',
  delivering: 'Delivering',
  delivered: 'Delivered',
  completed: 'Completed',
} as const;

// Engagement Type → UI Label
export const ENGAGEMENT_TYPE_LABELS = {
  project: 'Project',
  retainer: 'Retainer',
} as const;

// Health Gating Reason → UI Label (Spec §6.6)
export const HEALTH_GATING_LABELS = {
  no_tasks: 'N/A',
  task_linking_incomplete: 'N/A',
  recently_cleared: 'Clear',
} as const;

export const HEALTH_GATING_TOOLTIPS = {
  no_tasks: 'Health is computed only when there is active open work',
  task_linking_incomplete: 'Health pending: task linking below 90% coverage',
  recently_cleared: 'All tasks complete in last 7 days',
} as const;

// Tier → UI Label
export const TIER_LABELS = {
  platinum: 'Platinum',
  gold: 'Gold',
  silver: 'Silver',
  bronze: 'Bronze',
  none: 'None',
} as const;

// ==== §0.4 Button Label → API Action Mapping ====

// Inbox actions (Spec §0.4)
export const INBOX_ACTION_LABELS = {
  tag: 'Tag & Watch',
  assign: 'Assign',
  snooze: 'Snooze',
  dismiss: 'Dismiss',
  link: 'Link to Engagement',
  create: 'Create Engagement',
  select: 'Select Match',
  unsnooze: 'Unsnooze',
} as const;

// Issue actions (Spec §0.4)
export const ISSUE_ACTION_LABELS = {
  acknowledge: 'Acknowledge',
  assign: 'Assign',
  snooze: 'Snooze',
  unsnooze: 'Unsnooze',
  resolve: 'Resolve',
  escalate: 'Escalate',
  mark_awaiting: 'Mark Awaiting',
} as const;

// Engagement actions (Spec §6.7)
export const ENGAGEMENT_ACTION_LABELS = {
  activate: 'Start Work',
  block: 'Mark Blocked',
  pause: 'Pause',
  unblock: 'Unblock',
  resume: 'Resume',
  mark_delivering: 'Mark Delivering',
  mark_delivered: 'Mark Delivered',
  complete: 'Complete',
  reopen: 'Reopen',
} as const;

// Client Detail action mapping (Spec §0.4)
// "Acknowledge" on client detail = "Tag & Watch" from inbox
export const CLIENT_ACTION_TO_INBOX_ACTION = {
  Acknowledge: 'tag',
  'Snooze 7d': 'snooze',
  Resolve: 'resolve',
  Escalate: 'escalate',
} as const;

// ==== Colors ====

export const SEVERITY_COLORS = {
  critical: { bg: 'bg-red-500', text: 'text-white', ring: 'ring-red-500/50' },
  high: { bg: 'bg-orange-500', text: 'text-white', ring: 'ring-orange-500/50' },
  medium: { bg: 'bg-yellow-500', text: 'text-black', ring: 'ring-yellow-500/50' },
  low: { bg: 'bg-blue-500', text: 'text-white', ring: 'ring-blue-500/50' },
  info: { bg: 'bg-slate-500', text: 'text-white', ring: 'ring-slate-500/50' },
} as const;

export const TIER_COLORS = {
  platinum: { bg: 'bg-purple-500', text: 'text-white' },
  gold: { bg: 'bg-yellow-500', text: 'text-black' },
  silver: { bg: 'bg-slate-400', text: 'text-black' },
  bronze: { bg: 'bg-orange-700', text: 'text-white' },
  none: { bg: 'bg-slate-600', text: 'text-slate-300' },
} as const;

export const CLIENT_STATUS_COLORS = {
  active: { bg: 'bg-green-600', text: 'text-white' },
  recently_active: { bg: 'bg-yellow-600', text: 'text-black' },
  cold: { bg: 'bg-slate-600', text: 'text-slate-300' },
} as const;

export const ENGAGEMENT_STATE_COLORS = {
  planned: { bg: 'bg-slate-600', text: 'text-white' },
  active: { bg: 'bg-green-600', text: 'text-white' },
  blocked: { bg: 'bg-red-600', text: 'text-white' },
  paused: { bg: 'bg-yellow-600', text: 'text-black' },
  delivering: { bg: 'bg-blue-600', text: 'text-white' },
  delivered: { bg: 'bg-purple-600', text: 'text-white' },
  completed: { bg: 'bg-slate-500', text: 'text-white' },
} as const;

export const SENTIMENT_COLORS = {
  good: { bg: 'bg-green-500', text: 'text-white', icon: '🟢' },
  neutral: { bg: 'bg-yellow-500', text: 'text-black', icon: '🟡' },
  bad: { bg: 'bg-red-500', text: 'text-white', icon: '🔴' },
} as const;

// ==== Icons ====

export const INBOX_TYPE_ICONS: Record<InboxItemType, string> = {
  issue: '⚠️',
  flagged_signal: '🚩',
  orphan: '❓',
  ambiguous: '🔀',
};

export const ISSUE_TYPE_ICONS: Record<IssueType, string> = {
  financial: '💰',
  schedule_delivery: '📅',
  communication: '💬',
  risk: '🚨',
};

// Signal source icons (Spec §6.11)
export const SIGNAL_SOURCE_ICONS = {
  asana: '📋',
  gmail: '✉️',
  gchat: '💬',
  calendar: '📅',
  meet: '🎥',
  minutes: '📝',
  xero: '💵',
} as const;

export const SIGNAL_SOURCE_LABELS = {
  asana: 'Tasks',
  gmail: 'Email',
  gchat: 'Chat',
  calendar: 'Calendar',
  meet: 'Meetings',
  minutes: 'Minutes',
  xero: 'Xero',
} as const;
