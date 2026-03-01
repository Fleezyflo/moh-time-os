// ForecastChart — bar chart showing capacity forecast per day
import { useMemo } from 'react';
import type { ForecastEntry } from '../../lib/api';

interface ForecastChartProps {
  forecasts: ForecastEntry[];
  laneId: string;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  // Show MM/DD format
  const parts = dateStr.split('-');
  if (parts.length >= 3) return `${parts[1]}/${parts[2]}`;
  return dateStr;
}

export function ForecastChart({ forecasts, laneId }: ForecastChartProps) {
  const maxValue = useMemo(() => {
    let max = 0;
    for (const f of forecasts) {
      const available = typeof f.available_hours === 'number' ? f.available_hours : 0;
      const scheduled = typeof f.scheduled_hours === 'number' ? f.scheduled_hours : 0;
      const total = typeof f.total_hours === 'number' ? f.total_hours : 0;
      max = Math.max(max, available, scheduled, total);
    }
    return max || 8; // Default to 8h workday
  }, [forecasts]);

  if (forecasts.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-[var(--grey-muted)]">
        No forecast data for {laneId}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-3 text-xs text-[var(--grey-light)]">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded" style={{ backgroundColor: 'var(--accent)' }} />
          Scheduled
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded" style={{ backgroundColor: 'var(--grey)' }} />
          Available
        </div>
      </div>
      <div className="flex items-end gap-1 h-40">
        {forecasts.map((f, i) => {
          const available = typeof f.available_hours === 'number' ? f.available_hours : 0;
          const scheduled = typeof f.scheduled_hours === 'number' ? f.scheduled_hours : 0;
          const scheduledPct = maxValue > 0 ? (scheduled / maxValue) * 100 : 0;
          const availablePct = maxValue > 0 ? (available / maxValue) * 100 : 0;

          return (
            <div key={f.date || i} className="flex-1 flex flex-col items-center gap-0.5">
              <div className="w-full flex flex-col items-center justify-end h-32">
                {/* Available (background) bar */}
                <div
                  className="w-full max-w-[40px] rounded-t relative"
                  style={{
                    height: `${Math.max(availablePct, 2)}%`,
                    backgroundColor: 'var(--grey)',
                  }}
                >
                  {/* Scheduled (overlay) bar */}
                  <div
                    className="absolute bottom-0 left-0 right-0 rounded-t transition-all"
                    style={{
                      height:
                        availablePct > 0
                          ? `${Math.min((scheduledPct / availablePct) * 100, 100)}%`
                          : '0%',
                      backgroundColor:
                        scheduledPct > availablePct * 0.9
                          ? 'var(--danger)'
                          : scheduledPct > availablePct * 0.7
                            ? 'var(--warning)'
                            : 'var(--accent)',
                    }}
                  />
                </div>
              </div>
              <div className="text-xs text-[var(--grey-muted)] mt-1">{formatDate(f.date)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
