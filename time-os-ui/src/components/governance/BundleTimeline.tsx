// Bundle audit trail — recent bundles with rollback option
import { useCallback, useState } from 'react';
import type { Bundle } from '../../lib/api';
import { rollbackBundle } from '../../lib/api';

interface Props {
  bundles: Bundle[];
  rollbackable: Bundle[];
  onRefresh: () => void;
}

export function BundleTimeline({ bundles, rollbackable, onRefresh }: Props) {
  const [rolling, setRolling] = useState<string | null>(null);

  const rollbackIds = new Set(rollbackable.map((b) => b.bundle_id));

  const handleRollback = useCallback(
    async (bundleId: string) => {
      setRolling(bundleId);
      try {
        await rollbackBundle(bundleId);
        onRefresh();
      } finally {
        setRolling(null);
      }
    },
    [onRefresh]
  );

  if (bundles.length === 0) {
    return <div className="text-sm text-[var(--grey-light)]">No bundles recorded.</div>;
  }

  return (
    <div className="space-y-2">
      {bundles.map((b) => (
        <div
          key={b.bundle_id}
          className="flex items-center justify-between bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg px-4 py-3"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  b.status === 'applied'
                    ? 'bg-green-500'
                    : b.status === 'rolled_back'
                      ? 'bg-amber-500'
                      : 'bg-[var(--grey-muted)]'
                }`}
              />
              <span className="text-sm font-medium truncate">{b.description}</span>
            </div>
            <div className="text-xs text-[var(--grey-light)] mt-0.5 pl-4">
              {b.domain} &middot; {b.status} &middot; {new Date(b.created_at).toLocaleDateString()}
            </div>
          </div>
          {rollbackIds.has(b.bundle_id) && (
            <button
              onClick={() => handleRollback(b.bundle_id)}
              disabled={rolling === b.bundle_id}
              className="text-xs px-3 py-1.5 rounded-lg bg-amber-700/50 hover:bg-amber-700 disabled:opacity-50 transition-colors ml-3 flex-shrink-0"
            >
              {rolling === b.bundle_id ? 'Rolling back...' : 'Rollback'}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
