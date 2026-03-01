// Data quality health score gauge and issue breakdown
import type { DataQualityResponse } from '../../lib/api';

interface Props {
  data: DataQualityResponse;
}

function scoreColor(score: number): string {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-amber-400';
  if (score >= 40) return 'text-orange-400';
  return 'text-red-400';
}

function scoreBg(score: number): string {
  if (score >= 80) return 'bg-green-500';
  if (score >= 60) return 'bg-amber-500';
  if (score >= 40) return 'bg-orange-500';
  return 'bg-red-500';
}

export function DataQualityHealthScore({ data }: Props) {
  const { health_score, total_active_tasks, issues, metrics } = data;

  return (
    <div className="space-y-4">
      {/* Score gauge */}
      <div className="flex items-center gap-6">
        <div className="text-center">
          <div className={`text-4xl font-bold ${scoreColor(health_score)}`}>{health_score}</div>
          <div className="text-xs text-[var(--grey-light)] mt-1">Health Score</div>
        </div>
        <div className="flex-1">
          <div className="w-full bg-[var(--grey)] rounded-full h-3">
            <div
              className={`h-3 rounded-full transition-all ${scoreBg(health_score)}`}
              style={{ width: `${Math.min(health_score, 100)}%` }}
            />
          </div>
          <div className="text-xs text-[var(--grey-light)] mt-1">
            {total_active_tasks} active tasks
          </div>
        </div>
      </div>

      {/* Issue breakdown */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg p-3">
          <div className="text-lg font-semibold text-amber-400">{issues.stale_tasks.count}</div>
          <div className="text-xs text-[var(--grey-light)]">Stale tasks</div>
        </div>
        <div className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg p-3">
          <div className="text-lg font-semibold text-orange-400">{issues.ancient_tasks.count}</div>
          <div className="text-xs text-[var(--grey-light)]">Ancient tasks</div>
        </div>
        <div className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg p-3">
          <div className="text-lg font-semibold text-slate-400">{issues.inactive_tasks.count}</div>
          <div className="text-xs text-[var(--grey-light)]">Inactive tasks</div>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg p-3">
          <div className="text-xs text-[var(--grey-light)]">Priority Inflation</div>
          <div className="font-medium">{(metrics.priority_inflation_ratio * 100).toFixed(1)}%</div>
        </div>
        <div className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg p-3">
          <div className="text-xs text-[var(--grey-light)]">Stale Ratio</div>
          <div className="font-medium">{(metrics.stale_ratio * 100).toFixed(1)}%</div>
        </div>
      </div>

      {/* Suggestions */}
      {data.suggestions.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Suggestions</h4>
          {data.suggestions.map((s, i) => (
            <div
              key={i}
              className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg px-3 py-2 text-xs"
            >
              <span
                className={
                  s.severity === 'critical'
                    ? 'text-red-400'
                    : s.severity === 'high'
                      ? 'text-orange-400'
                      : s.severity === 'medium'
                        ? 'text-amber-400'
                        : 'text-slate-400'
                }
              >
                [{s.severity}]
              </span>{' '}
              {s.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
