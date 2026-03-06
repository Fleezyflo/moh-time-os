// Command Center — Detection-based single-view dashboard
// Replaces three-tab scored layout with factual findings
import { useState, useCallback } from 'react';
import { PageLayout } from '../components/layout/PageLayout';
import { SkeletonPanel } from '../components';
import { useWeekStrip, useFindings, useStaleness } from '../lib/hooks';
import * as api from '../lib/api';
import type { WeekStripDay, DetectionFinding, FindingGroup, StalenessResponse } from '../lib/api';

// --- Staleness Bar ---

function StalenessBar({ staleness }: { staleness: StalenessResponse | null }) {
  if (!staleness) return null;

  if (staleness.is_stale) {
    return (
      <div className="rounded-lg border border-[var(--warning)] bg-[var(--warning)]/10 px-4 py-3 mb-4">
        <p className="text-sm font-medium text-[var(--warning)]">
          Detection stale — last run{' '}
          {staleness.stale_since ? formatTimeAgo(staleness.last_run) : 'unknown'} ago. Findings may
          be outdated.
        </p>
      </div>
    );
  }

  return (
    <div className="text-xs text-[var(--grey)] mb-4">
      Last detection: {formatTimeAgo(staleness.last_run)} ago
    </div>
  );
}

// --- Week Strip ---

function getRatioColor(ratio: number): string {
  if (ratio > 2.0) return 'var(--danger)';
  if (ratio >= 1.0) return 'var(--warning)';
  return 'var(--success)';
}

function getRatioBg(ratio: number): string {
  if (ratio > 2.0) return 'bg-[var(--danger)]/20';
  if (ratio >= 1.0) return 'bg-[var(--warning)]/20';
  return 'bg-[var(--success)]/10';
}

