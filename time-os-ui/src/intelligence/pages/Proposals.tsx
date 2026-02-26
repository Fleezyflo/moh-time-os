/**
 * Proposals — Ranked Proposals List
 *
 * Shows all proposals sorted by priority with filtering.
 */

import { useProposals } from '../hooks';
import { useProposalFilters } from '../lib';
import { ErrorState, NoProposals, NoResults } from '../../components';
import { SkeletonProposalsPage, ProposalCard } from '../components';

export default function Proposals() {
  const { urgency, limit, setUrgency, setLimit, resetFilters } = useProposalFilters();

  const { data: proposals, loading, error, refetch } = useProposals(limit, urgency || undefined);

  // Show error state if we have an error and no data
  if (error && !proposals) {
    return (
      <div className="p-6">
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  if (loading && !proposals) {
    return <SkeletonProposalsPage />;
  }

  const proposalList = proposals ?? [];

  return (
    <div className="space-y-6">
      {/* Error banner when we have stale data */}
      {error && proposals && <ErrorState error={error} onRetry={refetch} hasData />}

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Proposals</h1>
        <div className="text-sm text-slate-500">{proposalList.length} proposals</div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 bg-slate-800 rounded-lg p-4">
        <div>
          <label className="text-sm text-slate-400 block mb-1">Urgency</label>
          <select
            value={urgency}
            onChange={(e) => setUrgency(e.target.value)}
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
            onChange={(e) => setLimit(Number(e.target.value))}
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
            <button onClick={resetFilters} className="text-xs text-slate-400 hover:text-white">
              Reset
            </button>
          </div>
        )}
      </div>

      {/* Proposal List */}
      <div className="space-y-4">
        {proposalList.length === 0 ? (
          urgency ? (
            <NoResults query={`urgency: ${urgency}`} />
          ) : (
            <NoProposals />
          )
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
