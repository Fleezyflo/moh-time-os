/**
 * ActivityHeatmap — Grid of cells showing activity intensity per week
 */

import { useState } from 'react';

interface WeekData {
  week_start: string;
  activity_level: number;
}

interface ActivityHeatmapProps {
  data: WeekData[];
  weeks?: number;
  label?: string;
}

function formatWeekLabel(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

export function ActivityHeatmap({
  data = [],
  weeks = 12,
  label = 'Activity',
}: ActivityHeatmapProps) {
  const [hoverWeek, setHoverWeek] = useState<number | null>(null);

  const maxActivity = Math.max(1, ...data.map((d) => d.activity_level));
  const displayData = data.slice(-weeks);

  function getIntensityClass(level: number): string {
    if (level === 0) return 'bg-slate-700/30';
    const ratio = level / maxActivity;
    if (ratio <= 0.25) return 'bg-green-500/30';
    if (ratio <= 0.5) return 'bg-green-500/55';
    if (ratio <= 0.75) return 'bg-green-500/80';
    return 'bg-green-500';
  }

  if (displayData.length === 0) {
    return <div className="text-sm text-slate-500">No activity data</div>;
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs text-slate-500 font-medium">{label}</span>
      <div className="flex gap-[3px] flex-wrap">
        {displayData.map((week, i) => (
          <div
            key={week.week_start || i}
            className={`w-[18px] h-[18px] rounded-[3px] cursor-default transition-opacity ${getIntensityClass(week.activity_level)}`}
            onMouseEnter={() => setHoverWeek(i)}
            onMouseLeave={() => setHoverWeek(null)}
            title={`Week of ${formatWeekLabel(week.week_start)}: ${week.activity_level} activities`}
          />
        ))}
      </div>
      {hoverWeek != null && displayData[hoverWeek] && (
        <div className="text-xs text-slate-400 py-1">
          Week of {formatWeekLabel(displayData[hoverWeek].week_start)}:{' '}
          {displayData[hoverWeek].activity_level} activities
        </div>
      )}
      <div className="flex items-center gap-[3px] mt-1">
        <span className="text-[10px] text-slate-500">Less</span>
        <div className="w-3.5 h-3.5 rounded-[3px] bg-slate-700/30" />
        <div className="w-3.5 h-3.5 rounded-[3px] bg-green-500/30" />
        <div className="w-3.5 h-3.5 rounded-[3px] bg-green-500/55" />
        <div className="w-3.5 h-3.5 rounded-[3px] bg-green-500/80" />
        <div className="w-3.5 h-3.5 rounded-[3px] bg-green-500" />
        <span className="text-[10px] text-slate-500">More</span>
      </div>
    </div>
  );
}
