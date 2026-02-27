// Control Room Inbox — Spec §1, §7.10
// Primary page for processing proposals

import { useState, useEffect, useCallback } from 'react';
import type { InboxItem, InboxCounts, Severity, InboxItemType } from '../types/spec';
import { TeamMemberPicker } from '../components/pickers';
import { SkeletonCardList } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { InboxCategoryTabs } from '../components/inbox';
import * as api from '../lib/api';

// Severity colors
const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'bg-[var(--danger)] text-[var(--white)]',
  high: 'bg-orange-500 text-[var(--white)]',
  medium: 'bg-[var(--warning)] text-black',
  low: 'bg-[var(--info)] text-[var(--white)]',
  info: 'bg-[var(--grey-muted)] text-[var(--white)]',
};

const SEVERITY_RING: Record<Severity, string> = {
  critical: 'ring-red-500/50',
  high: 'ring-orange-500/50',
  medium: 'ring-yellow-500/50',
  low: 'ring-blue-500/50',
  info: 'ring-[var(--grey-muted)]/50',
};

// Item type icons
const TYPE_ICONS: Record<InboxItemType, string> = {
  issue: '⚠️',
  flagged_signal: '🚩',
  orphan: '❓',
  ambiguous: '🔀',
};

// Tabs per spec §1.2
type TabId = 'needs_attention' | 'snoozed' | 'recently_actioned';

interface Tab {
  id: TabId;
  label: string;
  countKey: keyof InboxCounts;
}

const TABS: Tab[] = [
  { id: 'needs_attention', label: 'Needs Attention', countKey: 'needs_attention' },
  { id: 'snoozed', label: 'Snoozed', countKey: 'snoozed' },
  { id: 'recently_actioned', label: 'Recently Actioned', countKey: 'recently_actioned' },
];

// Sort options per spec §1.2
type SortOption = 'severity' | 'age' | 'age_desc' | 'client';

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: 'severity', label: 'Severity (highest first)' },
  { value: 'age', label: 'Age (oldest first)' },
  { value: 'age_desc', label: 'Age (newest first)' },
  { value: 'client', label: 'Client (A-Z)' },
];

// Severity order for sorting
const SEVERITY_ORDER: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
};

