// WeekView — renders a week overview with per-day summaries
import type { WeekViewResponse } from '../../lib/api';

interface WeekViewProps {
  data: WeekViewResponse;
  onDayClick?: (date: string) => void;
}

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

interface DayEntry {
  date: string;
  blocks?: unknown[];
  total_minutes?: number;
  scheduled_minutes?: number;
  [key: string]: unknown;
}

export function WeekView({ data, onDayClick }: WeekViewProps) {
  // The week response shape varies — extract days array from common patterns
  const days: DayEntry[] = (() => {
    if (Array.isArray(data)) return data as DayEntry[];
    if ('days' in data && Array.isArray(data.days)) return data.days as DayEntry[];
    if ('blocks' in data && Array.isArray(data.blocks)) {
      // Group blocks by date
      const byDate = new Map<string, unknown[]>();
      for (const block of data.blocks as Array<{ date: string }>) {
        const dateBlocks = byDate.get(block.date) ?? [];
        dateBlocks.push(block);
        byDate.set(block.date, dateBlocks);
      }
      return Array.from(byDate.entries()).map(([date, blocks]) => ({
        date,
        blocks,
      }));
    }
    return [];
  })();

  if (days.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-[var(--grey-muted)]">
        No week data available
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
      {days.map((day, i) => {
        const blockCount = Array.isArray(day.blocks) ? day.blocks.length : 0;
        const totalMin = typeof day.total_minutes === 'number' ? day.total_minutes : 0;
        const scheduledMin = typeof day.scheduled_minutes === 'number' ? day.scheduled_minutes : 0;
        const utilPct = totalMin > 0 ? Math.round((scheduledMin / totalMin) * 100) : 0;

        return (
          <button
            key={day.date || i}
            onClick={() => day.date && onDayClick?.(day.date)}
            className="p-3 rounded-lg border border-[var(--grey)] hover:border-[var(--accent)] transition-colors text-center"
          >
            <div className="text-xs text-[var(--grey-light)] mb-1">{DAY_NAMES[i] || ''}</div>
            <div className="text-sm font-medium mb-2">
              {day.date ? day.date.slice(5) : `Day ${i + 1}`}
            </div>
            {blockCount > 0 && (
              <div className="text-xs text-[var(--grey-muted)]">
                {blockCount} block{blockCount !== 1 ? 's' : ''}
              </div>
            )}
            {totalMin > 0 && (
              <div className="mt-2">
                <div className="h-1.5 rounded-full bg-[var(--grey)] overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${Math.min(utilPct, 100)}%`,
                      backgroundColor:
                        utilPct > 90
                          ? 'var(--danger)'
                          : utilPct > 70
                            ? 'var(--warning)'
                            : 'var(--accent)',
                    }}
                  />
                </div>
                <div className="text-xs text-[var(--grey-muted)] mt-1">{utilPct}%</div>
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
