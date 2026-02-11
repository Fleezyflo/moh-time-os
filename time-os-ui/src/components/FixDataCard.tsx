// FixDataCard — displays data quality issues from real API
import type { FixData } from '../types/api';

interface FixDataSummaryProps {
  fixData: FixData | null;
  onClick?: () => void;
}

export function FixDataSummary({ fixData, onClick }: FixDataSummaryProps) {
  const total = fixData?.total || 0;

  if (total === 0) {
    return (
      <div className="bg-green-900/20 border border-green-700/50 rounded-lg p-4 text-center">
        <span className="text-green-400">✓ No data quality issues</span>
      </div>
    );
  }

  return (
    <div
      className="bg-amber-900/20 border border-amber-700/50 rounded-lg p-4 cursor-pointer hover:border-amber-600 transition-colors"
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-amber-400">⚠️</span>
          <span className="text-amber-300 font-medium">
            {total} data quality issue{total !== 1 ? 's' : ''}
          </span>
        </div>
        <span className="text-slate-400 text-sm">Fix →</span>
      </div>
      {fixData && (
        <div className="flex items-center gap-4 mt-2 text-sm text-slate-400">
          {fixData.identity_conflicts.length > 0 && (
            <span>🔀 {fixData.identity_conflicts.length} identity conflicts</span>
          )}
          {fixData.ambiguous_links.length > 0 && (
            <span>🔗 {fixData.ambiguous_links.length} ambiguous links</span>
          )}
        </div>
      )}
    </div>
  );
}

interface FixDataCardProps {
  type: 'identity_conflict' | 'ambiguous_link' | 'missing_mapping';
  item: {
    id: string;
    display_name?: string;
    source?: string;
    confidence_score?: number;
    entity_type?: string;
    entity_id?: string;
    linked_type?: string;
    linked_id?: string;
    confidence?: number;
  };
  onResolve?: () => void;
  isResolving?: boolean;
}

const typeConfig = {
  identity_conflict: { icon: '🔀', label: 'Identity Conflict', color: 'border-purple-700/50' },
  ambiguous_link: { icon: '🔗', label: 'Ambiguous Link', color: 'border-amber-700/50' },
  missing_mapping: { icon: '➕', label: 'Missing Mapping', color: 'border-blue-700/50' },
};

export function FixDataCard({ type, item, onResolve, isResolving }: FixDataCardProps) {
  const config = typeConfig[type] || typeConfig.identity_conflict;

  return (
    <div className={`bg-slate-800 border ${config.color} rounded-lg p-4`}>
      <div className="flex items-start gap-3">
        <span className="text-lg">{config.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="text-xs text-slate-400 uppercase tracking-wide">{config.label}</div>
          <h3 className="font-medium text-slate-100 mt-1">
            {item.display_name || item.entity_id || item.id}
          </h3>
          {item.source && <div className="text-sm text-slate-500 mt-1">Source: {item.source}</div>}
          {item.confidence_score !== undefined && (
            <div className="text-sm text-slate-500 mt-1">
              Confidence: {(item.confidence_score * 100).toFixed(0)}%
            </div>
          )}
          {item.entity_type && item.linked_type && (
            <div className="text-sm text-slate-500 mt-1">
              {item.entity_type} → {item.linked_type}
            </div>
          )}
        </div>
      </div>
      {onResolve && (
        <div className="mt-3 pt-3 border-t border-slate-700">
          <button
            onClick={onResolve}
            disabled={isResolving}
            className={`text-sm ${isResolving ? 'text-slate-500 cursor-not-allowed' : 'text-blue-400 hover:text-blue-300'}`}
          >
            {isResolving ? 'Resolving...' : 'Resolve →'}
          </button>
        </div>
      )}
    </div>
  );
}
