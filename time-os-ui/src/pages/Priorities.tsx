// Priorities page — Priority workspace with filters, grouping, bulk actions
import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { SkeletonCardList, ErrorState, NoResults } from '../components';
import ExportButton from '../components/ExportButton';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { PriorityFilters } from '../components/priorities/PriorityFilters';
import { GroupedPriorityView } from '../components/priorities/GroupedPriorityView';
import { BulkActionBar } from '../components/priorities/BulkActionBar';
import { SavedFilterSelector } from '../components/priorities/SavedFilterSelector';
import { usePrioritiesFiltered, useSavedFilters, usePrioritiesGrouped } from '../lib/hooks';
import {
  bulkPriorityAction,
  completePriority,
  snoozePriority,
  archiveStalePriorities,
} from '../lib/api';
import type { PriorityFilteredParams, PriorityItem } from '../lib/api';

type ViewTab = 'list' | 'grouped';

const VIEW_TABS: TabDef<ViewTab>[] = [
  { id: 'list', label: 'List View' },
  { id: 'grouped', label: 'Grouped' },
];

export default function Priorities() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<PriorityFilteredParams>({});
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);
  const [groupBy, setGroupBy] = useState<string>('project');

  // Fetch data
  const {
    data: priorityData,
    loading: priorityLoading,
    error: priorityError,
    refetch: refetchPriorities,
  } = usePrioritiesFiltered(filters);

  const { data: savedFilterData } = useSavedFilters();
  const { data: groupedData } = usePrioritiesGrouped(groupBy, 100);

  const items = useMemo(() => priorityData?.items ?? [], [priorityData]);
  const savedFilters = useMemo(() => savedFilterData?.filters ?? [], [savedFilterData]);

  // Derive metrics
  const totalCount = priorityData?.total || 0;
  const overdueCount = useMemo(
    () =>
      items.filter((item) => {
        if (!item.due) return false;
        return new Date(item.due) < new Date();
      }).length,
    [items]
  );
  const highPriorityCount = useMemo(() => items.filter((item) => item.score >= 60).length, [items]);
  const avgScore = useMemo(() => {
    if (items.length === 0) return 0;
    return Math.round(items.reduce((sum, item) => sum + item.score, 0) / items.length);
  }, [items]);

  // Selection handlers
  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelectedIds(new Set(items.map((i) => i.id)));
  }, [items]);

  // Bulk action handlers
  const handleBulkComplete = useCallback(async () => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      await bulkPriorityAction({ action: 'complete', ids: Array.from(selectedIds) });
      setSelectedIds(new Set());
      refetchPriorities();
    } finally {
      setBulkLoading(false);
    }
  }, [selectedIds, refetchPriorities]);

  const handleBulkSnooze = useCallback(
    async (days: number) => {
      if (selectedIds.size === 0) return;
      setBulkLoading(true);
      try {
        await bulkPriorityAction({
          action: 'snooze',
          ids: Array.from(selectedIds),
          snooze_days: days,
        });
        setSelectedIds(new Set());
        refetchPriorities();
      } finally {
        setBulkLoading(false);
      }
    },
    [selectedIds, refetchPriorities]
  );

  const handleBulkArchive = useCallback(async () => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      await bulkPriorityAction({ action: 'archive', ids: Array.from(selectedIds) });
      setSelectedIds(new Set());
      refetchPriorities();
    } finally {
      setBulkLoading(false);
    }
  }, [selectedIds, refetchPriorities]);

  // Single item actions
  const handleItemClick = useCallback(
    (item: PriorityItem) => {
      navigate({ to: '/tasks/$taskId', params: { taskId: item.id } });
    },
    [navigate]
  );

  const handleComplete = useCallback(
    async (itemId: string) => {
      await completePriority(itemId);
      refetchPriorities();
    },
    [refetchPriorities]
  );

  const handleSnooze = useCallback(
    async (itemId: string, days: number) => {
      await snoozePriority(itemId, days);
      refetchPriorities();
    },
    [refetchPriorities]
  );

  const handleArchiveStale = useCallback(async () => {
    setBulkLoading(true);
    try {
      await archiveStalePriorities(14);
      refetchPriorities();
    } finally {
      setBulkLoading(false);
    }
  }, [refetchPriorities]);

  const handleFilterChange = useCallback((newFilters: PriorityFilteredParams) => {
    setFilters(newFilters);
    setSelectedIds(new Set());
  }, []);

  // Build groups from grouped data for GroupedPriorityView
  const groupedItems: Record<string, PriorityItem[]> = useMemo(() => {
    if (!groupedData) return {};
    // groupedData comes as Record<string, unknown> from the server
    // The server returns { groups: { groupName: [items] } } or similar
    const raw = groupedData as Record<string, unknown>;
    const groups = (raw.groups || raw) as Record<string, unknown>;
    const result: Record<string, PriorityItem[]> = {};
    for (const [key, val] of Object.entries(groups)) {
      if (Array.isArray(val)) {
        result[key] = val as PriorityItem[];
      }
    }
    return result;
  }, [groupedData]);

  if (priorityLoading) return <SkeletonCardList count={6} />;
  if (priorityError) {
    return <ErrorState error={priorityError} onRetry={refetchPriorities} hasData={false} />;
  }

  return (
    <PageLayout
      title="Priorities"
      subtitle={`${totalCount} priority items`}
      actions={
        <div className="flex items-center gap-2">
          <SavedFilterSelector
            savedFilters={savedFilters}
            onApply={handleFilterChange}
            loading={priorityLoading}
          />
          <button
            onClick={handleArchiveStale}
            disabled={bulkLoading}
            className="px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--grey-light)] hover:text-[var(--white)] transition-colors disabled:opacity-50"
            title="Archive items stale for 14+ days"
          >
            Archive stale
          </button>
          <ExportButton
            data={items}
            filename="priorities"
            columns={['id', 'title', 'score', 'status', 'due', 'client_name', 'project_name']}
          />
        </div>
      }
    >
      {/* Metrics */}
      <SummaryGrid>
        <MetricCard label="Total Items" value={totalCount} />
        <MetricCard
          label="Overdue"
          value={overdueCount}
          severity={overdueCount > 0 ? 'danger' : 'success'}
        />
        <MetricCard
          label="High Priority"
          value={highPriorityCount}
          severity={highPriorityCount > 0 ? 'warning' : undefined}
        />
        <MetricCard label="Avg Score" value={avgScore} />
      </SummaryGrid>

      {/* Filters */}
      <PriorityFilters filters={filters} onFilterChange={handleFilterChange} />

      {/* View tabs */}
      <TabContainer tabs={VIEW_TABS} defaultTab="list">
        {(activeTab) => {
          if (activeTab === 'grouped') {
            return (
              <div className="space-y-4">
                {/* Group by selector */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[var(--grey-light)]">Group by:</span>
                  {['project', 'assignee', 'source'].map((option) => (
                    <button
                      key={option}
                      onClick={() => setGroupBy(option)}
                      className={`px-2 py-1 text-xs rounded transition-colors ${
                        groupBy === option
                          ? 'bg-[var(--accent)] text-[var(--white)]'
                          : 'bg-[var(--grey)] text-[var(--grey-light)] hover:text-[var(--white)]'
                      }`}
                    >
                      {option.charAt(0).toUpperCase() + option.slice(1)}
                    </button>
                  ))}
                </div>

                <GroupedPriorityView
                  groups={groupedItems}
                  groupBy={groupBy}
                  selectedIds={selectedIds}
                  onToggleSelect={handleToggleSelect}
                  onItemClick={handleItemClick}
                />
              </div>
            );
          }

          // List view
          if (items.length === 0) {
            return <NoResults />;
          }

          return (
            <div className="space-y-1">
              {/* Select all bar */}
              <div className="flex items-center gap-3 px-2 py-1.5">
                <input
                  type="checkbox"
                  checked={selectedIds.size === items.length && items.length > 0}
                  onChange={() => {
                    if (selectedIds.size === items.length) {
                      handleClearSelection();
                    } else {
                      handleSelectAll();
                    }
                  }}
                  className="w-4 h-4 rounded border-[var(--grey)] accent-[var(--accent)]"
                  aria-label="Select all items"
                />
                <span className="text-xs text-[var(--grey-light)]">
                  {selectedIds.size > 0
                    ? `${selectedIds.size} of ${items.length} selected`
                    : `${items.length} items`}
                </span>
              </div>

              {/* Priority items */}
              {items.map((item) => (
                <PriorityListItem
                  key={item.id}
                  item={item}
                  selected={selectedIds.has(item.id)}
                  onToggle={() => handleToggleSelect(item.id)}
                  onClick={() => handleItemClick(item)}
                  onComplete={() => handleComplete(item.id)}
                  onSnooze={(days) => handleSnooze(item.id, days)}
                />
              ))}
            </div>
          );
        }}
      </TabContainer>

      {/* Bulk action bar */}
      <BulkActionBar
        selectedCount={selectedIds.size}
        onComplete={handleBulkComplete}
        onSnooze={handleBulkSnooze}
        onArchive={handleBulkArchive}
        onClearSelection={handleClearSelection}
        loading={bulkLoading}
      />
    </PageLayout>
  );
}

