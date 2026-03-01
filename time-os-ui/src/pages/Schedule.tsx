// Schedule page — day/week views with time block management (Phase 8)
import { useState, useCallback, useMemo } from 'react';
import { SkeletonCardList, ErrorState } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { TimeBlockGrid } from '../components/schedule/TimeBlockGrid';
import { WeekView } from '../components/schedule/WeekView';
import { ScheduleTaskDialog } from '../components/schedule/ScheduleTaskDialog';
import { useTimeBlocks, useTimeSummary, useWeekView, useEvents } from '../lib/hooks';
import { scheduleTask, unscheduleTask } from '../lib/api';
import type { TimeBlock } from '../lib/api';

type ViewTab = 'day' | 'week' | 'events';

const VIEW_TABS: TabDef<ViewTab>[] = [
  { id: 'day', label: 'Day View' },
  { id: 'week', label: 'Week View' },
  { id: 'events', label: 'Events' },
];

function todayString(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function Schedule() {
  const [selectedDate, setSelectedDate] = useState(todayString);
  const [dialogBlock, setDialogBlock] = useState<TimeBlock | null>(null);

  const {
    data: blocksData,
    loading: blocksLoading,
    error: blocksError,
    refetch: refetchBlocks,
  } = useTimeBlocks(selectedDate);

  const { data: summaryData } = useTimeSummary(selectedDate);
  const {
    data: weekData,
    loading: weekLoading,
    error: weekError,
    refetch: refetchWeek,
  } = useWeekView();
  const {
    data: eventsData,
    loading: eventsLoading,
    error: eventsError,
    refetch: refetchEvents,
  } = useEvents(selectedDate, selectedDate);

  const blocks = useMemo(() => blocksData?.blocks ?? [], [blocksData]);
  const totalBlocks = blocksData?.total ?? 0;
  const events = useMemo(() => eventsData?.items ?? [], [eventsData]);

  // Derive metrics from blocks
  const scheduledBlocks = useMemo(() => blocks.filter((b) => b.task_id), [blocks]);
  const availableBlocks = useMemo(
    () => blocks.filter((b) => b.is_available && !b.task_id),
    [blocks]
  );
  const totalMinutes = useMemo(() => blocks.reduce((sum, b) => sum + b.duration_min, 0), [blocks]);
  const scheduledMinutes = useMemo(
    () => scheduledBlocks.reduce((sum, b) => sum + b.duration_min, 0),
    [scheduledBlocks]
  );

  const handleBlockClick = useCallback((block: TimeBlock) => {
    if (block.is_available && !block.task_id) {
      setDialogBlock(block);
    }
  }, []);

  const handleSchedule = useCallback(
    async (taskId: string, blockId: string) => {
      await scheduleTask(taskId, blockId, selectedDate);
      refetchBlocks();
    },
    [selectedDate, refetchBlocks]
  );

  const handleUnschedule = useCallback(
    async (taskId: string) => {
      await unscheduleTask(taskId);
      refetchBlocks();
    },
    [refetchBlocks]
  );

  const handleDayClick = useCallback((date: string) => {
    setSelectedDate(date);
  }, []);

  const handleDateChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedDate(e.target.value);
  }, []);

  if (blocksLoading && !blocksData) return <SkeletonCardList count={6} />;
  if (blocksError && !blocksData) {
    return <ErrorState error={blocksError} onRetry={refetchBlocks} hasData={false} />;
  }

  return (
    <PageLayout
      title="Schedule"
      subtitle={`${selectedDate} — ${totalBlocks} blocks`}
      actions={
        <input
          type="date"
          value={selectedDate}
          onChange={handleDateChange}
          className="px-3 py-1.5 rounded-lg bg-[var(--black)] border border-[var(--grey)] text-sm focus:border-[var(--accent)] outline-none"
        />
      }
    >
      <SummaryGrid>
        <MetricCard label="Total Blocks" value={totalBlocks} />
        <MetricCard
          label="Scheduled"
          value={scheduledBlocks.length}
          severity={scheduledBlocks.length > 0 ? 'info' : undefined}
        />
        <MetricCard
          label="Available"
          value={availableBlocks.length}
          severity={availableBlocks.length > 0 ? 'success' : 'warning'}
        />
        <MetricCard label="Time" value={`${scheduledMinutes}/${totalMinutes}m`} />
      </SummaryGrid>

      <TabContainer tabs={VIEW_TABS} defaultTab="day">
        {(activeTab) => {
          if (activeTab === 'week') {
            if (weekLoading) return <SkeletonCardList count={4} />;
            if (weekError)
              return <ErrorState error={weekError} onRetry={refetchWeek} hasData={false} />;
            if (!weekData) return null;
            return <WeekView data={weekData} onDayClick={handleDayClick} />;
          }

          if (activeTab === 'events') {
            if (eventsLoading) return <SkeletonCardList count={4} />;
            if (eventsError)
              return <ErrorState error={eventsError} onRetry={refetchEvents} hasData={false} />;
            if (events.length === 0) {
              return (
                <div className="text-center py-8 text-sm text-[var(--grey-muted)]">
                  No events for {selectedDate}
                </div>
              );
            }
            return (
              <div className="space-y-2">
                {events.map((event) => (
                  <div
                    key={event.id}
                    className="p-3 rounded-lg border border-[var(--grey)] hover:border-[var(--grey-light)] transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{event.title}</span>
                      {event.source && (
                        <span className="text-xs text-[var(--grey-muted)]">{event.source}</span>
                      )}
                    </div>
                    <div className="text-xs text-[var(--grey-light)] mt-1">
                      {event.start_time} &ndash; {event.end_time}
                    </div>
                    {event.location && (
                      <div className="text-xs text-[var(--grey-muted)] mt-1">{event.location}</div>
                    )}
                  </div>
                ))}
              </div>
            );
          }

          // Day view (default)
          return (
            <div>
              {summaryData && (
                <div className="text-xs text-[var(--grey-muted)] mb-3">
                  {Object.keys(summaryData.time || {}).length > 0 && 'Day summary available'}
                </div>
              )}
              <TimeBlockGrid blocks={blocks} onBlockClick={handleBlockClick} />
              {/* Inline unschedule for scheduled blocks */}
              {scheduledBlocks.length > 0 && (
                <div className="mt-4 pt-4 border-t border-[var(--grey)]">
                  <div className="text-sm text-[var(--grey-light)] mb-2">
                    Scheduled tasks ({scheduledBlocks.length})
                  </div>
                  {scheduledBlocks.map((block) => (
                    <div key={block.id} className="flex items-center justify-between py-2">
                      <div className="text-sm">
                        {block.task_title || block.task_id}
                        <span className="ml-2 text-xs text-[var(--grey-muted)]">
                          {block.start_time} &ndash; {block.end_time}
                        </span>
                      </div>
                      <button
                        onClick={() => block.task_id && handleUnschedule(block.task_id)}
                        className="text-xs px-2 py-1 rounded border border-[var(--grey)] hover:border-[var(--danger)] hover:text-[var(--danger)] transition-colors"
                      >
                        Unschedule
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        }}
      </TabContainer>

      {dialogBlock && (
        <ScheduleTaskDialog
          block={dialogBlock}
          open={true}
          onClose={() => setDialogBlock(null)}
          onSchedule={handleSchedule}
        />
      )}
    </PageLayout>
  );
}
