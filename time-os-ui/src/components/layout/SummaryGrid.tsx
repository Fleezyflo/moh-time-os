/**
 * SummaryGrid — Responsive grid for top-level page metrics.
 *
 * 2-4 column responsive grid that holds MetricCard instances.
 * Collapses to 1 column on mobile.
 */

import type { ReactNode } from 'react';

interface SummaryGridProps {
  /** MetricCard children */
  children: ReactNode;
}

export function SummaryGrid({ children }: SummaryGridProps) {
  return (
    <div
      className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"
      role="region"
      aria-label="Summary metrics"
    >
      {children}
    </div>
  );
}
