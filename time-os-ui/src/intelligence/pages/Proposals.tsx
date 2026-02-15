/**
 * Proposals — Ranked Proposals List
 * 
 * Shows all proposals sorted by priority with filtering.
 */

import { useProposals } from '../hooks';
import { useProposalFilters } from '../lib';
import type { Proposal } from '../api';

function UrgencyBadge({ urgency }: { urgency: string }) {
  const colors: Record<string, string> = {
    immediate: 'bg-red-500/20 text-red-400',
    this_week: 'bg-amber-500/20 text-amber-400',
    monitor: 'bg-slate-500/20 text-slate-400',
  };
  
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[urgency] || colors.monitor}`}>
      {urgency.replace('_', ' ')}
    </span>
  );
}

function ProposalCard({ proposal, rank }: { proposal: Proposal; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className={`rounded-lg border ${
      proposal.urgency === 'immediate' ? 'bg-red-500/5 border-red-500/30' :
      proposal.urgency === 'this_week' ? 'bg-amber-500/5 border-amber-500/30' :
      'bg-slate-800 border-slate-700'
    }`}>
      <div 
        className="p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-slate-500 font-mono text-sm">#{rank}</span>
              <UrgencyBadge urgency={proposal.urgency} />
              <span className="text-xs text-slate-500">{proposal.type.replace('_', ' ')}</span>
            </div>
            <div className="font-medium">{proposal.headline}</div>
            <div className="text-sm text-slate-400 mt-1">
              {proposal.entity.type}: {proposal.entity.name}
            </div>
          </div>
          <div className="text-right">
            {proposal.priority_score && (
              <div className="text-lg font-bold text-slate-300">
                {Math.round(proposal.priority_score.raw_score)}
              </div>
            )}
            <div className="text-xs text-slate-500">
              {expanded ? '▲' : '▼'}
            </div>
          </div>
        </div>
      </div>
      
      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-700 pt-4">
          <div className="text-sm text-slate-300 mb-4">{proposal.summary}</div>
          
          {/* Evidence */}
          {proposal.evidence && proposal.evidence.length > 0 && (
            <div className="mb-4">
              <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Evidence</div>
              <div className="space-y-2">
                {proposal.evidence.map((e, i) => (
                  <div key={i} className="text-sm bg-slate-800 rounded p-2">
                    <span className="text-slate-400">{e.description}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Implied Action */}
          <div className="bg-slate-700/50 rounded p-3">
            <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Recommended Action</div>
            <div className="text-sm">{proposal.implied_action}</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Proposals() {
  const { urgency, limit, setUrgency, setLimit, resetFilters } = useProposalFilters();
  
  const { data: proposals, loading, error } = useProposals(limit, urgency || undefined);
  
  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-12 bg-slate-800 rounded w-full" />
        <div className="h-24 bg-slate-800 rounded" />
        <div className="h-24 bg-slate-800 rounded" />
        <div className="h-24 bg-slate-800 rounded" />
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
        <div className="text-red-400">Failed to load proposals</div>
        <div className="text-sm text-slate-500 mt-2">{error.message}</div>
      </div>
    );
  }
  
  const proposalList = proposals ?? [];
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Proposals</h1>
        <div className="text-sm text-slate-500">
          {proposalList.length} proposals
        </div>
      </div>
      
      {/* Filters */}
      <div className="flex flex-wrap gap-4 bg-slate-800 rounded-lg p-4">
        <div>
          <label className="text-sm text-slate-400 block mb-1">Urgency</label>
          <select
            value={urgency}
            onChange={e => setUrgency(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm"
          >
            <option value="">All</option>
            <option value="immediate">Immediate</option>
            <option value="this_week">This Week</option>
            <option value="monitor">Monitor</option>
          </select>
        </div>
        <div>
          <label className="text-sm text-slate-400 block mb-1">Limit</label>
          <select
            value={limit}
            onChange={e => setLimit(Number(e.target.value))}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm"
          >
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
        {urgency && (
          <div className="flex items-end">
            <button
              onClick={resetFilters}
              className="text-xs text-slate-400 hover:text-white"
            >
              Reset
            </button>
          </div>
        )}
      </div>
      
      {/* Proposal List */}
      <div className="space-y-4">
        {proposalList.length === 0 ? (
          <div className="bg-slate-800 rounded-lg p-8 text-center text-slate-400">
            No proposals match the current filters
          </div>
        ) : (
          proposalList.map((proposal, i) => (
            <ProposalCard 
              key={proposal.id || i} 
              proposal={proposal} 
              rank={proposal.priority_score?.rank || i + 1}
            />
          ))
        )}
      </div>
    </div>
  );
}
