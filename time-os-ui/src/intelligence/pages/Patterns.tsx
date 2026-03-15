/**
 * Patterns — Detected Patterns List
 *
 * Shows structural patterns across entities.
 * Patterns with unrecognized severity are displayed in an "Other" group
 * instead of being silently excluded.
 */

import { usePatterns } from '../hooks';
import { ErrorState, NoPatternsDetected } from '../../components';
import { SkeletonPatternsPage, PatternCard } from '../components';
import { PageLayout } from '../../components/layout/PageLayout';
import { SummaryGrid } from '../../components/layout/SummaryGrid';
import { MetricCard } from '../../components/layout/MetricCard';

/** Format an ISO timestamp into a human-readable freshness label */
function freshnessLabel(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const KNOWN_SEVERITIES = new Set(['structural', 'operational', 'informational']);

export default function Patterns() {
  const { data, loading, error, hasLoaded, computedAt, refetch } = usePatterns();

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

  const hasPatterns = data?.patterns != null;
  const patterns = data?.patterns ?? [];

  // Group by severity — unknown severities go to "other" instead of being silently dropped
  const structural = patterns.filter((p) => p.severity === 'structural');
  const operational = patterns.filter((p) => p.severity === 'operational');
  const informational = patterns.filter((p) => p.severity === 'informational');
  const other = patterns.filter((p) => !KNOWN_SEVERITIES.has(p.severity));

  return (
    <PageLayout title="Detected Patterns">
      {/* Freshness indicator */}
      {computedAt && (
        <div className="text-xs text-[var(--grey)] mb-2">
          Data computed {freshnessLabel(computedAt)}
          {error && hasLoaded && ' (showing last known data)'}
        </div>
      )}

      {/* Error banner when we have stale data */}
      {error && data && <ErrorState error={error} onRetry={refetch} hasData />}

      {/* Summary Metrics */}
      <SummaryGrid>
        <MetricCard
          label="Total Detected"
          value={hasPatterns ? (data?.total_detected ?? patterns.length) : '--'}
        />
        <MetricCard label="Structural" value={hasPatterns ? structural.length : '--'} />
        <MetricCard label="Operational" value={hasPatterns ? operational.length : '--'} />
        <MetricCard label="Informational" value={hasPatterns ? informational.length : '--'} />
        {other.length > 0 && <MetricCard label="Other" value={other.length} />}
      </SummaryGrid>

      {!hasPatterns ? (
        <div className="p-6 text-center text-[var(--grey-light)]">
          {hasLoaded ? 'Pattern data could not be loaded.' : 'Loading patterns...'}
        </div>
      ) : patterns.length === 0 ? (
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

          {/* Other (unrecognized severity) — rendered instead of silently dropped */}
          {other.length > 0 && (
            <div>
              <h2 className="text-lg font-medium text-purple-400 mb-3">
                Other ({other.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {other.map((pattern, i) => (
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
