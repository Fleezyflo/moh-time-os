// Data Quality page — health score, issues, cleanup, recalculation (Phase 11)
import { useCallback, useState } from 'react';
import { SkeletonCardList, ErrorState } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { DataQualityHealthScore } from '../components/governance/DataQualityHealthScore';
import { CleanupPreviewConfirm } from '../components/governance/CleanupPreviewConfirm';
import { useDataQuality } from '../lib/hooks';
import { recalculatePriorities } from '../lib/api';

export default function DataQuality() {
  const { data, loading, error, refetch } = useDataQuality();
  const [recalculating, setRecalculating] = useState(false);

  const handleRecalculate = useCallback(async () => {
    setRecalculating(true);
    try {
      await recalculatePriorities();
      refetch();
    } finally {
      setRecalculating(false);
    }
  }, [refetch]);

  if (loading && !data) return <SkeletonCardList count={4} />;
  if (error && !data) {
    return <ErrorState error={error} onRetry={refetch} hasData={false} />;
  }
  if (!data) return null;

  return (
    <PageLayout
      title="Data Quality"
      subtitle={`Score: ${data.health_score}/100`}
      actions={
        <button
          onClick={handleRecalculate}
          disabled={recalculating}
          className="text-xs px-3 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {recalculating ? 'Recalculating...' : 'Recalculate Priorities'}
        </button>
      }
    >
      <DataQualityHealthScore data={data} />

      {/* Cleanup Actions */}
      <section className="mt-6 space-y-4">
        <h3 className="text-sm font-medium">Cleanup Actions</h3>
        <p className="text-xs text-[var(--grey-light)]">
          Preview and confirm cleanup operations. Each shows affected items before executing.
        </p>
        <div className="flex flex-wrap gap-3">
          <CleanupPreviewConfirm
            cleanupType="ancient"
            label="Archive Ancient Tasks"
            onComplete={refetch}
          />
          <CleanupPreviewConfirm
            cleanupType="stale"
            label="Archive Stale Tasks"
            onComplete={refetch}
          />
          <CleanupPreviewConfirm
            cleanupType="legacy-signals"
            label="Expire Legacy Signals"
            onComplete={refetch}
          />
        </div>
      </section>
    </PageLayout>
  );
}
