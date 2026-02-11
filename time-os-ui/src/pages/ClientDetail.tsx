// Client Detail page
import { useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { RoomDrawer, IssueDrawer, PostureStrip, EvidenceViewer, SkeletonCardList } from '../components'
import { priorityLabel, priorityBadgeClass } from '../lib/priority'
import { formatDate, formatRelative } from '../lib/datetime'
import { formatNumber } from '../lib/format'
import type { Proposal, Issue } from '../types/api'
import type { IssueState } from '../lib/api'
import { useClients, useProposals, useIssues, useEvidence } from '../lib/hooks'
import * as api from '../lib/api'

const trendIcons: Record<string, { icon: string; color: string; label: string }> = {
  improving: { icon: '📈', color: 'text-green-400', label: 'Improving' },
  stable: { icon: '➡️', color: 'text-slate-400', label: 'Stable' },
  declining: { icon: '📉', color: 'text-red-400', label: 'Declining' },
};

export function ClientDetail() {
  const { clientId } = useParams({ from: '/clients/$clientId' });
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [proposalDrawerOpen, setProposalDrawerOpen] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [issueDrawerOpen, setIssueDrawerOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const { data: apiClients, loading: clientsLoading } = useClients();
  const { data: apiProposals, refetch: refetchProposals } = useProposals(20, 'open', 7, clientId, undefined);
  const { data: apiIssues, refetch: refetchIssues } = useIssues(20, 7, clientId, undefined);
  const { data: apiEvidence } = useEvidence('client', clientId);

  const client = apiClients?.items?.find(c => c.id === clientId);

  if (clientsLoading) return <SkeletonCardList count={3} />;
  if (!client) return <div className="text-slate-400">Client not found</div>;

  const clientProposals = (apiProposals?.items || []).filter(p => p.status === 'open').sort((a, b) => b.score - a.score);
  const clientIssues = (apiIssues?.items || []).filter(i => ['open','monitoring','awaiting','blocked'].includes(i.state));
  const evidenceItems = apiEvidence?.items || [];

  const handleTag = async (proposal: Proposal) => {
    const result = await api.tagProposal(proposal.proposal_id ?? '');
    if (result.success) { refetchProposals(); refetchIssues(); setProposalDrawerOpen(false); setSelectedProposal(null); }
  };

  const handleSnooze = async (proposal: Proposal) => {
    const result = await api.snoozeProposal(proposal.proposal_id ?? '', 7);
    if (result.success) { refetchProposals(); setProposalDrawerOpen(false); setSelectedProposal(null); }
  };

  const handleDismiss = async (proposal: Proposal) => {
    const result = await api.dismissProposal(proposal.proposal_id ?? '');
    if (result.success) { refetchProposals(); setProposalDrawerOpen(false); setSelectedProposal(null); }
  };

  const handleResolveIssue = async (issue: Issue) => {
    const result = await api.resolveIssue(issue.issue_id ?? '');
    if (result.success) refetchIssues();
    else throw new Error(result.error || 'Failed to resolve');
  };

  const handleAddIssueNote = async (issue: Issue, text: string) => {
    const result = await api.addIssueNote(issue.issue_id ?? '', text);
    if (!result.success) throw new Error(result.error || 'Failed to add note');
  };

  const handleChangeIssueState = async (issue: Issue, newState: IssueState) => {
    const result = await api.changeIssueState(issue.issue_id ?? '', newState);
    if (result.success) {
      refetchIssues();
    } else {
      throw new Error(result.error || 'Failed to change state');
    }
  };

  const trend = trendIcons[client.relationship_trend || 'stable'] || trendIcons.stable;

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-center gap-4 mb-2">
          <Link to="/clients" className="text-slate-400 hover:text-slate-200">← Clients</Link>
        </div>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold">{client.name}</h1>
            <div className="flex items-center gap-3 mt-1">
              <PostureStrip health={client.relationship_health || 'good'} />
              <span className={`text-sm ${trend.color}`}>{trend.icon} {trend.label}</span>
            </div>
          </div>
          <div className="text-right">
            {client.tier && (
              <span className="px-2 py-1 rounded text-xs bg-slate-700 text-slate-300 mr-2">
                Tier {client.tier}
              </span>
            )}
            <span className={`px-3 py-1 rounded text-sm ${
              (client.health_score || 0) >= 80 ? 'bg-green-900/30 text-green-400' :
              (client.health_score || 0) >= 60 ? 'bg-amber-900/30 text-amber-400' :
              'bg-red-900/30 text-red-400'
            }`}>
              Health: {client.health_score || 0}%
            </span>
          </div>
        </div>
      </div>

      {/* Quick Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        {/* Financial: AR Outstanding */}
        <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <div className="text-xs text-slate-400 uppercase tracking-wide">AR Outstanding</div>
          <div className="text-xl font-semibold text-slate-100 mt-1">
            {client.financial_ar_total != null
              ? `$${formatNumber(client.financial_ar_total ?? 0)}`
              : '—'}
          </div>
          {client.financial_ar_aging_bucket && (
            <div className="text-xs text-slate-500 mt-1">
              {client.financial_ar_aging_bucket === 'current' ? 'Current' : `${client.financial_ar_aging_bucket} days overdue`}
            </div>
          )}
        </div>

        {/* Last Interaction */}
        <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <div className="text-xs text-slate-400 uppercase tracking-wide">Last Interaction</div>
          <div className="text-lg font-medium text-slate-100 mt-1">
            {client.relationship_last_interaction
              ? formatRelative(client.relationship_last_interaction ?? '')
              : '—'}
          </div>
          {client.relationship_last_interaction && (
            <div className="text-xs text-slate-500 mt-1">
              {formatDate(client.relationship_last_interaction ?? '')}
            </div>
          )}
        </div>

        {/* Open Issues */}
        <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <div className="text-xs text-slate-400 uppercase tracking-wide">Open Issues</div>
          <div className="text-xl font-semibold text-slate-100 mt-1">{clientIssues.length}</div>
        </div>

        {/* Active Proposals */}
        <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <div className="text-xs text-slate-400 uppercase tracking-wide">Active Proposals</div>
          <div className="text-xl font-semibold text-slate-100 mt-1">{clientProposals.length}</div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Proposals */}
        <section className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <h2 className="text-lg font-medium mb-4">Open Proposals ({clientProposals.length})</h2>
          {clientProposals.length === 0 ? (
            <p className="text-slate-500">No open proposals</p>
          ) : (
            <div className="space-y-3">
              {clientProposals.slice(0, 5).map(p => (
                <div key={p.proposal_id} onClick={() => { setSelectedProposal(p); setProposalDrawerOpen(true); }} className="p-3 bg-slate-800 rounded-lg border border-slate-700 cursor-pointer hover:border-slate-600">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-200">{p.headline}</span>
                    <span className="text-xs text-slate-500">Score: {p.score}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Issues */}
        <section className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <h2 className="text-lg font-medium mb-4">Active Issues ({clientIssues.length})</h2>
          {clientIssues.length === 0 ? (
            <p className="text-slate-500">No active issues</p>
          ) : (
            <div className="space-y-3">
              {clientIssues.slice(0, 5).map(issue => (
                <div key={issue.issue_id} onClick={() => { setSelectedIssue(issue); setIssueDrawerOpen(true); }} className="p-3 bg-slate-800 rounded-lg border border-slate-700 cursor-pointer hover:border-slate-600">
                  <div className="flex items-center gap-2">
                    <span className={issue.state === 'open' ? 'text-blue-400' : 'text-amber-400'}>●</span>
                    <span className="text-slate-200 flex-1 truncate">{issue.headline}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${priorityBadgeClass(issue.priority ?? 0)}`}>
                      {priorityLabel(issue.priority ?? 0).charAt(0).toUpperCase() + priorityLabel(issue.priority ?? 0).slice(1)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Evidence */}
      {evidenceItems.length > 0 && (
        <section className="mt-6 bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium">Evidence ({evidenceItems.length})</h2>
            <button onClick={() => setEvidenceOpen(true)} className="text-sm text-blue-400 hover:text-blue-300">View All</button>
          </div>
        </section>
      )}

      {selectedProposal && (
        <RoomDrawer open={proposalDrawerOpen} onClose={() => { setProposalDrawerOpen(false); setSelectedProposal(null); }} proposal={selectedProposal} onTag={() => handleTag(selectedProposal)} onSnooze={() => handleSnooze(selectedProposal)} onDismiss={() => handleDismiss(selectedProposal)} />
      )}

      <IssueDrawer
        issue={selectedIssue}
        open={issueDrawerOpen}
        onClose={() => { setIssueDrawerOpen(false); setSelectedIssue(null); }}
        onResolve={selectedIssue ? () => handleResolveIssue(selectedIssue) : undefined}
        onAddNote={selectedIssue ? (text) => handleAddIssueNote(selectedIssue, text) : undefined}
        onChangeState={selectedIssue ? (newState) => handleChangeIssueState(selectedIssue, newState) : undefined}
      />

      {evidenceOpen && (
        <div className="fixed inset-0 z-40 overflow-hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setEvidenceOpen(false)} />
          <div className="absolute right-0 top-0 h-full w-full max-w-lg bg-slate-900 border-l border-slate-700 shadow-xl overflow-y-auto p-4">
            <EvidenceViewer evidence={evidenceItems} onClose={() => setEvidenceOpen(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
