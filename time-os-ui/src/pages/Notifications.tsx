// Notifications page — list, stats bar, dismiss actions (Phase 10)
import { useState, useCallback, useMemo } from 'react';
import { SkeletonCardList, ErrorState } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { NotificationList } from '../components/notifications/NotificationList';
import { useNotifications, useNotificationStats } from '../lib/hooks';
import { dismissNotification, dismissAllNotifications } from '../lib/api';

export default function Notifications() {
  const [showDismissed, setShowDismissed] = useState(false);

  const { data: notifData, loading, error, refetch } = useNotifications(showDismissed);

  const { data: statsData, refetch: refetchStats } = useNotificationStats();

  const notifications = useMemo(() => notifData?.notifications ?? [], [notifData]);
  const totalCount = statsData?.total ?? 0;
  const unreadCount = statsData?.unread ?? 0;
  const dismissedCount = totalCount - unreadCount;

  const handleDismiss = useCallback(
    async (id: string) => {
      await dismissNotification(id);
      refetch();
      refetchStats();
    },
    [refetch, refetchStats]
  );

  const handleDismissAll = useCallback(async () => {
    await dismissAllNotifications();
    refetch();
    refetchStats();
  }, [refetch, refetchStats]);

  if (loading && !notifData) return <SkeletonCardList count={6} />;
  if (error && !notifData) {
    return <ErrorState error={error} onRetry={refetch} hasData={false} />;
  }

  return (
    <PageLayout
      title="Notifications"
      subtitle={`${unreadCount} unread`}
      actions={
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={showDismissed}
              onChange={(e) => setShowDismissed(e.target.checked)}
              className="rounded"
            />
            Show dismissed
          </label>
          {unreadCount > 0 && (
            <button
              onClick={handleDismissAll}
              className="text-xs px-3 py-1.5 rounded-lg bg-[var(--grey)] hover:bg-[var(--grey-light)] transition-colors"
            >
              Dismiss all
            </button>
          )}
        </div>
      }
    >
      <SummaryGrid>
        <MetricCard label="Total" value={totalCount} />
        <MetricCard
          label="Unread"
          value={unreadCount}
          severity={unreadCount > 0 ? 'warning' : undefined}
        />
        <MetricCard label="Dismissed" value={dismissedCount} />
      </SummaryGrid>

      <NotificationList notifications={notifications} onDismiss={handleDismiss} />
    </PageLayout>
  );
}
