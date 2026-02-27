// IssueCard — displays issue from real API data
import type { Issue } from '../types/api';
import {
  stateStyles,
  defaultStateStyle,
  getTitle,
  getType,
  getPriority,
  getLastActivity,
  getPriorityInfo,
} from '../lib/issueStyles';

interface IssueCardProps {
  issue: Issue;
  onOpen?: () => void;
}

export function IssueCard({ issue, onOpen }: IssueCardProps) {
  const stateStyle = stateStyles[issue.state] || defaultStateStyle;
  const priorityInfo = getPriorityInfo(getPriority(issue));
  const lastActivity = getLastActivity(issue);

  return (
    <div
      role="button"
      tabIndex={0}
      className={`${stateStyle.bg} border border-[var(--grey)] rounded-lg p-4 cursor-pointer hover:border-[var(--grey-mid)] transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--accent)]`}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen?.();
        }
      }}
    >
      <div className="flex items-start gap-3">
        <span className={`text-lg ${stateStyle.color}`}>{stateStyle.icon}</span>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-[var(--white)] leading-tight">{getTitle(issue)}</h3>
          <div className="flex items-center gap-3 mt-2 text-sm">
            <span className={stateStyle.color}>{issue.state}</span>
            <span className={priorityInfo.color}>{priorityInfo.label}</span>
            <span className="text-[var(--grey-muted)]">{getType(issue)}</span>
          </div>
          {lastActivity && (
            <div className="text-xs text-[var(--grey-muted)] mt-2">
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
  const stateStyle = stateStyles[issue.state] || defaultStateStyle;
  const priorityInfo = getPriorityInfo(getPriority(issue));

  return (
    <div
      role="button"
      tabIndex={0}
      className="flex items-center gap-3 px-3 py-2 rounded hover:bg-[var(--grey-dim)] cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen?.();
        }
      }}
    >
      <span className={`${stateStyle.color}`}>{stateStyle.icon}</span>
      <span className="flex-1 text-sm text-[var(--white)] truncate">{getTitle(issue)}</span>
      <span className={`text-xs ${priorityInfo.color}`}>{priorityInfo.label}</span>
    </div>
  );
}
