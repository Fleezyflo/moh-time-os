/**
 * Centralized chart color constants — reads from CSS custom properties in tokens.css.
 * Falls back to hardcoded values if CSS vars are not available (SSR, tests).
 */

function getCSSVar(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback;
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return val ? `rgb(${val})` : fallback;
}

// Semantic sparkline colors
export const SPARKLINE_COLORS = {
  get neutral() {
    return getCSSVar('--chart-neutral', 'rgb(148 163 184)');
  },
  get positive() {
    return getCSSVar('--chart-positive', 'rgb(74 222 128)');
  },
  get negative() {
    return getCSSVar('--chart-negative', 'rgb(248 113 113)');
  },
  get threshold() {
    return getCSSVar('--chart-threshold', 'rgb(100 116 139)');
  },
  get stroke() {
    return getCSSVar('--chart-stroke', 'rgb(30 41 59)');
  },
} as const;

// Categorical distribution colors (used by DistributionChart, CommunicationChart)
export const CHART_COLORS = [
  getCSSVar('--chart-blue', 'rgb(59 130 246)'),
  getCSSVar('--chart-emerald', 'rgb(16 185 129)'),
  getCSSVar('--chart-purple', 'rgb(168 85 247)'),
  getCSSVar('--chart-amber', 'rgb(245 158 11)'),
  getCSSVar('--chart-pink', 'rgb(236 72 153)'),
  getCSSVar('--chart-neutral', 'rgb(100 116 139)'),
] as const;

// Named channel colors for CommunicationChart
export const CHANNEL_COLORS = {
  email: CHART_COLORS[0],
  chat: CHART_COLORS[1],
  meetings: CHART_COLORS[2],
} as const;

// Status colors for ProjectOperationalState
export const STATUS_COLORS = {
  get completed() {
    return getCSSVar('--chart-completed', 'rgb(34 197 94)');
  },
  get open() {
    return getCSSVar('--chart-blue', 'rgb(59 130 246)');
  },
  get overdue() {
    return getCSSVar('--chart-overdue', 'rgb(239 68 68)');
  },
} as const;
