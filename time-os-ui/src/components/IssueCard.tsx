// IssueCard — renders issue with state, priority, and watcher info
import type { Issue } from '../fixtures';

interface IssueCardProps {
  issue: Issue;
  onOpen?: () => void;
}

const stateConfig = {
  open: { icon: '●', color: 'text-red-500', bg: 'bg-red-500/10' },
  monitoring: { icon: '◐', color: 'text-amber-500', bg: 'bg-amber-500/10' },
  awaiting: { icon: '◑', color: 'text-blue-500', bg: 'bg-blue-500/10' },
  blocked: { icon: '■', color: 'text-slate-900', bg: 'bg-slate-400' },
  resolved: { icon: '✓', color: 'text-green-500', bg: 'bg-green-500/10' },
  closed: { icon: '○', color: 'text-slate-400', bg: 'bg-slate-500/10' }
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

export function IssueCard({ issue, onOpen }: IssueCardProps) {
  const state = stateConfig[issue.state];
  const priority = priorityConfig[issue.priority];
  
  return (
    <div 
      className="p-3 bg-slate-800/50 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors cursor-pointer"
      onClick={onOpen}
    >
      <div className="flex items-start gap-3">
        {/* State icon */}
        <span className={`text-lg ${state.color}`}>{state.icon}</span>
        
        <div className="flex-1 min-w-0">
          {/* Headline */}
          <h4 className="text-sm font-medium text-slate-200 truncate">{issue.headline}</h4>
          
          {/* Meta row */}
          <div className="flex items-center gap-2 mt-1 text-xs">
            <span className={`px-1.5 py-0.5 rounded ${priority.bg} ${priority.color}`}>
              {issue.priority}
            </span>
            <span className={`px-1.5 py-0.5 rounded ${state.bg} ${state.color}`}>
              {issue.state}
            </span>
            <span className="text-slate-500">
              {formatRelativeTime(issue.last_activity_at)}
            </span>
          </div>
          
          {/* Resolution criteria */}
          <p className="text-xs text-slate-500 mt-1 truncate">
            Resolve: {issue.resolution_criteria}
          </p>
          
          {/* Next trigger */}
          {issue.next_trigger && (
            <p className="text-xs text-blue-400 mt-1">
              ⏰ Next check: {formatFutureTime(issue.next_trigger)}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// Compact row variant for right rail
export function IssueRow({ issue, onOpen }: IssueCardProps) {
  const state = stateConfig[issue.state];
  const priority = priorityConfig[issue.priority];
  
  return (
    <div 
      className="py-2 px-3 hover:bg-slate-700/30 rounded cursor-pointer transition-colors"
      onClick={onOpen}
    >
      <div className="flex items-center gap-2">
        <span className={`${state.color}`}>{state.icon}</span>
        <span className="flex-1 text-sm text-slate-300 truncate">{issue.headline}</span>
        <span className={`text-xs px-1.5 py-0.5 rounded ${priority.bg} ${priority.color}`}>
          {issue.priority}
        </span>
      </div>
    </div>
  );
}
