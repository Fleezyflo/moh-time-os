// Team Member Detail page - Rich profile with workload visualization
import { useState } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import { RoomDrawer, IssueDrawer } from '../components';
import { priorityLabel, priorityBadgeClass } from '../lib/priority';
import { formatRelative } from '../lib/datetime';
import type { Proposal, Issue } from '../types/api';
import type { IssueState } from '../lib/api';
import { useTeam, useProposals, useIssues, useTasks } from '../lib/hooks';
import * as api from '../lib/api';

const taskPriorityColors: Record<string, string> = {
  urgent: 'text-red-400 bg-red-900/30',
  high: 'text-orange-400 bg-orange-900/30',
  medium: 'text-amber-400 bg-amber-900/30',
  low: 'text-slate-400 bg-slate-700',
};

const taskStatusIcons: Record<string, { icon: string; color: string }> = {
  open: { icon: '○', color: 'text-blue-400' },
  in_progress: { icon: '◐', color: 'text-purple-400' },
  blocked: { icon: '⊘', color: 'text-red-400' },
  done: { icon: '✓', color: 'text-green-400' },
  cancelled: { icon: '✗', color: 'text-slate-400' },
};

const loadLevels = {
  overloaded: { label: 'Overloaded', bg: 'bg-red-900/50', text: 'text-red-300' },
  high: { label: 'High Load', bg: 'bg-orange-900/50', text: 'text-orange-300' },
  normal: { label: 'Normal', bg: 'bg-green-900/50', text: 'text-green-300' },
  light: { label: 'Light', bg: 'bg-blue-900/50', text: 'text-blue-300' },
  idle: { label: 'Idle', bg: 'bg-slate-700', text: 'text-slate-400' },
};

function getLoadLevel(openTasks: number, overdue: number) {
  if (overdue > 5 || openTasks > 20) return loadLevels.overloaded;
  if (overdue > 2 || openTasks > 12) return loadLevels.high;
  if (openTasks > 5) return loadLevels.normal;
  if (openTasks > 0) return loadLevels.light;
  return loadLevels.idle;
}

