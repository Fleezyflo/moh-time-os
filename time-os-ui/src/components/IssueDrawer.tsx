// IssueDrawer — detail view for an issue
import { useState, useEffect, useRef } from 'react';
import type { Issue } from '../types/api';
import type { IssueState } from '../lib/api';
import { useToast } from './Toast';
import {
  stateStyles,
  defaultStateStyle,
  getTitle,
  getType,
  getPriority,
  getCreatedAt,
  getLastActivity,
  getPriorityInfo,
} from '../lib/issueStyles';

interface IssueDrawerProps {
  issue: Issue | null;
  open: boolean;
  onClose: () => void;
  onResolve?: () => Promise<void>;
  onAddNote?: (text: string) => Promise<void>;
  onChangeState?: (newState: IssueState) => Promise<void>;
}

export function IssueDrawer({
  issue,
  open,
  onClose,
  onResolve,
  onAddNote,
  onChangeState,
}: IssueDrawerProps) {
  const toast = useToast();
  const [isResolving, setIsResolving] = useState(false);
  const [isChangingState, setIsChangingState] = useState(false);
  const [isAddingNote, setIsAddingNote] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [showNoteInput, setShowNoteInput] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ESC key to close
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  // Lock body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [open]);

  // Focus trap - keep focus within drawer
  const drawerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open || !drawerRef.current) return;

    // Focus first focusable element
    const firstFocusable = drawerRef.current.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    firstFocusable?.focus();

    // Trap focus within drawer
    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !drawerRef.current) return;

      const focusables = drawerRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };

    document.addEventListener('keydown', handleTab);
    return () => document.removeEventListener('keydown', handleTab);
  }, [open]);

  if (!open || !issue) return null;

  const stateStyle = stateStyles[issue.state] || defaultStateStyle;
  const priorityInfo = getPriorityInfo(getPriority(issue));

  const handleResolve = async () => {
    if (!onResolve) return;
    setIsResolving(true);
    setError(null);
    try {
      await onResolve();
      toast.success('Issue resolved');
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to resolve';
      setError(message);
      toast.error(message);
    } finally {
      setIsResolving(false);
    }
  };

  const handleChangeState = async (newState: IssueState) => {
    if (!onChangeState) return;
    setIsChangingState(true);
    setError(null);
    try {
      await onChangeState(newState);
      toast.success(`Issue state changed to ${newState}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to change state';
      setError(message);
      toast.error(message);
    } finally {
      setIsChangingState(false);
    }
  };

  const handleAddNote = async () => {
    if (!onAddNote || !noteText.trim()) return;
    setIsAddingNote(true);
    setError(null);
    try {
      await onAddNote(noteText.trim());
      toast.success('Note added');
      setNoteText('');
      setShowNoteInput(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add note';
      setError(message);
      toast.error(message);
    } finally {
      setIsAddingNote(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Drawer */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="issue-drawer-title"
        className="absolute right-0 top-0 h-full w-full max-w-lg bg-[var(--black)] border-l border-[var(--grey)] shadow-xl overflow-y-auto"
      >
        {/* Header */}
        <div className={`p-4 border-b border-[var(--grey)] ${stateStyle.bg}`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className={`text-lg ${stateStyle.color}`}>{stateStyle.icon}</span>
              <span className={`font-medium ${stateStyle.color}`}>{stateStyle.label}</span>
            </div>
            <button
              onClick={onClose}
              aria-label="Close issue drawer"
              className="text-[var(--grey-light)] hover:text-[var(--white)] focus:outline-none focus:ring-2 focus:ring-[var(--grey-light)] rounded"
            >
              ✕
            </button>
          </div>
          <h2 id="issue-drawer-title" className="text-lg font-semibold text-[var(--white)]">
            {getTitle(issue)}
          </h2>
        </div>

        {/* Details */}
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-[var(--grey-light)] uppercase tracking-wide">
                Priority
              </div>
              <div className={`font-medium ${priorityInfo.color}`}>{priorityInfo.label}</div>
            </div>
            <div>
              <div className="text-xs text-[var(--grey-light)] uppercase tracking-wide">Type</div>
              <div className="text-[var(--white)]">{getType(issue) || 'N/A'}</div>
            </div>
            {getCreatedAt(issue) && (
              <div>
                <div className="text-xs text-[var(--grey-light)] uppercase tracking-wide">
                  Created
                </div>
                <div className="text-[var(--white)]">
                  {new Date(getCreatedAt(issue)).toLocaleString()}
                </div>
              </div>
            )}
            {getLastActivity(issue) && (
              <div>
                <div className="text-xs text-[var(--grey-light)] uppercase tracking-wide">
                  Last Activity
                </div>
                <div className="text-[var(--white)]">
                  {new Date(getLastActivity(issue)).toLocaleString()}
                </div>
              </div>
            )}
          </div>

          {issue.client_id && (
            <div className="border-t border-[var(--grey)] pt-4">
              <div className="text-xs text-[var(--grey-light)] uppercase tracking-wide mb-2">
                Client
              </div>
              <div className="text-sm text-[var(--grey-subtle)]">{issue.client_id}</div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="p-4 border-t border-[var(--grey)] space-y-3">
          {error && (
            <div className="text-sm text-red-400 bg-red-900/20 px-3 py-2 rounded">{error}</div>
          )}

          {showNoteInput && (
            <div className="space-y-2">
              <textarea
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                placeholder="Add a note..."
                className="w-full px-3 py-2 bg-[var(--grey-dim)] border border-[var(--grey-mid)] rounded text-sm text-[var(--white)] placeholder-[var(--grey-muted)] focus:outline-none focus:border-blue-500"
                rows={3}
              />
              <div className="flex gap-2">
                <button
                  onClick={handleAddNote}
                  disabled={isAddingNote || !noteText.trim()}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-[var(--grey)] disabled:cursor-not-allowed text-white text-sm rounded"
                >
                  {isAddingNote ? 'Saving...' : 'Save Note'}
                </button>
                <button
                  onClick={() => {
                    setShowNoteInput(false);
                    setNoteText('');
                  }}
                  className="px-3 py-1.5 bg-[var(--grey)] hover:bg-[var(--grey-mid)] text-[var(--white)] text-sm rounded"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="flex items-center gap-2" role="group" aria-label="Issue actions">
            <button
              onClick={handleResolve}
              disabled={isResolving || issue.state === 'resolved'}
              aria-label={
                isResolving
                  ? 'Resolving issue...'
                  : issue.state === 'resolved'
                    ? 'Issue already resolved'
                    : 'Resolve this issue'
              }
              className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-[var(--grey)] disabled:cursor-not-allowed text-white text-sm font-medium rounded focus:outline-none focus:ring-2 focus:ring-green-400 focus:ring-offset-2 focus:ring-offset-[var(--black)]"
            >
              {isResolving ? 'Resolving...' : issue.state === 'resolved' ? 'Resolved' : 'Resolve'}
            </button>
            <button
              onClick={() => setShowNoteInput(true)}
              aria-label="Add a note to this issue"
              disabled={showNoteInput}
              className="px-4 py-2 bg-[var(--grey)] hover:bg-[var(--grey-mid)] disabled:bg-[var(--grey-mid)] text-[var(--white)] text-sm rounded"
            >
              Add Note
            </button>
          </div>

          {/* State Transition Buttons */}
          {onChangeState && issue.state !== 'resolved' && issue.state !== 'closed' && (
            <div
              className="flex flex-wrap items-center gap-2 mt-3"
              role="group"
              aria-label="State transitions"
            >
              {issue.state !== 'monitoring' && (
                <button
                  onClick={() => handleChangeState('monitoring')}
                  disabled={isChangingState}
                  className="px-3 py-1.5 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 text-white text-xs rounded"
                >
                  {isChangingState ? '...' : 'Monitor'}
                </button>
              )}
              {issue.state !== 'blocked' && (
                <button
                  onClick={() => handleChangeState('blocked')}
                  disabled={isChangingState}
                  className="px-3 py-1.5 bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white text-xs rounded"
                >
                  {isChangingState ? '...' : 'Block'}
                </button>
              )}
              {issue.state === 'blocked' && (
                <button
                  onClick={() => handleChangeState('open')}
                  disabled={isChangingState}
                  className="px-3 py-1.5 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-white text-xs rounded"
                >
                  {isChangingState ? '...' : 'Unblock'}
                </button>
              )}
              {issue.state !== 'awaiting' && (
                <button
                  onClick={() => handleChangeState('awaiting')}
                  disabled={isChangingState}
                  className="px-3 py-1.5 bg-amber-700 hover:bg-amber-600 disabled:opacity-50 text-white text-xs rounded"
                >
                  {isChangingState ? '...' : 'Set Awaiting'}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
