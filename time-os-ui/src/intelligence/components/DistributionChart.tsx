/**
 * DistributionChart — Horizontal stacked bar showing proportional distribution
 */

import { useState } from 'react';

interface Segment {
  label: string;
  value: number;
  color?: string;
}

interface DistributionChartProps {
  segments: Segment[];
  showLabels?: boolean;
  showValues?: boolean;
  height?: number;
}

const DEFAULT_COLORS = [
  'rgb(59 130 246)', // blue-500
  'rgb(16 185 129)', // emerald-500
  'rgb(168 85 247)', // purple-500
  'rgb(245 158 11)', // amber-500
  'rgb(236 72 153)', // pink-500
  'rgb(100 116 139)', // slate-500
];

export function DistributionChart({
  segments = [],
  showLabels = true,
  showValues = true,
  height = 32,
}: DistributionChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const total = segments.reduce((sum, s) => sum + (s.value || 0), 0);

  if (total === 0 || segments.length === 0) {
    return <div className="text-sm text-[var(--grey-muted)]">No data</div>;
  }

  const processedSegments = segments.map((s, i) => ({
    ...s,
    pct: (s.value / total) * 100,
    displayPct: Math.max(3, (s.value / total) * 100),
    color: s.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
  }));

  return (
    <div className="my-2">
      {/* Stacked bar */}
      <div className="flex rounded overflow-hidden" style={{ height: `${height}px` }}>
        {processedSegments.map((seg, i) => (
          <div
            key={seg.label || i}
            className={`flex items-center justify-center transition-opacity ${hoverIndex === i ? 'opacity-85' : ''}`}
            style={{ width: `${seg.displayPct}%`, background: seg.color, minWidth: '3%' }}
            onMouseEnter={() => setHoverIndex(i)}
            onMouseLeave={() => setHoverIndex(null)}
          >
            {showValues && seg.pct >= 10 && (
              <span className="text-[10px] text-white font-semibold">{Math.round(seg.pct)}%</span>
            )}
          </div>
        ))}
      </div>

      {/* Labels */}
      {showLabels && (
        <div className="flex flex-wrap gap-3 mt-2">
          {processedSegments.map((seg, i) => (
            <div
              key={seg.label || i}
              className={`flex items-center gap-1 text-xs ${hoverIndex === i ? 'font-medium' : ''}`}
            >
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ background: seg.color }}
              />
              <span className="text-[var(--grey-light)]">{seg.label}</span>
              {showValues && (
                <span className="text-[var(--grey-muted)]">{Math.round(seg.pct)}%</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Tooltip for small segments */}
      {hoverIndex != null &&
        processedSegments[hoverIndex] &&
        processedSegments[hoverIndex].pct < 10 && (
          <div className="text-xs text-[var(--grey-light)] py-1">
            {processedSegments[hoverIndex].label}: {processedSegments[hoverIndex].value} (
            {Math.round(processedSegments[hoverIndex].pct)}%)
          </div>
        )}
    </div>
  );
}
