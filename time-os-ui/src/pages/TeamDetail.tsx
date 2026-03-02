// Team Member Detail page - Rich profile with workload visualization
import { useState } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import { RoomDrawer, IssueDrawer, SkeletonCardList } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { priorityLabel, priorityBadgeClass } from '../lib/priority';
import { formatRelative } from '../lib/datetime';
import type { Proposal, Issue } from '../types/api';
import type { IssueState } from '../lib/api';
import { useTeam, useProposals, useIssues, useTasks, usePersonCalendarDetail } from '../lib/hooks';
import { usePersonTrajectory } from '../intelligence/hooks';
import { TrajectorySparkline } from '../components/layout/TrajectorySparkline';
import * as api from '../lib/api';

const taskPriorityColors: Record<string, string> = {
  urgent: 'text-[var(--danger)] bg-red-900/30',
  high: 'text-[var(--warning)] bg-orange-900/30',
  medium: 'text-amber-400 bg-[var(--warning)]/30',
  normal: 'text-amber-400 bg-[var(--warning)]/30',
  low: 'text-[var(--grey-light)] bg-[var(--grey)]',
};

const taskStatusIcons: Record<string, { icon: string; color: string }> = {
  active: { icon: '○', color: 'text-[var(--info)]' },
  open: { icon: '○', color: 'text-[var(--info)]' },
  pending: { icon: '○', color: 'text-[var(--grey-light)]' },
  in_progress: { icon: '◐', color: 'text-purple-400' },
  overdue: { icon: '⚠', color: 'text-[var(--danger)]' },
  blocked: { icon: '⊘', color: 'text-[var(--danger)]' },
  completed: { icon: '✓', color: 'text-[var(--success)]' },
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
  const { data: apiTasks } = useTasks(id, undefined, undefined, 20);

  // Trajectory sparkline data — must be before early returns (React hooks rule)
  const { data: trajectoryData } = usePersonTrajectory(id);
  const trajectoryPoints = (trajectoryData?.windows || []).map((w) => ({
    date: w.start,
    value: w.metrics?.composite_score ?? w.metrics?.performance_score ?? 0,
  }));

  // Calendar detail data for tabs (Phase 13)
  const { data: calendarDetail } = usePersonCalendarDetail(id);

  const member = apiTeam?.items?.find((m) => m.id === id);

  if (teamLoading) return <SkeletonCardList count={3} />;
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

  const actions = (
    <Link to="/team" className="text-[var(--grey-light)] hover:text-[var(--white)]">
      ← Team
    </Link>
  );

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

  // Tab definitions for Phase 13 depth tabs
  const overviewTabs: TabDef<'overview' | 'calendar'>[] = [
    { id: 'overview', label: 'Overview' },
    {
      id: 'calendar',
      label: 'Calendar Detail',
      badge: (calendarDetail?.total_attendees ?? 0) + (calendarDetail?.total_recurrence ?? 0),
    },
  ];

  return (
    <PageLayout title={member.name} actions={actions}>
      <SummaryGrid>
        <MetricCard label="Open Tasks" value={(member.open_tasks || 0).toString()} />
        <MetricCard
          label="Overdue"
          value={(member.overdue_tasks || 0).toString()}
          severity={hasOverdue ? 'danger' : undefined}
        />
        <MetricCard label="Due Today" value={(member.due_today || 0).toString()} />
        <MetricCard
          label="Done This Week"
          value={(member.completed_this_week || 0).toString()}
          severity="success"
        />
      </SummaryGrid>

      {/* Tabbed content - Overview and Calendar Detail */}
      <TabContainer<'overview' | 'calendar'> tabs={overviewTabs} defaultTab="overview">
        {(activeTab) =>
          activeTab === 'overview' ? (
            <>
              {/* Member Details */}
              <div className="bg-[var(--grey-dim)] rounded-lg p-4 mb-6">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[var(--grey)] mb-2">
                      {member.role || member.department || 'Team Member'}
                      {member.company && (
                        <span className="ml-2 text-[var(--grey-light)]">• {member.company}</span>
                      )}
                    </p>
                    {member.email && <p className="text-sm text-[var(--grey)]">{member.email}</p>}
                    <div className="mt-3">
                      <span className={`px-3 py-1 rounded text-sm ${load.bg} ${load.text}`}>
                        {load.label}
                      </span>
                    </div>
                  </div>
                  {trajectoryPoints.length >= 2 && (
                    <div className="flex flex-col items-end">
                      <span className="text-xs text-[var(--grey-light)] mb-1">Trajectory</span>
                      <TrajectorySparkline
                        data={trajectoryPoints}
                        width={140}
                        height={36}
                        showArea
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Due Today Alert */}
              {(member.due_today || 0) > 0 && (
                <div className="mb-6 p-3 bg-amber-900/20 border border-amber-900/50 rounded-lg text-[var(--warning)] text-sm">
                  ⚡ <strong>{member.due_today} tasks due today</strong> — requires immediate
                  attention
                </div>
              )}

              {/* Overdue Alert */}
              {hasOverdue && (
                <div className="mb-6 p-3 bg-red-900/20 border border-[var(--danger)]/50 rounded-lg text-[var(--danger)] text-sm">
                  🚨 <strong>{member.overdue_tasks} overdue tasks</strong> — escalation may be
                  needed
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
              <section className="mb-6 bg-[var(--grey-dim)] rounded-lg p-4">
                <h2 className="text-lg font-medium mb-4">Open Tasks ({memberTasks.length})</h2>
                {memberTasks.length === 0 ? (
                  <p className="text-[var(--grey)]">No open tasks</p>
                ) : (
                  <div className="space-y-2">
                    {memberTasks.slice(0, 10).map((task) => {
                      const statusStyle = taskStatusIcons[task.status] || taskStatusIcons.open;
                      const priorityStyle =
                        taskPriorityColors[String(task.priority)] || taskPriorityColors.low;
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
                          <span
                            className={`text-xs px-2 py-0.5 rounded capitalize ${priorityStyle}`}
                          >
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
                <section className="bg-[var(--grey-dim)] rounded-lg p-4">
                  <h2 className="text-lg font-medium mb-4">
                    Assigned Issues ({memberIssues.length})
                  </h2>
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
                              className={
                                issue.state === 'open' ? 'text-[var(--info)]' : 'text-amber-400'
                              }
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
                <section className="bg-[var(--grey-dim)] rounded-lg p-4">
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
                            <span className="text-[var(--white)] truncate flex-1">
                              {p.headline}
                            </span>
                            <span className="text-xs text-[var(--grey)] ml-2">
                              Score: {p.score}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            </>
          ) : (
            <>
              {/* Calendar Detail Tab */}
              <div className="space-y-6">
                {/* Attendees Section */}
                <section className="bg-[var(--grey-dim)] rounded-lg p-4">
                  <h2 className="text-lg font-medium mb-4">
                    Calendar Attendees ({calendarDetail?.total_attendees ?? 0})
                  </h2>
                  {!calendarDetail || calendarDetail.attendees.length === 0 ? (
                    <p className="text-[var(--grey-light)]">
                      No calendar detail data available. Run the Calendar collector to populate.
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-[var(--grey)]">
                            <th className="text-left px-3 py-2 text-[var(--grey-light)]">Email</th>
                            <th className="text-left px-3 py-2 text-[var(--grey-light)]">
                              Display Name
                            </th>
                            <th className="text-left px-3 py-2 text-[var(--grey-light)]">
                              Response Status
                            </th>
                            <th className="text-center px-3 py-2 text-[var(--grey-light)]">
                              Organizer
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {calendarDetail.attendees.map((attendee, idx) => (
                            <tr key={idx} className="border-b border-[var(--grey)]/20">
                              <td className="px-3 py-2 text-[var(--white)]">{attendee.email}</td>
                              <td className="px-3 py-2 text-[var(--grey-light)]">
                                {attendee.display_name || '--'}
                              </td>
                              <td className="px-3 py-2 text-[var(--grey-light)]">
                                {attendee.response_status || '--'}
                              </td>
                              <td className="px-3 py-2 text-center">
                                {attendee.organizer === 1 ? (
                                  <span className="text-[var(--success)]">✓</span>
                                ) : (
                                  <span className="text-[var(--grey)]">—</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                {/* Recurrence Rules Section */}
                <section className="bg-[var(--grey-dim)] rounded-lg p-4">
                  <h2 className="text-lg font-medium mb-4">
                    Recurrence Rules ({calendarDetail?.total_recurrence ?? 0})
                  </h2>
                  {!calendarDetail || calendarDetail.recurrence.length === 0 ? (
                    <p className="text-[var(--grey-light)]">
                      No recurrence rules. Run the Calendar collector to populate.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {calendarDetail.recurrence.map((rule, idx) => (
                        <div
                          key={idx}
                          className="p-3 bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)]"
                        >
                          <div className="text-xs text-[var(--grey-light)] mb-1">Event ID</div>
                          <div className="text-sm text-[var(--white)] font-mono mb-2">
                            {rule.event_id}
                          </div>
                          <div className="text-xs text-[var(--grey-light)] mb-1">Rule</div>
                          <div className="text-sm text-[var(--white)] font-mono">{rule.rrule}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            </>
          )
        }
      </TabContainer>

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
    </PageLayout>
  );
}

export default TeamDetail;
