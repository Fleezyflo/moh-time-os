// CommitmentList — renders a list of commitments with status, owner, and actions (Phase 9)
import { useCallback } from 'react';
import type { Commitment } from '../../lib/api';

interface CommitmentListProps {
  commitments: Commitment[];
  onMarkDone?: (id: string) => void;
  onLinkTask?: (commitment: Commitment) => void;
  showActions?: boolean;
}

function statusColor(status: string): string {
  switch (status) {
    case 'done':
      return 'var(--success)';
    case 'overdue':
      return 'var(--danger)';
    case 'at_risk':
      return 'var(--warning)';
    default:
      return 'var(--grey-light)';
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'done':
      return 'Done';
    case 'overdue':
      return 'Overdue';
    case 'at_risk':
      return 'At Risk';
    case 'open':
      return 'Open';
    default:
      return status;
  }
}

export function CommitmentList({
  commitments,
  onMarkDone,
  onLinkTask,
  showActions = true,
}: CommitmentListProps) {
  const handleDone = useCallback(
    (id: string) => {
      onMarkDone?.(id);
    },
    [onMarkDone]
  );

  if (commitments.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-[var(--grey-muted)]">No commitments found</div>
    );
  }

  return (
    <div className="space-y-2">
      {commitments.map((c) => (
        <div
          key={c.id}
          className="p-3 rounded-lg border border-[var(--grey)] hover:border-[var(--grey-light)] transition-colors"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{c.text}</div>
              <div className="flex items-center gap-3 mt-1 text-xs text-[var(--grey-light)]">
                <span
                  className="inline-flex items-center gap-1"
                  style={{ color: statusColor(c.status) }}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full inline-block"
                    style={{ backgroundColor: statusColor(c.status) }}
                  />
                  {statusLabel(c.status)}
                </span>
                {c.owner && <span>Owner: {c.owner}</span>}
                {c.due_date && <span>Due: {c.due_date}</span>}
                {c.source_type && <span className="text-[var(--grey-muted)]">{c.source_type}</span>}
                {c.task_id && <span className="text-[var(--accent)]">Linked: {c.task_id}</span>}
              </div>
            </div>
            {showActions && c.status !== 'done' && (
              <div className="flex items-center gap-2 shrink-0">
                {!c.task_id && onLinkTask && (
                  <button
                    onClick={() => onLinkTask(c)}
                    className="text-xs px-2 py-1 rounded border border-[var(--grey)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors"
                  >
                    Link Task
                  </button>
                )}
                {onMarkDone && (
                  <button
                    onClick={() => handleDone(c.id)}
                    className="text-xs px-2 py-1 rounded border border-[var(--grey)] hover:border-[var(--success)] hover:text-[var(--success)] transition-colors"
                  >
                    Done
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
