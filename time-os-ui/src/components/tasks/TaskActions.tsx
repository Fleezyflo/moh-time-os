// TaskActions — Action buttons for task detail (delegate, escalate, recall, notes)
import { useState } from 'react';
import type { Task } from '../../types/api';
import * as api from '../../lib/api';

interface TaskActionsProps {
  task: Task;
  onAction: () => void;
  onApprovalRequired: (response: { reason?: string; decision_id?: string }) => void;
  toast: { success: (msg: string) => void; error: (msg: string) => void };
}

type ActionMode = null | 'delegate' | 'escalate' | 'note';

export function TaskActions({ task, onAction, onApprovalRequired, toast }: TaskActionsProps) {
  const [mode, setMode] = useState<ActionMode>(null);
  const [loading, setLoading] = useState(false);
  const [delegateTo, setDelegateTo] = useState('');
  const [delegateNote, setDelegateNote] = useState('');
  const [delegateDueDate, setDelegateDueDate] = useState('');
  const [escalateTo, setEscalateTo] = useState('');
  const [escalateReason, setEscalateReason] = useState('');
  const [noteText, setNoteText] = useState('');

  const isDelegated = !!task.delegated_by;

  const handleDelegate = async () => {
    if (!delegateTo.trim()) return;
    setLoading(true);
    try {
      const result = await api.delegateTask(task.id, {
        to: delegateTo.trim(),
        note: delegateNote.trim() || undefined,
        due_date: delegateDueDate || undefined,
      });
      if (result.requires_approval) {
        onApprovalRequired({
          reason: result.reason,
          decision_id: result.decision_id,
        });
      } else if (result.success) {
        toast.success(`Delegated to ${result.delegated_to || delegateTo}`);
        if (result.warning) toast.error(result.warning);
        setMode(null);
        onAction();
      } else {
        toast.error(result.error || 'Delegation failed');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delegation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleEscalate = async () => {
    if (!escalateTo.trim()) return;
    setLoading(true);
    try {
      const result = await api.escalateTask(task.id, {
        to: escalateTo.trim(),
        reason: escalateReason.trim() || undefined,
      });
      if (result.requires_approval) {
        onApprovalRequired({
          reason: result.reason,
          decision_id: result.decision_id,
        });
      } else if (result.success) {
        toast.success(
          `Escalated to ${result.escalated_to || escalateTo} (priority: ${result.new_priority})`
        );
        setMode(null);
        onAction();
      } else {
        toast.error(result.error || 'Escalation failed');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Escalation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRecall = async () => {
    setLoading(true);
    try {
      const result = await api.recallTask(task.id);
      if (result.success) {
        toast.success('Delegation recalled');
        onAction();
      } else {
        toast.error(result.error || 'Recall failed');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Recall failed');
    } finally {
      setLoading(false);
    }
  };

  const handleAddNote = async () => {
    if (!noteText.trim()) return;
    setLoading(true);
    try {
      const result = await api.addTaskNote(task.id, noteText.trim());
      if (result.success) {
        toast.success('Note added');
        setNoteText('');
        setMode(null);
        onAction();
      } else {
        toast.error(result.error || 'Failed to add note');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add note');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Action buttons */}
      {!mode && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setMode('delegate')}
            className="px-3 py-1.5 text-xs font-medium rounded bg-[var(--accent)] hover:bg-[var(--accent)]/80 text-white transition-colors"
          >
            Delegate
          </button>
          <button
            onClick={() => setMode('escalate')}
            className="px-3 py-1.5 text-xs font-medium rounded bg-[var(--warning)] hover:bg-[var(--warning)]/80 text-white transition-colors"
          >
            Escalate
          </button>
          {isDelegated && (
            <button
              onClick={handleRecall}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-medium rounded bg-[var(--grey)] hover:bg-[var(--grey-light)] text-[var(--white)] transition-colors disabled:opacity-50"
            >
              {loading ? 'Recalling...' : 'Recall'}
            </button>
          )}
          <button
            onClick={() => setMode('note')}
            className="px-3 py-1.5 text-xs font-medium rounded bg-[var(--grey)] hover:bg-[var(--grey-light)] text-[var(--white)] transition-colors"
          >
            Add Note
          </button>
        </div>
      )}

      {/* Delegate form */}
      {mode === 'delegate' && (
        <div className="card p-3 space-y-2">
          <h4 className="text-sm font-medium text-[var(--white)]">Delegate Task</h4>
          <input
            type="text"
            placeholder="Delegate to (name)..."
            value={delegateTo}
            onChange={(e) => setDelegateTo(e.target.value)}
            className="w-full px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] placeholder-[var(--grey-muted)]"
          />
          <input
            type="text"
            placeholder="Note (optional)..."
            value={delegateNote}
            onChange={(e) => setDelegateNote(e.target.value)}
            className="w-full px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] placeholder-[var(--grey-muted)]"
          />
          <input
            type="date"
            value={delegateDueDate}
            onChange={(e) => setDelegateDueDate(e.target.value)}
            className="w-full px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)]"
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setMode(null)}
              className="px-3 py-1.5 text-xs rounded bg-[var(--grey)] text-[var(--white)] hover:bg-[var(--grey-light)]"
            >
              Cancel
            </button>
            <button
              onClick={handleDelegate}
              disabled={loading || !delegateTo.trim()}
              className="px-3 py-1.5 text-xs rounded bg-[var(--accent)] text-white hover:bg-[var(--accent)]/80 disabled:opacity-50"
            >
              {loading ? 'Delegating...' : 'Delegate'}
            </button>
          </div>
        </div>
      )}

      {/* Escalate form */}
      {mode === 'escalate' && (
        <div className="card p-3 space-y-2">
          <h4 className="text-sm font-medium text-[var(--white)]">Escalate Task</h4>
          <input
            type="text"
            placeholder="Escalate to (name)..."
            value={escalateTo}
            onChange={(e) => setEscalateTo(e.target.value)}
            className="w-full px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] placeholder-[var(--grey-muted)]"
          />
          <textarea
            placeholder="Reason (optional)..."
            value={escalateReason}
            onChange={(e) => setEscalateReason(e.target.value)}
            rows={2}
            className="w-full px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] placeholder-[var(--grey-muted)] resize-none"
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setMode(null)}
              className="px-3 py-1.5 text-xs rounded bg-[var(--grey)] text-[var(--white)] hover:bg-[var(--grey-light)]"
            >
              Cancel
            </button>
            <button
              onClick={handleEscalate}
              disabled={loading || !escalateTo.trim()}
              className="px-3 py-1.5 text-xs rounded bg-[var(--warning)] text-white hover:bg-[var(--warning)]/80 disabled:opacity-50"
            >
              {loading ? 'Escalating...' : 'Escalate'}
            </button>
          </div>
        </div>
      )}

      {/* Note form */}
      {mode === 'note' && (
        <div className="card p-3 space-y-2">
          <h4 className="text-sm font-medium text-[var(--white)]">Add Note</h4>
          <textarea
            placeholder="Enter note..."
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            rows={3}
            className="w-full px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] placeholder-[var(--grey-muted)] resize-none"
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setMode(null)}
              className="px-3 py-1.5 text-xs rounded bg-[var(--grey)] text-[var(--white)] hover:bg-[var(--grey-light)]"
            >
              Cancel
            </button>
            <button
              onClick={handleAddNote}
              disabled={loading || !noteText.trim()}
              className="px-3 py-1.5 text-xs rounded bg-[var(--accent)] text-white hover:bg-[var(--accent)]/80 disabled:opacity-50"
            >
              {loading ? 'Adding...' : 'Add Note'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
