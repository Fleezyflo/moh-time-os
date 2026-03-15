// Commitments page — list, summary, untracked alert, due view (Phase 9)
import { useState, useCallback, useMemo } from 'react';
import { SkeletonCardList, ErrorState } from '../components';
import ExportButton from '../components/ExportButton';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { CommitmentList } from '../components/commitments/CommitmentList';
import { LinkToTaskDialog } from '../components/commitments/LinkToTaskDialog';
import {
  useCommitments,
  useUntrackedCommitments,
  useCommitmentsDue,
  useCommitmentsSummary,
} from '../lib/hooks';
import { linkCommitment, markCommitmentDone } from '../lib/api';
import type { Commitment } from '../lib/api';

type CommitmentTab = 'all' | 'untracked' | 'due';

const COMMITMENT_TABS: TabDef<CommitmentTab>[] = [
  { id: 'all', label: 'All' },
  { id: 'untracked', label: 'Untracked' },
  { id: 'due', label: 'Due Soon' },
];

function todayString(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function Commitments() {
  const [dialogCommitment, setDialogCommitment] = useState<Commitment | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  const {
    data: commitmentsData,
    loading: commitmentsLoading,
    error: commitmentsError,
    refetch: refetchCommitments,
  } = useCommitments(statusFilter);

  const {
    data: untrackedData,
    loading: untrackedLoading,
    error: untrackedError,
    refetch: refetchUntracked,
  } = useUntrackedCommitments();

  const {
    data: dueData,
    loading: dueLoading,
    error: dueError,
    refetch: refetchDue,
  } = useCommitmentsDue(todayString());

  const { data: summaryData } = useCommitmentsSummary();

  const allCommitments = useMemo(() => commitmentsData?.commitments ?? [], [commitmentsData]);
  const untrackedCommitments = useMemo(() => untrackedData?.commitments ?? [], [untrackedData]);
  const dueCommitments = useMemo(() => dueData?.commitments ?? [], [dueData]);

  const totalCount = commitmentsData != null ? (commitmentsData.total ?? 0) : null;
  const untrackedCount = untrackedData != null ? (untrackedData.total ?? 0) : null;
  const dueCount = dueData != null ? (dueData.total ?? 0) : null;

  // Derive summary stats
  const doneCount = useMemo(
    () => allCommitments.filter((c) => c.status === 'done').length,
    [allCommitments]
  );

  const handleMarkDone = useCallback(
    async (id: string) => {
      await markCommitmentDone(id);
      refetchCommitments();
      refetchUntracked();
      refetchDue();
    },
    [refetchCommitments, refetchUntracked, refetchDue]
  );

  const handleLink = useCallback(
    async (commitmentId: string, taskId: string) => {
      await linkCommitment(commitmentId, taskId);
      refetchCommitments();
      refetchUntracked();
    },
    [refetchCommitments, refetchUntracked]
  );

  const handleLinkTask = useCallback((commitment: Commitment) => {
    setDialogCommitment(commitment);
  }, []);

  if (commitmentsLoading && !commitmentsData) return <SkeletonCardList count={6} />;
  if (commitmentsError && !commitmentsData) {
    return <ErrorState error={commitmentsError} onRetry={refetchCommitments} hasData={false} />;
  }

  return (
    <PageLayout
      title="Commitments"
      subtitle={totalCount != null ? `${totalCount} commitments tracked` : 'Loading...'}
      actions={
        <div className="flex items-center gap-2">
          <select
            value={statusFilter ?? ''}
            onChange={(e) => setStatusFilter(e.target.value || undefined)}
            className="px-3 py-1.5 rounded-lg bg-[var(--black)] border border-[var(--grey)] text-sm focus:border-[var(--accent)] outline-none"
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="done">Done</option>
            <option value="overdue">Overdue</option>
            <option value="at_risk">At Risk</option>
          </select>
          <ExportButton
            data={allCommitments}
            filename="commitments"
            columns={['id', 'text', 'status', 'source', 'due_date', 'client_name']}
          />
        </div>
      }
    >
      {/* Untracked alert */}
      {untrackedCount != null && untrackedCount > 0 && (
        <div className="p-3 rounded-lg border border-[var(--warning)] bg-[var(--warning)]/10">
          <div className="text-sm font-medium" style={{ color: 'var(--warning)' }}>
            {untrackedCount} untracked commitment{untrackedCount !== 1 ? 's' : ''}
          </div>
          <div className="text-xs text-[var(--grey-light)] mt-1">
            These commitments are not linked to any task. Link them to track progress.
          </div>
        </div>
      )}

      <SummaryGrid>
        <MetricCard label="Total" value={totalCount ?? '--'} />
        <MetricCard
          label="Untracked"
          value={untrackedCount ?? '--'}
          severity={untrackedCount != null && untrackedCount > 0 ? 'warning' : undefined}
        />
        <MetricCard label="Due" value={dueCount ?? '--'} severity={dueCount != null && dueCount > 0 ? 'danger' : undefined} />
        <MetricCard
          label="Done"
          value={doneCount}
          severity={doneCount > 0 ? 'success' : undefined}
        />
      </SummaryGrid>

      {/* Summary stats from backend */}
      {summaryData && Object.keys(summaryData).length > 0 && (
        <div className="text-xs text-[var(--grey-muted)]">
          {Object.entries(summaryData)
            .filter(([key]) => key !== 'timestamp')
            .map(([key, val]) => (
              <span key={key} className="mr-4">
                {key}: {String(val)}
              </span>
            ))}
        </div>
      )}

      <TabContainer tabs={COMMITMENT_TABS} defaultTab="all">
        {(activeTab) => {
          if (activeTab === 'untracked') {
            if (untrackedLoading) return <SkeletonCardList count={4} />;
            if (untrackedError) {
              return (
                <ErrorState error={untrackedError} onRetry={refetchUntracked} hasData={false} />
              );
            }
            return (
              <CommitmentList
                commitments={untrackedCommitments}
                onMarkDone={handleMarkDone}
                onLinkTask={handleLinkTask}
              />
            );
          }

          if (activeTab === 'due') {
            if (dueLoading) return <SkeletonCardList count={4} />;
            if (dueError) {
              return <ErrorState error={dueError} onRetry={refetchDue} hasData={false} />;
            }
            return (
              <CommitmentList
                commitments={dueCommitments}
                onMarkDone={handleMarkDone}
                onLinkTask={handleLinkTask}
              />
            );
          }

          // All commitments (default)
          return (
            <CommitmentList
              commitments={allCommitments}
              onMarkDone={handleMarkDone}
              onLinkTask={handleLinkTask}
            />
          );
        }}
      </TabContainer>

      {dialogCommitment && (
        <LinkToTaskDialog
          commitment={dialogCommitment}
          open={true}
          onClose={() => setDialogCommitment(null)}
          onLink={handleLink}
        />
      )}
    </PageLayout>
  );
}
