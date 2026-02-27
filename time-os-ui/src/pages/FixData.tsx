// Fix Data page
import { useState } from 'react';
import { FixDataCard, SkeletonCardList, ErrorState, useToast } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { useFixData } from '../lib/hooks';
import { resolveFixDataItem } from '../lib/api';

export function FixData() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isBulkResolving, setIsBulkResolving] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<{
    show: boolean;
    itemId?: string;
    itemType?: 'identity_conflict' | 'ambiguous_link';
    bulk?: boolean;
  }>({ show: false });
  const { data: apiFixData, loading, error, refetch } = useFixData();

  if (loading) return <SkeletonCardList count={4} />;
  if (error) return <ErrorState error={error} onRetry={refetch} hasData={false} />;

  // Summary stats
  const identityCount = apiFixData?.identity_conflicts?.length || 0;
  const linkCount = apiFixData?.ambiguous_links?.length || 0;
  const totalIssues = identityCount + linkCount;

  // Combine identity_conflicts and ambiguous_links into a single list
  const identityConflicts = (apiFixData?.identity_conflicts || []).map((item) => ({
    ...item,
    issue_type: 'identity_conflict' as const,
  }));
  const ambiguousLinks = (apiFixData?.ambiguous_links || []).map((item) => ({
    ...item,
    issue_type: 'ambiguous_link' as const,
  }));
  const allItems = [...identityConflicts, ...ambiguousLinks];

  const filtered = allItems.filter((item) => {
    if (search === '') return true;
    const searchLower = search.toLowerCase();
    // Use display_name for identity conflicts, entity_id for ambiguous links
    const searchableText = 'display_name' in item ? item.display_name : item.entity_id;
    return (searchableText || '').toLowerCase().includes(searchLower);
  });

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const selectAll = () => {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((item) => item.id)));
    }
  };

  const handleResolveConfirmed = async (
    itemId: string,
    itemType: 'identity_conflict' | 'ambiguous_link'
  ) => {
    setResolvingId(itemId);
    setResolveError(null);
    setConfirmDialog({ show: false });
    try {
      const apiType = itemType === 'identity_conflict' ? 'identity' : 'link';
      const result = await resolveFixDataItem(apiType, itemId, 'manually_resolved');
      if (result.success) {
        toast.success('Item resolved');
        refetch();
      } else {
        setResolveError(result.error || 'Failed to resolve');
        toast.error(result.error || 'Failed to resolve');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to resolve';
      setResolveError(msg);
      toast.error(msg);
    } finally {
      setResolvingId(null);
    }
  };

  const handleResolve = (itemId: string, itemType: 'identity_conflict' | 'ambiguous_link') => {
    setConfirmDialog({ show: true, itemId, itemType, bulk: false });
  };

  const handleBulkResolve = async () => {
    setConfirmDialog({ show: false });
    setIsBulkResolving(true);
    setResolveError(null);

    const itemsToResolve = filtered.filter((item) => selectedIds.has(item.id));
    let successCount = 0;
    let failCount = 0;

    for (const item of itemsToResolve) {
      try {
        const apiType = item.issue_type === 'identity_conflict' ? 'identity' : 'link';
        const result = await resolveFixDataItem(apiType, item.id, 'manually_resolved');
        if (result.success) {
          successCount++;
        } else {
          failCount++;
        }
      } catch {
        failCount++;
      }
    }

    setIsBulkResolving(false);
    setSelectedIds(new Set());

    if (successCount > 0) {
      toast.success(`Resolved ${successCount} item${successCount !== 1 ? 's' : ''}`);
    }
    if (failCount > 0) {
      toast.error(`Failed to resolve ${failCount} item${failCount !== 1 ? 's' : ''}`);
    }

    refetch();
  };

  const handleBulkResolveClick = () => {
    setConfirmDialog({ show: true, bulk: true });
  };

  return (
    <PageLayout
      title="Fix Data"
      subtitle={
        totalIssues === 0
          ? '✓ No issues — data quality is good!'
          : `${totalIssues} items need attention`
      }
      actions={
        <input
          type="text"
          placeholder="Search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-1.5 bg-[var(--grey-dim)] border border-[var(--grey)] rounded text-sm w-48"
        />
      }
    >
      {/* Summary Grid */}
      <SummaryGrid>
        <MetricCard
          label="Total Issues"
          value={totalIssues}
          severity={totalIssues > 0 ? 'warning' : 'success'}
        />
        <MetricCard
          label="Identity Conflicts"
          value={identityCount}
          severity={identityCount > 0 ? 'warning' : 'success'}
        />
        <MetricCard
          label="Ambiguous Links"
          value={linkCount}
          severity={linkCount > 0 ? 'warning' : 'success'}
        />
        <MetricCard label="Selected" value={selectedIds.size} />
      </SummaryGrid>

      {/* Bulk Actions Bar */}
      {filtered.length > 0 && (
        <div className="flex items-center gap-4 mb-4 p-3 bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)]">
          <label className="flex items-center gap-2 text-sm text-[var(--grey-light)] cursor-pointer">
            <input
              type="checkbox"
              checked={selectedIds.size === filtered.length && filtered.length > 0}
              onChange={selectAll}
              className="rounded bg-[var(--grey)] border-[var(--grey-light)]"
            />
            Select All ({filtered.length})
          </label>
          {selectedIds.size > 0 && (
            <>
              <span className="text-[var(--grey)]">|</span>
              <span className="text-sm text-[var(--grey-light)]">{selectedIds.size} selected</span>
              <button
                onClick={handleBulkResolveClick}
                disabled={isBulkResolving}
                className="ml-auto px-4 py-1.5 bg-blue-600 hover:bg-[var(--info)] disabled:bg-[var(--grey)] disabled:cursor-not-allowed text-[var(--white)] text-sm rounded"
              >
                {isBulkResolving ? 'Resolving...' : `Resolve ${selectedIds.size} Items`}
              </button>
            </>
          )}
        </div>
      )}

      {resolveError && (
        <div className="mb-4 p-3 bg-red-900/20 border border-[var(--danger)]/50 rounded text-[var(--danger)] text-sm">
          {resolveError}
          <button
            onClick={() => setResolveError(null)}
            className="ml-2 text-[var(--danger)] hover:text-red-200"
          >
            ×
          </button>
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)] p-8 text-center">
          <p className="text-[var(--grey-light)]">No data issues to fix</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((item) => (
            <div key={item.id} className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={selectedIds.has(item.id)}
                onChange={() => toggleSelect(item.id)}
                className="mt-4 rounded bg-[var(--grey)] border-[var(--grey-light)]"
              />
              <div className="flex-1">
                <FixDataCard
                  type={item.issue_type}
                  item={item}
                  onResolve={() => handleResolve(item.id, item.issue_type)}
                  isResolving={resolvingId === item.id}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Confirmation Dialog */}
      {confirmDialog.show && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setConfirmDialog({ show: false })}
          />
          <div className="relative bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
            <h3 className="text-lg font-medium text-[var(--white)] mb-2">Confirm Resolution</h3>
            <p className="text-[var(--grey-light)] mb-4">
              {confirmDialog.bulk
                ? `Are you sure you want to resolve ${selectedIds.size} selected item${selectedIds.size !== 1 ? 's' : ''}? This action cannot be undone.`
                : 'Are you sure you want to resolve this item? This action cannot be undone.'}
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmDialog({ show: false })}
                className="px-4 py-2 bg-[var(--grey)] hover:bg-[var(--grey-light)] text-[var(--white)] text-sm rounded"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (confirmDialog.bulk) {
                    handleBulkResolve();
                  } else if (confirmDialog.itemId && confirmDialog.itemType) {
                    handleResolveConfirmed(confirmDialog.itemId, confirmDialog.itemType);
                  }
                }}
                className="px-4 py-2 bg-blue-600 hover:bg-[var(--info)] text-[var(--white)] text-sm rounded"
              >
                {confirmDialog.bulk ? `Resolve ${selectedIds.size} Items` : 'Resolve'}
              </button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  );
}

export default FixData;
