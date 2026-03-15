// Project Enrollment page — candidates, enrolled, detected projects (Phase 12)
import { useState, useCallback, useMemo } from 'react';
import { SkeletonCardList, ErrorState } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { CandidateList } from '../components/enrollment/CandidateList';
import { DetectedProjectsAlert } from '../components/enrollment/DetectedProjectsAlert';
import { EnrollmentActionBar } from '../components/enrollment/EnrollmentActionBar';
import {
  useProjectCandidates,
  useProjectsEnrolled,
  useDetectedProjects,
  useLinkingStats,
} from '../lib/hooks';
import { processEnrollment, syncXero, proposeProject } from '../lib/api';
import type { EnrolledProject } from '../lib/api';

type EnrollmentTab = 'candidates' | 'enrolled';

const BASE_TABS: TabDef<EnrollmentTab>[] = [
  { id: 'candidates', label: 'Candidates' },
  { id: 'enrolled', label: 'Enrolled' },
];

function ProjectEnrollment() {
  const [activeTab, setActiveTab] = useState<EnrollmentTab>('candidates');
  const [showDetected, setShowDetected] = useState(true);
  const [syncLoading, setSyncLoading] = useState(false);

  const {
    data: candidatesData,
    loading: candidatesLoading,
    error: candidatesError,
    refetch: refetchCandidates,
  } = useProjectCandidates();

  const {
    data: enrolledData,
    loading: enrolledLoading,
    error: enrolledError,
    refetch: refetchEnrolled,
  } = useProjectsEnrolled();

  const { data: detectedData } = useDetectedProjects();

  const { data: linkingStats } = useLinkingStats();

  const candidates = useMemo(() => candidatesData?.items ?? [], [candidatesData]);

  const retainers = useMemo(() => enrolledData?.retainers ?? [], [enrolledData]);

  const enrolledProjects = useMemo(() => enrolledData?.projects ?? [], [enrolledData]);

  const detected = useMemo(() => detectedData?.detected ?? [], [detectedData]);

  const totalEnrolled = enrolledData != null ? (enrolledData.total ?? 0) : null;
  const totalCandidates = candidatesData != null ? (candidatesData.total ?? 0) : null;
  const linkRate = linkingStats != null ? (linkingStats.link_rate ?? 0) : null;
  const detectedCount = detected.length;

  const tabsWithBadges = useMemo(
    () =>
      BASE_TABS.map((tab) => ({
        ...tab,
        badge: tab.id === 'candidates' ? (totalCandidates ?? 0) : (totalEnrolled ?? 0),
      })),
    [totalCandidates, totalEnrolled]
  );

  const handleEnroll = useCallback(
    async (projectId: string) => {
      await processEnrollment(projectId, { action: 'enroll' });
      refetchCandidates();
      refetchEnrolled();
    },
    [refetchCandidates, refetchEnrolled]
  );

  const handleReject = useCallback(
    async (projectId: string) => {
      await processEnrollment(projectId, { action: 'reject' });
      refetchCandidates();
    },
    [refetchCandidates]
  );

  const handleSnooze = useCallback(
    async (projectId: string) => {
      await processEnrollment(projectId, {
        action: 'snooze',
        snooze_days: 7,
      });
      refetchCandidates();
    },
    [refetchCandidates]
  );

  const handleSyncXero = useCallback(async () => {
    setSyncLoading(true);
    try {
      await syncXero();
      refetchEnrolled();
      refetchCandidates();
    } finally {
      setSyncLoading(false);
    }
  }, [refetchEnrolled, refetchCandidates]);

  const handlePropose = useCallback(
    async (name: string, clientId?: string, type?: string) => {
      await proposeProject({ name, client_id: clientId, type });
      refetchCandidates();
    },
    [refetchCandidates]
  );

  const loading = candidatesLoading || enrolledLoading;
  const error = candidatesError || enrolledError;

  if (loading) {
    return (
      <PageLayout title="Project Enrollment">
        <SkeletonCardList count={4} />
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout title="Project Enrollment">
        <ErrorState
          error={error}
          onRetry={() => {
            refetchCandidates();
            refetchEnrolled();
          }}
          hasData={false}
        />
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title="Project Enrollment"
      subtitle={totalEnrolled != null && totalCandidates != null ? `${totalEnrolled} enrolled, ${totalCandidates} candidates` : 'Loading...'}
      actions={
        <EnrollmentActionBar
          onSyncXero={handleSyncXero}
          onPropose={handlePropose}
          syncLoading={syncLoading}
        />
      }
    >
      <SummaryGrid>
        <MetricCard label="Enrolled" value={totalEnrolled ?? '--'} severity={totalEnrolled != null ? 'info' : undefined} />
        <MetricCard
          label="Candidates"
          value={totalCandidates ?? '--'}
          severity={totalCandidates != null && totalCandidates > 0 ? 'warning' : totalCandidates != null ? 'success' : undefined}
        />
        <MetricCard
          label="Detected"
          value={detectedCount}
          severity={detectedCount > 0 ? 'warning' : 'success'}
        />
        <MetricCard
          label="Link Rate"
          value={linkRate != null ? `${linkRate}%` : '--'}
          severity={linkRate != null ? (linkRate >= 80 ? 'success' : linkRate >= 50 ? 'warning' : 'danger') : undefined}
        />
      </SummaryGrid>

      {showDetected && detected.length > 0 && (
        <DetectedProjectsAlert detected={detected} onDismiss={() => setShowDetected(false)} />
      )}

      <TabContainer tabs={tabsWithBadges} activeTab={activeTab} onTabChange={setActiveTab}>
        {(tab) => {
          if (tab === 'candidates') {
            return (
              <CandidateList
                candidates={candidates}
                onEnroll={handleEnroll}
                onReject={handleReject}
                onSnooze={handleSnooze}
              />
            );
          }

          return <EnrolledList retainers={retainers} projects={enrolledProjects} />;
        }}
      </TabContainer>
    </PageLayout>
  );
}

// Enrolled projects split into retainers and projects
function EnrolledList({
  retainers,
  projects,
}: {
  retainers: EnrolledProject[];
  projects: EnrolledProject[];
}) {
  if (retainers.length === 0 && projects.length === 0) {
    return (
      <div className="text-center py-8 text-[var(--grey-muted)]">
        No enrolled projects yet. Enroll candidates from the Candidates tab.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {retainers.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-[var(--grey-light)] mb-2">
            Retainers ({retainers.length})
          </h3>
          <div className="space-y-2">
            {retainers.map((p) => (
              <EnrolledRow key={p.id} project={p} />
            ))}
          </div>
        </div>
      )}

      {projects.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-[var(--grey-light)] mb-2">
            Projects ({projects.length})
          </h3>
          <div className="space-y-2">
            {projects.map((p) => (
              <EnrolledRow key={p.id} project={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EnrolledRow({ project }: { project: EnrolledProject }) {
  const hasOverdue = project.overdue_tasks > 0;

  return (
    <div className="card p-4 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <span className="w-2 h-2 rounded-full shrink-0 bg-green-400" />
        <div className="min-w-0">
          <div className="font-medium truncate">{project.name}</div>
          <div className="text-xs text-[var(--grey-light)] flex gap-2 mt-0.5">
            {project.client_name && (
              <span>
                {project.client_name}
                {project.client_tier && (
                  <span className="ml-1 text-[var(--grey-muted)]">({project.client_tier})</span>
                )}
              </span>
            )}
            <span className="capitalize">{project.involvement_type}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs shrink-0">
        <span className="text-[var(--grey-light)]">{project.open_tasks} open</span>
        {hasOverdue && (
          <span className="text-red-400 font-medium">{project.overdue_tasks} overdue</span>
        )}
      </div>
    </div>
  );
}

export default ProjectEnrollment;
