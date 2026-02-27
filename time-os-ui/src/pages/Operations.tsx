// Operations page — System health, data quality, and housekeeping
// Consolidates Fix Data + Watchers + Couplings into a single ops view
import { useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { FixDataCard, SkeletonCardList, ErrorState, useToast } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { useFixData, useWatchers, useAllCouplings, useHealth } from '../lib/hooks';
import * as api from '../lib/api';
import type { Watcher, Coupling, FixData } from '../types/api';

type OpsTab = 'data-quality' | 'watchers' | 'couplings';

const TABS: TabDef<OpsTab>[] = [
  { id: 'data-quality', label: 'Data Quality' },
  { id: 'watchers', label: 'Watchers' },
  { id: 'couplings', label: 'Couplings' },
];

export function Operations() {
  const toast = useToast();
  const navigate = useNavigate();
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  const { data: fixData, loading: fixLoading, error: fixError, refetch: refetchFix } = useFixData();
  const { data: watcherData, refetch: refetchWatchers } = useWatchers(24);
  const { data: couplingData } = useAllCouplings();
  const { data: healthData } = useHealth();

  // Derive counts
  const identityCount = fixData?.identity_conflicts?.length || 0;
  const linkCount = fixData?.ambiguous_links?.length || 0;
  const totalFixItems = identityCount + linkCount;
  const watcherCount = watcherData?.items?.length || 0;
  const couplingCount = couplingData?.items?.length || 0;
  const systemStatus = healthData?.status || 'unknown';

  // Update tab badges
  const tabsWithBadges: TabDef<OpsTab>[] = TABS.map((tab) => {
    if (tab.id === 'data-quality') return { ...tab, badge: totalFixItems };
    if (tab.id === 'watchers') return { ...tab, badge: watcherCount };
    if (tab.id === 'couplings') return { ...tab, badge: couplingCount };
    return tab;
  });

  // Fix data resolution handler
  const handleResolve = async (
    itemId: string,
    itemType: 'identity_conflict' | 'ambiguous_link'
  ) => {
    setResolvingId(itemId);
    try {
      const apiType = itemType === 'identity_conflict' ? 'identity' : 'link';
      const result = await api.resolveFixDataItem(apiType, itemId, 'manually_resolved');
      if (result.success) {
        toast.success('Item resolved');
        refetchFix();
      } else {
        toast.error(result.error || 'Failed to resolve');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to resolve');
    } finally {
      setResolvingId(null);
    }
  };

  if (fixLoading) return <SkeletonCardList count={4} />;
  if (fixError) return <ErrorState error={fixError} onRetry={refetchFix} hasData={false} />;

  return (
    <PageLayout title="Operations" subtitle="System health, data quality & housekeeping">
      <SummaryGrid>
        <MetricCard
          label="Fix Items"
          value={totalFixItems}
          severity={totalFixItems > 0 ? 'warning' : 'success'}
        />
        <MetricCard label="Active Watchers" value={watcherCount} />
        <MetricCard label="Couplings" value={couplingCount} />
        <MetricCard
          label="System Health"
          value={systemStatus === 'healthy' ? '✓ Healthy' : '✗ Unhealthy'}
          severity={systemStatus === 'healthy' ? 'success' : 'danger'}
        />
      </SummaryGrid>

      <TabContainer tabs={tabsWithBadges}>
        {(tab) => {
          switch (tab) {
            case 'data-quality':
              return (
                <DataQualityTab
                  fixData={fixData}
                  resolvingId={resolvingId}
                  onResolve={handleResolve}
                />
              );
            case 'watchers':
              return (
                <WatchersTab
                  watchers={watcherData?.items || []}
                  refetch={refetchWatchers}
                  navigate={navigate}
                />
              );
            case 'couplings':
              return <CouplingsTab couplings={couplingData?.items || []} />;
            default:
              return null;
          }
        }}
      </TabContainer>
    </PageLayout>
  );
}

// ---- Data Quality Tab ----

function DataQualityTab({
  fixData,
  resolvingId,
  onResolve,
}: {
  fixData: FixData | null;
  resolvingId: string | null;
  onResolve: (id: string, type: 'identity_conflict' | 'ambiguous_link') => void;
}) {
  const identityConflicts = (fixData?.identity_conflicts || []).map((item) => ({
    ...item,
    issue_type: 'identity_conflict' as const,
  }));
  const ambiguousLinks = (fixData?.ambiguous_links || []).map((item) => ({
    ...item,
    issue_type: 'ambiguous_link' as const,
  }));
  const allItems = [...identityConflicts, ...ambiguousLinks];

  if (allItems.length === 0) {
    return (
      <div className="p-8 text-center">
        <p className="text-[var(--success)]">✓ No data issues — everything looks clean</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 pt-4">
      {allItems.map((item) => (
        <FixDataCard
          key={item.id}
          type={item.issue_type}
          item={item}
          onResolve={() => onResolve(item.id, item.issue_type)}
          isResolving={resolvingId === item.id}
        />
      ))}
    </div>
  );
}

// ---- Watchers Tab ----

function WatchersTab({
  watchers,
  refetch,
  navigate,
}: {
  watchers: Watcher[];
  refetch: () => void;
  navigate: ReturnType<typeof useNavigate>;
}) {
  if (watchers.length === 0) {
    return (
      <div className="p-8 text-center">
        <p className="text-[var(--grey-light)]">No watchers triggered in the last 24h</p>
      </div>
    );
  }

  return (
    <div className="space-y-3 pt-4">
      {watchers.map((w, i) => (
        <div
          key={w.watcher_id || i}
          className="flex items-center justify-between p-3 bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)]"
        >
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <span className="px-1.5 py-0.5 text-xs bg-[var(--info)]/20 text-[var(--info)] border border-blue-500/30 rounded font-medium shrink-0">
              {(w.watch_type || 'WATCH').toString().toUpperCase()}
            </span>
            <span
              className="text-[var(--grey-light)] truncate cursor-pointer hover:text-[var(--info)]"
              onClick={() => navigate({ to: '/issues' })}
            >
              {w.issue_title || 'Watcher alert'}
            </span>
            {w.trigger_count > 1 && (
              <span className="text-xs text-[var(--grey)] shrink-0">×{w.trigger_count}</span>
            )}
          </div>
          <div className="flex gap-1 shrink-0 ml-2">
            <button
              onClick={async () => {
                if (w.watcher_id) {
                  await api.snoozeWatcher(w.watcher_id, 4);
                  refetch();
                }
              }}
              className="px-1.5 py-0.5 text-xs bg-[var(--grey)] hover:bg-[var(--grey-light)] rounded"
              title="Snooze 4h"
            >
              4h
            </button>
            <button
              onClick={async () => {
                if (w.watcher_id) {
                  await api.snoozeWatcher(w.watcher_id, 24);
                  refetch();
                }
              }}
              className="px-1.5 py-0.5 text-xs bg-[var(--grey)] hover:bg-[var(--grey-light)] rounded"
              title="Snooze 24h"
            >
              24h
            </button>
            <button
              onClick={async () => {
                if (w.watcher_id) {
                  await api.dismissWatcher(w.watcher_id);
                  refetch();
                }
              }}
              className="px-1.5 py-0.5 text-xs bg-[var(--danger)]/20 hover:bg-red-800/50 text-[var(--danger)] rounded"
              title="Dismiss"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---- Couplings Tab ----

function CouplingsTab({ couplings }: { couplings: Coupling[] }) {
  if (couplings.length === 0) {
    return (
      <div className="p-8 text-center">
        <p className="text-[var(--grey-light)]">No entity couplings detected</p>
      </div>
    );
  }

  // Group by coupling_type
  const grouped = couplings.reduce<Record<string, Coupling[]>>((acc, c) => {
    const key = c.coupling_type || 'other';
    if (!acc[key]) acc[key] = [];
    acc[key].push(c);
    return acc;
  }, {});

  return (
    <div className="space-y-6 pt-4">
      {Object.entries(grouped).map(([type, items]) => (
        <div key={type}>
          <h3 className="text-sm font-medium text-[var(--grey-light)] mb-3 capitalize">
            {type.replace(/_/g, ' ')} ({items.length})
          </h3>
          <div className="space-y-2">
            {items.slice(0, 10).map((c) => {
              const anchorLabel = c.anchor_ref_id;
              const targets = c.entity_refs || [];
              return (
                <div
                  key={c.coupling_id}
                  className="flex items-center gap-3 p-3 bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)]"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[var(--white)] text-sm truncate">{anchorLabel}</span>
                      <span className="text-[var(--grey)] text-xs">→</span>
                      <span className="text-[var(--grey-light)] text-sm truncate">
                        {targets.map((t) => t.label || t.ref_id).join(', ')}
                      </span>
                    </div>
                    {c.why && (
                      <p className="text-xs text-[var(--grey)] mt-1 truncate">
                        {Object.entries(c.why)
                          .filter(([, v]) => typeof v === 'number' && v > 0)
                          .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
                          .slice(0, 3)
                          .join(' · ')}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <div className="w-16 h-1.5 bg-[var(--grey)] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[var(--info)] rounded-full"
                        style={{ width: `${Math.round((c.strength || 0) * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-[var(--grey-light)] w-8 text-right">
                      {Math.round((c.strength || 0) * 100)}%
                    </span>
                  </div>
                </div>
              );
            })}
            {items.length > 10 && (
              <p className="text-sm text-[var(--grey)] text-center pt-1">
                +{items.length - 10} more
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export default Operations;
