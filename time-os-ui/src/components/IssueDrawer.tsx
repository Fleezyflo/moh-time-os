// IssueDrawer — detail view for an issue
import { useState, useEffect, useRef } from 'react';
import type { Issue } from '../types/api';
import type { IssueState } from '../lib/api';
import { priorityLabel } from '../lib/priority';
import { useToast } from './notifications';

interface IssueDrawerProps {
  issue: Issue | null;
  open: boolean;
  onClose: () => void;
  onResolve?: () => Promise<void>;
  onAddNote?: (text: string) => Promise<void>;
  onChangeState?: (newState: IssueState) => Promise<void>;
}

const stateStyles: Record<string, { icon: string; color: string; bg: string; label: string }> = {
  // v29 states
  detected: { icon: '◎', color: 'text-blue-300', bg: 'bg-blue-900/20', label: 'Detected' },
  surfaced: { icon: '○', color: 'text-blue-400', bg: 'bg-blue-900/30', label: 'Surfaced' },
  snoozed: { icon: '◷', color: 'text-amber-400', bg: 'bg-amber-900/30', label: 'Snoozed' },
  acknowledged: {
    icon: '◉',
    color: 'text-purple-400',
    bg: 'bg-purple-900/30',
    label: 'Acknowledged',
  },
  addressing: { icon: '⊕', color: 'text-cyan-400', bg: 'bg-cyan-900/30', label: 'Addressing' },
  awaiting_resolution: {
    icon: '◷',
    color: 'text-amber-400',
    bg: 'bg-amber-900/30',
    label: 'Awaiting Resolution',
  },
  regression_watch: {
    icon: '◎',
    color: 'text-yellow-400',
    bg: 'bg-yellow-900/30',
    label: 'Regression Watch',
  },
  regressed: { icon: '⊘', color: 'text-red-400', bg: 'bg-red-900/30', label: 'Regressed' },
  closed: { icon: '✓', color: 'text-green-400', bg: 'bg-green-900/30', label: 'Closed' },
  // Legacy states
  open: { icon: '○', color: 'text-blue-400', bg: 'bg-blue-900/30', label: 'Open' },
  monitoring: { icon: '◉', color: 'text-purple-400', bg: 'bg-purple-900/30', label: 'Monitoring' },
  awaiting: { icon: '◷', color: 'text-amber-400', bg: 'bg-amber-900/30', label: 'Awaiting' },
  blocked: { icon: '⊘', color: 'text-red-400', bg: 'bg-red-900/30', label: 'Blocked' },
  resolved: { icon: '✓', color: 'text-green-400', bg: 'bg-green-900/30', label: 'Resolved' },
};

const priorityColors: Record<string, string> = {
  critical: 'text-red-400',
  high: 'text-orange-400',
  medium: 'text-amber-400',
  low: 'text-slate-400',
  info: 'text-slate-500',
};

// Convert v29 severity to priority number
const severityToPriority = (severity: string | undefined): number => {
  switch (severity) {
    case 'critical':
      return 90;
    case 'high':
      return 70;
    case 'medium':
      return 50;
    case 'low':
      return 30;
    case 'info':
      return 10;
    default:
      return 50;
  }
};

// Get issue title (v29: title, legacy: headline)
const getTitle = (issue: Issue): string => issue.title || issue.headline || '';

// Get issue type (v29: type, legacy: issue_type - not in Issue type but may exist)
const getType = (issue: Issue): string => issue.type || '';

// Get priority (v29: severity→number, legacy: priority)
const getPriority = (issue: Issue): number => issue.priority ?? severityToPriority(issue.severity);

// Get created at (v29: created_at, legacy: opened_at - not in Issue type)
const getCreatedAt = (issue: Issue): string => issue.created_at || '';

// Get last activity (v29: updated_at, legacy: last_activity_at)
const getLastActivity = (issue: Issue): string => issue.updated_at || issue.last_activity_at || '';

function getPriorityInfo(priority: number): { label: string; color: string } {
  const label = priorityLabel(priority);
  return {
    label: label.charAt(0).toUpperCase() + label.slice(1),
    color: priorityColors[label] || priorityColors.medium,
  };
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

  const stateStyle = stateStyles[issue.state] || stateStyles.open;
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
        className="absolute right-0 top-0 h-full w-full max-w-lg bg-slate-900 border-l border-slate-700 shadow-xl overflow-y-auto"
      >
        {/* Header */}
        <div className={`p-4 border-b border-slate-700 ${stateStyle.bg}`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className={`text-lg ${stateStyle.color}`}>{stateStyle.icon}</span>
              <span className={`font-medium ${stateStyle.color}`}>{stateStyle.label}</span>
            </div>
            <button
              onClick={onClose}
              aria-label="Close issue drawer"
              className="text-slate-400 hover:text-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-400 rounded"
            >
              ✕
            </button>
          </div>
          <h2 id="issue-drawer-title" className="text-lg font-semibold text-slate-100">
            {getTitle(issue)}
          </h2>
        </div>

        {/* Details */}
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wide">Priority</div>
              <div className={`font-medium ${priorityInfo.color}`}>{priorityInfo.label}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wide">Type</div>
              <div className="text-slate-200">{getType(issue) || 'N/A'}</div>
            </div>
            {getCreatedAt(issue) && (
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wide">Created</div>
                <div className="text-slate-200">
                  {new Date(getCreatedAt(issue)).toLocaleString()}
                </div>
              </div>
            )}
            {getLastActivity(issue) && (
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wide">Last Activity</div>
                <div className="text-slate-200">
                  {new Date(getLastActivity(issue)).toLocaleString()}
                </div>
              </div>
            )}
          </div>

          {issue.client_id && (
            <div className="border-t border-slate-700 pt-4">
              <div className="text-xs text-slate-400 uppercase tracking-wide mb-2">Client</div>
              <div className="text-sm text-slate-300">{issue.client_id}</div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="p-4 border-t border-slate-700 space-y-3">
          {error && (
            <div className="text-sm text-red-400 bg-red-900/20 px-3 py-2 rounded">{error}</div>
          )}

          {showNoteInput && (
            <div className="space-y-2">
              <textarea
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                placeholder="Add a note..."
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                rows={3}
              />
              <div className="flex gap-2">
                <button
                  onClick={handleAddNote}
                  disabled={isAddingNote || !noteText.trim()}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-sm rounded"
                >
                  {isAddingNote ? 'Saving...' : 'Save Note'}
                </button>
                <button
                  onClick={() => {
                    setShowNoteInput(false);
                    setNoteText('');
                  }}
                  className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded"
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
              className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-sm font-medium rounded focus:outline-none focus:ring-2 focus:ring-green-400 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              {isResolving ? 'Resolving...' : issue.state === 'resolved' ? 'Resolved' : 'Resolve'}
            </button>
            <button
              onClick={() => setShowNoteInput(true)}
              aria-label="Add a note to this issue"
              disabled={showNoteInput}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-600 text-slate-200 text-sm rounded"
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
