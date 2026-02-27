// ProposalCard — displays proposal with hierarchy context
import { useState, useCallback } from 'react';
import type { Proposal } from '../types/api';

interface ProposalCardProps {
  proposal: Proposal;
  onTag?: () => Promise<void> | void;
  onSnooze?: () => Promise<void> | void;
  onDismiss?: () => Promise<void> | void;
  onOpen?: () => void;
  isPending?: boolean;
}

export function ProposalCard({
  proposal,
  onTag,
  onSnooze,
  onDismiss,
  onOpen,
  isPending = false,
}: ProposalCardProps) {
  const [isTagging, setIsTagging] = useState(false);
  const [isSnoozing, setIsSnoozing] = useState(false);

  const handleTag = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!onTag || isTagging) return;
      setIsTagging(true);
      try {
        await onTag();
      } finally {
        setIsTagging(false);
      }
    },
    [onTag, isTagging]
  );

  const handleSnooze = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!onSnooze || isSnoozing) return;
      setIsSnoozing(true);
      try {
        await onSnooze();
      } finally {
        setIsSnoozing(false);
      }
    },
    [onSnooze, isSnoozing]
  );

  const isBusy = isPending || isTagging || isSnoozing;

  // Tier badge colors
  const tierColors: Record<string, string> = {
    A: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    B: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    C: 'bg-[var(--grey-muted)]/20 text-[var(--grey-light)] border-[var(--grey-muted)]/30',
  };

  // Score color based on severity
  const getScoreColor = (score: number) => {
    if (score >= 100) return 'text-red-400';
    if (score >= 50) return 'text-orange-400';
    if (score >= 25) return 'text-amber-400';
    return 'text-[var(--grey-light)]';
  };

  // Signal category labels and colors (no emojis)
  const categoryLabels: Record<string, { label: string; color: string; bg: string }> = {
    overdue: { label: 'OVERDUE', color: 'text-red-400', bg: 'bg-red-500/20 border-red-500/30' },
    approaching: {
      label: 'DUE SOON',
      color: 'text-amber-400',
      bg: 'bg-amber-500/20 border-amber-500/30',
    },
    blocked: { label: 'BLOCKED', color: 'text-red-400', bg: 'bg-red-500/20 border-red-500/30' },
    health: { label: 'HEALTH', color: 'text-pink-400', bg: 'bg-pink-500/20 border-pink-500/30' },
    financial: {
      label: 'AR',
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/20 border-yellow-500/30',
    },
    process: {
      label: 'PROCESS',
      color: 'text-[var(--grey-light)]',
      bg: 'bg-[var(--grey-muted)]/20 border-[var(--grey-muted)]/30',
    },
    other: {
      label: 'OTHER',
      color: 'text-[var(--grey-light)]',
      bg: 'bg-[var(--grey-muted)]/20 border-[var(--grey-muted)]/30',
    },
  };

  // Get display name - prefer scope_name, fallback to headline
  const displayName = proposal.scope_name || proposal.headline?.split(':')[0] || 'Unknown';
  const clientName = proposal.client_name;
  const showClientSubtitle = clientName && clientName !== displayName;

  // Get signal summary
  const summary = proposal.signal_summary;
  const signalCount = proposal.signal_count || summary?.total || proposal.impact?.signal_count || 0;
  const remainingCount = proposal.remaining_count || 0;

  // Build category badges
  const categoryBadges = summary?.by_category
    ? Object.entries(summary.by_category)
        .filter(([_, count]) => count > 0)
        .map(([cat, count]) => ({ cat, count, ...categoryLabels[cat] }))
        .filter((b) => b.label)
    : [];

  return (
    <div
      className="bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)] hover:border-[var(--grey-mid)] transition-colors cursor-pointer overflow-hidden"
      onClick={onOpen}
    >
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            {/* Title row with tier badge */}
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-[var(--white)] leading-tight truncate">
                {displayName}
              </h3>
              {proposal.client_tier && (
                <span
                  className={`px-1.5 py-0.5 text-xs font-medium rounded border ${tierColors[proposal.client_tier] || tierColors['C']}`}
                >
                  {proposal.client_tier}
                </span>
              )}
              {proposal.engagement_type === 'retainer' && (
                <span className="px-1.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded">
                  RETAINER
                </span>
              )}
            </div>

            {/* Client subtitle if different from scope */}
            {showClientSubtitle && (
              <p className="text-sm text-[var(--grey-muted)] mt-0.5 truncate">{clientName}</p>
            )}

            {/* Score and trend */}
            <div className="flex items-center gap-3 mt-2">
              <span className={`text-lg font-bold ${getScoreColor(proposal.score)}`}>
                {proposal.score.toFixed(0)}
              </span>
              <span
                className={`text-xs px-1.5 py-0.5 rounded ${
                  proposal.trend === 'worsening'
                    ? 'bg-red-500/20 text-red-400'
                    : proposal.trend === 'improving'
                      ? 'bg-green-500/20 text-green-400'
                      : 'text-[var(--grey-muted)]'
                }`}
              >
                {proposal.trend === 'worsening'
                  ? 'WORSE'
                  : proposal.trend === 'improving'
                    ? 'BETTER'
                    : '—'}
              </span>
              <span className="text-sm text-[var(--grey-muted)]">
                {signalCount} signal{signalCount !== 1 ? 's' : ''}
              </span>
            </div>
          </div>

          {/* Scope level indicator */}
          <span
            className={`px-2 py-1 rounded text-xs ${
              proposal.scope_level === 'client'
                ? 'bg-indigo-900/50 text-indigo-300'
                : proposal.scope_level === 'brand'
                  ? 'bg-violet-900/50 text-violet-300'
                  : 'bg-[var(--grey)] text-[var(--grey-subtle)]'
            }`}
          >
            {proposal.scope_level || proposal.impact?.entity_type || 'project'}
          </span>
        </div>

        {/* Signal category badges */}
        {categoryBadges.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mt-3">
            {categoryBadges.map(({ cat, count, label, color, bg }) => (
              <span
                key={cat}
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-xs font-medium ${bg} ${color}`}
              >
                <span>{label}</span>
                <span className="opacity-70">{count}</span>
              </span>
            ))}
          </div>
        )}

        {/* Worst signal text */}
        {(proposal.worst_signal || proposal.impact?.worst_signal) && (
          <p className="mt-3 text-sm text-[var(--grey-light)] line-clamp-2">
            {proposal.worst_signal || proposal.impact?.worst_signal}
          </p>
        )}

        {/* "And X more" link */}
        {remainingCount > 0 && (
          <p className="mt-2 text-xs text-[var(--grey-muted)]">
            and {remainingCount} more issue{remainingCount !== 1 ? 's' : ''}...
          </p>
        )}
      </div>

      {/* Score breakdown bar (visual) */}
      {proposal.score_breakdown && (
        <div className="px-4 pb-3">
          <div className="flex h-1.5 rounded-full overflow-hidden bg-[var(--grey)]/50">
            <div
              className="bg-red-500/70"
              style={{ width: `${(proposal.score_breakdown.urgency / 60) * 40}%` }}
              title={`Urgency: ${proposal.score_breakdown.urgency}`}
            />
            <div
              className="bg-amber-500/70"
              style={{ width: `${(proposal.score_breakdown.breadth / 40) * 30}%` }}
              title={`Breadth: ${proposal.score_breakdown.breadth}`}
            />
            <div
              className="bg-blue-500/70"
              style={{ width: `${(proposal.score_breakdown.diversity / 30) * 30}%` }}
              title={`Diversity: ${proposal.score_breakdown.diversity}`}
            />
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="px-4 py-3 border-t border-[var(--grey)]/50 flex items-center gap-2">
        <button
          onClick={handleTag}
          disabled={isBusy}
          className={`px-3 py-1.5 text-white text-sm font-medium rounded transition-colors ${
            isBusy ? 'bg-[var(--grey-mid)] cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500'
          }`}
        >
          {isTagging ? (
            <span className="flex items-center gap-2">
              <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
              ...
            </span>
          ) : (
            'Tag'
          )}
        </button>
        <button
          onClick={handleSnooze}
          disabled={isBusy}
          className={`px-3 py-1.5 text-[var(--grey-subtle)] text-sm rounded transition-colors ${
            isBusy
              ? 'bg-[var(--grey)]/50 cursor-not-allowed'
              : 'bg-[var(--grey)] hover:bg-[var(--grey-mid)]'
          }`}
        >
          {isSnoozing ? '...' : 'Snooze'}
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDismiss?.();
          }}
          disabled={isBusy}
          className="px-3 py-1.5 text-[var(--grey-muted)] text-sm rounded hover:text-[var(--grey-subtle)] transition-colors ml-auto"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
