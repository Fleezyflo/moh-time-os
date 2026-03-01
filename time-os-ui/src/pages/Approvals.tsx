// Approvals page — pending approval queue with actions (Phase 11)
import { useMemo } from 'react';
import { SkeletonCardList, ErrorState } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { ApprovalQueue } from '../components/governance/ApprovalQueue';
import { useApprovals, usePendingActions } from '../lib/hooks';

export default function Approvals() {
  const { data: approvalsData, loading, error, refetch } = useApprovals();
  const { data: actionsData, refetch: refetchActions } = usePendingActions();

  const approvals = useMemo(() => approvalsData?.approvals ?? [], [approvalsData]);
  const pendingActions = useMemo(() => actionsData?.actions ?? [], [actionsData]);
  const totalPending = approvals.length + pendingActions.length;

  const handleRefresh = () => {
    refetch();
    refetchActions();
  };

  if (loading && !approvalsData) return <SkeletonCardList count={4} />;
  if (error && !approvalsData) {
    return <ErrorState error={error} onRetry={refetch} hasData={false} />;
  }

  // Count by risk level
  const riskCounts = useMemo(() => {
    const counts: Record<string, number> = { low: 0, medium: 0, high: 0, critical: 0 };
    for (const a of approvals) {
      const level = a.risk_level ?? 'medium';
      counts[level] = (counts[level] ?? 0) + 1;
    }
    return counts;
  }, [approvals]);

  return (
    <PageLayout title="Approvals" subtitle={`${totalPending} pending`}>
      <SummaryGrid>
        <MetricCard
          label="Pending"
          value={totalPending}
          severity={totalPending > 0 ? 'warning' : undefined}
        />
        <MetricCard label="Low Risk" value={riskCounts.low} />
        <MetricCard
          label="High Risk"
          value={riskCounts.high + riskCounts.critical}
          severity={riskCounts.high + riskCounts.critical > 0 ? 'danger' : undefined}
        />
        <MetricCard label="Actions Queue" value={pendingActions.length} />
      </SummaryGrid>

      {approvals.length > 0 && (
        <section>
          <h3 className="text-sm font-medium mb-3">Decision Approvals</h3>
          <ApprovalQueue approvals={approvals} onRefresh={handleRefresh} />
        </section>
      )}

      {pendingActions.length > 0 && (
        <section className="mt-6">
          <h3 className="text-sm font-medium mb-3">Pending Actions</h3>
          <div className="space-y-2">
            {pendingActions.map((a) => (
              <div
                key={a.action_id}
                className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg px-4 py-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{a.action_type}</span>
                  <span className="text-xs text-[var(--grey-light)]">{a.risk_level}</span>
                </div>
                <div className="text-xs text-[var(--grey-light)] mt-0.5">
                  {a.target_entity}:{a.target_id} &middot; confidence:{' '}
                  {(a.confidence_score * 100).toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {totalPending === 0 && (
        <div className="text-center py-12 text-[var(--grey-light)]">
          <p className="text-sm">No pending approvals or actions</p>
        </div>
      )}
    </PageLayout>
  );
}
