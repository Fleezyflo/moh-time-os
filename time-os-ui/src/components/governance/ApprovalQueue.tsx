// Approval queue — pending approvals with approve/reject actions
import { useState, useCallback } from 'react';
import type { Approval } from '../../lib/api';
import { processApproval } from '../../lib/api';

interface Props {
  approvals: Approval[];
  onRefresh: () => void;
}

const RISK_COLORS: Record<string, string> = {
  low: 'text-green-400',
  medium: 'text-amber-400',
  high: 'text-orange-400',
  critical: 'text-red-400',
};

export function ApprovalQueue({ approvals, onRefresh }: Props) {
  const [processing, setProcessing] = useState<string | null>(null);

  const handleAction = useCallback(
    async (decisionId: string, action: 'approve' | 'reject') => {
      setProcessing(decisionId);
      try {
        await processApproval(decisionId, action);
        onRefresh();
      } finally {
        setProcessing(null);
      }
    },
    [onRefresh]
  );

  if (approvals.length === 0) {
    return (
      <div className="text-center py-12 text-[var(--grey-light)]">
        <p className="text-sm">No pending approvals</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {approvals.map((a) => (
        <div
          key={a.decision_id}
          className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-xl p-4 space-y-2"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{a.description || a.action_type}</span>
                <span className={`text-xs ${RISK_COLORS[a.risk_level] ?? 'text-slate-400'}`}>
                  {a.risk_level}
                </span>
              </div>
              <div className="text-xs text-[var(--grey-light)] mt-1">
                {a.target_entity}:{a.target_id} &middot; {a.source} &middot;{' '}
                {new Date(a.created_at).toLocaleDateString()}
              </div>
            </div>
          </div>

          {/* Payload preview */}
          {a.payload && Object.keys(a.payload).length > 0 && (
            <div className="text-xs text-[var(--grey-light)] bg-[var(--grey)]/50 rounded-lg p-2 font-mono overflow-x-auto">
              {JSON.stringify(a.payload, null, 2).slice(0, 200)}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => handleAction(a.decision_id, 'approve')}
              disabled={processing === a.decision_id}
              className="text-xs px-3 py-1.5 rounded-lg bg-green-700/50 hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              Approve
            </button>
            <button
              onClick={() => handleAction(a.decision_id, 'reject')}
              disabled={processing === a.decision_id}
              className="text-xs px-3 py-1.5 rounded-lg bg-red-700/50 hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
