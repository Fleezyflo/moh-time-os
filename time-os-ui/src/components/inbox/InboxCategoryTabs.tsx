// InboxCategoryTabs — secondary filter tabs for inbox item types
// Shows counts per type from InboxCounts.by_type

import type { InboxItemType, InboxCounts } from '../../types/spec';

/** Category definitions matching InboxItemType values */
const CATEGORIES: Array<{ id: InboxItemType | 'all'; label: string; icon: string }> = [
  { id: 'all', label: 'All', icon: '📋' },
  { id: 'issue', label: 'Issues', icon: '⚠️' },
  { id: 'flagged_signal', label: 'Flagged Signals', icon: '🚩' },
  { id: 'orphan', label: 'Orphans', icon: '❓' },
  { id: 'ambiguous', label: 'Ambiguous', icon: '🔀' },
];

interface InboxCategoryTabsProps {
  counts: InboxCounts | null;
  activeCategory: InboxItemType | 'all';
  onCategoryChange: (category: InboxItemType | 'all') => void;
}

export function InboxCategoryTabs({
  counts,
  activeCategory,
  onCategoryChange,
}: InboxCategoryTabsProps) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {CATEGORIES.map((cat) => {
        const count =
          cat.id === 'all' ? (counts?.needs_attention ?? 0) : (counts?.by_type?.[cat.id] ?? 0);

        // Hide categories with zero items (except 'all' and active)
        if (count === 0 && cat.id !== 'all' && cat.id !== activeCategory) {
          return null;
        }

        const isActive = activeCategory === cat.id;

        return (
          <button
            key={cat.id}
            onClick={() => onCategoryChange(cat.id)}
            className={`
              inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm
              transition-colors
              ${
                isActive
                  ? 'bg-blue-600 text-[var(--white)]'
                  : 'bg-[var(--grey-dim)] text-[var(--grey-light)] hover:bg-[var(--grey)] hover:text-[var(--white)]'
              }
            `}
          >
            <span>{cat.icon}</span>
            <span>{cat.label}</span>
            <span
              className={`
                px-1.5 py-0.5 rounded-full text-xs font-medium
                ${isActive ? 'bg-blue-500/50' : 'bg-[var(--grey)]'}
              `}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export default InboxCategoryTabs;
