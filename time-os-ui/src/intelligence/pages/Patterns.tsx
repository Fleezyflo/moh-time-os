/**
 * Patterns — Detected Patterns List
 *
 * Shows structural patterns across entities.
 */

import { usePatterns } from '../hooks';
import { ErrorState, NoPatternsDetected } from '../../components';
import { SkeletonPatternsPage, PatternCard } from '../components';

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
        <div className="text-sm text-[var(--grey-muted)]">{data?.total_detected ?? 0} detected</div>
      </div>

      {patterns.length === 0 ? (
        <NoPatternsDetected />
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
              <h2 className="text-lg font-medium text-[var(--grey-light)] mb-3">
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
