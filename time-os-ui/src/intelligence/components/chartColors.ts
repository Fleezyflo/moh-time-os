/**
 * Centralized chart color constants — replaces hardcoded rgb() values.
 * Each color name maps to its CSS rgb() string for use in SVG and inline styles.
 */

// Semantic sparkline colors
export const SPARKLINE_COLORS = {
  neutral: 'rgb(148 163 184)', // slate-400
  positive: 'rgb(74 222 128)', // green-400
  negative: 'rgb(248 113 113)', // red-400
  threshold: 'rgb(100 116 139)', // slate-500
  stroke: 'rgb(30 41 59)', // slate-900
} as const;

// Categorical distribution colors (used by DistributionChart, CommunicationChart)
export const CHART_COLORS = [
  'rgb(59 130 246)', // blue-500
  'rgb(16 185 129)', // emerald-500
  'rgb(168 85 247)', // purple-500
  'rgb(245 158 11)', // amber-500
  'rgb(236 72 153)', // pink-500
  'rgb(100 116 139)', // slate-500
] as const;

// Named channel colors for CommunicationChart
export const CHANNEL_COLORS = {
  email: CHART_COLORS[0], // blue-500
  chat: CHART_COLORS[1], // emerald-500
  meetings: CHART_COLORS[2], // purple-500
} as const;

// Status colors for ProjectOperationalState
export const STATUS_COLORS = {
  completed: 'rgb(34 197 94)', // green-500
  open: 'rgb(59 130 246)', // blue-500
  overdue: 'rgb(239 68 68)', // red-500
} as const;