export function Inbox() {
  const [activeTab, setActiveTab] = useState<TabId>('needs_attention');
  const [items, setItems] = useState<InboxItem[]>([]);
  const [counts, setCounts] = useState<InboxCounts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<InboxItem | null>(null);

  // Category filter (InboxCategoryTabs)
  const [activeCategory, setActiveCategory] = useState<InboxItemType | 'all'>('all');

  // Filters (§1.2)
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [clientFilter, setClientFilter] = useState<string>('');

  // Sort (§1.2)
  const [sortBy, setSortBy] = useState<SortOption>('severity');

  // Show/hide filters panel
  const [showFilters, setShowFilters] = useState(false);

  // Fetch counts (separate, cacheable)
  const fetchCounts = useCallback(async () => {
    try {
      const data = await api.fetchInboxCounts();
      setCounts(data);
    } catch (e) {
      console.error('Failed to fetch counts:', e);
    }
  }, []);

  // Fetch items based on active tab and category filter
  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const typeParam = activeCategory !== 'all' ? activeCategory : undefined;

      if (activeTab === 'recently_actioned') {
        const data = await api.fetchInboxRecent(7, typeParam);
        setItems(data.items || []);
        if (data.counts) setCounts(data.counts);
      } else {
        const state = activeTab === 'needs_attention' ? 'proposed' : 'snoozed';
        const data = await api.fetchInbox({ state, type: typeParam });
        setItems(data.items || []);
        if (data.counts) setCounts(data.counts);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [activeTab, activeCategory]);

  // Initial load
  useEffect(() => {
    fetchCounts();
    fetchItems();
  }, [fetchCounts, fetchItems]);

  // Filter and sort items
  const filteredAndSortedItems = useCallback(() => {
    let result = [...items];

    // Apply type filter (only if category is 'all', since category already filters server-side)
    if (activeCategory === 'all' && typeFilter !== 'all') {
      result = result.filter((item) => item.type === typeFilter);
    }

    // Apply severity filter
    if (severityFilter !== 'all') {
      result = result.filter(
        (item) => (item.display_severity || item.severity || 'medium') === severityFilter
      );
    }

    // Apply client filter (search)
    if (clientFilter.trim()) {
      const search = clientFilter.toLowerCase();
      result = result.filter((item) => item.client?.name?.toLowerCase().includes(search));
    }

    // Apply sort
    result.sort((a, b) => {
      switch (sortBy) {
        case 'severity': {
          const sevA = SEVERITY_ORDER[a.display_severity || a.severity || 'medium'] ?? 3;
          const sevB = SEVERITY_ORDER[b.display_severity || b.severity || 'medium'] ?? 3;
          return sevA - sevB;
        }
        case 'age': {
          return (
            new Date(a.attention_age_start_at).getTime() -
            new Date(b.attention_age_start_at).getTime()
          );
        }
        case 'age_desc': {
          return (
            new Date(b.attention_age_start_at).getTime() -
            new Date(a.attention_age_start_at).getTime()
          );
        }
        case 'client': {
          const nameA = a.client?.name || '';
          const nameB = b.client?.name || '';
          return nameA.localeCompare(nameB);
        }
        default:
          return 0;
      }
    });

    return result;
  }, [items, activeCategory, typeFilter, severityFilter, clientFilter, sortBy]);

  // Execute action on inbox item
  const executeAction = async (
    itemId: string,
    action: string,
    payload: Record<string, unknown> = {}
  ) => {
    try {
      await api.executeInboxAction(itemId, action, payload, 'user');

      // Refresh data
      fetchCounts();
      fetchItems();
      setSelectedItem(null);
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Action failed');
    }
  };

  // Format relative time
  const formatAge = (isoDate: string): string => {
    const diff = Date.now() - new Date(isoDate).getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor(diff / (1000 * 60));

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'just now';
  };

  const displayItems = filteredAndSortedItems();

  return (
    <PageLayout
      title="Control Room"
      actions={
        counts && counts.snoozed_returning_soon > 0 ? (
          <span className="text-sm text-[var(--warning)]">
            ⏰ {counts.snoozed_returning_soon} returning soon
          </span>
        ) : undefined
      }
    >
      {/* Summary metrics */}
      {counts && (
        <SummaryGrid>
          <MetricCard
            label="Unprocessed"
            value={counts.unprocessed}
            severity={counts.unprocessed > 0 ? 'warning' : undefined}
          />
          <MetricCard
            label="Critical"
            value={counts.by_severity?.critical ?? 0}
            severity={(counts.by_severity?.critical ?? 0) > 0 ? 'danger' : undefined}
          />
          <MetricCard
            label="High"
            value={counts.by_severity?.high ?? 0}
            severity={(counts.by_severity?.high ?? 0) > 0 ? 'warning' : undefined}
          />
          <MetricCard
            label="Categories"
            value={counts.by_type ? Object.values(counts.by_type).filter((c) => c > 0).length : 0}
          />
        </SummaryGrid>
      )}

      {/* Category filter tabs */}
      {activeTab !== 'recently_actioned' && (
        <InboxCategoryTabs
          counts={counts}
          activeCategory={activeCategory}
          onCategoryChange={(cat) => {
            setActiveCategory(cat);
            // Reset type filter when category changes (category is the primary type filter)
            setTypeFilter('all');
          }}
        />
      )}

      {/* Severity and Type breakdown (§1.9) */}
      {counts && activeTab === 'needs_attention' && (
        <div className="flex flex-wrap gap-4 text-xs">
          {/* by_severity */}
          {counts.by_severity && (
            <div className="flex items-center gap-2">
              <span className="text-[var(--grey-light)]">Severity:</span>
              {Object.entries(counts.by_severity).map(
                ([sev, count]) =>
                  count > 0 && (
                    <button
                      key={sev}
                      onClick={() => setSeverityFilter(severityFilter === sev ? 'all' : sev)}
                      className={`px-1.5 py-0.5 rounded ${
                        severityFilter === sev
                          ? SEVERITY_COLORS[sev as Severity]
                          : 'bg-[var(--grey)] text-[var(--grey-light)]'
                      }`}
                    >
                      {sev}: {count}
                    </button>
                  )
              )}
            </div>
          )}
          {/* by_type */}
          {counts.by_type && (
            <div className="flex items-center gap-2">
              <span className="text-[var(--grey-light)]">Type:</span>
              {Object.entries(counts.by_type).map(
                ([type, count]) =>
                  count > 0 && (
                    <button
                      key={type}
                      onClick={() => setTypeFilter(typeFilter === type ? 'all' : type)}
                      className={`px-1.5 py-0.5 rounded ${
                        typeFilter === type
                          ? 'bg-blue-600 text-[var(--white)]'
                          : 'bg-[var(--grey)] text-[var(--grey-light)]'
                      }`}
                    >
                      {TYPE_ICONS[type as InboxItemType]} {count}
                    </button>
                  )
              )}
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center justify-between border-b border-[var(--grey)]">
        <div className="flex gap-1">
          {TABS.map((tab) => {
            const countValue = counts?.[tab.countKey];
            const count = typeof countValue === 'number' ? countValue : 0;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  px-4 py-2 text-sm font-medium rounded-t-lg transition-colors
                  ${
                    isActive
                      ? 'bg-[var(--grey)] text-[var(--white)] border-b-2 border-blue-500'
                      : 'text-[var(--grey-light)] hover:text-[var(--white)] hover:bg-[var(--grey-dim)]'
                  }
                `}
              >
                {tab.label}
                <span
                  className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
                    isActive ? 'bg-[var(--info)]' : 'bg-[var(--grey-light)]'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Filter/Sort controls */}
        <div className="flex items-center gap-2 pb-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`px-2 py-1 text-sm rounded ${showFilters ? 'bg-blue-600' : 'bg-[var(--grey)]'}`}
          >
            🔍 Filters
          </button>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="bg-[var(--grey)] border-none rounded px-2 py-1 text-sm"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Filters panel */}
      {showFilters && (
        <div className="flex flex-wrap gap-3 p-3 bg-[var(--grey-dim)] rounded-lg">
          {/* Type filter */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--grey-light)]">Type:</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-[var(--grey)] border-none rounded px-2 py-1 text-sm"
            >
              <option value="all">All</option>
              <option value="issue">⚠️ Issue</option>
              <option value="flagged_signal">🚩 Flagged Signal</option>
              <option value="orphan">❓ Orphan</option>
              <option value="ambiguous">🔀 Ambiguous</option>
            </select>
          </div>

          {/* Severity filter */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--grey-light)]">Severity:</label>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-[var(--grey)] border-none rounded px-2 py-1 text-sm"
            >
              <option value="all">All</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="info">Info</option>
            </select>
          </div>

          {/* Client search */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--grey-light)]">Client:</label>
            <input
              type="text"
              value={clientFilter}
              onChange={(e) => setClientFilter(e.target.value)}
              placeholder="Search client..."
              className="bg-[var(--grey)] border-none rounded px-2 py-1 text-sm w-40"
            />
          </div>

          {/* Clear filters */}
          {(typeFilter !== 'all' || severityFilter !== 'all' || clientFilter) && (
            <button
              onClick={() => {
                setTypeFilter('all');
                setSeverityFilter('all');
                setClientFilter('');
              }}
              className="text-sm text-[var(--info)] hover:text-[var(--info)]"
            >
              Clear all
            </button>
          )}
        </div>
      )}

      {/* Content */}
      <div className="min-h-[400px]">
        {loading ? (
          <SkeletonCardList count={5} />
        ) : error ? (
          <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-8 text-center">
            <div className="text-red-400 text-2xl mb-2">⚠️</div>
            <div className="text-red-300 text-lg font-medium mb-2">Failed to load inbox</div>
            <p className="text-[var(--grey-light)] text-sm">{error}</p>
          </div>
        ) : displayItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-[var(--grey-light)]">
            <span className="text-4xl mb-2">✨</span>
            <span>{items.length === 0 ? 'Nothing here' : 'No items match filters'}</span>
          </div>
        ) : (
          <div className="space-y-2">
            {displayItems.map((item) => (
              <InboxCard
                key={item.id}
                item={item}
                onSelect={() => setSelectedItem(item)}
                onAction={(action, payload) => executeAction(item.id, action, payload)}
                formatAge={formatAge}
              />
            ))}
          </div>
        )}
      </div>

      {/* Detail drawer */}
      {selectedItem && (
        <InboxDrawer
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
          onAction={(action, payload) => executeAction(selectedItem.id, action, payload)}
          formatAge={formatAge}
        />
      )}
    </PageLayout>
  );
}

// ==== Inbox Card Component ====

interface InboxCardProps {
  item: InboxItem;
  onSelect: () => void;
  onAction: (action: string, payload?: Record<string, unknown>) => void;
  formatAge: (iso: string) => string;
}

function InboxCard({ item, onSelect, onAction, formatAge }: InboxCardProps) {
  const severity = item.display_severity || item.severity || 'medium';
  const isUnread = !item.read_at || (item.resurfaced_at && item.read_at < item.resurfaced_at);

  return (
    <div
      onClick={onSelect}
      className={`
        p-4 rounded-lg cursor-pointer transition-all
        bg-[var(--grey-dim)] hover:bg-[var(--grey)]
        ${isUnread ? 'border-l-4 border-[var(--info)]' : 'border-l-4 border-transparent'}
        ring-1 ${SEVERITY_RING[severity]}
      `}
    >
      <div className="flex items-start gap-3">
        {/* Type icon */}
        <span className="text-xl" title={item.type}>
          {TYPE_ICONS[item.type]}
        </span>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`px-1.5 py-0.5 rounded text-xs font-medium ${SEVERITY_COLORS[severity]}`}
            >
              {severity}
            </span>
            {item.client && (
              <span className="text-sm text-[var(--grey-light)] truncate">{item.client.name}</span>
            )}
            <span className="text-xs text-[var(--grey)]">
              {formatAge(item.attention_age_start_at)}
            </span>
          </div>

          {/* Title */}
          <h3 className="font-medium text-[var(--white)] truncate">{item.title}</h3>

          {/* Issue-specific info */}
          {item.type === 'issue' && item.issue_state && (
            <div className="mt-1 text-xs text-[var(--grey-light)]">
              {item.issue_category} · {item.issue_state}
              {item.issue_assignee && ` · Assigned to ${item.issue_assignee.name}`}
            </div>
          )}
        </div>

        {/* Quick actions */}
        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
          {item.available_actions.includes('snooze') && (
            <button
              onClick={() => onAction('snooze', { snooze_days: 7 })}
              className="p-1.5 rounded hover:bg-[var(--grey)] text-[var(--grey-light)] hover:text-[var(--white)]"
              title="Snooze 7 days"
            >
              ⏰
            </button>
          )}
          {item.available_actions.includes('dismiss') && (
            <button
              onClick={() => onAction('dismiss')}
              className="p-1.5 rounded hover:bg-[var(--grey)] text-[var(--grey-light)] hover:text-[var(--white)]"
              title="Dismiss"
            >
              ✕
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ==== Inbox Drawer Component ====

interface InboxDrawerProps {
  item: InboxItem;
  onClose: () => void;
  onAction: (action: string, payload?: Record<string, unknown>) => void;
  formatAge: (iso: string) => string;
}

function InboxDrawer({ item, onClose, onAction, formatAge }: InboxDrawerProps) {
  const severity = item.display_severity || item.severity || 'medium';
  const [snoozeDays, setSnoozeDays] = useState(7);
  const [showSnoozePicker, setShowSnoozePicker] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Drawer */}
      <div className="relative w-full max-w-lg bg-[var(--grey-dim)] h-full overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-[var(--grey-dim)] border-b border-[var(--grey)] p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">{TYPE_ICONS[item.type]}</span>
              <span
                className={`px-2 py-0.5 rounded text-sm font-medium ${SEVERITY_COLORS[severity]}`}
              >
                {severity}
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded hover:bg-[var(--grey)] text-[var(--grey-light)]"
            >
              ✕
            </button>
          </div>
          <h2 className="mt-2 text-lg font-semibold text-[var(--white)]">{item.title}</h2>
          {item.client && (
            <div className="mt-1 text-sm text-[var(--grey-light)]">
              {item.client.name}
              {item.brand && ` · ${item.brand.name}`}
              {item.engagement && ` · ${item.engagement.name}`}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Meta */}
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-[var(--grey-light)]">Age:</span>
              <span className="ml-2 text-[var(--white)]">
                {formatAge(item.attention_age_start_at)}
              </span>
            </div>
            <div>
              <span className="text-[var(--grey-light)]">State:</span>
              <span className="ml-2 text-[var(--white)]">{item.state}</span>
            </div>
            {item.type === 'issue' && (
              <>
                <div>
                  <span className="text-[var(--grey-light)]">Category:</span>
                  <span className="ml-2 text-[var(--white)]">{item.issue_category || 'N/A'}</span>
                </div>
                <div>
                  <span className="text-[var(--grey-light)]">Issue State:</span>
                  <span className="ml-2 text-[var(--white)]">{item.issue_state || 'N/A'}</span>
                </div>
              </>
            )}
          </div>

          {/* Evidence */}
          {item.evidence && (
            <div className="p-3 bg-[var(--grey)]/50 rounded space-y-2">
              {/* Why flagged */}
              {(item.evidence.payload as { flagged_reason?: string })?.flagged_reason && (
                <div className="flex items-center gap-2 text-xs text-amber-400">
                  <span>⚡</span>
                  <span>
                    {String((item.evidence.payload as { flagged_reason?: string }).flagged_reason)}
                  </span>
                </div>
              )}

              {/* Sender */}
              {(item.evidence.payload as { sender?: string })?.sender && (
                <p className="text-xs text-[var(--grey-light)]">
                  From: {String((item.evidence.payload as { sender?: string }).sender)}
                </p>
              )}

              {/* Snippet preview - only show if actual body content exists */}
              {(item.evidence.payload as { snippet?: string })?.snippet && (
                <div className="text-sm text-[var(--grey-light)] bg-[var(--grey-dim)]/50 p-2 rounded border-l-2 border-[var(--grey-light)]">
                  {String((item.evidence.payload as { snippet?: string }).snippet)}
                </div>
              )}

              {/* Link to source */}
              {item.evidence.url && (
                <a
                  href={item.evidence.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-sm text-[var(--info)] hover:text-[var(--info)]"
                >
                  Open in Gmail ↗
                </a>
              )}
            </div>
          )}

          {/* Snooze info */}
          {item.state === 'snoozed' && item.snooze_until && (
            <div className="p-3 bg-[var(--warning)]/10 rounded border border-yellow-500/30">
              <div className="flex items-center gap-2">
                <span>⏰</span>
                <span className="text-sm text-[var(--warning)]">
                  Returns {new Date(item.snooze_until).toLocaleDateString()}
                </span>
              </div>
              {item.snooze_reason && (
                <p className="mt-1 text-sm text-[var(--grey-light)]">{item.snooze_reason}</p>
              )}
            </div>
          )}

          {/* Snooze picker */}
          {showSnoozePicker && (
            <div className="p-3 bg-[var(--grey)] rounded">
              <h4 className="text-sm font-medium mb-2">Snooze duration</h4>
              <div className="flex gap-2">
                {[1, 3, 7, 14, 30].map((days) => (
                  <button
                    key={days}
                    onClick={() => setSnoozeDays(days)}
                    className={`px-3 py-1 rounded text-sm ${
                      snoozeDays === days ? 'bg-[var(--warning)]' : 'bg-[var(--grey-light)]'
                    }`}
                  >
                    {days}d
                  </button>
                ))}
              </div>
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => {
                    onAction('snooze', { snooze_days: snoozeDays });
                    setShowSnoozePicker(false);
                  }}
                  className="px-3 py-1 bg-[var(--warning)] rounded text-sm"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setShowSnoozePicker(false)}
                  className="px-3 py-1 bg-[var(--grey-light)] rounded text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="sticky bottom-0 bg-[var(--grey-dim)] border-t border-[var(--grey)] p-4">
          <div className="flex flex-wrap gap-2">
            {item.available_actions.map((action) => (
              <ActionButton
                key={action}
                action={action}
                onAction={(act, payload) => {
                  if (act === 'snooze') {
                    setShowSnoozePicker(true);
                  } else {
                    onAction(act, payload);
                  }
                }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ==== Action Button Component ====

interface ActionButtonProps {
  action: string;
  onAction: (action: string, payload?: Record<string, unknown>) => void;
}

const ACTION_LABELS: Record<string, { label: string; style: string }> = {
  tag: { label: 'Tag & Watch', style: 'bg-purple-600 hover:bg-purple-500' },
  assign: { label: 'Assign', style: 'bg-blue-600 hover:bg-[var(--info)]' },
  snooze: { label: 'Snooze', style: 'bg-[var(--warning)] hover:bg-[var(--warning)]' },
  dismiss: { label: 'Dismiss', style: 'bg-[var(--grey-light)] hover:bg-[var(--grey-muted)]' },
  link: { label: 'Link to Engagement', style: 'bg-[var(--success)] hover:bg-[var(--success)]' },
  create: { label: 'Create Engagement', style: 'bg-[var(--success)] hover:bg-[var(--success)]' },
  select: { label: 'Select Match', style: 'bg-blue-600 hover:bg-[var(--info)]' },
  unsnooze: { label: 'Unsnooze', style: 'bg-[var(--warning)] hover:bg-[var(--warning)]' },
};

function ActionButton({ action, onAction }: ActionButtonProps) {
  const config = ACTION_LABELS[action] || {
    label: action,
    style: 'bg-[var(--grey-light)] hover:bg-[var(--grey-muted)]',
  };
  const [showPicker, setShowPicker] = useState(false);

  const handleClick = () => {
    if (action === 'assign') {
      setShowPicker(true);
    } else {
      onAction(action);
    }
  };

  if (action === 'assign' && showPicker) {
    return (
      <div className="w-full">
        <div className="mb-2 text-sm text-[var(--white)]">Select assignee:</div>
        <TeamMemberPicker
          onSelect={(memberId) => {
            onAction(action, { assign_to: memberId });
            setShowPicker(false);
          }}
          placeholder="Search team member..."
        />
        <button
          onClick={() => setShowPicker(false)}
          className="mt-2 px-3 py-1 text-sm rounded bg-[var(--grey-light)] hover:bg-[var(--grey-muted)] text-[var(--white)]"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={handleClick}
      className={`px-3 py-1.5 rounded text-sm font-medium text-[var(--white)] ${config.style}`}
    >
      {config.label}
    </button>
  );
}

export default Inbox;
