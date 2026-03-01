// BulkActionBar — Floating action bar for bulk priority operations
import { useState, useCallback } from 'react';

interface BulkActionBarProps {
  selectedCount: number;
  onComplete: () => void;
  onSnooze: (days: number) => void;
  onArchive: () => void;
  onClearSelection: () => void;
  loading?: boolean;
}

export function BulkActionBar({
  selectedCount,
  onComplete,
  onSnooze,
  onArchive,
  onClearSelection,
  loading,
}: BulkActionBarProps) {
  const [showSnoozeMenu, setShowSnoozeMenu] = useState(false);

  const handleSnooze = useCallback(
    (days: number) => {
      onSnooze(days);
      setShowSnoozeMenu(false);
    },
    [onSnooze]
  );

  if (selectedCount === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg shadow-xl px-4 py-3 flex items-center gap-3">
      <span className="text-sm text-[var(--white)] font-medium">{selectedCount} selected</span>

      <div className="w-px h-5 bg-[var(--grey)]" />

      <button
        onClick={onComplete}
        disabled={loading}
        className="px-3 py-1.5 text-sm rounded bg-[var(--success)]/20 text-[var(--success)] hover:bg-[var(--success)]/30 transition-colors disabled:opacity-50"
      >
        Complete
      </button>

      <div className="relative">
        <button
          onClick={() => setShowSnoozeMenu(!showSnoozeMenu)}
          disabled={loading}
          className="px-3 py-1.5 text-sm rounded bg-[var(--accent)]/20 text-[var(--accent)] hover:bg-[var(--accent)]/30 transition-colors disabled:opacity-50"
        >
          Snooze
        </button>
        {showSnoozeMenu && (
          <div className="absolute bottom-full mb-2 left-0 bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg shadow-xl py-1 min-w-[120px]">
            {[1, 3, 7, 14].map((days) => (
              <button
                key={days}
                onClick={() => handleSnooze(days)}
                className="block w-full text-left px-3 py-1.5 text-sm text-[var(--white)] hover:bg-[var(--grey)]"
              >
                {days === 1 ? '1 day' : `${days} days`}
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        onClick={onArchive}
        disabled={loading}
        className="px-3 py-1.5 text-sm rounded bg-[var(--warning)]/20 text-[var(--warning)] hover:bg-[var(--warning)]/30 transition-colors disabled:opacity-50"
      >
        Archive
      </button>

      <div className="w-px h-5 bg-[var(--grey)]" />

      <button
        onClick={onClearSelection}
        className="px-3 py-1.5 text-sm rounded text-[var(--grey-light)] hover:text-[var(--white)] hover:bg-[var(--grey)] transition-colors"
      >
        Clear
      </button>
    </div>
  );
}
