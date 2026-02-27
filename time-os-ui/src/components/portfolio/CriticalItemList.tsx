/**
 * CriticalItemList -- Renders critical items as actionable cards.
 *
 * Used on the Portfolio page to show top-priority items requiring attention.
 * Data comes from useCriticalItems() intelligence hook.
 */

import type { CriticalItem } from '../../intelligence/api';

interface CriticalItemListProps {
  items: CriticalItem[];
  maxItems?: number;
}

export function CriticalItemList({ items, maxItems = 5 }: CriticalItemListProps) {
  const displayed = items.slice(0, maxItems);

  if (displayed.length === 0) {
    return (
      <div className="text-center py-8 text-[var(--grey-light)]">No critical items right now</div>
    );
  }

  return (
    <div className="space-y-3">
      {displayed.map((item, idx) => (
        <div
          key={`${item.entity.id}-${idx}`}
          className="p-4 bg-[var(--grey-dim)] rounded-lg border-l-4 border-red-500/70 hover:bg-[var(--grey)] transition-colors"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <h4 className="font-medium text-[var(--white)] truncate">{item.headline}</h4>
              <div className="mt-1 flex items-center gap-2 text-sm text-[var(--grey-light)]">
                <span className="px-1.5 py-0.5 rounded text-xs bg-[var(--grey)] text-[var(--grey-subtle)]">
                  {item.entity.type}
                </span>
                <span className="truncate">{item.entity.name}</span>
              </div>
              {item.implied_action && (
                <p className="mt-2 text-sm text-[var(--grey-muted)]">{item.implied_action}</p>
              )}
            </div>
            <div className="flex flex-col items-end gap-1 shrink-0">
              <span className="text-lg font-bold text-red-400">
                {Math.round(item.priority_score)}
              </span>
              <span className="text-xs text-[var(--grey-muted)]">priority</span>
              {item.evidence_count > 0 && (
                <span className="text-xs text-[var(--grey-light)]">
                  {item.evidence_count} evidence
                </span>
              )}
            </div>
          </div>
        </div>
      ))}
      {items.length > maxItems && (
        <div className="text-center text-sm text-[var(--grey-muted)]">
          +{items.length - maxItems} more critical items
        </div>
      )}
    </div>
  );
}
