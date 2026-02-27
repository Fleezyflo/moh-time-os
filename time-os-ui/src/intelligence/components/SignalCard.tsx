/**
 * SignalCard — Signal summary card with expandable detail
 */

import { useState } from 'react';
import type { Signal } from '../api';
import { SeverityBadge } from './Badges';
import { EntityLink } from './EntityLink';

interface SignalCardProps {
  signal: Signal;
  compact?: boolean;
  onClick?: () => void;
}

export function SignalCard({ signal, compact = false, onClick }: SignalCardProps) {
  const [expanded, setExpanded] = useState(false);

  const bgColor =
    signal.severity === 'critical'
      ? 'bg-red-500/5 border-red-500/30'
      : signal.severity === 'warning'
        ? 'bg-amber-500/5 border-amber-500/30'
        : 'bg-[var(--grey-dim)] border-[var(--grey)]';

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else if (!compact) {
      setExpanded(!expanded);
    }
  };

  if (compact) {
    return (
      <div
        role="button"
        tabIndex={0}
        className={`rounded-lg p-3 border ${bgColor} cursor-pointer hover:border-[var(--grey-mid)] transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--accent)]`}
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleClick();
          }
        }}
      >
        <div className="flex items-center gap-2 mb-1">
          <SeverityBadge severity={signal.severity} />
          <span className="text-xs text-[var(--grey-muted)]">{signal.entity_type}</span>
        </div>
        <div className="text-sm font-medium truncate">{signal.name}</div>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border ${bgColor}`}>
      <div
        role="button"
        tabIndex={0}
        className="p-4 cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleClick();
          }
        }}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <SeverityBadge severity={signal.severity} />
              <span className="text-sm text-[var(--grey-muted)]">{signal.entity_type}</span>
            </div>
            <div className="font-medium">{signal.name}</div>
            <div className="text-sm text-[var(--grey-light)] mt-1">
              {signal.entity_name || signal.entity_id}
            </div>
          </div>
          <div className="text-xs text-[var(--grey-muted)]">{expanded ? '▲' : '▼'}</div>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-[var(--grey)] pt-4">
          {/* Evidence */}
          <div className="text-sm text-[var(--grey-subtle)] mb-4">{signal.evidence}</div>

          {/* Entity link */}
          <div className="mb-4">
            <div className="text-xs text-[var(--grey-muted)] mb-1">Entity</div>
            <EntityLink
              entity={{
                type: signal.entity_type,
                id: signal.entity_id,
                name: signal.entity_name || signal.entity_id,
              }}
            />
          </div>

          {/* Implied action */}
          <div className="bg-[var(--grey)]/50 rounded p-3">
            <div className="text-xs text-[var(--grey-muted)] uppercase tracking-wide mb-1">
              Recommended Action
            </div>
            <div className="text-sm">{signal.implied_action}</div>
          </div>

          {/* Detection time */}
          {signal.detected_at && (
            <div className="text-xs text-[var(--grey-muted)] mt-3">
              Detected: {new Date(signal.detected_at).toLocaleString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SignalCard;
