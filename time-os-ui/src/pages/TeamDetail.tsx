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
  urgent: 'text-[var(--danger)] bg-red-900/30',
  high: 'text-[var(--warning)] bg-orange-900/30',
  medium: 'text-amber-400 bg-[var(--warning)]/30',
  low: 'text-[var(--grey-light)] bg-[var(--grey)]',
};

const taskStatusIcons: Record<string, { icon: string; color: string }> = {
  open: { icon: '○', color: 'text-[var(--info)]' },
  in_progress: { icon: '◐', color: 'text-purple-400' },
  blocked: { icon: '⊘', color: 'text-[var(--danger)]' },
  done: { icon: '✓', color: 'text-[var(--success)]' },
  cancelled: { icon: '✗', color: 'text-[var(--grey-light)]' },
};

const loadLevels = {
  overloaded: { label: 'Overloaded', bg: 'bg-[var(--danger)]/20', text: 'text-[var(--danger)]' },
  high: { label: 'High Load', bg: 'bg-[var(--warning)]/20', text: 'text-[var(--warning)]' },
  normal: { label: 'Normal', bg: 'bg-[var(--success)]/20', text: 'text-[var(--success)]' },
  light: { label: 'Light', bg: 'bg-[var(--info)]/20', text: 'text-[var(--info)]' },
  idle: { label: 'Idle', bg: 'bg-[var(--grey)]', text: 'text-[var(--grey-light)]' },
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

  if (teamLoading)
    return <div className="text-[var(--grey-light)] p-8 text-center">Loading...</div>;
  if (!member)
    return <div className="text-[var(--grey-light)] p-8 text-center">Team member not found</div>;

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
        <Link
          to="/team"
          className="text-[var(--grey-light)] hover:text-[var(--white)] mb-2 inline-block"
        >
          ← Team
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold">{member.name}</h1>
            <p className="text-[var(--grey)]">
              {member.role || member.department || 'Team Member'}
              {member.company && (
                <span className="ml-2 text-[var(--grey-light)]">• {member.company}</span>
              )}
            </p>
            {member.email && <p className="text-sm text-[var(--grey)] mt-1">{member.email}</p>}
          </div>
          <span className={`px-3 py-1 rounded text-sm ${load.bg} ${load.text}`}>{load.label}</span>
        </div>
      </div>

      {/* Workload Stats Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-[var(--grey)]">
          <div className="text-2xl font-bold text-[var(--info)]">{member.open_tasks || 0}</div>
          <div className="text-sm text-[var(--grey-light)]">Open Tasks</div>
        </div>
        <div
          className={`bg-[var(--grey-dim)] rounded-lg p-4 border ${hasOverdue ? 'border-[var(--danger)]/50' : 'border-[var(--grey)]'}`}
        >
          <div
            className={`text-2xl font-bold ${hasOverdue ? 'text-[var(--danger)]' : 'text-[var(--grey-light)]'}`}
          >
            {member.overdue_tasks || 0}
          </div>
          <div className="text-sm text-[var(--grey-light)]">Overdue</div>
        </div>
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-amber-900/50">
          <div className="text-2xl font-bold text-amber-400">{member.due_today || 0}</div>
          <div className="text-sm text-[var(--grey-light)]">Due Today</div>
        </div>
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-green-900/50">
          <div className="text-2xl font-bold text-[var(--success)]">
            {member.completed_this_week || 0}
          </div>
          <div className="text-sm text-[var(--grey-light)]">Done This Week</div>
        </div>
      </div>

      {/* Due Today Alert */}
      {(member.due_today || 0) > 0 && (
        <div className="mb-6 p-3 bg-amber-900/20 border border-amber-900/50 rounded-lg text-[var(--warning)] text-sm">
          ⚡ <strong>{member.due_today} tasks due today</strong> — requires immediate attention
        </div>
      )}

      {/* Overdue Alert */}
      {hasOverdue && (
        <div className="mb-6 p-3 bg-red-900/20 border border-[var(--danger)]/50 rounded-lg text-[var(--danger)] text-sm">
          🚨 <strong>{member.overdue_tasks} overdue tasks</strong> — escalation may be needed
        </div>
      )}

      {/* Client Association */}
      {member.client_name && (
        <div className="mb-6 p-3 bg-[var(--grey-dim)]/50 border border-[var(--grey)] rounded-lg">
          <span className="text-[var(--grey-light)] text-sm">Primary Client: </span>
          <Link
            to="/clients/$clientId"
            params={{ clientId: member.client_id || '' }}
            className="text-[var(--info)] hover:text-[var(--info)]"
          >
            {member.client_name}
          </Link>
        </div>
      )}

      {/* Task List */}
      <section className="mb-6 bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)] p-4">
        <h2 className="text-lg font-medium mb-4">Open Tasks ({memberTasks.length})</h2>
        {memberTasks.length === 0 ? (
          <p className="text-[var(--grey)]">No open tasks</p>
        ) : (
          <div className="space-y-2">
            {memberTasks.slice(0, 10).map((task) => {
              const statusStyle = taskStatusIcons[task.status] || taskStatusIcons.open;
              const priorityStyle = taskPriorityColors[task.priority] || taskPriorityColors.low;
              const isOverdue = task.due_date && new Date(task.due_date) < new Date();
              return (
                <div
                  key={task.id}
                  className={`flex items-center gap-3 p-3 bg-[var(--grey-dim)] rounded-lg border ${
                    isOverdue ? 'border-[var(--danger)]/50' : 'border-[var(--grey)]'
                  }`}
                >
                  <span className={statusStyle.color}>{statusStyle.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[var(--white)] truncate">{task.title}</div>
                    {task.due_date && (
                      <div
                        className={`text-xs ${isOverdue ? 'text-[var(--danger)]' : 'text-[var(--grey)]'}`}
                      >
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
              <div className="text-center text-sm text-[var(--grey)] pt-2">
                +{memberTasks.length - 10} more tasks
              </div>
            )}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Scoped Issues */}
        <section className="bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)] p-4">
          <h2 className="text-lg font-medium mb-4">Assigned Issues ({memberIssues.length})</h2>
          {memberIssues.length === 0 ? (
            <p className="text-[var(--grey)]">No assigned issues</p>
          ) : (
            <div className="space-y-3">
              {memberIssues.map((issue) => (
                <div
                  key={issue.issue_id}
                  onClick={() => {
                    setSelectedIssue(issue);
                    setIssueDrawerOpen(true);
                  }}
                  className="p-3 bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)] cursor-pointer hover:border-[var(--grey-light)]"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className={issue.state === 'open' ? 'text-[var(--info)]' : 'text-amber-400'}
                    >
                      ●
                    </span>
                    <h3 className="font-medium text-[var(--white)] truncate flex-1">
                      {issue.headline}
                    </h3>
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${priorityBadgeClass(issue.priority ?? 0)}`}
                    >
                      {priorityLabel(issue.priority ?? 0)
                        .charAt(0)
                        .toUpperCase() + priorityLabel(issue.priority ?? 0).slice(1)}
                    </span>
                  </div>
                  <p className="text-sm text-[var(--grey)]">
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
        <section className="bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)] p-4">
          <h2 className="text-lg font-medium mb-4">
            Relevant Proposals ({memberProposals.length})
          </h2>
          {memberProposals.length === 0 ? (
            <p className="text-[var(--grey)]">No relevant proposals</p>
          ) : (
            <div className="space-y-3">
              {memberProposals.slice(0, 5).map((p) => (
                <div
                  key={p.proposal_id}
                  onClick={() => {
                    setSelectedProposal(p);
                    setProposalDrawerOpen(true);
                  }}
                  className="p-3 bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)] cursor-pointer hover:border-[var(--grey-light)]"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--white)] truncate flex-1">{p.headline}</span>
                    <span className="text-xs text-[var(--grey)] ml-2">Score: {p.score}</span>
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

export default TeamDetail;
