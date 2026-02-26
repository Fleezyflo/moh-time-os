/**
 * Signals — Active Signals List
 *
 * Shows all detected signals with filtering by severity and entity type.
 */

import { useSignals } from '../hooks';
import { useSignalFilters } from '../lib';
import { ErrorState, NoSignals, NoResults } from '../../components';
import { SkeletonSignalsPage, SignalCard } from '../components';

export default function Signals() {
  const { severity, entityType, setSeverity, setEntityType, resetFilters } = useSignalFilters();

  const { data, loading, error, refetch } = useSignals(true);

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

  const signals = data?.signals ?? [];

  // Apply filters
  const filtered = signals.filter((s) => {
    if (severity !== 'all' && s.severity !== severity) return false;
    if (entityType !== 'all' && s.entity_type !== entityType) return false;
    return true;
  });

  // Get unique values for filters
  const severities = ['all', ...new Set(signals.map((s) => s.severity))];
  const entityTypes = ['all', ...new Set(signals.map((s) => s.entity_type))];

  return (
    <div className="space-y-6">
      {/* Error banner when we have stale data */}
      {error && data && <ErrorState error={error} onRetry={refetch} hasData />}

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Active Signals</h1>
        <div className="text-sm text-slate-500">{data?.total_signals ?? 0} total</div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 bg-slate-800 rounded-lg p-4">
        <div>
          <label className="text-sm text-slate-400 block mb-1">Severity</label>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm"
          >
            {severities.map((s) => (
              <option key={s} value={s}>
                {s === 'all' ? 'All' : s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-sm text-slate-400 block mb-1">Entity Type</label>
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm"
          >
            {entityTypes.map((t) => (
              <option key={t} value={t}>
                {t === 'all' ? 'All' : t}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end gap-2">
          <span className="text-sm text-slate-500">
            Showing {filtered.length} of {signals.length}
          </span>
          {(severity !== 'all' || entityType !== 'all') && (
            <button onClick={resetFilters} className="text-xs text-slate-400 hover:text-white">
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Signal List */}
      <div className="space-y-4">
        {filtered.length === 0 ? (
          severity !== 'all' || entityType !== 'all' ? (
            <NoResults query={`severity: ${severity}, type: ${entityType}`} />
          ) : (
            <NoSignals />
          )
        ) : (
          filtered.map((signal, i) => <SignalCard key={signal.signal_id || i} signal={signal} />)
        )}
      </div>
    </div>
  );
}
