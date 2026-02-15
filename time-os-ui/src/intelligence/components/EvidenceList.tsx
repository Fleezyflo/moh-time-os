/**
 * EvidenceList — Display evidence items for proposals/signals
 */

interface Evidence {
  source: string;
  source_id: string;
  description: string;
  data?: Record<string, unknown>;
}

interface EvidenceListProps {
  evidence: Evidence[];
  maxItems?: number;
  compact?: boolean;
}

export function EvidenceList({ evidence, maxItems, compact = false }: EvidenceListProps) {
  const items = maxItems ? evidence.slice(0, maxItems) : evidence;
  const hasMore = maxItems && evidence.length > maxItems;
  
  if (evidence.length === 0) {
    return (
      <div className="text-sm text-slate-500 italic">
        No evidence available
      </div>
    );
  }
  
  if (compact) {
    return (
      <div className="space-y-1">
        {items.map((e, i) => (
          <div key={i} className="text-sm text-slate-400">
            • {e.description}
          </div>
        ))}
        {hasMore && (
          <div className="text-xs text-slate-500">
            +{evidence.length - maxItems!} more
          </div>
        )}
      </div>
    );
  }
  
  return (
    <div className="space-y-2">
      <div className="text-xs text-slate-500 uppercase tracking-wide">
        Evidence ({evidence.length})
      </div>
      {items.map((e, i) => (
        <div key={i} className="bg-slate-800 rounded p-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="text-sm text-slate-300">{e.description}</div>
              <div className="text-xs text-slate-500 mt-1">
                Source: {e.source}
              </div>
            </div>
          </div>
          {e.data && Object.keys(e.data).length > 0 && (
            <div className="mt-2 pt-2 border-t border-slate-700">
              <div className="flex flex-wrap gap-2">
                {Object.entries(e.data).slice(0, 4).map(([key, value]) => (
                  <span key={key} className="text-xs bg-slate-700 px-2 py-0.5 rounded">
                    {key}: {String(value)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
      {hasMore && (
        <div className="text-sm text-slate-500 text-center py-2">
          +{evidence.length - maxItems!} more evidence items
        </div>
      )}
    </div>
  );
}

export default EvidenceList;
