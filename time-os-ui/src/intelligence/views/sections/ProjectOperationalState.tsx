/**
 * ProjectOperationalState — Task metrics and completion status
 */

import { ProfileSection } from '../../components/ProfileSection';
import { DistributionChart } from '../../components/DistributionChart';
import { SeverityBadge } from '../../components/Badges';
import { STATUS_COLORS } from '../../components/chartColors';
import type { ProjectOperationalState as ProjectState } from '../../api';

interface ProjectOperationalStateProps {
  project: ProjectState;
}

interface MetricDisplayProps {
  label: string;
  value: string | number;
  warning?: boolean;
}

function MetricDisplay({ label, value, warning }: MetricDisplayProps) {
  return (
    <div className="p-3 bg-[var(--grey-dim)] rounded-lg text-center">
      <div className={`text-2xl font-bold ${warning ? 'text-red-400' : 'text-white'}`}>{value}</div>
      <div className="text-xs text-[var(--grey-muted)] mt-1">{label}</div>
    </div>
  );
}

export function ProjectOperationalState({ project }: ProjectOperationalStateProps) {
  const totalTasks = project.total_tasks || 0;
  const openTasks = project.open_tasks || 0;
  const completedTasks = project.completed_tasks || 0;
  const overdueTasks = project.overdue_tasks || 0;
  const completionRate = project.completion_rate_pct || 0;
  const assignedPeople = project.assigned_people || 0;

  const hasOverdue = overdueTasks > 0;

  // Task distribution segments
  const taskSegments = [
    { label: 'Completed', value: completedTasks, color: STATUS_COLORS.completed },
    { label: 'Open', value: openTasks - overdueTasks, color: STATUS_COLORS.open },
    { label: 'Overdue', value: overdueTasks, color: STATUS_COLORS.overdue },
  ].filter((s) => s.value > 0);

  return (
    <ProfileSection
      title="Operational State"
      description="Current task status and team allocation."
      badge={hasOverdue ? <SeverityBadge severity="warning" /> : undefined}
    >
      {/* Metrics grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <MetricDisplay label="Total Tasks" value={totalTasks} />
        <MetricDisplay label="Open" value={openTasks} />
        <MetricDisplay label="Completed" value={completedTasks} />
        <MetricDisplay label="Overdue" value={overdueTasks} warning={hasOverdue} />
        <MetricDisplay label="Completion" value={`${Math.round(completionRate)}%`} />
        <MetricDisplay label="Team Size" value={assignedPeople} />
      </div>

      {/* Task distribution bar */}
      {totalTasks > 0 && (
        <div>
          <div className="text-xs text-[var(--grey-muted)] mb-2">Task Distribution</div>
          <DistributionChart segments={taskSegments} height={24} />
        </div>
      )}

      {/* Overdue warning */}
      {hasOverdue && (
        <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
          <span className="text-sm text-red-400">
            {overdueTasks} task{overdueTasks > 1 ? 's' : ''} overdue — requires immediate attention
          </span>
        </div>
      )}
    </ProfileSection>
  );
}
