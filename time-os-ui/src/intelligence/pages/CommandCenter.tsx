/**
 * Command Center — Main Intelligence Dashboard
 * 
 * The "30-second scan" view showing:
 * - Portfolio health score
 * - Critical items (IMMEDIATE)
 * - Attention items (THIS_WEEK)
 * - Signal summary
 * - Structural patterns
 */

import { Link } from '@tanstack/react-router';
import { useCriticalItems, usePortfolioScore, useSignalSummary, usePatterns, useProposals } from '../hooks';
import { HealthScore, CountBadge, ProposalCard, PatternCard } from '../components';

export default function CommandCenter() {
  const { data: critical, loading: criticalLoading } = useCriticalItems();
  const { data: portfolio, loading: portfolioLoading } = usePortfolioScore();
  const { data: signalSummary, loading: signalLoading } = useSignalSummary();
  const { data: patterns, loading: patternsLoading } = usePatterns();
  const { data: proposals, loading: proposalsLoading } = useProposals(5, 'this_week');
  
  const loading = criticalLoading || portfolioLoading || signalLoading || patternsLoading;
  
  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-32 bg-slate-800 rounded-lg" />
        <div className="h-64 bg-slate-800 rounded-lg" />
      </div>
    );
  }
  
  const portfolioScore = portfolio?.composite_score ?? 0;
  const criticalItems = critical ?? [];
  const structuralPatterns = patterns?.patterns?.filter(p => p.severity === 'structural') ?? [];
  const attentionProposals = proposals ?? [];
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Command Center</h1>
        <div className="flex gap-2">
          <Link to="/intel/briefing" className="text-sm text-slate-400 hover:text-white px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 transition-colors">
            📋 Briefing
          </Link>
          <Link to="/intel/proposals" className="text-sm text-slate-400 hover:text-white px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 transition-colors">
            📊 All Proposals
          </Link>
        </div>
      </div>
      
      {/* Portfolio Health + Signal Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <HealthScore score={portfolioScore} label="Portfolio Health" />
        
        <div className="md:col-span-3 bg-slate-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm text-slate-400">Signal Summary</div>
            <Link to="/intel/signals" className="text-xs text-slate-500 hover:text-white">
              View all →
            </Link>
          </div>
          <div className="flex flex-wrap gap-2">
            <CountBadge severity="critical" count={signalSummary?.by_severity?.critical ?? 0} />
            <CountBadge severity="warning" count={signalSummary?.by_severity?.warning ?? 0} />
            <CountBadge severity="watch" count={signalSummary?.by_severity?.watch ?? 0} />
          </div>
          <div className="text-sm text-slate-500 mt-3">
            {signalSummary?.total_active ?? 0} active signals • {signalSummary?.new_since_last_check ?? 0} new
          </div>
        </div>
      </div>
      
      {/* Critical Items */}
      {criticalItems.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-medium text-red-400">
              🚨 Critical ({criticalItems.length})
            </h2>
            <Link to="/intel/proposals?urgency=immediate" className="text-xs text-slate-500 hover:text-white">
              View all →
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {criticalItems.slice(0, 4).map((item, i) => (
              <div key={i} className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                <div className="font-medium text-red-400">{item.headline}</div>
                <div className="text-sm text-slate-400 mt-1">{item.entity.name}</div>
                <div className="text-sm text-slate-500 mt-2">→ {item.implied_action}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Attention Items (This Week) */}
      {attentionProposals.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-medium text-amber-400">
              ⚠️ Needs Attention ({attentionProposals.length})
            </h2>
            <Link to="/intel/proposals?urgency=this_week" className="text-xs text-slate-500 hover:text-white">
              View all →
            </Link>
          </div>
          <div className="space-y-3">
            {attentionProposals.slice(0, 3).map((proposal, i) => (
              <ProposalCard key={proposal.id || i} proposal={proposal} rank={i + 1} compact />
            ))}
          </div>
        </div>
      )}
      
      {/* Structural Patterns */}
      {structuralPatterns.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-medium text-orange-400">
              🔺 Structural Patterns ({structuralPatterns.length})
            </h2>
            <Link to="/intel/patterns" className="text-xs text-slate-500 hover:text-white">
              View all →
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {structuralPatterns.slice(0, 4).map((pattern, i) => (
              <PatternCard key={pattern.pattern_id || i} pattern={pattern} compact />
            ))}
          </div>
        </div>
      )}
      
      {/* All Clear State */}
      {criticalItems.length === 0 && structuralPatterns.length === 0 && attentionProposals.length === 0 && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-8 text-center">
          <div className="text-green-400 text-lg">✓ All Clear</div>
          <div className="text-slate-400 mt-2">No critical items, structural patterns, or attention items</div>
        </div>
      )}
    </div>
  );
}
