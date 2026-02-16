/**
 * Signals — Active Signals List
 *
 * Shows all detected signals with filtering by severity and entity type.
 */

import { useSignals } from '../hooks';
import { useSignalFilters } from '../lib';
import { ErrorState, NoSignals, NoResults } from '../../components';
import { SkeletonSignalsPage } from '../components';
import type { Signal } from '../api';

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: 'bg-red-500/20 text-red-400',
    warning: 'bg-amber-500/20 text-amber-400',
    watch: 'bg-slate-500/20 text-slate-400',
  };

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[severity] || colors.watch}`}>
      {severity}
    </span>
  );
}

function SignalCard({ signal }: { signal: Signal }) {
  return (
    <div
      className={`rounded-lg p-4 border ${
        signal.severity === 'critical'
          ? 'bg-red-500/5 border-red-500/30'
          : signal.severity === 'warning'
            ? 'bg-amber-500/5 border-amber-500/30'
            : 'bg-slate-800 border-slate-700'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <SeverityBadge severity={signal.severity} />
            <span className="text-sm text-slate-500">{signal.entity_type}</span>
          </div>
          <div className="font-medium mt-2">{signal.name}</div>
          <div className="text-sm text-slate-400 mt-1">
            {signal.entity_name || signal.entity_id}
          </div>
        </div>
      </div>
      <div className="text-sm text-slate-500 mt-3">{signal.evidence}</div>
      <div className="text-sm text-slate-400 mt-2 pt-2 border-t border-slate-700">
        → {signal.implied_action}
      </div>
    </div>
  );
}

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
        <h1 className="text-xl sm:text-2xl font-semibold">Active Signals</h1>
        <div className="text-sm text-slate-500">{data?.total_signals ?? 0} total</div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row flex-wrap gap-3 sm:gap-4 bg-slate-800 rounded-lg p-3 sm:p-4">
        <div className="flex-1 sm:flex-none">
          <label className="text-sm text-slate-400 block mb-1">Severity</label>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="w-full sm:w-auto bg-slate-700 border border-slate-600 rounded px-3 py-2 min-h-[44px] text-sm"
          >
            {severities.map((s) => (
              <option key={s} value={s}>
                {s === 'all' ? 'All' : s}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1 sm:flex-none">
          <label className="text-sm text-slate-400 block mb-1">Entity Type</label>
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="w-full sm:w-auto bg-slate-700 border border-slate-600 rounded px-3 py-2 min-h-[44px] text-sm"
          >
            {entityTypes.map((t) => (
              <option key={t} value={t}>
                {t === 'all' ? 'All' : t}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center sm:items-end gap-2 pt-2 sm:pt-0">
          <span className="text-sm text-slate-500">
            Showing {filtered.length} of {signals.length}
          </span>
          {(severity !== 'all' || entityType !== 'all') && (
            <button
              onClick={resetFilters}
              className="text-xs text-slate-400 hover:text-white px-2 py-1 min-h-[32px]"
            >
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
