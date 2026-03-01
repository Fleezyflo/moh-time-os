// GroupedPriorityView — Display priorities grouped by project/assignee
import type { PriorityItem } from '../../lib/api';

interface GroupedPriorityViewProps {
  groups: Record<string, PriorityItem[]>;
  groupBy: string;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onItemClick: (item: PriorityItem) => void;
}

function priorityColor(score: number): string {
  if (score >= 80) return 'var(--danger)';
  if (score >= 60) return 'var(--warning)';
  if (score >= 30) return 'var(--accent)';
  return 'var(--grey-light)';
}

function dueDateDisplay(dateStr: string | null): { text: string; color: string } {
  if (!dateStr) return { text: 'No due date', color: 'var(--grey-muted)' };
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return { text: `${Math.abs(diffDays)}d overdue`, color: 'var(--danger)' };
  if (diffDays === 0) return { text: 'Due today', color: 'var(--warning)' };
  if (diffDays === 1) return { text: 'Due tomorrow', color: 'var(--warning)' };
  if (diffDays <= 7) return { text: `Due in ${diffDays}d`, color: 'var(--grey-light)' };
  return {
    text: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    color: 'var(--grey-light)',
  };
}

export function GroupedPriorityView({
  groups,
  groupBy,
  selectedIds,
  onToggleSelect,
  onItemClick,
}: GroupedPriorityViewProps) {
  const groupEntries = Object.entries(groups).sort(([, a], [, b]) => b.length - a.length);

  if (groupEntries.length === 0) {
    return <p className="text-sm text-[var(--grey-muted)] py-8 text-center">No items to display</p>;
  }

  return (
    <div className="space-y-6">
      {groupEntries.map(([groupName, items]) => (
        <div key={groupName} className="bg-[var(--grey-dim)] rounded-lg overflow-hidden">
          {/* Group header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--grey)]">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-medium text-[var(--white)]">
                {groupName || `No ${groupBy}`}
              </h3>
              <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--grey)] text-[var(--grey-light)]">
                {items.length}
              </span>
            </div>
            <span className="text-xs text-[var(--grey-light)]">
              Avg score:{' '}
              {items.length > 0
                ? Math.round(items.reduce((sum, i) => sum + i.score, 0) / items.length)
                : 0}
            </span>
          </div>

          {/* Group items */}
          <div className="divide-y divide-[var(--grey)]">
            {items.map((item) => {
              const due = dueDateDisplay(item.due);
              const isSelected = selectedIds.has(item.id);
              return (
                <div
                  key={item.id}
                  className={`flex items-center gap-3 px-4 py-3 hover:bg-[var(--grey)]/30 transition-colors ${
                    isSelected ? 'bg-[var(--accent)]/5' : ''
                  }`}
                >
                  {/* Checkbox */}
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => onToggleSelect(item.id)}
                    className="w-4 h-4 rounded border-[var(--grey)] accent-[var(--accent)] flex-shrink-0"
                    aria-label={`Select ${item.title}`}
                  />

                  {/* Item content */}
                  <button
                    onClick={() => onItemClick(item)}
                    className="flex-1 min-w-0 text-left focus:outline-none focus:ring-2 focus:ring-[var(--accent)] rounded"
                  >
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm text-[var(--white)] truncate">{item.title}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span style={{ color: priorityColor(item.score) }}>Score {item.score}</span>
                      {item.assignee && (
                        <span className="text-[var(--grey-light)]">{item.assignee}</span>
                      )}
                      {item.reasons.length > 0 && (
                        <span className="text-[var(--grey-muted)] truncate">
                          {item.reasons.join(' · ')}
                        </span>
                      )}
                    </div>
                  </button>

                  {/* Due date */}
                  <span className="text-xs flex-shrink-0" style={{ color: due.color }}>
                    {due.text}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
