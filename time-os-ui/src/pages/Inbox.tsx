// Control Room Inbox — Spec §1, §7.10
// Primary page for processing proposals

import { useState, useEffect, useCallback } from 'react';
import type { InboxItem, InboxCounts, InboxResponse, Severity, InboxItemType } from '../types/spec';

// API base for spec endpoints
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';

// Severity colors
const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'bg-red-500 text-white',
  high: 'bg-orange-500 text-white',
  medium: 'bg-yellow-500 text-black',
  low: 'bg-blue-500 text-white',
  info: 'bg-slate-500 text-white',
};

const SEVERITY_RING: Record<Severity, string> = {
  critical: 'ring-red-500/50',
  high: 'ring-orange-500/50',
  medium: 'ring-yellow-500/50',
  low: 'ring-blue-500/50',
  info: 'ring-slate-500/50',
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
      const res = await fetch(`${API_BASE}/inbox/counts`);
      if (!res.ok) throw new Error('Failed to fetch counts');
      const data = await res.json();
      setCounts(data);
    } catch (e) {
      console.error('Failed to fetch counts:', e);
    }
  }, []);

  // Fetch items based on active tab
  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      let url: string;

      if (activeTab === 'recently_actioned') {
        url = `${API_BASE}/inbox/recent?days=7`;
      } else {
        const state = activeTab === 'needs_attention' ? 'proposed' : 'snoozed';
        url = `${API_BASE}/inbox?state=${state}`;
      }

      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to fetch inbox');

      const data: InboxResponse = await res.json();
      setItems(data.items || []);

      // Update counts from response if present
      if (data.counts) {
        setCounts(data.counts);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  // Initial load
  useEffect(() => {
    fetchCounts();
    fetchItems();
  }, [fetchCounts, fetchItems]);

  // Filter and sort items
  const filteredAndSortedItems = useCallback(() => {
    let result = [...items];

    // Apply type filter
    if (typeFilter !== 'all') {
      result = result.filter(item => item.type === typeFilter);
    }

    // Apply severity filter
    if (severityFilter !== 'all') {
      result = result.filter(item =>
        (item.display_severity || item.severity || 'medium') === severityFilter
      );
    }

    // Apply client filter (search)
    if (clientFilter.trim()) {
      const search = clientFilter.toLowerCase();
      result = result.filter(item =>
        item.client?.name?.toLowerCase().includes(search)
      );
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
          return new Date(a.attention_age_start_at).getTime() -
                 new Date(b.attention_age_start_at).getTime();
        }
        case 'age_desc': {
          return new Date(b.attention_age_start_at).getTime() -
                 new Date(a.attention_age_start_at).getTime();
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
  }, [items, typeFilter, severityFilter, clientFilter, sortBy]);

  // Execute action on inbox item
  const executeAction = async (itemId: string, action: string, payload: Record<string, unknown> = {}) => {
    try {
      const res = await fetch(`${API_BASE}/inbox/${itemId}/action?actor=user`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...payload }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || 'Action failed');
      }

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
    <div className="space-y-4">
      {/* Header with counts */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Control Room</h1>
        {counts && (
          <div className="flex gap-4 text-sm">
            <span className="text-slate-400">
              Unprocessed: <span className="text-white font-medium">{counts.unprocessed}</span>
            </span>
            {counts.snoozed_returning_soon > 0 && (
              <span className="text-yellow-400">
                ⏰ {counts.snoozed_returning_soon} returning soon
              </span>
            )}
          </div>
        )}
      </div>

      {/* Severity and Type breakdown (§1.9) */}
      {counts && activeTab === 'needs_attention' && (
        <div className="flex flex-wrap gap-4 text-xs">
          {/* by_severity */}
          {counts.by_severity && (
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Severity:</span>
              {Object.entries(counts.by_severity).map(([sev, count]) => (
                count > 0 && (
                  <button
                    key={sev}
                    onClick={() => setSeverityFilter(severityFilter === sev ? 'all' : sev)}
                    className={`px-1.5 py-0.5 rounded ${
                      severityFilter === sev
                        ? SEVERITY_COLORS[sev as Severity]
                        : 'bg-slate-700 text-slate-300'
                    }`}
                  >
                    {sev}: {count}
                  </button>
                )
              ))}
            </div>
          )}
          {/* by_type */}
          {counts.by_type && (
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Type:</span>
              {Object.entries(counts.by_type).map(([type, count]) => (
                count > 0 && (
                  <button
                    key={type}
                    onClick={() => setTypeFilter(typeFilter === type ? 'all' : type)}
                    className={`px-1.5 py-0.5 rounded ${
                      typeFilter === type
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-700 text-slate-300'
                    }`}
                  >
                    {TYPE_ICONS[type as InboxItemType]} {count}
                  </button>
                )
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center justify-between border-b border-slate-700">
        <div className="flex gap-1">
          {TABS.map((tab) => {
            const count = counts?.[tab.countKey] ?? 0;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  px-4 py-2 text-sm font-medium rounded-t-lg transition-colors
                  ${isActive
                    ? 'bg-slate-700 text-white border-b-2 border-blue-500'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  }
                `}
              >
                {tab.label}
                <span className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
                  isActive ? 'bg-blue-500' : 'bg-slate-600'
                }`}>
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
            className={`px-2 py-1 text-sm rounded ${
              showFilters ? 'bg-blue-600' : 'bg-slate-700'
            }`}
          >
            🔍 Filters
          </button>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="bg-slate-700 border-none rounded px-2 py-1 text-sm"
          >
            {SORT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Filters panel */}
      {showFilters && (
        <div className="flex flex-wrap gap-3 p-3 bg-slate-800 rounded-lg">
          {/* Type filter */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-400">Type:</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-slate-700 border-none rounded px-2 py-1 text-sm"
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
            <label className="text-sm text-slate-400">Severity:</label>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-slate-700 border-none rounded px-2 py-1 text-sm"
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
            <label className="text-sm text-slate-400">Client:</label>
            <input
              type="text"
              value={clientFilter}
              onChange={(e) => setClientFilter(e.target.value)}
              placeholder="Search client..."
              className="bg-slate-700 border-none rounded px-2 py-1 text-sm w-40"
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
              className="text-sm text-blue-400 hover:text-blue-300"
            >
              Clear all
            </button>
          )}
        </div>
      )}

      {/* Content */}
      <div className="min-h-[400px]">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-pulse text-slate-400">Loading...</div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-red-400">{error}</div>
          </div>
        ) : displayItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <span className="text-4xl mb-2">✨</span>
            <span>
              {items.length === 0
                ? 'Nothing here'
                : 'No items match filters'}
            </span>
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
    </div>
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
        bg-slate-800 hover:bg-slate-750
        ${isUnread ? 'border-l-4 border-blue-500' : 'border-l-4 border-transparent'}
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
            <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${SEVERITY_COLORS[severity]}`}>
              {severity}
            </span>
            {item.client && (
              <span className="text-sm text-slate-400 truncate">
                {item.client.name}
              </span>
            )}
            <span className="text-xs text-slate-500">
              {formatAge(item.attention_age_start_at)}
            </span>
          </div>

          {/* Title */}
          <h3 className="font-medium text-white truncate">{item.title}</h3>

          {/* Issue-specific info */}
          {item.type === 'issue' && item.issue_state && (
            <div className="mt-1 text-xs text-slate-400">
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
              className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-white"
              title="Snooze 7 days"
            >
              ⏰
            </button>
          )}
          {item.available_actions.includes('dismiss') && (
            <button
              onClick={() => onAction('dismiss')}
              className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-white"
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
      <div className="relative w-full max-w-lg bg-slate-800 h-full overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-slate-800 border-b border-slate-700 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">{TYPE_ICONS[item.type]}</span>
              <span className={`px-2 py-0.5 rounded text-sm font-medium ${SEVERITY_COLORS[severity]}`}>
                {severity}
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded hover:bg-slate-700 text-slate-400"
            >
              ✕
            </button>
          </div>
          <h2 className="mt-2 text-lg font-semibold text-white">{item.title}</h2>
          {item.client && (
            <div className="mt-1 text-sm text-slate-400">
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
              <span className="text-slate-400">Age:</span>
              <span className="ml-2 text-white">{formatAge(item.attention_age_start_at)}</span>
            </div>
            <div>
              <span className="text-slate-400">State:</span>
              <span className="ml-2 text-white">{item.state}</span>
            </div>
            {item.type === 'issue' && (
              <>
                <div>
                  <span className="text-slate-400">Category:</span>
                  <span className="ml-2 text-white">{item.issue_category || 'N/A'}</span>
                </div>
                <div>
                  <span className="text-slate-400">Issue State:</span>
                  <span className="ml-2 text-white">{item.issue_state || 'N/A'}</span>
                </div>
              </>
            )}
          </div>

          {/* Evidence */}
          {item.evidence && (
            <div className="p-3 bg-slate-700/50 rounded space-y-2">
              {/* Why flagged */}
              {item.evidence.payload?.flagged_reason && (
                <div className="flex items-center gap-2 text-xs text-amber-400">
                  <span>⚡</span>
                  <span>{item.evidence.payload.flagged_reason}</span>
                </div>
              )}

              {/* Sender */}
              {item.evidence.payload?.sender && (
                <p className="text-xs text-slate-400">From: {item.evidence.payload.sender}</p>
              )}

              {/* Snippet preview - only show if actual body content exists */}
              {item.evidence.payload?.snippet && (
                <div className="text-sm text-slate-300 bg-slate-800/50 p-2 rounded border-l-2 border-slate-600">
                  {item.evidence.payload.snippet}
                </div>
              )}

              {/* Link to source */}
              {item.evidence.url && (
                <a
                  href={item.evidence.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-sm text-blue-400 hover:text-blue-300"
                >
                  Open in Gmail ↗
                </a>
              )}
            </div>
          )}

          {/* Snooze info */}
          {item.state === 'snoozed' && item.snooze_until && (
            <div className="p-3 bg-yellow-500/10 rounded border border-yellow-500/30">
              <div className="flex items-center gap-2">
                <span>⏰</span>
                <span className="text-sm text-yellow-300">
                  Returns {new Date(item.snooze_until).toLocaleDateString()}
                </span>
              </div>
              {item.snooze_reason && (
                <p className="mt-1 text-sm text-slate-300">{item.snooze_reason}</p>
              )}
            </div>
          )}

          {/* Snooze picker */}
          {showSnoozePicker && (
            <div className="p-3 bg-slate-700 rounded">
              <h4 className="text-sm font-medium mb-2">Snooze duration</h4>
              <div className="flex gap-2">
                {[1, 3, 7, 14, 30].map(days => (
                  <button
                    key={days}
                    onClick={() => setSnoozeDays(days)}
                    className={`px-3 py-1 rounded text-sm ${
                      snoozeDays === days ? 'bg-yellow-600' : 'bg-slate-600'
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
                  className="px-3 py-1 bg-yellow-600 rounded text-sm"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setShowSnoozePicker(false)}
                  className="px-3 py-1 bg-slate-600 rounded text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="sticky bottom-0 bg-slate-800 border-t border-slate-700 p-4">
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
  assign: { label: 'Assign', style: 'bg-blue-600 hover:bg-blue-500' },
  snooze: { label: 'Snooze', style: 'bg-yellow-600 hover:bg-yellow-500' },
  dismiss: { label: 'Dismiss', style: 'bg-slate-600 hover:bg-slate-500' },
  link: { label: 'Link to Engagement', style: 'bg-green-600 hover:bg-green-500' },
  create: { label: 'Create Engagement', style: 'bg-green-600 hover:bg-green-500' },
  select: { label: 'Select Match', style: 'bg-blue-600 hover:bg-blue-500' },
  unsnooze: { label: 'Unsnooze', style: 'bg-yellow-600 hover:bg-yellow-500' },
};

function ActionButton({ action, onAction }: ActionButtonProps) {
  const config = ACTION_LABELS[action] || { label: action, style: 'bg-slate-600 hover:bg-slate-500' };

  const handleClick = () => {
    if (action === 'assign') {
      // TODO: Show assignee picker modal
      const assignTo = prompt('Enter user ID to assign to:');
      if (assignTo) {
        onAction(action, { assign_to: assignTo });
      }
    } else {
      onAction(action);
    }
  };

  return (
    <button
      onClick={handleClick}
      className={`px-3 py-1.5 rounded text-sm font-medium text-white ${config.style}`}
    >
      {config.label}
    </button>
  );
}

export default Inbox;
