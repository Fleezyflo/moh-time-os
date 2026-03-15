/**
 * Signals — Active Signals List
 *
 * Shows all detected signals with filtering by severity and entity type.
 * Includes freshness indicator from API computed_at timestamp.
 */

import { useSignals } from '../hooks';
import { useSignalFilters } from '../lib';
import { ErrorState, NoSignals, NoResults } from '../../components';
import { SkeletonSignalsPage, SignalCard } from '../components';
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

export default function Signals() {
  const { severity, entityType, setSeverity, setEntityType, resetFilters } = useSignalFilters();

  const { data, loading, error, hasLoaded, computedAt, refetch } = useSignals(true);

  // Show error state if we have an error and no data
  if (error && !data) {
    return (
      <div className="p-6">
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  if (loading && !data) {
    return <SkeletonSignalsPage />;
  }

  // Distinguish "data loaded but empty" from "data never loaded / failed"
  const signals = data?.signals;
  const hasSignals = signals != null;
  const signalList = signals ?? [];

  // Apply filters
  const filtered = signalList.filter((s) => {
    if (severity !== 'all' && s.severity !== severity) return false;
    if (entityType !== 'all' && s.entity_type !== entityType) return false;
    return true;
  });

  // Get unique values for filters
  const severities = ['all', ...new Set(signalList.map((s) => s.severity))];
  const entityTypes = ['all', ...new Set(signalList.map((s) => s.entity_type))];

  const filterControls = (
    <div className="flex flex-wrap gap-4 bg-[var(--grey-dim)] rounded-lg p-4">
      <div>
        <label className="text-sm text-[var(--grey-light)] block mb-1">Severity</label>
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="bg-[var(--grey)] border border-[var(--grey-mid)] rounded px-3 py-1.5 text-sm"
        >
          {severities.map((s) => (
            <option key={s} value={s}>
              {s === 'all' ? 'All' : s}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="text-sm text-[var(--grey-light)] block mb-1">Entity Type</label>
        <select
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          className="bg-[var(--grey)] border border-[var(--grey-mid)] rounded px-3 py-1.5 text-sm"
        >
          {entityTypes.map((t) => (
            <option key={t} value={t}>
              {t === 'all' ? 'All' : t}
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-end gap-2">
        <span className="text-sm text-[var(--grey-muted)]">
          Showing {filtered.length} of {signalList.length}
        </span>
        {(severity !== 'all' || entityType !== 'all') && (
          <button
            onClick={resetFilters}
            className="text-xs text-[var(--grey-light)] hover:text-white"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );

  return (
    <PageLayout title="Active Signals" actions={filterControls}>
      {/* Freshness indicator */}
      {computedAt && (
        <div className="text-xs text-[var(--grey)] mb-2">
          Data computed {freshnessLabel(computedAt)}
          {error && hasLoaded && ' (showing last known data)'}
        </div>
      )}

      {/* Error banner when we have stale data */}
      {error && data && <ErrorState error={error} onRetry={refetch} hasData />}

      {/* Summary Grid */}
      <SummaryGrid>
        <MetricCard
          label="Total Signals"
          value={hasSignals ? (data?.total_signals ?? signalList.length) : '--'}
        />
        {(severity !== 'all' || entityType !== 'all') && (
          <MetricCard label="Filtered" value={filtered.length} />
        )}
      </SummaryGrid>

      {/* Signal List */}
      <div className="space-y-4">
        {!hasSignals ? (
          <div className="p-6 text-center text-[var(--grey-light)]">
            {hasLoaded ? 'Signal data could not be loaded.' : 'Loading signals...'}
          </div>
        ) : filtered.length === 0 ? (
          severity !== 'all' || entityType !== 'all' ? (
            <NoResults query={`severity: ${severity}, type: ${entityType}`} />
          ) : (
            <NoSignals />
          )
        ) : (
          filtered.map((signal, i) => <SignalCard key={signal.signal_id || i} signal={signal} />)
        )}
      </div>
    </PageLayout>
  );
}
