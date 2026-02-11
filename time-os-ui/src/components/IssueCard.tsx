// IssueCard — displays issue from real API data
import type { Issue } from '../types/api';
import { priorityLabel } from '../lib/priority';

interface IssueCardProps {
  issue: Issue;
  onOpen?: () => void;
}

const stateStyles: Record<string, { icon: string; color: string; bg: string }> = {
  // v29 states
  detected: { icon: '◎', color: 'text-blue-300', bg: 'bg-blue-900/20' },
  surfaced: { icon: '○', color: 'text-blue-400', bg: 'bg-blue-900/30' },
  snoozed: { icon: '◷', color: 'text-amber-400', bg: 'bg-amber-900/30' },
  acknowledged: { icon: '◉', color: 'text-purple-400', bg: 'bg-purple-900/30' },
  addressing: { icon: '⊕', color: 'text-cyan-400', bg: 'bg-cyan-900/30' },
  awaiting_resolution: { icon: '◷', color: 'text-amber-400', bg: 'bg-amber-900/30' },
  regression_watch: { icon: '◎', color: 'text-yellow-400', bg: 'bg-yellow-900/30' },
  regressed: { icon: '⊘', color: 'text-red-400', bg: 'bg-red-900/30' },
  closed: { icon: '✓', color: 'text-green-400', bg: 'bg-green-900/30' },
  // Legacy states
  open: { icon: '○', color: 'text-blue-400', bg: 'bg-blue-900/30' },
  monitoring: { icon: '◉', color: 'text-purple-400', bg: 'bg-purple-900/30' },
  awaiting: { icon: '◷', color: 'text-amber-400', bg: 'bg-amber-900/30' },
  blocked: { icon: '⊘', color: 'text-red-400', bg: 'bg-red-900/30' },
  resolved: { icon: '✓', color: 'text-green-400', bg: 'bg-green-900/30' },
};

// Priority display using centralized thresholds
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

// Get issue type (v29: type, legacy: issue_type)
const getType = (issue: Issue): string => issue.type || '';

// Get priority (v29: severity→number, legacy: priority)
const getPriority = (issue: Issue): number => issue.priority ?? severityToPriority(issue.severity);

// Get last activity (v29: updated_at, legacy: last_activity_at)
const getLastActivity = (issue: Issue): string => issue.updated_at || issue.last_activity_at || '';

function getPriorityInfo(priority: number): { label: string; color: string } {
  const label = priorityLabel(priority);
  return {
    label: label.charAt(0).toUpperCase() + label.slice(1),
    color: priorityColors[label] || priorityColors.medium,
  };
}

export function IssueCard({ issue, onOpen }: IssueCardProps) {
  const stateStyle = stateStyles[issue.state] || stateStyles.open;
  const priorityInfo = getPriorityInfo(getPriority(issue));
  const lastActivity = getLastActivity(issue);

  return (
    <div
      className={`${stateStyle.bg} border border-slate-700 rounded-lg p-4 cursor-pointer hover:border-slate-600 transition-colors`}
      onClick={onOpen}
    >
      <div className="flex items-start gap-3">
        <span className={`text-lg ${stateStyle.color}`}>{stateStyle.icon}</span>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-slate-100 leading-tight">{getTitle(issue)}</h3>
          <div className="flex items-center gap-3 mt-2 text-sm">
            <span className={stateStyle.color}>{issue.state}</span>
            <span className={priorityInfo.color}>{priorityInfo.label}</span>
            <span className="text-slate-500">{getType(issue)}</span>
          </div>
          {lastActivity && (
            <div className="text-xs text-slate-500 mt-2">
              Last activity: {new Date(lastActivity).toLocaleString()}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Compact row version for lists
export function IssueRow({ issue, onOpen }: IssueCardProps) {
  const stateStyle = stateStyles[issue.state] || stateStyles.open;
  const priorityInfo = getPriorityInfo(getPriority(issue));

  return (
    <div
      className="flex items-center gap-3 px-3 py-2 rounded hover:bg-slate-800 cursor-pointer transition-colors"
      onClick={onOpen}
    >
      <span className={`${stateStyle.color}`}>{stateStyle.icon}</span>
      <span className="flex-1 text-sm text-slate-200 truncate">{getTitle(issue)}</span>
      <span className={`text-xs ${priorityInfo.color}`}>{priorityInfo.label}</span>
    </div>
  );
}
