// DelegationPanel — Shows delegation info on task detail
import type { Task } from '../../types/api';

interface DelegationPanelProps {
  task: Task;
}

export function DelegationPanel({ task }: DelegationPanelProps) {
  const isDelegated = !!task.delegated_by;
  const isEscalated = !!task.escalated_to;

  if (!isDelegated && !isEscalated) return null;

  return (
    <div className="space-y-3">
      {isDelegated && (
        <div className="card p-3">
          <h4 className="text-xs font-medium text-[var(--accent)] uppercase tracking-wide mb-2">
            Delegation
          </h4>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--grey-light)]">Delegated by</span>
              <span className="text-[var(--white)]">{task.delegated_by}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--grey-light)]">Assigned to</span>
              <span className="text-[var(--white)]">{task.assignee || 'Unassigned'}</span>
            </div>
            {task.delegated_at && (
              <div className="flex justify-between">
                <span className="text-[var(--grey-light)]">Since</span>
                <span className="text-[var(--white)]">
                  {new Date(task.delegated_at).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            )}
            {task.delegation_status && (
              <div className="flex justify-between">
                <span className="text-[var(--grey-light)]">Status</span>
                <span className="text-[var(--accent)]">{task.delegation_status}</span>
              </div>
            )}
            {task.delegated_note && (
              <div className="mt-2 p-2 rounded bg-[var(--grey)]/50 text-xs text-[var(--grey-light)]">
                {task.delegated_note}
              </div>
            )}
          </div>
        </div>
      )}

      {isEscalated && (
        <div className="card p-3">
          <h4 className="text-xs font-medium text-[var(--warning)] uppercase tracking-wide mb-2">
            Escalation
          </h4>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--grey-light)]">Escalated to</span>
              <span className="text-[var(--white)]">{task.escalated_to}</span>
            </div>
            {task.escalation_level != null && (
              <div className="flex justify-between">
                <span className="text-[var(--grey-light)]">Level</span>
                <span className="text-[var(--warning)]">{task.escalation_level}</span>
              </div>
            )}
            {task.escalated_at && (
              <div className="flex justify-between">
                <span className="text-[var(--grey-light)]">Since</span>
                <span className="text-[var(--white)]">
                  {new Date(task.escalated_at).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            )}
            {task.escalation_reason && (
              <div className="mt-2 p-2 rounded bg-[var(--grey)]/50 text-xs text-[var(--grey-light)]">
                {task.escalation_reason}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
