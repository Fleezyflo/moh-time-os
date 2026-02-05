// FixDataCard — data quality resolution component
import type { FixData } from '../fixtures';

interface FixDataCardProps {
  fixData: FixData;
  onResolve?: (action: string) => void;
  onOpen?: () => void;
}

const fixTypeConfig = {
  identity_conflict: { icon: '🔀', label: 'Identity Conflict', color: 'text-purple-400' },
  ambiguous_link: { icon: '🔗', label: 'Ambiguous Link', color: 'text-blue-400' },
  missing_mapping: { icon: '➕', label: 'Missing Mapping', color: 'text-green-400' }
};

export function FixDataCard({ fixData, onResolve, onOpen }: FixDataCardProps) {
  const config = fixTypeConfig[fixData.fix_type];
  
  return (
    <div 
      className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden"
      onClick={onOpen}
    >
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <span className="text-xl">{config.icon}</span>
          <span className={`text-sm font-medium uppercase tracking-wide ${config.color}`}>
            {config.label}
          </span>
        </div>
        <p className="mt-2 text-slate-200">{fixData.description}</p>
      </div>
      
      {/* Candidates */}
      <div className="p-4 border-b border-slate-700 bg-slate-800/50">
        <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">
          Candidates
        </h4>
        <ul className="space-y-2">
          {fixData.candidates.map((c, i) => (
            <li key={i} className="flex items-center justify-between text-sm">
              <span className="text-slate-300">{c.label}</span>
              <span className={`text-xs ${c.match_score >= 0.80 ? 'text-green-400' : c.match_score >= 0.60 ? 'text-amber-400' : 'text-slate-400'}`}>
                {(c.match_score * 100).toFixed(0)}% match
              </span>
            </li>
          ))}
        </ul>
      </div>
      
      {/* Impact */}
      <div className="p-4 border-b border-slate-700 bg-amber-900/10">
        <div className="flex items-center gap-2">
          <span className="text-amber-500">⚠️</span>
          <span className="text-sm text-amber-300">{fixData.impact_summary}</span>
        </div>
        {fixData.affected_proposal_ids.length > 0 && (
          <p className="text-xs text-slate-500 mt-1 ml-6">
            Affects: {fixData.affected_proposal_ids.join(', ')}
          </p>
        )}
      </div>
      
      {/* Actions */}
      <div className="p-4 flex flex-wrap gap-2">
        {fixData.fix_type === 'identity_conflict' && (
          <>
            <button 
              onClick={(e) => { e.stopPropagation(); onResolve?.('merge'); }}
              className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded transition-colors"
            >
              Merge all
            </button>
            <button 
              onClick={(e) => { e.stopPropagation(); onResolve?.('keep_separate'); }}
              className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded transition-colors"
            >
              Keep separate
            </button>
          </>
        )}
        {fixData.fix_type === 'ambiguous_link' && (
          <>
            {fixData.candidates.slice(0, 2).map((c, i) => (
              <button 
                key={i}
                onClick={(e) => { e.stopPropagation(); onResolve?.(`assign:${c.label}`); }}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors truncate max-w-[150px]"
              >
                → {c.label.split(' ')[0]}
              </button>
            ))}
          </>
        )}
        {fixData.fix_type === 'missing_mapping' && (
          <>
            <button 
              onClick={(e) => { e.stopPropagation(); onResolve?.('create_alias'); }}
              className="px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white text-sm rounded transition-colors"
            >
              Create alias
            </button>
            <button 
              onClick={(e) => { e.stopPropagation(); onResolve?.('ignore'); }}
              className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded transition-colors"
            >
              Ignore
            </button>
          </>
        )}
        <button 
          onClick={(e) => { e.stopPropagation(); onOpen?.(); }}
          className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm rounded transition-colors ml-auto"
        >
          Review →
        </button>
      </div>
    </div>
  );
}

// Summary card for right rail
export function FixDataSummary({ count, onClick }: { count: number; onClick?: () => void }) {
  return (
    <div 
      className="p-3 bg-amber-900/20 rounded-lg border border-amber-700/30 cursor-pointer hover:border-amber-600/50 transition-colors"
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-amber-500">🔧</span>
          <span className="text-sm text-slate-300">Fix Data</span>
        </div>
        <span className="text-lg font-semibold text-amber-400">{count}</span>
      </div>
      <p className="text-xs text-slate-500 mt-1">Items need attention</p>
    </div>
  );
}
