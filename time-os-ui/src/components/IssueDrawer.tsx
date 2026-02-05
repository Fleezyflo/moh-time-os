// IssueDrawer — Detail drawer for issues with state, watchers, and actions
import type { Issue, Watcher } from '../fixtures';

interface IssueDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  issue: Issue;
  watchers?: Watcher[];
  onTransition?: (newState: Issue['state']) => void;
}

const stateConfig = {
  open: { icon: '●', color: 'text-red-500', bg: 'bg-red-500/10', label: 'Open' },
  monitoring: { icon: '◐', color: 'text-amber-500', bg: 'bg-amber-500/10', label: 'Monitoring' },
  awaiting: { icon: '◑', color: 'text-blue-500', bg: 'bg-blue-500/10', label: 'Awaiting' },
  blocked: { icon: '■', color: 'text-slate-400', bg: 'bg-slate-500/10', label: 'Blocked' },
  resolved: { icon: '✓', color: 'text-green-500', bg: 'bg-green-500/10', label: 'Resolved' },
  closed: { icon: '○', color: 'text-slate-400', bg: 'bg-slate-500/10', label: 'Closed' }
};

const priorityConfig = {
  critical: { color: 'text-red-400', bg: 'bg-red-900/30' },
  high: { color: 'text-orange-400', bg: 'bg-orange-900/30' },
  medium: { color: 'text-amber-400', bg: 'bg-amber-900/30' },
  low: { color: 'text-slate-400', bg: 'bg-slate-700' }
};

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHrs / 24);
  
  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHrs > 0) return `${diffHrs}h ago`;
  return 'Just now';
}

function formatFutureTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHrs / 24);
  
  if (diffDays > 0) return `in ${diffDays}d`;
  if (diffHrs > 0) return `in ${diffHrs}h`;
  return 'Soon';
}

export function IssueDrawer({ isOpen, onClose, issue, watchers = [], onTransition }: IssueDrawerProps) {
  if (!isOpen) return null;

  const state = stateConfig[issue.state];
  const priority = priorityConfig[issue.priority];
  const issueWatchers = watchers.filter(w => w.issue_id === issue.issue_id);

  const stateTransitions: Record<Issue['state'], Issue['state'][]> = {
    open: ['monitoring', 'awaiting', 'blocked', 'resolved'],
    monitoring: ['open', 'awaiting', 'blocked', 'resolved'],
    awaiting: ['open', 'monitoring', 'blocked', 'resolved'],
    blocked: ['open', 'monitoring', 'awaiting', 'resolved'],
    resolved: ['closed', 'open'],
    closed: ['open']
  };

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40 lg:bg-black/30"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[400px] bg-slate-900 border-l border-slate-700 shadow-drawer overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-slate-900/95 backdrop-blur border-b border-slate-700 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-lg ${state.color}`}>{state.icon}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${state.bg} ${state.color}`}>
                  {state.label}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded ${priority.bg} ${priority.color}`}>
                  {issue.priority}
                </span>
              </div>
              <h2 className="text-lg font-semibold text-slate-100 leading-tight">
                {issue.headline}
              </h2>
            </div>
            <button 
              onClick={onClose}
              className="p-2 hover:bg-slate-800 rounded transition-colors text-slate-400 hover:text-slate-200"
              aria-label="Close drawer"
            >
              ✕
            </button>
          </div>
        </div>
        
        {/* Content */}
        <div className="p-4 space-y-6">
          {/* Resolution criteria */}
          <section>
            <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-2">
              Resolution criteria
            </h3>
            <p className="text-slate-300 bg-slate-800 rounded-lg p-3">
              {issue.resolution_criteria}
            </p>
          </section>
          
          {/* Activity */}
          <section>
            <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-2">
              Activity
            </h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">Last activity</span>
                <span className="text-slate-300">{formatRelativeTime(issue.last_activity_at)}</span>
              </div>
              {issue.next_trigger && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Next trigger</span>
                  <span className="text-blue-400">{formatFutureTime(issue.next_trigger)}</span>
                </div>
              )}
            </div>
          </section>
          
          {/* Watchers */}
          {issueWatchers.length > 0 && (
            <section>
              <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-2">
                Watchers ({issueWatchers.length})
              </h3>
              <div className="space-y-2">
                {issueWatchers.map(w => (
                  <div key={w.watcher_id} className="bg-slate-800 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-blue-400">⏰</span>
                      <span className="text-slate-300">{w.trigger_condition}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1 ml-6">
                      Next check: {formatFutureTime(w.next_check_at)}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}
          
          {/* State transitions */}
          <section>
            <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-2">
              Transition state
            </h3>
            <div className="flex flex-wrap gap-2">
              {stateTransitions[issue.state].map(newState => {
                const config = stateConfig[newState];
                return (
                  <button
                    key={newState}
                    onClick={() => onTransition?.(newState)}
                    className={`px-3 py-1.5 rounded text-sm transition-colors ${config.bg} ${config.color} hover:opacity-80`}
                  >
                    {config.icon} {config.label}
                  </button>
                );
              })}
            </div>
          </section>
          
          {/* Actions */}
          <div className="flex items-center gap-2 pt-4 border-t border-slate-700">
            <button className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded transition-colors">
              Add commitment
            </button>
            <button className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded transition-colors">
              Add watcher
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
