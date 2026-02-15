/**
 * Scorecard — Entity scorecard with dimension breakdown
 */

import type { Scorecard as ScorecardType } from '../api';

interface ScorecardProps {
  scorecard: ScorecardType;
  compact?: boolean;
}

function ScoreBar({ score, label, weight }: { score: number; label: string; weight?: number }) {
  const color = score >= 60 ? 'bg-green-500' : score >= 30 ? 'bg-amber-500' : 'bg-red-500';
  const textColor =
    score >= 60 ? 'text-green-400' : score >= 30 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-300">{label}</span>
        <span className={textColor}>{Math.round(score)}</span>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-300`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
      {weight !== undefined && (
        <div className="text-xs text-slate-500 text-right">{Math.round(weight * 100)}% weight</div>
      )}
    </div>
  );
}

export function Scorecard({ scorecard, compact = false }: ScorecardProps) {
  const compositeScore = scorecard.composite_score ?? 0;
  const dimensions = scorecard.dimensions ?? {};

  const color =
    compositeScore >= 60
      ? 'text-green-400'
      : compositeScore >= 30
        ? 'text-amber-400'
        : 'text-red-400';
  const bgColor =
    compositeScore >= 60
      ? 'bg-green-500/10'
      : compositeScore >= 30
        ? 'bg-amber-500/10'
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
                <span className="text-slate-400">{dim.name}: </span>
                <span
                  className={
                    dim.score >= 60
                      ? 'text-green-400'
                      : dim.score >= 30
                        ? 'text-amber-400'
                        : 'text-red-400'
                  }
                >
                  {Math.round(dim.score)}
                </span>
              </div>
            ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-800 rounded-lg p-6">
      {/* Header with composite score */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-sm text-slate-400">{scorecard.entity_type} Score</div>
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

      {/* Computed timestamp */}
      {scorecard.computed_at && (
        <div className="text-xs text-slate-500 mt-4 pt-4 border-t border-slate-700">
          Computed: {new Date(scorecard.computed_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}

export default Scorecard;
