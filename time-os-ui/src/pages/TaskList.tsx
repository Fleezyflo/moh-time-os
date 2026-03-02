// TaskList page — Task management with filter, group, and delegation views
import { useState } from 'react';
import { SkeletonCardList, ErrorState, NoTasks } from '../components';
import ExportButton from '../components/ExportButton';
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

// Status values from Asana collector: "active", "overdue", "completed"
// Status values from manual/API: "pending", "in_progress", "blocked", "done", "cancelled", "archived"
const ACTIVE_STATUSES = ['active', 'pending', 'in_progress'];
const BLOCKED_STATUSES = ['blocked', 'overdue'];
const COMPLETED_STATUSES = ['completed', 'done'];

function isOverdue(task: Task): boolean {
  if (!task.due_date) return false;
  if (task.status === 'overdue') return true;
  const due = new Date(task.due_date);
  return due < new Date() && !COMPLETED_STATUSES.includes(task.status);
}

function filterByTab(tasks: Task[], tab: TaskTab): Task[] {
  switch (tab) {
    case 'active':
      return tasks.filter((t) => ACTIVE_STATUSES.includes(t.status));
    case 'blocked':
      return tasks.filter((t) => BLOCKED_STATUSES.includes(t.status));
    case 'delegated':
      return tasks.filter((t) => !!t.delegated_by);
    case 'completed':
      return tasks.filter((t) => COMPLETED_STATUSES.includes(t.status));
    default:
      return tasks;
  }
}

export default function TaskList() {
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

  // Derive counts using same status groupings as tab filters
  const totalCount = allTasks.length;
  const activeCount = allTasks.filter((t) => ACTIVE_STATUSES.includes(t.status)).length;
  const blockedCount = allTasks.filter((t) => BLOCKED_STATUSES.includes(t.status)).length;
  const overdueCount = allTasks.filter((t) => isOverdue(t)).length;
  const delegatedByMe = delegationData?.delegated_by_me?.length || 0;

  // Tab badges
  const tabsWithBadges: TabDef<TaskTab>[] = TABS.map((tab) => {
    const count = filterByTab(filteredTasks, tab.id).length;
    return { ...tab, badge: count };
  });

  if (taskLoading) return <SkeletonCardList count={6} />;
  if (taskError) return <ErrorState error={taskError} onRetry={refetchTasks} hasData={false} />;

  return (
    <PageLayout
      title="Tasks"
      subtitle={`${totalCount} tasks across all projects`}
      actions={
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Search tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] placeholder-[var(--grey-muted)] w-48 sm:w-64"
          />
          <ExportButton
            data={filteredTasks}
            filename="tasks"
            columns={['id', 'title', 'status', 'priority', 'assignee', 'due_date', 'project']}
          />
        </div>
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
                <TaskCard key={task.id} task={task} />
              ))}
            </div>
          );
        }}
      </TabContainer>
    </PageLayout>
  );
}
