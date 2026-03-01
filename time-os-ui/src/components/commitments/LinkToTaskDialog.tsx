// LinkToTaskDialog — dialog for linking a commitment to a task (Phase 9)
import { useState, useCallback } from 'react';
import type { Commitment } from '../../lib/api';

interface LinkToTaskDialogProps {
  commitment: Commitment;
  open: boolean;
  onClose: () => void;
  onLink: (commitmentId: string, taskId: string) => Promise<void>;
}

export function LinkToTaskDialog({ commitment, open, onClose, onLink }: LinkToTaskDialogProps) {
  const [taskId, setTaskId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    if (!taskId.trim()) {
      setError('Task ID is required');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onLink(commitment.id, taskId.trim());
      setTaskId('');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to link commitment');
    } finally {
      setSubmitting(false);
    }
  }, [taskId, commitment.id, onLink, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      role="dialog"
      aria-modal="true"
      aria-label="Link commitment to task"
    >
      <div className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-xl p-6 w-full max-w-md mx-4">
        <h3 className="text-lg font-semibold mb-4">Link to Task</h3>
        <div className="text-sm text-[var(--grey-light)] mb-4 line-clamp-2">{commitment.text}</div>
        <label className="block text-sm mb-1">Task ID</label>
        <input
          type="text"
          value={taskId}
          onChange={(e) => setTaskId(e.target.value)}
          placeholder="Enter task ID to link"
          className="w-full px-3 py-2 rounded-lg bg-[var(--black)] border border-[var(--grey)] text-sm focus:border-[var(--accent)] outline-none"
          disabled={submitting}
          autoFocus
        />
        {error && <div className="text-sm text-[var(--danger)] mt-2">{error}</div>}
        <div className="flex justify-end gap-2 mt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-[var(--grey)] hover:bg-[var(--grey)] transition-colors"
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className="px-4 py-2 text-sm rounded-lg bg-[var(--accent)] text-white hover:opacity-90 transition-opacity"
            disabled={submitting}
          >
            {submitting ? 'Linking...' : 'Link'}
          </button>
        </div>
      </div>
    </div>
  );
}
