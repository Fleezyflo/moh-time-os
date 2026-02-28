// ApprovalDialog — Shown when a task action requires governance approval
interface ApprovalDialogProps {
  reason?: string;
  decisionId?: string;
  onClose: () => void;
}

export function ApprovalDialog({ reason, decisionId, onClose }: ApprovalDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-[var(--grey-dim)] rounded-lg shadow-lg max-w-sm mx-4 p-6">
        <h2 className="text-lg font-semibold text-[var(--warning)] mb-3">Approval Required</h2>
        <p className="text-sm text-[var(--grey-light)] mb-4">
          {reason || 'This action requires governance approval before it can be executed.'}
        </p>
        {decisionId && (
          <p className="text-xs text-[var(--grey-muted)] mb-4">
            Decision ID: <code className="text-[var(--grey-light)]">{decisionId}</code>
          </p>
        )}
        <p className="text-sm text-[var(--grey-light)] mb-6">
          The request has been submitted for review. You will be notified when a decision is made.
        </p>
        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded text-sm font-medium bg-[var(--grey)] hover:bg-[var(--grey-light)] text-[var(--white)] transition-colors"
          >
            Understood
          </button>
        </div>
      </div>
    </div>
  );
}
