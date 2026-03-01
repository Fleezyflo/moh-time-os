// Digest page — weekly summary tab + email triage tab (Phase 10)
import { useState, useCallback, useMemo } from 'react';
import { SkeletonCardList, ErrorState } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { WeeklyDigestView } from '../components/notifications/WeeklyDigestView';
import { EmailTriageList } from '../components/notifications/EmailTriageList';
import { useWeeklyDigest, useEmails } from '../lib/hooks';
import { markEmailActionable, dismissEmail } from '../lib/api';

type DigestTab = 'digest' | 'emails';

const DIGEST_TABS: TabDef<DigestTab>[] = [
  { id: 'digest', label: 'Weekly Digest' },
  { id: 'emails', label: 'Email Triage' },
];

export default function Digest() {
  const [emailFilter, setEmailFilter] = useState<'all' | 'actionable' | 'unread'>('all');

  const {
    data: digestData,
    loading: digestLoading,
    error: digestError,
    refetch: refetchDigest,
  } = useWeeklyDigest();

  const {
    data: emailsData,
    loading: emailsLoading,
    error: emailsError,
    refetch: refetchEmails,
  } = useEmails(emailFilter === 'actionable', emailFilter === 'unread');

  const emails = useMemo(() => emailsData?.emails ?? [], [emailsData]);

  const handleMarkActionable = useCallback(
    async (id: string) => {
      await markEmailActionable(id);
      refetchEmails();
    },
    [refetchEmails]
  );

  const handleDismissEmail = useCallback(
    async (id: string) => {
      await dismissEmail(id);
      refetchEmails();
    },
    [refetchEmails]
  );

  return (
    <PageLayout title="Digest" subtitle="Weekly summary and email triage">
      <TabContainer tabs={DIGEST_TABS} defaultTab="digest">
        {(activeTab) => {
          if (activeTab === 'digest') {
            if (digestLoading && !digestData) return <SkeletonCardList count={3} />;
            if (digestError && !digestData) {
              return <ErrorState error={digestError} onRetry={refetchDigest} hasData={false} />;
            }
            if (!digestData) return null;
            return <WeeklyDigestView digest={digestData} />;
          }

          // Email triage tab
          return (
            <div className="space-y-4">
              {/* Filter bar */}
              <div className="flex items-center gap-2">
                <select
                  value={emailFilter}
                  onChange={(e) =>
                    setEmailFilter(e.target.value as 'all' | 'actionable' | 'unread')
                  }
                  className="px-3 py-1.5 rounded-lg bg-[var(--black)] border border-[var(--grey)] text-sm focus:border-[var(--accent)] outline-none"
                >
                  <option value="all">All emails</option>
                  <option value="actionable">Actionable</option>
                  <option value="unread">Unread</option>
                </select>
                <span className="text-xs text-[var(--grey-light)]">
                  {emailsData?.total ?? 0} email{(emailsData?.total ?? 0) !== 1 ? 's' : ''}
                </span>
              </div>

              {emailsLoading && !emailsData ? (
                <SkeletonCardList count={4} />
              ) : emailsError && !emailsData ? (
                <ErrorState error={emailsError} onRetry={refetchEmails} hasData={false} />
              ) : (
                <EmailTriageList
                  emails={emails}
                  onMarkActionable={handleMarkActionable}
                  onDismiss={handleDismissEmail}
                />
              )}
            </div>
          );
        }}
      </TabContainer>
    </PageLayout>
  );
}