function WeekStrip({
  days,
  selectedDate,
  onSelectDate,
}: {
  days: WeekStripDay[];
  selectedDate: string | null;
  onSelectDate: (date: string) => void;
}) {
  return (
    <div className="mb-6">
      <div className="flex gap-2 overflow-x-auto pb-2">
        {days.map((day) => {
          const hours = Math.round((day.available_minutes / 60) * 10) / 10;
          const isSelected = selectedDate === day.date;
          const dayLabel = formatDayLabel(day.date);

          return (
            <button
              key={day.date}
              onClick={() => onSelectDate(day.date)}
              className={`flex-shrink-0 w-20 rounded-lg border p-2 text-center transition-colors cursor-pointer ${
                isSelected
                  ? 'border-[var(--white)] bg-[var(--grey-dim)]'
                  : 'border-[var(--grey)] bg-[var(--black)]/30 hover:border-[var(--grey-light)]'
              } ${day.has_collision ? getRatioBg(day.weighted_ratio) : ''}`}
            >
              <div className="text-xs text-[var(--grey)] mb-1">{dayLabel}</div>
              <div className="text-sm font-semibold text-[var(--white)]">{hours}h</div>
              <div className="text-xs mt-0.5" style={{ color: getRatioColor(day.weighted_ratio) }}>
                {day.tasks_due} task{day.tasks_due !== 1 ? 's' : ''}
              </div>
              {day.has_collision && (
                <div
                  className="text-xs font-medium mt-0.5"
                  style={{ color: getRatioColor(day.weighted_ratio) }}
                >
                  {day.weighted_ratio.toFixed(1)}:1
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// --- Finding Card ---

function FindingCard({
  finding,
  onAcknowledge,
  onSuppress,
}: {
  finding: DetectionFinding;
  onAcknowledge: (id: string) => void;
  onSuppress: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<DetectionFinding | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const handleExpand = useCallback(async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    setExpanded(true);
    setRefreshing(true);
    try {
      const result = await api.fetchFinding(finding.id, true);
      setDetail(result.finding);
    } catch {
      // Show existing data on refresh failure
      setDetail(finding);
    } finally {
      setRefreshing(false);
    }
  }, [expanded, finding]);

  const detectorLabel = finding.detector.charAt(0).toUpperCase() + finding.detector.slice(1);

  return (
    <div className="bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)] p-4 mb-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-[var(--grey)] uppercase tracking-wide">
              {detectorLabel}
            </span>
          </div>
          <h3 className="font-medium text-[var(--white)]">{finding.entity_name}</h3>
          <p className="text-sm text-[var(--grey-light)] mt-1">{finding.summary}</p>
        </div>
        <button
          onClick={handleExpand}
          className="text-xs text-[var(--grey-light)] hover:text-[var(--white)] px-2 py-1 rounded hover:bg-[var(--grey)]/20 transition-colors"
        >
          {expanded ? '▾ Hide' : '▸ Detail'}
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-[var(--grey)]/50">
          {refreshing ? (
            <p className="text-sm text-[var(--grey)] animate-pulse">
              Refreshing calendar &amp; email...
            </p>
          ) : (
            <AdjacentData data={(detail ?? finding).adjacent_data} />
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 mt-3">
        <button
          onClick={() => onAcknowledge(finding.id)}
          className="text-xs px-3 py-1.5 rounded border border-[var(--grey)] text-[var(--grey-light)] hover:text-[var(--white)] hover:border-[var(--grey-light)] transition-colors"
        >
          Got it
        </button>
        <button
          onClick={() => onSuppress(finding.id)}
          className="text-xs px-3 py-1.5 rounded border border-[var(--grey)] text-[var(--grey-light)] hover:text-[var(--white)] hover:border-[var(--grey-light)] transition-colors"
        >
          Expected
        </button>
      </div>
    </div>
  );
}

// --- Adjacent Data renderer ---

function AdjacentData({ data }: { data: Record<string, unknown> }) {
  if (!data || Object.keys(data).length === 0) {
    return <p className="text-sm text-[var(--grey)]">No additional data available.</p>;
  }

  return (
    <div className="space-y-2">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <span className="text-xs text-[var(--grey)] uppercase tracking-wide">
            {key.replace(/_/g, ' ')}
          </span>
          <div className="text-sm text-[var(--grey-light)] mt-0.5">
            {renderAdjacentValue(value)}
          </div>
        </div>
      ))}
    </div>
  );
}

function renderAdjacentValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) {
    return value.map((v) => (typeof v === 'object' ? JSON.stringify(v) : String(v))).join(', ');
  }
  return JSON.stringify(value);
}

// --- Correlated Group ---

function CorrelatedGroup({
  group,
  onAcknowledge,
  onSuppress,
}: {
  group: FindingGroup;
  onAcknowledge: (id: string) => void;
  onSuppress: (id: string) => void;
}) {
  return (
    <div className="mb-4">
      <FindingCard finding={group.primary} onAcknowledge={onAcknowledge} onSuppress={onSuppress} />
      {group.subordinates.length > 0 && (
        <div className="ml-4 border-l-2 border-[var(--grey)]/30 pl-3">
          <div className="text-xs text-[var(--grey)] mb-2 uppercase tracking-wide">
            Related findings
          </div>
          {group.subordinates.map((sub) => (
            <FindingCard
              key={sub.id}
              finding={sub}
              onAcknowledge={onAcknowledge}
              onSuppress={onSuppress}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// --- Team Collisions ---

function TeamCollisions({ collisions }: { collisions: DetectionFinding[] }) {
  const [open, setOpen] = useState(false);

  if (collisions.length === 0) return null;

  // Group by entity_name (team member)
  const byPerson = new Map<string, DetectionFinding[]>();
  for (const c of collisions) {
    const existing = byPerson.get(c.entity_name) ?? [];
    existing.push(c);
    byPerson.set(c.entity_name, existing);
  }

  return (
    <div className="border-t border-[var(--grey)]/30 pt-4 mt-6">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm font-medium text-[var(--grey-light)] hover:text-[var(--white)] transition-colors w-full text-left"
      >
        <span>{open ? '▾' : '▸'}</span>
        <span>
          Team Collisions ({byPerson.size} member{byPerson.size !== 1 ? 's' : ''} with collisions)
        </span>
      </button>
      {open && (
        <div className="mt-3 space-y-4">
          {Array.from(byPerson.entries()).map(([person, findings]) => (
            <div key={person}>
              <h4 className="text-sm font-medium text-[var(--white)] mb-2">{person}</h4>
              {findings.map((f) => (
                <div
                  key={f.id}
                  className="bg-[var(--black)]/30 rounded border border-[var(--grey)]/50 p-3 mb-2"
                >
                  <p className="text-sm text-[var(--grey-light)]">{f.summary}</p>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Collapsible Section ---

function CollapsibleSection({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  if (count === 0) return null;

  return (
    <div className="border-t border-[var(--grey)]/30 pt-4 mt-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm font-medium text-[var(--grey-light)] hover:text-[var(--white)] transition-colors w-full text-left"
      >
        <span>{open ? '▾' : '▸'}</span>
        <span>
          {title} ({count})
        </span>
      </button>
      {open && <div className="mt-3">{children}</div>}
    </div>
  );
}

// --- Helpers ---

function formatTimeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

function formatDayLabel(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

// --- Main Component ---

export default function CommandCenter() {
  const { data: weekStrip, loading: weekLoading } = useWeekStrip();
  const { data: findings, loading: findingsLoading, refetch: refetchFindings } = useFindings();
  const { data: staleness, loading: stalenessLoading } = useStaleness();

  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleAcknowledge = useCallback(
    async (findingId: string) => {
      setActionLoading(findingId);
      try {
        await api.acknowledgeFinding(findingId);
        refetchFindings();
      } catch (err) {
        if (import.meta.env.DEV) {
          console.error('Acknowledge failed:', err);
        }
      } finally {
        setActionLoading(null);
      }
    },
    [refetchFindings]
  );

  const handleSuppress = useCallback(
    async (findingId: string) => {
      setActionLoading(findingId);
      try {
        await api.suppressFinding(findingId);
        refetchFindings();
      } catch (err) {
        if (import.meta.env.DEV) {
          console.error('Suppress failed:', err);
        }
      } finally {
        setActionLoading(null);
      }
    },
    [refetchFindings]
  );

  const loading = weekLoading || findingsLoading || stalenessLoading;
  const isStale = staleness?.is_stale ?? false;
  const hasActiveFindings = (findings?.groups.length ?? 0) > 0;

  return (
    <PageLayout title="Command Center" subtitle="Detection-based operations dashboard">
      {/* Staleness indicator */}
      {!stalenessLoading && <StalenessBar staleness={staleness} />}

      {/* Week strip -- always visible */}
      {weekLoading ? (
        <div className="flex gap-2 mb-6">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="w-20 h-24 bg-[var(--grey-dim)] rounded-lg animate-pulse" />
          ))}
        </div>
      ) : weekStrip ? (
        <WeekStrip days={weekStrip} selectedDate={selectedDate} onSelectDate={setSelectedDate} />
      ) : null}

      {/* Active findings */}
      <div className="mb-6">
        {findingsLoading ? (
          <div className="space-y-3">
            <SkeletonPanel rows={3} />
            <SkeletonPanel rows={2} />
          </div>
        ) : hasActiveFindings ? (
          <>
            {findings?.groups.map((group) => (
              <CorrelatedGroup
                key={group.primary.id}
                group={group}
                onAcknowledge={handleAcknowledge}
                onSuppress={handleSuppress}
              />
            ))}
          </>
        ) : !isStale ? (
          <div className="bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)] p-8 text-center">
            <p className="text-[var(--grey-light)]">Nothing requires attention.</p>
          </div>
        ) : null}
      </div>

      {/* Acknowledged section (collapsed) */}
      {!loading && findings && (
        <CollapsibleSection title="Acknowledged" count={findings.acknowledged.length}>
          {findings.acknowledged.map((f) => (
            <div
              key={f.id}
              className="bg-[var(--black)]/30 rounded border border-[var(--grey)]/50 p-3 mb-2"
            >
              <div className="text-xs text-[var(--grey)] uppercase tracking-wide mb-1">
                {f.detector}
              </div>
              <p className="text-sm text-[var(--grey-light)]">
                {f.entity_name} — {f.summary}
              </p>
            </div>
          ))}
        </CollapsibleSection>
      )}

      {/* Suppressed section (collapsed) */}
      {!loading && findings && (
        <CollapsibleSection title="Suppressed" count={findings.suppressed.length}>
          {findings.suppressed.map((f) => (
            <div
              key={f.id}
              className="bg-[var(--black)]/30 rounded border border-[var(--grey)]/50 p-3 mb-2"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-[var(--grey)] uppercase tracking-wide">
                  {f.detector}
                </span>
                {f.suppressed_until && (
                  <span className="text-xs text-[var(--grey)]">until {f.suppressed_until}</span>
                )}
              </div>
              <p className="text-sm text-[var(--grey-light)]">
                {f.entity_name} — {f.summary}
              </p>
            </div>
          ))}
        </CollapsibleSection>
      )}

      {/* Team Collisions (collapsed) */}
      {!loading && findings && <TeamCollisions collisions={findings.team_collisions} />}

      {/* Loading overlay for action buttons */}
      {actionLoading && (
        <div className="fixed bottom-4 right-4 bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg px-4 py-2 text-xs text-[var(--grey-light)]">
          Processing...
        </div>
      )}
    </PageLayout>
  );
}
