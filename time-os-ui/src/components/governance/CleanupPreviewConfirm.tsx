// Cleanup preview and confirm dialog
import { useState, useCallback } from 'react';
import { executeCleanup } from '../../lib/api';
import { useCleanupPreview } from '../../lib/hooks';

interface Props {
  cleanupType: 'ancient' | 'stale' | 'legacy-signals';
  label: string;
  onComplete: () => void;
}

export function CleanupPreviewConfirm({ cleanupType, label, onComplete }: Props) {
  const [showPreview, setShowPreview] = useState(false);
  const [executing, setExecuting] = useState(false);

  const { data: preview, loading: previewLoading } = useCleanupPreview(
    showPreview ? cleanupType : ''
  );

  const handleExecute = useCallback(async () => {
    setExecuting(true);
    try {
      await executeCleanup(cleanupType);
      setShowPreview(false);
      onComplete();
    } finally {
      setExecuting(false);
    }
  }, [cleanupType, onComplete]);

  if (!showPreview) {
    return (
      <button
        onClick={() => setShowPreview(true)}
        className="text-xs px-3 py-1.5 rounded-lg bg-[var(--grey)] hover:bg-[var(--grey-light)] transition-colors"
      >
        {label}
      </button>
    );
  }

  return (
    <div className="bg-[var(--grey-dim)] border border-amber-500/30 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">{label} Preview</h4>
        <button
          onClick={() => setShowPreview(false)}
          className="text-xs text-[var(--grey-light)] hover:text-white"
        >
          Cancel
        </button>
      </div>

      {previewLoading ? (
        <div className="text-xs text-[var(--grey-light)]">Loading preview...</div>
      ) : preview ? (
        <>
          <div className="text-sm">
            <span className="font-semibold text-amber-400">{preview.count}</span> items will be
            affected
          </div>

          {/* Sample items */}
          {preview.sample.length > 0 && (
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {preview.sample.slice(0, 5).map((item, i) => (
                <div
                  key={i}
                  className="text-xs bg-[var(--grey)]/50 rounded px-2 py-1 font-mono truncate"
                >
                  {JSON.stringify(item).slice(0, 120)}
                </div>
              ))}
              {preview.sample.length > 5 && (
                <div className="text-xs text-[var(--grey-light)]">
                  ...and {preview.sample.length - 5} more
                </div>
              )}
            </div>
          )}

          <button
            onClick={handleExecute}
            disabled={executing}
            className="text-xs px-4 py-2 rounded-lg bg-red-700 hover:bg-red-600 disabled:opacity-50 transition-colors"
          >
            {executing ? 'Executing...' : `Confirm ${label}`}
          </button>
        </>
      ) : (
        <div className="text-xs text-[var(--grey-light)]">No preview available.</div>
      )}
    </div>
  );
}