// ---- Inline subcomponent: PriorityListItem ----

interface PriorityListItemProps {
  item: PriorityItem;
  selected: boolean;
  onToggle: () => void;
  onClick: () => void;
  onComplete: () => void;
  onSnooze: (days: number) => void;
}

function priorityColor(score: number): string {
  if (score >= 80) return 'var(--danger)';
  if (score >= 60) return 'var(--warning)';
  if (score >= 30) return 'var(--accent)';
  return 'var(--grey-light)';
}

function dueDateText(dateStr: string | null): { text: string; color: string } {
  if (!dateStr) return { text: '', color: 'var(--grey-muted)' };
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return { text: `${Math.abs(diffDays)}d overdue`, color: 'var(--danger)' };
  if (diffDays === 0) return { text: 'Due today', color: 'var(--warning)' };
  if (diffDays === 1) return { text: 'Due tomorrow', color: 'var(--warning)' };
  if (diffDays <= 7) return { text: `Due in ${diffDays}d`, color: 'var(--grey-light)' };
  return {
    text: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    color: 'var(--grey-light)',
  };
}

function PriorityListItem({
  item,
  selected,
  onToggle,
  onClick,
  onComplete,
  onSnooze,
}: PriorityListItemProps) {
  const [showActions, setShowActions] = useState(false);
  const due = dueDateText(item.due);

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded hover:bg-[var(--grey-dim)] transition-colors ${
        selected ? 'bg-[var(--accent)]/5 border border-[var(--accent)]/20' : ''
      }`}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* Checkbox */}
      <input
        type="checkbox"
        checked={selected}
        onChange={onToggle}
        className="w-4 h-4 rounded border-[var(--grey)] accent-[var(--accent)] flex-shrink-0"
        aria-label={`Select ${item.title}`}
      />

      {/* Score badge */}
      <span
        className="text-xs font-medium w-10 text-center flex-shrink-0"
        style={{ color: priorityColor(item.score) }}
      >
        {item.score}
      </span>

      {/* Content */}
      <button
        onClick={onClick}
        className="flex-1 min-w-0 text-left focus:outline-none focus:ring-2 focus:ring-[var(--accent)] rounded"
      >
        <span className="text-sm text-[var(--white)] truncate block">{item.title}</span>
        <div className="flex items-center gap-2 text-xs mt-0.5">
          {item.assignee && <span className="text-[var(--grey-light)]">{item.assignee}</span>}
          {item.project && (
            <span className="text-[var(--grey-muted)] truncate max-w-[120px]">{item.project}</span>
          )}
          {item.reasons.length > 0 && (
            <span className="text-[var(--grey-muted)]">{item.reasons[0]}</span>
          )}
        </div>
      </button>

      {/* Due date */}
      {due.text && (
        <span className="text-xs flex-shrink-0" style={{ color: due.color }}>
          {due.text}
        </span>
      )}

      {/* Quick actions (on hover) */}
      {showActions && (
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onComplete();
            }}
            className="p-1 rounded text-[var(--success)] hover:bg-[var(--success)]/20 transition-colors"
            title="Complete"
            aria-label="Complete this item"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSnooze(1);
            }}
            className="p-1 rounded text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors"
            title="Snooze 1 day"
            aria-label="Snooze 1 day"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
