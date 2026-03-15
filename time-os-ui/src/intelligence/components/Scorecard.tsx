/**
 * Scorecard — Entity scorecard with dimension breakdown.
 *
 * Uses 5-level color coding matching HealthScore:
 *   >= 70  strong   (green)
 *   >= 50  fair     (teal)
 *   >= 30  warning  (amber)
 *   >= 10  poor     (orange)
 *   <  10  critical (red)
 */

import type { Scorecard as ScorecardType } from '../api';

interface ScorecardProps {
  scorecard: ScorecardType;
  compact?: boolean;
}

function barColor(score: number): string {
  if (score >= 70) return 'bg-green-500';
  if (score >= 50) return 'bg-teal-500';
  if (score >= 30) return 'bg-amber-500';
  if (score >= 10) return 'bg-orange-500';
  return 'bg-red-500';
}

function dimTextColor(score: number): string {
  if (score >= 70) return 'text-green-400';
  if (score >= 50) return 'text-teal-400';
  if (score >= 30) return 'text-amber-400';
  if (score >= 10) return 'text-orange-400';
  return 'text-red-400';
}

function ScoreBar({ score, label, weight }: { score: number; label: string; weight?: number }) {
  const color = barColor(score);
  const tc = dimTextColor(score);

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-[var(--grey-subtle)]">{label}</span>
        <span className={tc}>{Math.round(score)}</span>
      </div>
      <div className="h-2 bg-[var(--grey)] rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-300`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
      {weight !== undefined && (
        <div className="text-xs text-[var(--grey-muted)] text-right">
          {Math.round(weight * 100)}% weight
        </div>
      )}
    </div>
  );
}

function freshnessLabel(computedAt: string): string {
  const diff = Date.now() - new Date(computedAt).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function Scorecard({ scorecard, compact = false }: ScorecardProps) {
  const compositeScore = scorecard.composite_score ?? null;
  const dimensions = scorecard.dimensions ?? {};

  // Handle null/undefined composite score -- show unknown state, not zero
  if (compositeScore == null) {
    return (
      <div className="bg-[var(--grey-dim)] rounded-lg p-6 text-center">
        <div className="text-sm text-[var(--grey-light)]">{scorecard.entity_type} Score</div>
        {scorecard.entity_name && (
          <div className="text-lg font-medium mt-1">{scorecard.entity_name}</div>
        )}
        <div className="text-4xl font-bold text-[var(--grey-light)] mt-2">—</div>
        <div className="text-sm text-[var(--grey)] mt-1">Score unavailable</div>
      </div>
    );
  }

  const color = dimTextColor(compositeScore);
  const bgColor =
    compositeScore >= 70
      ? 'bg-green-500/10'
      : compositeScore >= 50
        ? 'bg-teal-500/10'
        : compositeScore >= 30
          ? 'bg-amber-500/10'
          : compositeScore >= 10
            ? 'bg-orange-500/10'
            : 'bg-red-500/10';

  if (compact) {
    return (
      <div className={`${bgColor} rounded-lg p-4 flex items-center gap-4`}>
        <div className={`text-3xl font-bold ${color}`}>{Math.round(compositeScore)}</div>
        <div className="flex-1 grid grid-cols-2 gap-2">
          {Object.entries(dimensions)
            .slice(0, 4)
            .map(([key, dim]) => (
              <div key={key} className="text-sm">
                <span className="text-[var(--grey-light)]">{dim.name}: </span>
                <span className={dimTextColor(dim.score)}>{Math.round(dim.score)}</span>
              </div>
            ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[var(--grey-dim)] rounded-lg p-6">
      {/* Header with composite score */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-sm text-[var(--grey-light)]">{scorecard.entity_type} Score</div>
          {scorecard.entity_name && (
            <div className="text-lg font-medium">{scorecard.entity_name}</div>
          )}
        </div>
        <div className={`text-4xl font-bold ${color}`}>{Math.round(compositeScore)}</div>
      </div>

      {/* Dimension breakdown */}
      <div className="space-y-4">
        {Object.entries(dimensions).map(([key, dim]) => (
          <ScoreBar key={key} score={dim.score} label={dim.name} weight={dim.weight} />
        ))}
      </div>

      {/* Computed timestamp with relative freshness */}
      {scorecard.computed_at && (
        <div className="text-xs text-[var(--grey-muted)] mt-4 pt-4 border-t border-[var(--grey)]">
          Computed {freshnessLabel(scorecard.computed_at)} ({new Date(scorecard.computed_at).toLocaleString()})
        </div>
      )}
    </div>
  );
}

export default Scorecard;
