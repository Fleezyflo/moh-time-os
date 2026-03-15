// Governance page — domain cards, emergency brake, history, calibration, bundles (Phase 11)
import { useMemo, useCallback, useState } from 'react';
import { SkeletonCardList, ErrorState } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer } from '../components/layout/TabContainer';
import { GovernanceDomainCards } from '../components/governance/GovernanceDomainCards';
import { EmergencyBrakeToggle } from '../components/governance/EmergencyBrakeToggle';
import { BundleTimeline } from '../components/governance/BundleTimeline';
import {
  useGovernance,
  useGovernanceHistory,
  useCalibration,
  useBundles,
  useRollbackable,
  useBundleSummary,
} from '../lib/hooks';
import { runCalibration } from '../lib/api';

export default function Governance() {
  const [activeTab, setActiveTab] = useState('domains');
  const [calibrating, setCalibrating] = useState(false);

  const { data: govData, loading, error, refetch } = useGovernance();
  const { data: historyData, refetch: refetchHistory } = useGovernanceHistory();
  const { data: calData, refetch: refetchCal } = useCalibration();
  const { data: bundlesData, refetch: refetchBundles } = useBundles();
  const { data: rollbackData, refetch: refetchRollback } = useRollbackable();
  const { data: summaryData, refetch: refetchSummary } = useBundleSummary();

  const domains = useMemo(() => govData?.domains ?? [], [govData]);
  const brakeActive = govData?.emergency_brake ?? false;
  const bundles = useMemo(() => bundlesData?.bundles ?? [], [bundlesData]);
  const rollbackable = useMemo(() => rollbackData?.bundles ?? [], [rollbackData]);
  const history = useMemo(() => historyData?.history ?? [], [historyData]);

  const refreshAll = useCallback(() => {
    refetch();
    refetchHistory();
    refetchBundles();
    refetchRollback();
    refetchSummary();
  }, [refetch, refetchHistory, refetchBundles, refetchRollback, refetchSummary]);

  const handleRunCalibration = useCallback(async () => {
    setCalibrating(true);
    try {
      await runCalibration();
      refetchCal();
    } finally {
      setCalibrating(false);
    }
  }, [refetchCal]);

  if (loading && !govData) return <SkeletonCardList count={6} />;
  if (error && !govData) {
    return <ErrorState error={error} onRetry={refetch} hasData={false} />;
  }

  const tabs = [
    { id: 'domains', label: 'Domains' },
    { id: 'history', label: 'History' },
    { id: 'bundles', label: 'Bundles' },
    { id: 'calibration', label: 'Calibration' },
  ];

  return (
    <PageLayout
      title="Governance"
      subtitle={brakeActive ? 'BRAKE ACTIVE' : `${domains.length} domains`}
    >
      <SummaryGrid>
        <MetricCard label="Domains" value={domains.length} />
        <MetricCard
          label="Emergency Brake"
          value={brakeActive ? 'ON' : 'OFF'}
          severity={brakeActive ? 'danger' : undefined}
        />
        <MetricCard label="Total Bundles" value={summaryData != null ? (summaryData.total_bundles ?? 0) : '--'} />
        <MetricCard label="Rollbackable" value={summaryData != null ? (summaryData.rollbackable_count ?? 0) : '--'} />
      </SummaryGrid>

      <EmergencyBrakeToggle active={brakeActive} onRefresh={refreshAll} />

      <TabContainer tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab}>
        {(tab) => {
          if (tab === 'domains') {
            return <GovernanceDomainCards domains={domains} onRefresh={refreshAll} />;
          }
          if (tab === 'history') {
            return (
              <div className="space-y-2">
                {history.length === 0 ? (
                  <div className="text-sm text-[var(--grey-light)]">
                    No governance actions recorded.
                  </div>
                ) : (
                  history.map((h) => (
                    <div
                      key={h.id}
                      className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg px-4 py-3 text-sm"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{h.action}</span>
                        <span className="text-xs text-[var(--grey-light)]">
                          {new Date(h.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-xs text-[var(--grey-light)] mt-0.5">
                        {h.domain} &middot; {h.actor}
                      </div>
                    </div>
                  ))
                )}
              </div>
            );
          }
          if (tab === 'bundles') {
            return (
              <BundleTimeline
                bundles={bundles}
                rollbackable={rollbackable}
                onRefresh={refreshAll}
              />
            );
          }
          if (tab === 'calibration') {
            return (
              <div className="space-y-4">
                <button
                  onClick={handleRunCalibration}
                  disabled={calibrating}
                  className="text-sm px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-blue-600 disabled:opacity-50 transition-colors"
                >
                  {calibrating ? 'Running calibration...' : 'Run Calibration'}
                </button>
                {calData && (
                  <div className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-xl p-4">
                    <h4 className="text-sm font-medium mb-2">Last Calibration Result</h4>
                    <pre className="text-xs text-[var(--grey-light)] overflow-x-auto whitespace-pre-wrap">
                      {JSON.stringify(calData, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          }
          return null;
        }}
      </TabContainer>
    </PageLayout>
  );
}
