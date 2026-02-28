// TaskCard — Compact task display for list views
import type { Task } from '../../types/api';

interface TaskCardProps {
  task: Task;
  onClick?: (task: Task) => void;
}

const statusColors: Record<string, string> = {
  pending: 'var(--grey-light)',
  in_progress: 'var(--accent)',
  blocked: 'var(--danger)',
  completed: 'var(--success)',
  done: 'var(--success)',
  cancelled: 'var(--grey-muted)',
  archived: 'var(--grey-muted)',
};

const urgencyLabels: Record<string, string> = {
  critical: 'Critical',
  high: 'High',
  normal: 'Normal',
  low: 'Low',
};

function priorityLabel(score: number): string {
  if (score >= 80) return 'Urgent';
  if (score >= 60) return 'High';
  if (score >= 30) return 'Medium';
  return 'Low';
}

function priorityColor(score: number): string {
  if (score >= 80) return 'var(--danger)';
  if (score >= 60) return 'var(--warning)';
  if (score >= 30) return 'var(--accent)';
  return 'var(--grey-light)';
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return `${Math.abs(diffDays)}d overdue`;
  if (diffDays === 0) return 'Due today';
  if (diffDays === 1) return 'Due tomorrow';
  if (diffDays <= 7) return `Due in ${diffDays}d`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function dueDateColor(dateStr: string | null): string {
  if (!dateStr) return 'var(--grey-muted)';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return 'var(--danger)';
  if (diffDays <= 1) return 'var(--warning)';
  return 'var(--grey-light)';
}

export function TaskCard({ task, onClick }: TaskCardProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.key === 'Enter' || e.key === ' ') && onClick) {
      e.preventDefault();
      onClick(task);
    }
  };

  const isDelegated = !!task.delegated_by;
  const isEscalated = !!task.escalated_to;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onClick?.(task)}
      onKeyDown={handleKeyDown}
      className="card p-4 cursor-pointer hover:bg-[var(--grey)]/50 transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Title + badges */}
          <div className="flex items-center gap-2 mb-1">
            <span
              className="inline-block w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: statusColors[task.status] || 'var(--grey-muted)' }}
              title={task.status}
            />
            <h3 className="text-sm font-medium text-[var(--white)] truncate">{task.title}</h3>
          </div>

          {/* Metadata row */}
          <div className="flex items-center gap-3 text-xs text-[var(--grey-light)]">
            <span style={{ color: priorityColor(task.priority) }}>
              {priorityLabel(task.priority)}
              {task.priority > 0 ? ` (${task.priority})` : ''}
            </span>
            {task.urgency && task.urgency !== 'normal' && (
              <span
                className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                style={{
                  backgroundColor:
                    task.urgency === 'critical'
                      ? 'var(--danger)'
                      : task.urgency === 'high'
                        ? 'var(--warning)'
                        : 'var(--grey)',
                  color: 'var(--white)',
                }}
              >
                {urgencyLabels[task.urgency] || task.urgency}
              </span>
            )}
            {task.assignee && <span title="Assignee">{task.assignee}</span>}
            {task.project && (
              <span
                className="text-[var(--grey-muted)] truncate max-w-[120px]"
                title={task.project}
              >
                {task.project}
              </span>
            )}
          </div>
        </div>

        {/* Right side: due date + delegation badges */}
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          {task.due_date && (
            <span className="text-xs" style={{ color: dueDateColor(task.due_date) }}>
              {formatDate(task.due_date)}
            </span>
          )}
          {isDelegated && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--accent)]/20 text-[var(--accent)]">
              Delegated
            </span>
          )}
          {isEscalated && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--warning)]/20 text-[var(--warning)]">
              Escalated
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
