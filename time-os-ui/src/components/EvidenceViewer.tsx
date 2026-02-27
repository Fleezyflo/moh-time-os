// EvidenceViewer — displays evidence/excerpts for an entity
import type { Evidence } from '../types/api';

interface EvidenceViewerProps {
  evidence: Evidence[];
  loading?: boolean;
  error?: Error | null;
  onClose?: () => void;
}

export function EvidenceViewer({ evidence, loading, error, onClose }: EvidenceViewerProps) {
  if (loading) {
    return <div className="text-[var(--grey-light)] p-4 text-center">Loading evidence...</div>;
  }

  if (error) {
    return <div className="text-red-400 p-4 text-center">Error: {error.message}</div>;
  }

  if (!evidence || evidence.length === 0) {
    return <div className="text-[var(--grey-muted)] p-4 text-center">No evidence found</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-[var(--white)]">
          Evidence ({evidence.length} excerpt{evidence.length !== 1 ? 's' : ''})
        </h3>
        {onClose && (
          <button onClick={onClose} className="text-[var(--grey-light)] hover:text-[var(--white)]">
            ✕
          </button>
        )}
      </div>

      <div className="space-y-3">
        {evidence.map((item, i) => (
          <div
            key={item.id || i}
            className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-blue-400">●</span>
              <span className="text-xs text-[var(--grey-light)] uppercase">{item.source}</span>
              <span className="text-xs text-[var(--grey-muted)]">{item.artifact_type}</span>
            </div>
            <p className="text-[var(--white)]">{item.excerpt_text}</p>
            <div className="text-xs text-[var(--grey-muted)] mt-2">
              {new Date(item.occurred_at).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
