// WeeklyDigestView — displays weekly summary: completed, slipped, archived counts (Phase 10)
import type { WeeklyDigestResponse } from '../../lib/api';

interface WeeklyDigestViewProps {
  digest: WeeklyDigestResponse;
}

export function WeeklyDigestView({ digest }: WeeklyDigestViewProps) {
  const { period, completed, slipped, archived } = digest;

  return (
    <div className="space-y-6">
      {/* Period header */}
      <div className="text-sm text-[var(--grey-light)]">
        Week of {period.start} to {period.end}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-4 rounded-lg bg-[var(--grey-dim)] border border-[var(--grey)] text-center">
          <div className="text-2xl font-bold" style={{ color: 'var(--success)' }}>
            {completed.count}
          </div>
          <div className="text-xs text-[var(--grey-light)] mt-1">Completed</div>
        </div>
        <div className="p-4 rounded-lg bg-[var(--grey-dim)] border border-[var(--grey)] text-center">
          <div className="text-2xl font-bold" style={{ color: 'var(--danger)' }}>
            {slipped.count}
          </div>
          <div className="text-xs text-[var(--grey-light)] mt-1">Slipped</div>
        </div>
        <div className="p-4 rounded-lg bg-[var(--grey-dim)] border border-[var(--grey)] text-center">
          <div className="text-2xl font-bold text-[var(--grey-light)]">{archived}</div>
          <div className="text-xs text-[var(--grey-light)] mt-1">Archived</div>
        </div>
      </div>

      {/* Completed items */}
      {completed.items.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-2" style={{ color: 'var(--success)' }}>
            Completed tasks
          </h3>
          <div className="space-y-1">
            {completed.items.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between py-2 px-3 rounded bg-[var(--grey-dim)] text-sm"
              >
                <span className="truncate">{item.title}</span>
                <span className="text-xs text-[var(--grey-light)] flex-shrink-0 ml-3">
                  {item.completed_at.slice(0, 10)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Slipped items */}
      {slipped.items.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-2" style={{ color: 'var(--danger)' }}>
            Slipped tasks
          </h3>
          <div className="space-y-1">
            {slipped.items.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between py-2 px-3 rounded bg-[var(--grey-dim)] text-sm"
              >
                <div className="truncate">
                  <span>{item.title}</span>
                  {item.assignee && (
                    <span className="text-xs text-[var(--grey-light)] ml-2">({item.assignee})</span>
                  )}
                </div>
                <span className="text-xs flex-shrink-0 ml-3" style={{ color: 'var(--danger)' }}>
                  due {item.due}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {completed.items.length === 0 && slipped.items.length === 0 && (
        <div className="text-center py-8 text-[var(--grey-light)]">No activity this week</div>
      )}
    </div>
  );
}
