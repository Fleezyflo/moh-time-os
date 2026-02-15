/**
 * Patterns — Detected Patterns List
 *
 * Shows structural patterns across entities.
 */

import { usePatterns } from '../hooks';
import { ErrorState } from '../../components/ErrorState';
import { SkeletonPatternsPage } from '../components';
import type { Pattern } from '../api';

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    structural: 'bg-red-500/20 text-red-400',
    operational: 'bg-amber-500/20 text-amber-400',
    informational: 'bg-slate-500/20 text-slate-400',
  };

  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${colors[severity] || colors.informational}`}
    >
      {severity}
    </span>
  );
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    concentration: 'bg-purple-500/20 text-purple-400',
    cascade: 'bg-orange-500/20 text-orange-400',
    degradation: 'bg-pink-500/20 text-pink-400',
    drift: 'bg-blue-500/20 text-blue-400',
    correlation: 'bg-cyan-500/20 text-cyan-400',
  };

  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${colors[type] || 'bg-slate-500/20 text-slate-400'}`}
    >
      {type}
    </span>
  );
}

function PatternCard({ pattern }: { pattern: Pattern }) {
  return (
    <div
      className={`rounded-lg p-4 border ${
        pattern.severity === 'structural'
          ? 'bg-red-500/5 border-red-500/30'
          : pattern.severity === 'operational'
            ? 'bg-amber-500/5 border-amber-500/30'
            : 'bg-slate-800 border-slate-700'
      }`}
    >
      <div className="flex items-start gap-2 mb-2">
        <SeverityBadge severity={pattern.severity} />
        <TypeBadge type={pattern.type} />
      </div>
      <div className="font-medium">{pattern.name}</div>
      <div className="text-sm text-slate-400 mt-2">{pattern.description}</div>

      {pattern.affected_entities && pattern.affected_entities.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-700">
          <div className="text-xs text-slate-500 mb-1">Affected Entities</div>
          <div className="flex flex-wrap gap-1">
            {pattern.affected_entities.slice(0, 5).map((entity, i) => (
              <span key={i} className="text-xs bg-slate-700 px-2 py-0.5 rounded">
                {entity.name}
              </span>
            ))}
            {pattern.affected_entities.length > 5 && (
              <span className="text-xs text-slate-500">
                +{pattern.affected_entities.length - 5} more
              </span>
            )}
          </div>
        </div>
      )}

      <div className="text-sm text-slate-400 mt-3 pt-2 border-t border-slate-700">
        → {pattern.implied_action}
      </div>
    </div>
  );
}

export default function Patterns() {
  const { data, loading, error, refetch } = usePatterns();

  // Show error state if we have an error and no data
  if (error && !data) {
    return (
      <div className="p-6">
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  if (loading && !data) {
    return <SkeletonPatternsPage />;
  }

  const patterns = data?.patterns ?? [];

  // Group by severity
  const structural = patterns.filter((p) => p.severity === 'structural');
  const operational = patterns.filter((p) => p.severity === 'operational');
  const informational = patterns.filter((p) => p.severity === 'informational');

  return (
    <div className="space-y-6">
      {/* Error banner when we have stale data */}
      {error && data && <ErrorState error={error} onRetry={refetch} hasData />}

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Detected Patterns</h1>
        <div className="text-sm text-slate-500">{data?.total_detected ?? 0} detected</div>
      </div>

      {patterns.length === 0 ? (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-8 text-center">
          <div className="text-green-400">✓ No patterns detected</div>
          <div className="text-slate-400 mt-2">Portfolio structure looks healthy</div>
        </div>
      ) : (
        <>
          {/* Structural */}
          {structural.length > 0 && (
            <div>
              <h2 className="text-lg font-medium text-red-400 mb-3">
                Structural ({structural.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {structural.map((pattern, i) => (
                  <PatternCard key={pattern.pattern_id || i} pattern={pattern} />
                ))}
              </div>
            </div>
          )}

          {/* Operational */}
          {operational.length > 0 && (
            <div>
              <h2 className="text-lg font-medium text-amber-400 mb-3">
                Operational ({operational.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {operational.map((pattern, i) => (
                  <PatternCard key={pattern.pattern_id || i} pattern={pattern} />
                ))}
              </div>
            </div>
          )}

          {/* Informational */}
          {informational.length > 0 && (
            <div>
              <h2 className="text-lg font-medium text-slate-400 mb-3">
                Informational ({informational.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {informational.map((pattern, i) => (
                  <PatternCard key={pattern.pattern_id || i} pattern={pattern} />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
