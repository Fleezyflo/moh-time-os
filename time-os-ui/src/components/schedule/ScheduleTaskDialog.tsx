// ScheduleTaskDialog — dialog for scheduling a task into a time block
import { useState, useCallback } from 'react';
import type { TimeBlock } from '../../lib/api';

interface ScheduleTaskDialogProps {
  block: TimeBlock;
  open: boolean;
  onClose: () => void;
  onSchedule: (taskId: string, blockId: string) => Promise<void>;
}

export function ScheduleTaskDialog({ block, open, onClose, onSchedule }: ScheduleTaskDialogProps) {
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
      await onSchedule(taskId.trim(), block.id);
      setTaskId('');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to schedule task');
    } finally {
      setSubmitting(false);
    }
  }, [taskId, block.id, onSchedule, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      role="dialog"
      aria-modal="true"
      aria-label="Schedule task"
    >
      <div className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-xl p-6 w-full max-w-md mx-4">
        <h3 className="text-lg font-semibold mb-4">Schedule Task</h3>
        <div className="text-sm text-[var(--grey-light)] mb-4">
          Block: {block.start_time} &ndash; {block.end_time} ({block.duration_min}m, {block.lane}{' '}
          lane)
        </div>
        <label className="block text-sm mb-1">Task ID</label>
        <input
          type="text"
          value={taskId}
          onChange={(e) => setTaskId(e.target.value)}
          placeholder="Enter task ID to schedule"
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
            {submitting ? 'Scheduling...' : 'Schedule'}
          </button>
        </div>
      </div>
    </div>
  );
}
