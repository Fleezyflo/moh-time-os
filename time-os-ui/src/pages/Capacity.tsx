// Capacity page — utilization gauges and forecast chart (Phase 8)
import { useState, useMemo } from 'react';
import { SkeletonCardList, ErrorState } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { CapacityGauge } from '../components/capacity/CapacityGauge';
import { ForecastChart } from '../components/capacity/ForecastChart';
import {
  useCapacityLanes,
  useCapacityUtilization,
  useCapacityForecast,
  useCapacityDebt,
} from '../lib/hooks';

type CapacityTab = 'utilization' | 'forecast' | 'debt';

const CAPACITY_TABS: TabDef<CapacityTab>[] = [
  { id: 'utilization', label: 'Utilization' },
  { id: 'forecast', label: 'Forecast' },
  { id: 'debt', label: 'Debt' },
];

export default function Capacity() {
  const [selectedLane, setSelectedLane] = useState<string | undefined>();
  const [forecastDays, setForecastDays] = useState(7);

  const {
    data: lanesData,
    loading: lanesLoading,
    error: lanesError,
    refetch: refetchLanes,
  } = useCapacityLanes();

  const {
    data: utilData,
    loading: utilLoading,
    error: utilError,
    refetch: refetchUtil,
  } = useCapacityUtilization(selectedLane);

  const {
    data: forecastData,
    loading: forecastLoading,
    error: forecastError,
    refetch: refetchForecast,
  } = useCapacityForecast(selectedLane || 'default', forecastDays);

  const {
    data: debtData,
    loading: debtLoading,
    error: debtError,
    refetch: refetchDebt,
  } = useCapacityDebt(selectedLane);

  const lanes = useMemo(() => lanesData?.lanes ?? [], [lanesData]);
  const forecasts = useMemo(() => forecastData?.forecasts ?? [], [forecastData]);

  // Extract utilization percentage from response — null when not loaded
  const utilizationPct = useMemo((): number | null => {
    if (!utilData) return null;
    const util = utilData.utilization;
    if (util && typeof util === 'object') {
      if ('percentage' in util && typeof util.percentage === 'number') return util.percentage;
      if ('utilization_pct' in util && typeof util.utilization_pct === 'number')
        return util.utilization_pct;
    }
    // Try top-level keys
    if ('utilization_pct' in utilData && typeof utilData.utilization_pct === 'number')
      return utilData.utilization_pct;
    if ('percentage' in utilData && typeof utilData.percentage === 'number')
      return utilData.percentage;
    return 0;
  }, [utilData]);

  // Extract debt info
  const debtItems = useMemo(() => {
    if (!debtData) return [];
    if ('items' in debtData && Array.isArray(debtData.items))
      return debtData.items as Array<Record<string, unknown>>;
    if ('debts' in debtData && Array.isArray(debtData.debts))
      return debtData.debts as Array<Record<string, unknown>>;
    return [];
  }, [debtData]);

  const totalDebtHours = useMemo((): number | null => {
    if (!debtData) return null;
    if ('total_hours' in debtData && typeof debtData.total_hours === 'number')
      return debtData.total_hours;
    return debtItems.reduce((sum, item) => {
      const hours = typeof item.hours === 'number' ? item.hours : 0;
      return sum + hours;
    }, 0);
  }, [debtData, debtItems]);

  if (lanesLoading && !lanesData) return <SkeletonCardList count={4} />;
  if (lanesError && !lanesData) {
    return <ErrorState error={lanesError} onRetry={refetchLanes} hasData={false} />;
  }

  return (
    <PageLayout
      title="Capacity"
      subtitle={`${lanes.length} lane${lanes.length !== 1 ? 's' : ''} configured`}
      actions={
        <select
          value={selectedLane || ''}
          onChange={(e) => setSelectedLane(e.target.value || undefined)}
          className="px-3 py-1.5 rounded-lg bg-[var(--black)] border border-[var(--grey)] text-sm focus:border-[var(--accent)] outline-none"
        >
          <option value="">All Lanes</option>
          {lanes.map((lane) => (
            <option key={lane.id} value={lane.id}>
              {lane.name || lane.id}
            </option>
          ))}
        </select>
      }
    >
      <SummaryGrid>
        <MetricCard
          label="Utilization"
          value={utilizationPct != null ? `${Math.round(utilizationPct)}%` : '--'}
          severity={
            utilizationPct != null
              ? utilizationPct >= 90
                ? 'danger'
                : utilizationPct >= 75
                  ? 'warning'
                  : utilizationPct >= 50
                    ? 'info'
                    : 'success'
              : undefined
          }
        />
        <MetricCard label="Lanes" value={lanes.length} />
        <MetricCard label="Forecast Days" value={forecastDays} />
        <MetricCard
          label="Debt"
          value={totalDebtHours != null ? `${totalDebtHours}h` : '--'}
          severity={
            totalDebtHours != null ? (totalDebtHours > 0 ? 'warning' : 'success') : undefined
          }
        />
      </SummaryGrid>

      <TabContainer tabs={CAPACITY_TABS} defaultTab="utilization">
        {(activeTab) => {
          if (activeTab === 'forecast') {
            if (forecastLoading) return <SkeletonCardList count={3} />;
            if (forecastError) {
              return <ErrorState error={forecastError} onRetry={refetchForecast} hasData={false} />;
            }
            return (
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <label className="text-sm text-[var(--grey-light)]">Days ahead:</label>
                  {[3, 7, 14].map((d) => (
                    <button
                      key={d}
                      onClick={() => setForecastDays(d)}
                      className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                        forecastDays === d
                          ? 'border-[var(--accent)] text-[var(--accent)]'
                          : 'border-[var(--grey)] text-[var(--grey-light)] hover:border-[var(--grey-light)]'
                      }`}
                    >
                      {d}d
                    </button>
                  ))}
                </div>
                <ForecastChart forecasts={forecasts} laneId={selectedLane || 'default'} />
              </div>
            );
          }

          if (activeTab === 'debt') {
            if (debtLoading) return <SkeletonCardList count={3} />;
            if (debtError) {
              return <ErrorState error={debtError} onRetry={refetchDebt} hasData={false} />;
            }
            if (debtItems.length === 0) {
              return (
                <div className="text-center py-8">
                  <div className="text-sm text-[var(--grey-muted)]">No capacity debt recorded</div>
                  <div className="text-xs text-[var(--grey-muted)] mt-1">
                    Debt accumulates when scheduled hours exceed available capacity
                  </div>
                </div>
              );
            }
            return (
              <div className="space-y-2">
                {debtItems.map((item, i) => (
                  <div
                    key={String(item.id || i)}
                    className="p-3 rounded-lg border border-[var(--grey)]"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm">
                        {String(item.description || item.lane || `Debt #${i + 1}`)}
                      </span>
                      <span className="text-sm font-medium text-[var(--warning)]">
                        {typeof item.hours === 'number' ? `${item.hours}h` : '—'}
                      </span>
                    </div>
                    {'date' in item && item.date ? (
                      <div className="text-xs text-[var(--grey-muted)] mt-1">
                        {String(item.date)}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            );
          }

          // Utilization (default)
          if (utilLoading) return <SkeletonCardList count={3} />;
          if (utilError) {
            return <ErrorState error={utilError} onRetry={refetchUtil} hasData={false} />;
          }
          return (
            <div>
              <div className="flex flex-wrap justify-center gap-8 py-4">
                {selectedLane ? (
                  utilizationPct != null ? (
                    <CapacityGauge label={selectedLane} value={utilizationPct} size={140} />
                  ) : (
                    <div className="text-sm text-[var(--grey-muted)]">No utilization data</div>
                  )
                ) : (
                  <>
                    {utilizationPct != null && (
                      <CapacityGauge label="Overall" value={utilizationPct} size={140} />
                    )}
                    {lanes.map((lane) => (
                      <CapacityGauge
                        key={lane.id}
                        label={lane.name || lane.id}
                        value={
                          typeof lane.utilization_pct === 'number'
                            ? (lane.utilization_pct as number)
                            : 0
                        }
                      />
                    ))}
                  </>
                )}
              </div>
              {/* Utilization details */}
              {utilData && (
                <div className="mt-4 p-4 rounded-lg border border-[var(--grey)]">
                  <div className="text-sm text-[var(--grey-light)] mb-2">Details</div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                    {Object.entries(utilData.utilization || utilData).map(([key, value]) => {
                      if (key === 'utilization' || typeof value === 'object') return null;
                      return (
                        <div key={key}>
                          <div className="text-xs text-[var(--grey-muted)] capitalize">
                            {key.replace(/_/g, ' ')}
                          </div>
                          <div>{String(value)}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        }}
      </TabContainer>
    </PageLayout>
  );
}
