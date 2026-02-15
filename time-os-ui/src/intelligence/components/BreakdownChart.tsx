/**
 * BreakdownChart — Vertical stack of DimensionBars for health score breakdown
 */

import { HealthScore } from './HealthScore';
import { DimensionBar } from './DimensionBar';

interface Dimension {
  label: string;
  value: number;
  threshold?: number;
  status?: 'critical' | 'warning' | 'watch' | 'healthy' | 'strong';
}

interface BreakdownChartProps {
  dimensions: Dimension[];
  compositeScore?: number | null;
}

export function BreakdownChart({ dimensions = [], compositeScore }: BreakdownChartProps) {
  // Sort worst-first so problems get attention
  const sorted = [...dimensions].sort((a, b) => a.value - b.value);

  return (
    <div>
      {compositeScore != null && (
        <div className="flex items-center gap-3 mb-4">
          <HealthScore score={compositeScore} size="lg" />
          <span className="text-sm text-slate-500">Overall</span>
        </div>
      )}
      <div className="flex flex-col gap-1">
        {sorted.map((dim, i) => (
          <DimensionBar
            key={dim.label || i}
            label={dim.label}
            value={dim.value}
            threshold={dim.threshold}
            status={dim.status}
            showValue
          />
        ))}
      </div>
    </div>
  );
}
