/**
 * Briefing — Daily Briefing View
 * 
 * Narrative format showing the day's intelligence summary.
 */

import { useBriefing } from '../hooks';

export default function Briefing() {
  const { data: briefing, loading, error } = useBriefing();
  
  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-slate-800 rounded w-1/3" />
        <div className="h-32 bg-slate-800 rounded" />
        <div className="h-64 bg-slate-800 rounded" />
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
        <div className="text-red-400">Failed to load briefing</div>
        <div className="text-sm text-slate-500 mt-2">{error.message}</div>
      </div>
    );
  }
  
  if (!briefing) return null;
  
  const { summary, critical_items, attention_items, watching, portfolio_health, top_proposal } = briefing;
  
  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">Daily Briefing</h1>
        <p className="text-slate-400 mt-1">
          Generated at {new Date(briefing.generated_at).toLocaleString()}
        </p>
      </div>
      
      {/* Summary */}
      <div className="bg-slate-800 rounded-lg p-6">
        <div className="text-lg">
          <span className="text-white font-medium">{summary.total_proposals}</span>
          <span className="text-slate-400"> proposals today: </span>
          {summary.immediate_count > 0 && (
            <span className="text-red-400">{summary.immediate_count} critical</span>
          )}
          {summary.immediate_count > 0 && summary.this_week_count > 0 && (
            <span className="text-slate-400">, </span>
          )}
          {summary.this_week_count > 0 && (
            <span className="text-amber-400">{summary.this_week_count} attention</span>
          )}
          {(summary.immediate_count > 0 || summary.this_week_count > 0) && summary.monitor_count > 0 && (
            <span className="text-slate-400">, </span>
          )}
          {summary.monitor_count > 0 && (
            <span className="text-slate-500">{summary.monitor_count} watching</span>
          )}
        </div>
      </div>
      
      {/* Top Priority */}
      {top_proposal && (
        <div className="bg-slate-800 border-l-4 border-red-500 rounded-lg p-6">
          <div className="text-sm text-slate-500 uppercase tracking-wide mb-2">Top Priority</div>
          <div className="text-lg text-white">{top_proposal}</div>
        </div>
      )}
      
      {/* Critical Items */}
      {critical_items && critical_items.length > 0 && (
        <div>
          <h2 className="text-lg font-medium text-red-400 mb-3">
            🚨 Critical ({critical_items.length})
          </h2>
          <div className="space-y-3">
            {critical_items.map((item, i) => (
              <div key={i} className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                <div className="font-medium">{item.headline}</div>
                <div className="text-sm text-slate-400 mt-2">{item.implied_action}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Attention Items */}
      {attention_items && attention_items.length > 0 && (
        <div>
          <h2 className="text-lg font-medium text-amber-400 mb-3">
            ⚠️ Needs Attention ({attention_items.length})
          </h2>
          <div className="space-y-3">
            {attention_items.map((item, i) => (
              <div key={i} className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4">
                <div className="font-medium">{item.headline}</div>
                <div className="text-sm text-slate-400 mt-2">{item.implied_action}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Watching */}
      {watching && watching.length > 0 && (
        <details className="group">
          <summary className="text-lg font-medium text-slate-400 mb-3 cursor-pointer">
            👁 Watching ({watching.length})
          </summary>
          <div className="space-y-3 mt-3">
            {watching.map((item, i) => (
              <div key={i} className="bg-slate-800 border border-slate-700 rounded-lg p-4">
                <div className="font-medium">{item.headline}</div>
                <div className="text-sm text-slate-400 mt-2">{item.implied_action}</div>
              </div>
            ))}
          </div>
        </details>
      )}
      
      {/* Portfolio Health */}
      {portfolio_health && (
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-sm text-slate-500 uppercase tracking-wide mb-2">Portfolio Health</div>
          <div className="flex items-center gap-4">
            <div className={`text-3xl font-bold ${
              portfolio_health.overall_score >= 60 ? 'text-green-400' :
              portfolio_health.overall_score >= 30 ? 'text-amber-400' : 'text-red-400'
            }`}>
              {portfolio_health.overall_score}
            </div>
            <div className="text-slate-400">
              <div>{portfolio_health.active_structural_patterns} structural patterns</div>
              <div className="text-sm">Trend: {portfolio_health.trend}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