export function TeamDetail() {
  const { id } = useParams({ from: '/team/$id' });
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [proposalDrawerOpen, setProposalDrawerOpen] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [issueDrawerOpen, setIssueDrawerOpen] = useState(false);

  const { data: apiTeam, loading: teamLoading } = useTeam();
  const { data: apiProposals, refetch: refetchProposals } = useProposals(
    20,
    'open',
    7,
    undefined,
    id
  );
  const { data: apiIssues, refetch: refetchIssues } = useIssues(20, 7, undefined, id);
  const { data: apiTasks } = useTasks(id, undefined, 20);

  const member = apiTeam?.items?.find((m) => m.id === id);

  if (teamLoading) return <div className="text-slate-400 p-8 text-center">Loading...</div>;
  if (!member) return <div className="text-slate-400 p-8 text-center">Team member not found</div>;

  const memberProposals = (apiProposals?.items || [])
    .filter((p) => p.status === 'open')
    .sort((a, b) => b.score - a.score);
  const memberIssues = (apiIssues?.items || [])
    .filter((i) => ['open', 'monitoring', 'awaiting', 'blocked'].includes(i.state))
    .slice(0, 5);
  const memberTasks = (apiTasks?.items || []).filter(
    (t) => t.status !== 'done' && t.status !== 'cancelled'
  );

  const load = getLoadLevel(member.open_tasks || 0, member.overdue_tasks || 0);
  const hasOverdue = (member.overdue_tasks || 0) > 0;

  const handleTag = async (proposal: Proposal) => {
    const result = await api.tagProposal(proposal.proposal_id ?? '');
    if (result.success) {
      refetchProposals();
      refetchIssues();
      setProposalDrawerOpen(false);
      setSelectedProposal(null);
    }
  };

  const handleSnooze = async (proposal: Proposal) => {
    const result = await api.snoozeProposal(proposal.proposal_id ?? '', 7);
    if (result.success) {
      refetchProposals();
      setProposalDrawerOpen(false);
      setSelectedProposal(null);
    }
  };

  const handleDismiss = async (proposal: Proposal) => {
    const result = await api.dismissProposal(proposal.proposal_id ?? '');
    if (result.success) {
      refetchProposals();
      setProposalDrawerOpen(false);
      setSelectedProposal(null);
    }
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

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link to="/team" className="text-slate-400 hover:text-slate-200 mb-2 inline-block">
          ← Team
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold">{member.name}</h1>
            <p className="text-slate-500">
              {member.role || member.department || 'Team Member'}
              {member.company && <span className="ml-2 text-slate-600">• {member.company}</span>}
            </p>
            {member.email && <p className="text-sm text-slate-500 mt-1">{member.email}</p>}
          </div>
          <span className={`px-3 py-1 rounded text-sm ${load.bg} ${load.text}`}>{load.label}</span>
        </div>
      </div>

      {/* Workload Stats Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
          <div className="text-2xl font-bold text-blue-400">{member.open_tasks || 0}</div>
          <div className="text-sm text-slate-400">Open Tasks</div>
        </div>
        <div
          className={`bg-slate-800 rounded-lg p-4 border ${hasOverdue ? 'border-red-900/50' : 'border-slate-700'}`}
        >
          <div className={`text-2xl font-bold ${hasOverdue ? 'text-red-400' : 'text-slate-400'}`}>
            {member.overdue_tasks || 0}
          </div>
          <div className="text-sm text-slate-400">Overdue</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4 border border-amber-900/50">
          <div className="text-2xl font-bold text-amber-400">{member.due_today || 0}</div>
          <div className="text-sm text-slate-400">Due Today</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4 border border-green-900/50">
          <div className="text-2xl font-bold text-green-400">{member.completed_this_week || 0}</div>
          <div className="text-sm text-slate-400">Done This Week</div>
        </div>
      </div>

      {/* Due Today Alert */}
      {(member.due_today || 0) > 0 && (
        <div className="mb-6 p-3 bg-amber-900/20 border border-amber-900/50 rounded-lg text-amber-300 text-sm">
          ⚡ <strong>{member.due_today} tasks due today</strong> — requires immediate attention
        </div>
      )}

      {/* Overdue Alert */}
      {hasOverdue && (
        <div className="mb-6 p-3 bg-red-900/20 border border-red-900/50 rounded-lg text-red-300 text-sm">
          🚨 <strong>{member.overdue_tasks} overdue tasks</strong> — escalation may be needed
        </div>
      )}

      {/* Client Association */}
      {member.client_name && (
        <div className="mb-6 p-3 bg-slate-800/50 border border-slate-700 rounded-lg">
          <span className="text-slate-400 text-sm">Primary Client: </span>
          <Link
            to="/clients/$clientId"
            params={{ clientId: member.client_id || '' }}
            className="text-blue-400 hover:text-blue-300"
          >
            {member.client_name}
          </Link>
        </div>
      )}

      {/* Task List */}
      <section className="mb-6 bg-slate-800/50 rounded-lg border border-slate-700 p-4">
        <h2 className="text-lg font-medium mb-4">Open Tasks ({memberTasks.length})</h2>
        {memberTasks.length === 0 ? (
          <p className="text-slate-500">No open tasks</p>
        ) : (
          <div className="space-y-2">
            {memberTasks.slice(0, 10).map((task) => {
              const statusStyle = taskStatusIcons[task.status] || taskStatusIcons.open;
              const priorityStyle = taskPriorityColors[task.priority] || taskPriorityColors.low;
              const isOverdue = task.due_date && new Date(task.due_date) < new Date();
              return (
                <div
                  key={task.id}
                  className={`flex items-center gap-3 p-3 bg-slate-800 rounded-lg border ${
                    isOverdue ? 'border-red-900/50' : 'border-slate-700'
                  }`}
                >
                  <span className={statusStyle.color}>{statusStyle.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-slate-200 truncate">{task.title}</div>
                    {task.due_date && (
                      <div className={`text-xs ${isOverdue ? 'text-red-400' : 'text-slate-500'}`}>
                        {isOverdue ? '⚠️ Overdue: ' : 'Due: '}
                        {formatRelative(task.due_date)}
                      </div>
                    )}
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded capitalize ${priorityStyle}`}>
                    {task.priority}
                  </span>
                </div>
              );
            })}
            {memberTasks.length > 10 && (
              <div className="text-center text-sm text-slate-500 pt-2">
                +{memberTasks.length - 10} more tasks
              </div>
            )}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Scoped Issues */}
        <section className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <h2 className="text-lg font-medium mb-4">Assigned Issues ({memberIssues.length})</h2>
          {memberIssues.length === 0 ? (
            <p className="text-slate-500">No assigned issues</p>
          ) : (
            <div className="space-y-3">
              {memberIssues.map((issue) => (
                <div
                  key={issue.issue_id}
                  onClick={() => {
                    setSelectedIssue(issue);
                    setIssueDrawerOpen(true);
                  }}
                  className="p-3 bg-slate-800 rounded-lg border border-slate-700 cursor-pointer hover:border-slate-600"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className={issue.state === 'open' ? 'text-blue-400' : 'text-amber-400'}>
                      ●
                    </span>
                    <h3 className="font-medium text-slate-200 truncate flex-1">{issue.headline}</h3>
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${priorityBadgeClass(issue.priority ?? 0)}`}
                    >
                      {priorityLabel(issue.priority ?? 0)
                        .charAt(0)
                        .toUpperCase() + priorityLabel(issue.priority ?? 0).slice(1)}
                    </span>
                  </div>
                  <p className="text-sm text-slate-500">
                    {issue.type ||
                      (issue as unknown as { issue_type?: string }).issue_type ||
                      'Issue'}
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Scoped Proposals */}
        <section className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <h2 className="text-lg font-medium mb-4">
            Relevant Proposals ({memberProposals.length})
          </h2>
          {memberProposals.length === 0 ? (
            <p className="text-slate-500">No relevant proposals</p>
          ) : (
            <div className="space-y-3">
              {memberProposals.slice(0, 5).map((p) => (
                <div
                  key={p.proposal_id}
                  onClick={() => {
                    setSelectedProposal(p);
                    setProposalDrawerOpen(true);
                  }}
                  className="p-3 bg-slate-800 rounded-lg border border-slate-700 cursor-pointer hover:border-slate-600"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-slate-200 truncate flex-1">{p.headline}</span>
                    <span className="text-xs text-slate-500 ml-2">Score: {p.score}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {selectedProposal && (
        <RoomDrawer
          open={proposalDrawerOpen}
          onClose={() => {
            setProposalDrawerOpen(false);
            setSelectedProposal(null);
          }}
          proposal={selectedProposal}
          onTag={() => handleTag(selectedProposal)}
          onSnooze={() => handleSnooze(selectedProposal)}
          onDismiss={() => handleDismiss(selectedProposal)}
        />
      )}

      <IssueDrawer
        issue={selectedIssue}
        open={issueDrawerOpen}
        onClose={() => {
          setIssueDrawerOpen(false);
          setSelectedIssue(null);
        }}
        onResolve={selectedIssue ? () => handleResolveIssue(selectedIssue) : undefined}
        onAddNote={selectedIssue ? (text) => handleAddIssueNote(selectedIssue, text) : undefined}
        onChangeState={
          selectedIssue ? (newState) => handleChangeIssueState(selectedIssue, newState) : undefined
        }
      />
    </div>
  );
}
