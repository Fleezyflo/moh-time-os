// TaskList page — Task management with filter, group, and delegation views
import { useState, useCallback } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { SkeletonCardList, ErrorState, NoTasks } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { TaskCard } from '../components/tasks/TaskCard';
import { useTasks, useDelegations } from '../lib/hooks';
import type { Task } from '../types/api';

type TaskTab = 'all' | 'active' | 'blocked' | 'delegated' | 'completed';

const TABS: TabDef<TaskTab>[] = [
  { id: 'all', label: 'All Tasks' },
  { id: 'active', label: 'Active' },
  { id: 'blocked', label: 'Blocked' },
  { id: 'delegated', label: 'Delegated' },
  { id: 'completed', label: 'Completed' },
];

function filterByTab(tasks: Task[], tab: TaskTab): Task[] {
  switch (tab) {
    case 'active':
      return tasks.filter((t) => t.status === 'pending' || t.status === 'in_progress');
    case 'blocked':
      return tasks.filter((t) => t.status === 'blocked');
    case 'delegated':
      return tasks.filter((t) => !!t.delegated_by);
    case 'completed':
      return tasks.filter((t) => t.status === 'completed' || t.status === 'done');
    default:
      return tasks;
  }
}

export default function TaskList() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch all tasks (unfiltered, server-side)
  const {
    data: taskData,
    loading: taskLoading,
    error: taskError,
    refetch: refetchTasks,
  } = useTasks(undefined, undefined, undefined, 100);

  // Fetch delegations
  const { data: delegationData } = useDelegations();

  const allTasks = taskData?.items || [];

  // Client-side search filter
  const filteredTasks = searchQuery.trim()
    ? allTasks.filter(
        (t) =>
          t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (t.assignee || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
          (t.project || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : allTasks;

  // Derive counts
  const totalCount = allTasks.length;
  const activeCount = allTasks.filter(
    (t) => t.status === 'pending' || t.status === 'in_progress'
  ).length;
  const blockedCount = allTasks.filter((t) => t.status === 'blocked').length;
  const overdueCount = allTasks.filter((t) => {
    if (!t.due_date) return false;
    return new Date(t.due_date) < new Date();
  }).length;
  const delegatedByMe = delegationData?.delegated_by_me?.length || 0;

  // Tab badges
  const tabsWithBadges: TabDef<TaskTab>[] = TABS.map((tab) => {
    const count = filterByTab(filteredTasks, tab.id).length;
    return { ...tab, badge: count };
  });

  const handleTaskClick = useCallback(
    (task: Task) => {
      navigate({ to: '/tasks/$taskId', params: { taskId: task.id } });
    },
    [navigate]
  );

  if (taskLoading) return <SkeletonCardList count={6} />;
  if (taskError) return <ErrorState error={taskError} onRetry={refetchTasks} hasData={false} />;

  return (
    <PageLayout
      title="Tasks"
      subtitle={`${totalCount} tasks across all projects`}
      actions={
        <input
          type="text"
          placeholder="Search tasks..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] placeholder-[var(--grey-muted)] w-48 sm:w-64"
        />
      }
    >
      <SummaryGrid>
        <MetricCard label="Total Tasks" value={totalCount} />
        <MetricCard
          label="Active"
          value={activeCount}
          severity={activeCount > 0 ? 'info' : undefined}
        />
        <MetricCard
          label="Blocked"
          value={blockedCount}
          severity={blockedCount > 0 ? 'danger' : 'success'}
        />
        <MetricCard
          label="Overdue"
          value={overdueCount}
          severity={overdueCount > 0 ? 'warning' : 'success'}
        />
      </SummaryGrid>

      {delegatedByMe > 0 && (
        <div className="mb-4 p-3 rounded bg-[var(--accent)]/10 border border-[var(--accent)]/20">
          <p className="text-sm text-[var(--accent)]">
            You have {delegatedByMe} task{delegatedByMe !== 1 ? 's' : ''} delegated to others
          </p>
        </div>
      )}

      <TabContainer tabs={tabsWithBadges} defaultTab="all">
        {(activeTab) => {
          const visibleTasks = filterByTab(filteredTasks, activeTab);

          if (visibleTasks.length === 0) {
            if (searchQuery) {
              return (
                <p className="text-sm text-[var(--grey-muted)] py-8 text-center">
                  No tasks matching &ldquo;{searchQuery}&rdquo;
                </p>
              );
            }
            return <NoTasks />;
          }

          return (
            <div className="space-y-2">
              {visibleTasks.map((task) => (
                <TaskCard key={task.id} task={task} onClick={handleTaskClick} />
              ))}
            </div>
          );
        }}
      </TabContainer>
    </PageLayout>
  );
}
