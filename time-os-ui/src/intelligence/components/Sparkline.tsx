/**
 * Sparkline — Compact SVG line chart for time-series trajectory data
 */

import { useMemo, useState } from 'react';
import { SPARKLINE_COLORS } from './chartColors';

// Constant padding — defined outside component to avoid recreation
const PADDING = { top: 4, right: 4, bottom: 4, left: 4 } as const;

type Polarity = 'positive' | 'negative' | 'neutral';

interface DataPoint {
  date: string;
  value: number;
}

interface SparklineProps {
  data: DataPoint[];
  width?: number;
  height?: number;
  polarity?: Polarity;
  showDots?: boolean;
  showArea?: boolean;
  threshold?: number | null;
}

export function Sparkline({
  data = [],
  width = 200,
  height = 40,
  polarity = 'positive',
  showDots = false,
  showArea = false,
  threshold = null,
}: SparklineProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const chartWidth = width - PADDING.left - PADDING.right;
  const chartHeight = height - PADDING.top - PADDING.bottom;

  const { points, linePath, areaPath, lineColor, thresholdY } = useMemo(() => {
    if (!data || data.length < 2) {
      return {
        points: [],
        linePath: '',
        areaPath: '',
        lineColor: SPARKLINE_COLORS.neutral,
        thresholdY: null,
      };
    }

    const values = data.map((d) => d.value);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 1;
    const paddedMin = minVal - range * 0.1;
    const paddedMax = maxVal + range * 0.1;
    const paddedRange = paddedMax - paddedMin;

    const pts = data.map((d, i) => ({
      x: PADDING.left + (i / (data.length - 1)) * chartWidth,
      y: PADDING.top + chartHeight - ((d.value - paddedMin) / paddedRange) * chartHeight,
      date: d.date,
      value: d.value,
    }));

    const pathStr = pts
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`)
      .join(' ');
    const areaStr =
      pathStr +
      ` L ${pts[pts.length - 1].x.toFixed(1)},${PADDING.top + chartHeight} L ${pts[0].x.toFixed(1)},${PADDING.top + chartHeight} Z`;

    const firstVal = values[0];
    const lastVal = values[values.length - 1];
    const trendUp = lastVal > firstVal;
    const trendDown = lastVal < firstVal;

    let color: string;
    if (polarity === 'neutral') {
      color = SPARKLINE_COLORS.neutral;
    } else if (polarity === 'positive') {
      color = trendUp
        ? SPARKLINE_COLORS.positive
        : trendDown
          ? SPARKLINE_COLORS.negative
          : SPARKLINE_COLORS.neutral;
    } else {
      color = trendUp
        ? SPARKLINE_COLORS.negative
        : trendDown
          ? SPARKLINE_COLORS.positive
          : SPARKLINE_COLORS.neutral;
    }

    let threshY: number | null = null;
    if (threshold != null) {
      threshY = PADDING.top + chartHeight - ((threshold - paddedMin) / paddedRange) * chartHeight;
    }

    return {
      points: pts,
      linePath: pathStr,
      areaPath: areaStr,
      lineColor: color,
      thresholdY: threshY,
    };
  }, [data, chartWidth, chartHeight, polarity, threshold]);

  if (!data || data.length < 2) {
    return (
      <svg width={width} height={height} className="opacity-50">
        <text
          x={width / 2}
          y={height / 2}
          textAnchor="middle"
          dominantBaseline="middle"
          className="text-[10px] fill-[var(--grey-muted)]"
        >
          No data
        </text>
      </svg>
    );
  }

  return (
    <svg
      width={width}
      height={height}
      className="overflow-visible"
      onMouseLeave={() => setHoverIndex(null)}
    >
      {showArea && <path d={areaPath} fill={lineColor} opacity="0.1" />}

      {thresholdY != null && (
        <line
          x1={PADDING.left}
          y1={thresholdY}
          x2={width - PADDING.right}
          y2={thresholdY}
          stroke={SPARKLINE_COLORS.threshold}
          strokeWidth="1"
          strokeDasharray="4,3"
        />
      )}

      <path
        d={linePath}
        fill="none"
        stroke={lineColor}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {showDots &&
        points.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r={hoverIndex === i ? 4 : 2.5}
            fill={lineColor}
            stroke={SPARKLINE_COLORS.stroke}
            strokeWidth="1.5"
          />
        ))}

      {points.map((p, i) => (
        <circle
          key={`hover-${i}`}
          cx={p.x}
          cy={p.y}
          r={12}
          fill="transparent"
          onMouseEnter={() => setHoverIndex(i)}
        />
      ))}

      {hoverIndex != null && points[hoverIndex] && (
        <g>
          <rect
            x={Math.min(points[hoverIndex].x - 30, width - 65)}
            y={Math.max(points[hoverIndex].y - 28, 0)}
            width="60"
            height="22"
            rx="3"
            fill={SPARKLINE_COLORS.stroke}
            opacity="0.95"
          />
          <text
            x={Math.min(points[hoverIndex].x, width - 35)}
            y={Math.max(points[hoverIndex].y - 14, 12)}
            textAnchor="middle"
            className="text-[10px] fill-white font-medium"
          >
            {points[hoverIndex].value}
          </text>
        </g>
      )}
    </svg>
  );
}
