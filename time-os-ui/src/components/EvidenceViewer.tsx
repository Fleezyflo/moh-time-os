// EvidenceViewer — Anchored excerpt navigation within drawer

interface Excerpt {
  excerpt_id: string;
  text: string;
  context?: string;
  source_type: string;
  source_ref: string;
  extracted_at: string;
}

interface EvidenceViewerProps {
  isOpen: boolean;
  onClose: () => void;
  excerpts: Excerpt[];
  anchorId?: string;
  onSourceClick?: (source_ref: string) => void;
}

const sourceIcons: Record<string, string> = {
  email: '📧',
  slack_message: '💬',
  asana_task: '📋',
  asana_comment: '💬',
  calendar: '📅',
  github_issue: '🐙',
  xero_invoice: '💰',
  teams_message: '💬'
};

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHrs / 24);
  
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString();
}

export function EvidenceViewer({ isOpen, onClose, excerpts, anchorId, onSourceClick }: EvidenceViewerProps) {
  if (!isOpen) return null;

  const anchorIndex = anchorId ? excerpts.findIndex(e => e.excerpt_id === anchorId) : 0;
  const currentExcerpt = excerpts[anchorIndex] || excerpts[0];

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40 lg:bg-black/30"
        onClick={onClose}
      />
      
      {/* Viewer */}
      <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[500px] bg-slate-900 border-l border-slate-700 shadow-drawer overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-slate-900/95 backdrop-blur border-b border-slate-700 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">
                Evidence ({excerpts.length} excerpts)
              </p>
              <h2 className="text-lg font-semibold text-slate-100">
                {anchorIndex + 1} of {excerpts.length}
              </h2>
            </div>
            <button 
              onClick={onClose}
              className="p-2 hover:bg-slate-800 rounded transition-colors text-slate-400 hover:text-slate-200"
              aria-label="Close viewer"
            >
              ✕
            </button>
          </div>
        </div>
        
        {/* Content */}
        <div className="p-4">
          {currentExcerpt && (
            <div className="space-y-4">
              {/* Anchored indicator */}
              {anchorId && currentExcerpt.excerpt_id === anchorId && (
                <div className="flex items-center gap-2 text-blue-400 text-sm">
                  <span>★</span>
                  <span>ANCHORED</span>
                </div>
              )}
              
              {/* Excerpt card */}
              <div className="bg-slate-800 rounded-lg p-4 border-l-4 border-blue-500">
                {/* Text */}
                <p className="text-slate-200 leading-relaxed">
                  "{currentExcerpt.text}"
                </p>
                
                {/* Context */}
                {currentExcerpt.context && (
                  <div className="mt-4 pt-4 border-t border-slate-700">
                    <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Context</p>
                    <p className="text-sm text-slate-400">{currentExcerpt.context}</p>
                  </div>
                )}
                
                {/* Source info */}
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <div className="flex items-center gap-2 text-sm">
                    <span>{sourceIcons[currentExcerpt.source_type] || '📄'}</span>
                    <span className="text-slate-400">{currentExcerpt.source_type.replace('_', ' ')}</span>
                    <span className="text-slate-600">·</span>
                    <span className="text-slate-500">{formatDate(currentExcerpt.extracted_at)}</span>
                  </div>
                  <button
                    onClick={() => onSourceClick?.(currentExcerpt.source_ref)}
                    className="mt-2 text-sm text-blue-400 hover:text-blue-300 hover:underline"
                  >
                    Open original source →
                  </button>
                </div>
              </div>
              
              {/* Navigation */}
              {excerpts.length > 1 && (
                <div className="flex items-center justify-between pt-4 border-t border-slate-700">
                  <button
                    disabled={anchorIndex === 0}
                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-slate-200 text-sm rounded transition-colors"
                  >
                    ← Previous
                  </button>
                  <span className="text-sm text-slate-500">
                    {anchorIndex + 1} / {excerpts.length}
                  </span>
                  <button
                    disabled={anchorIndex === excerpts.length - 1}
                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-slate-200 text-sm rounded transition-colors"
                  >
                    Next →
                  </button>
                </div>
              )}
            </div>
          )}
          
          {/* All excerpts list */}
          <div className="mt-6 pt-6 border-t border-slate-700">
            <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
              All excerpts
            </h3>
            <div className="space-y-2">
              {excerpts.map((excerpt, i) => (
                <div
                  key={excerpt.excerpt_id}
                  className={`p-3 rounded-lg cursor-pointer transition-colors ${
                    i === anchorIndex 
                      ? 'bg-blue-600/20 border border-blue-500/30' 
                      : 'bg-slate-800/50 hover:bg-slate-800'
                  }`}
                >
                  <p className="text-sm text-slate-300 line-clamp-2">{excerpt.text}</p>
                  <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                    <span>{sourceIcons[excerpt.source_type] || '📄'}</span>
                    <span>{formatDate(excerpt.extracted_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
