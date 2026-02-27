/**
 * ProposalCard — Proposal summary card with expandable detail
 */

import { useState } from 'react';
import type { Proposal } from '../api';
import { UrgencyBadge } from './Badges';
import { EntityLink } from './EntityLink';
import { EvidenceList } from './EvidenceList';

interface ProposalCardProps {
  proposal: Proposal;
  rank?: number;
  compact?: boolean;
  defaultExpanded?: boolean;
  onClick?: () => void;
}

export function ProposalCard({
  proposal,
  rank,
  compact = false,
  defaultExpanded = false,
  onClick,
}: ProposalCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const bgColor =
    proposal.urgency === 'immediate'
      ? 'bg-red-500/5 border-red-500/30'
      : proposal.urgency === 'this_week'
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
        className={`rounded-lg p-3 border ${bgColor} cursor-pointer hover:border-[var(--grey-mid)] transition-colors`}
        onClick={handleClick}
      >
        <div className="flex items-center gap-2 mb-1">
          {rank && <span className="text-[var(--grey-muted)] font-mono text-xs">#{rank}</span>}
          <UrgencyBadge urgency={proposal.urgency} />
        </div>
        <div className="text-sm font-medium truncate">{proposal.headline}</div>
        <div className="text-xs text-[var(--grey-muted)] mt-1">{proposal.entity.name}</div>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border ${bgColor}`}>
      <div className="p-4 cursor-pointer" onClick={handleClick}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              {rank && <span className="text-[var(--grey-muted)] font-mono text-sm">#{rank}</span>}
              <UrgencyBadge urgency={proposal.urgency} />
              <span className="text-xs text-[var(--grey-muted)]">
                {proposal.type.replace('_', ' ')}
              </span>
            </div>
            <div className="font-medium">{proposal.headline}</div>
            <div className="text-sm text-[var(--grey-light)] mt-1">
              {proposal.entity.type}: {proposal.entity.name}
            </div>
          </div>
          <div className="text-right">
            {proposal.priority_score && (
              <div className="text-lg font-bold text-[var(--grey-subtle)]">
                {Math.round(proposal.priority_score.raw_score)}
              </div>
            )}
            <div className="text-xs text-[var(--grey-muted)]">{expanded ? '▲' : '▼'}</div>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-[var(--grey)] pt-4">
          {/* Summary */}
          <div className="text-sm text-[var(--grey-subtle)] mb-4">{proposal.summary}</div>

          {/* Entity link */}
          <div className="mb-4">
            <div className="text-xs text-[var(--grey-muted)] mb-1">Entity</div>
            <EntityLink entity={proposal.entity} />
          </div>

          {/* Evidence */}
          {proposal.evidence && proposal.evidence.length > 0 && (
            <div className="mb-4">
              <EvidenceList evidence={proposal.evidence} maxItems={5} />
            </div>
          )}

          {/* Confidence and trend */}
          {(proposal.confidence || proposal.trend) && (
            <div className="flex gap-4 mb-4 text-sm">
              {proposal.confidence && (
                <div>
                  <span className="text-[var(--grey-muted)]">Confidence: </span>
                  <span className="text-[var(--grey-subtle)]">{proposal.confidence}</span>
                </div>
              )}
              {proposal.trend && (
                <div>
                  <span className="text-[var(--grey-muted)]">Trend: </span>
                  <span
                    className={
                      proposal.trend === 'escalating'
                        ? 'text-red-400'
                        : proposal.trend === 'new'
                          ? 'text-amber-400'
                          : 'text-[var(--grey-subtle)]'
                    }
                  >
                    {proposal.trend}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Implied action */}
          <div className="bg-[var(--grey)]/50 rounded p-3">
            <div className="text-xs text-[var(--grey-muted)] uppercase tracking-wide mb-1">
              Recommended Action
            </div>
            <div className="text-sm">{proposal.implied_action}</div>
          </div>

          {/* Priority score breakdown */}
          {proposal.priority_score?.components && (
            <div className="mt-4 pt-4 border-t border-[var(--grey)]">
              <div className="text-xs text-[var(--grey-muted)] uppercase tracking-wide mb-2">
                Priority Score Components
              </div>
              <div className="grid grid-cols-4 gap-2">
                {Object.entries(proposal.priority_score.components).map(([key, value]) => (
                  <div key={key} className="text-center">
                    <div className="text-lg font-medium">{Math.round(value as number)}</div>
                    <div className="text-xs text-[var(--grey-muted)]">{key}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ProposalCard;
