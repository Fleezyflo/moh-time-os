/**
 * Patterns — Detected Patterns List
 *
 * Shows structural patterns across entities.
 */

import { usePatterns } from '../hooks';
import { ErrorState, NoPatternsDetected } from '../../components';
import { SkeletonPatternsPage, PatternCard } from '../components';
import { PageLayout } from '../../components/layout/PageLayout';
import { SummaryGrid } from '../../components/layout/SummaryGrid';
import { MetricCard } from '../../components/layout/MetricCard';

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
    <PageLayout title="Detected Patterns">
      {/* Error banner when we have stale data */}
      {error && data && <ErrorState error={error} onRetry={refetch} hasData />}

      {/* Summary Metrics */}
      <SummaryGrid>
        <MetricCard label="Total Detected" value={data?.total_detected ?? patterns.length} />
        <MetricCard label="Structural" value={structural.length} />
        <MetricCard label="Operational" value={operational.length} />
        <MetricCard label="Informational" value={informational.length} />
      </SummaryGrid>

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
    </PageLayout>
  );
}
