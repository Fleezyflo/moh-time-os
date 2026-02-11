// Snapshot page - Primary executive entry point
import { useState } from 'react'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { ProposalCard, RoomDrawer, IssueDrawer, ErrorState, SkeletonCardList, SkeletonPanel, useToast } from '../components'
import { FixDataSummary } from '../components'
import { priorityBadgeClass } from '../lib/priority'
import type { Proposal, Issue } from '../types/api'
import type { IssueState } from '../lib/api'
import { useProposals, useIssues, useWatchers, useFixData, useClients, useTeam } from '../lib/hooks'
import * as api from '../lib/api'

// Scope search params type
export type ScopeSearch = {
  scope?: string;
  days?: number;
};

export function Snapshot() {
  const navigate = useNavigate({ from: '/snapshot' });
  const search = useSearch({ from: '/snapshot' }) as ScopeSearch;
  const toast = useToast();
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [issueDrawerOpen, setIssueDrawerOpen] = useState(false);

  // Parse scope from URL
  const parseScope = (scope?: string) => {
    if (!scope) return { clientId: undefined, memberId: undefined };
    if (scope.startsWith('client:')) return { clientId: scope.slice(7), memberId: undefined };
    if (scope.startsWith('member:')) return { clientId: undefined, memberId: scope.slice(7) };
    return { clientId: undefined, memberId: undefined };
  };

  const { clientId: filterClientId, memberId: filterMemberId } = parseScope(search.scope);
  const filterDays = search.days ?? 7;

  // Fetch data
  const { data: apiClients } = useClients();
  const { data: apiTeam } = useTeam();
  const clientOptions = apiClients?.items || [];
  const teamOptions = apiTeam?.items || [];

  const { data: apiProposals, loading: loadingProposals, error: errorProposals, refetch: refetchProposals } = useProposals(7, 'open', filterDays, filterClientId, filterMemberId);
  const { data: apiIssues, refetch: refetchIssues } = useIssues(5, filterDays, filterClientId, filterMemberId);
  const { data: apiWatchers, refetch: refetchWatchers } = useWatchers(24);
  const { data: apiFixData } = useFixData();

  const currentProposals = apiProposals?.items || [];
  const currentIssues = apiIssues?.items || [];
  const upcomingWatchers = apiWatchers?.items || [];

  // Handlers
  const handleOpenProposal = (proposal: Proposal) => {
    setSelectedProposal(proposal);
    setDrawerOpen(true);
  };

  const handleTag = async (proposal: Proposal) => {
    try {
      const result = await api.tagProposal(proposal.proposal_id);
      if (result.success) {
        toast.success('Tagged and monitoring');
        refetchProposals();
        refetchIssues();
        setDrawerOpen(false);
        setSelectedProposal(null);
      } else {
        toast.error(result.error || 'Failed to tag');
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to tag');
    }
  };

  const handleSnooze = async (proposal: Proposal) => {
    try {
      const result = await api.snoozeProposal(proposal.proposal_id, 7);
      if (result.success) {
        toast.success('Snoozed for 7 days');
        refetchProposals();
        setDrawerOpen(false);
        setSelectedProposal(null);
      } else {
        toast.error(result.error || 'Failed to snooze');
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to snooze');
    }
  };

  const handleDismiss = async (proposal: Proposal) => {
    try {
      const result = await api.dismissProposal(proposal.proposal_id);
      if (result.success) {
        toast.success('Dismissed');
        refetchProposals();
        setDrawerOpen(false);
        setSelectedProposal(null);
      } else {
        toast.error(result.error || 'Failed to dismiss');
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to dismiss');
    }
  };

  const handleFixData = () => navigate({ to: '/fix-data' });

  // Issue handlers
  const handleOpenIssue = (issue: Issue) => {
    setSelectedIssue(issue);
    setIssueDrawerOpen(true);
  };

  const handleResolveIssue = async () => {
    if (!selectedIssue) return;
    await api.resolveIssue(selectedIssue.issue_id ?? '');
    refetchIssues();
    setIssueDrawerOpen(false);
    setSelectedIssue(null);
  };

  const handleAddIssueNote = async (text: string) => {
    if (!selectedIssue) return;
    await api.addIssueNote(selectedIssue.issue_id ?? '', text);
    refetchIssues();
  };

  const handleChangeIssueState = async (newState: IssueState) => {
    if (!selectedIssue) return;
    await api.changeIssueState(selectedIssue.issue_id ?? '', newState);
    refetchIssues();
  };

  // Loading skeleton
  if (loadingProposals && !apiProposals) {
    return (
      <div className="lg:grid lg:grid-cols-12 lg:gap-6">
        <div className="lg:col-span-8">
          <SkeletonCardList count={4} />
        </div>
        <div className="lg:col-span-4 mt-6 lg:mt-0 space-y-6">
          <SkeletonPanel rows={3} />
          <SkeletonPanel rows={2} />
        </div>
      </div>
    );
  }

  // Error state
  if (errorProposals && !apiProposals) {
    return <ErrorState error={errorProposals} onRetry={refetchProposals} hasData={false} />;
  }

  // Quick pulse metrics
  const criticalIssues = currentIssues.filter((i: Issue) => (i.priority ?? 0) >= 80).length;
  const atRiskClients = clientOptions.filter((c) => c.relationship_health === 'critical' || c.relationship_health === 'poor').length;
  const totalAR = clientOptions.reduce((sum, c) => sum + (c.financial_ar_total || 0), 0);

  return (
    <div>
      {/* Executive Pulse - Key metrics at a glance */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className={`bg-slate-800 rounded-lg p-3 border ${currentProposals.length > 0 ? 'border-blue-900/50' : 'border-slate-700'}`}>
          <div className="text-xl font-bold text-blue-400">{currentProposals.length}</div>
          <div className="text-xs text-slate-400">Proposals</div>
        </div>
        <div className={`bg-slate-800 rounded-lg p-3 border ${criticalIssues > 0 ? 'border-red-900/50' : 'border-slate-700'}`}>
          <div className={`text-xl font-bold ${criticalIssues > 0 ? 'text-red-400' : 'text-slate-400'}`}>{criticalIssues}</div>
          <div className="text-xs text-slate-400">Critical Issues</div>
        </div>
        <div className={`bg-slate-800 rounded-lg p-3 border ${atRiskClients > 0 ? 'border-orange-900/50' : 'border-slate-700'}`}>
          <div className={`text-xl font-bold ${atRiskClients > 0 ? 'text-orange-400' : 'text-slate-400'}`}>{atRiskClients}</div>
          <div className="text-xs text-slate-400">At-Risk Clients</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-3 border border-slate-700">
          <div className="text-xl font-bold text-amber-400">${(totalAR / 1000).toFixed(0)}k</div>
          <div className="text-xs text-slate-400">Total AR</div>
        </div>
      </div>

      <div className="lg:grid lg:grid-cols-12 lg:gap-6">
      {errorProposals && apiProposals && (
        <div className="lg:col-span-12">
          <ErrorState error={errorProposals} onRetry={refetchProposals} hasData={true} />
        </div>
      )}

      <div className="lg:col-span-8 space-y-4">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-semibold">
            Snapshot <span className="text-xs text-green-500 ml-2">● Live</span>
          </h1>
          <div className="flex items-center gap-2 text-sm">
            <select
              className="bg-slate-800 border border-slate-700 rounded px-2 py-1"
              value={search.scope || ''}
              onChange={(e) => navigate({ search: { ...search, scope: e.target.value || undefined } })}
            >
              <option value="">All Scopes</option>
              <optgroup label="Clients">
                {clientOptions.map(client => (
                  <option key={`client-${client.id}`} value={`client:${client.id}`}>{client.name}</option>
                ))}
              </optgroup>
              <optgroup label="Team Members">
                {teamOptions.map(member => (
                  <option key={`member-${member.id}`} value={`member:${member.id}`}>{member.name}</option>
                ))}
              </optgroup>
            </select>
            <select
              className="bg-slate-800 border border-slate-700 rounded px-2 py-1"
              value={filterDays}
              onChange={(e) => navigate({ search: { ...search, days: Number(e.target.value) } })}
            >
              <option value={1}>Today</option>
              <option value={7}>7 days</option>
              <option value={30}>30 days</option>
            </select>
          </div>
        </div>

        <div className="space-y-4">
          {currentProposals.length === 0 ? (
            <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-8 text-center">
              <p className="text-slate-400">No proposals require attention right now</p>
            </div>
          ) : (
            currentProposals.map(proposal => (
              <ProposalCard
                key={proposal.proposal_id}
                proposal={proposal}
                onOpen={() => handleOpenProposal(proposal)}
              />
            ))
          )}
        </div>
      </div>

      <div className="lg:col-span-4 mt-6 lg:mt-0 space-y-6">
        {/* Issues Summary */}
        <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <h2 className="text-sm font-medium text-slate-400 mb-3">Open Issues ({currentIssues.length})</h2>
          <div className="space-y-2">
            {currentIssues.slice(0, 5).map((issue: Issue) => {
              // Strip emoji prefixes for cleaner display
              const rawHeadline = issue.title || issue.headline || '';
              const cleanHeadline = rawHeadline.replace(/^[⚠️⏰🚫💔💰⚙️📉📈🔄]+\s*/, '');
              return (
                <button
                  key={issue.issue_id}
                  onClick={() => handleOpenIssue(issue)}
                  className="flex items-center gap-2 text-sm w-full text-left hover:bg-slate-700/50 rounded px-2 py-1 -mx-2 transition-colors"
                >
                  <span className={priorityBadgeClass(issue.priority ?? 0).includes('red') ? 'text-red-400' : 'text-amber-400'}>●</span>
                  <span className="text-slate-300 truncate flex-1">{cleanHeadline}</span>
                  <span className="text-slate-500 text-xs">→</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Watchers */}
        <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <h2 className="text-sm font-medium text-slate-400 mb-3">Watchers ({upcomingWatchers.length})</h2>
          <div className="space-y-2">
            {upcomingWatchers.length === 0 ? (
              <p className="text-sm text-slate-500">No watchers triggered</p>
            ) : (
              upcomingWatchers.map((w, i) => (
                <div key={w.watcher_id || i} className="text-sm py-2 border-b border-slate-700 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 text-xs bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded font-medium">WATCH</span>
                    <span className="text-slate-300 cursor-pointer hover:text-blue-400" onClick={() => navigate({ to: '/issues' })}>
                      {w.issue_title || 'Watcher alert'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 ml-6 mt-1">
                    <div className="flex gap-1 ml-auto">
                      <button onClick={async (e) => { e.stopPropagation(); if (w.watcher_id) { await api.snoozeWatcher(w.watcher_id, 4); refetchWatchers(); } }} className="px-1.5 py-0.5 text-xs bg-slate-700 hover:bg-slate-600 rounded" title="Snooze 4h">4h</button>
                      <button onClick={async (e) => { e.stopPropagation(); if (w.watcher_id) { await api.snoozeWatcher(w.watcher_id, 24); refetchWatchers(); } }} className="px-1.5 py-0.5 text-xs bg-slate-700 hover:bg-slate-600 rounded" title="Snooze 24h">24h</button>
                      <button onClick={async (e) => { e.stopPropagation(); if (w.watcher_id) { await api.dismissWatcher(w.watcher_id); refetchWatchers(); } }} className="px-1.5 py-0.5 text-xs bg-red-900/50 hover:bg-red-800/50 text-red-300 rounded" title="Dismiss">✕</button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <FixDataSummary fixData={apiFixData || null} onClick={handleFixData} />
      </div>

      {selectedProposal && (
        <RoomDrawer
          open={drawerOpen}
          onClose={() => { setDrawerOpen(false); setSelectedProposal(null); }}
          proposal={selectedProposal}
          onTag={() => handleTag(selectedProposal)}
          onSnooze={() => handleSnooze(selectedProposal)}
          onDismiss={() => handleDismiss(selectedProposal)}
        />
      )}

      {selectedIssue && (
        <IssueDrawer
          open={issueDrawerOpen}
          issue={selectedIssue}
          onClose={() => { setIssueDrawerOpen(false); setSelectedIssue(null); }}
          onResolve={handleResolveIssue}
          onAddNote={handleAddIssueNote}
          onChangeState={handleChangeIssueState}
        />
      )}
    </div>
    </div>
  );
}
