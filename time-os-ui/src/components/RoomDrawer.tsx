// RoomDrawer — detail view for a proposal with signals
import { useEffect, useRef, useState } from 'react';
import type { Proposal } from '../types/api';
import { fetchProposalDetailLegacy } from '../lib/api';

interface SignalValue {
  // Deadline signals
  title?: string;
  due_date?: string;
  days_overdue?: number;
  days_until?: number;
  owner?: string;
  project_name?: string;
  // AR signals
  ar_total?: number;
  overdue_amount?: number;
  days_outstanding?: number;
  // Health signals
  health_status?: string;
  trend?: string;
  // Communication signals
  days_since_contact?: number;
  last_interaction?: string;
  threshold_days?: number;
  // Data quality
  issue_type?: string;
  message?: string;
  // Generic
  client_name?: string;
  tier?: string;
}

interface SignalDetail {
  signal_id: string;
  signal_type: string;
  entity_type?: string;
  entity_id?: string;
  description?: string;
  task_id?: string | null;
  task_title?: string | null;
  assignee?: string | null;
  days_overdue?: number | null;
  days_until?: number | null;
  severity: string;
  status: string;
  detected_at: string;
  value?: SignalValue;
}

interface ProposalDetail extends Proposal {
  signals?: SignalDetail[];
  total_signals?: number;
  affected_task_ids?: string[];
  issues_url?: string;
}

interface RoomDrawerProps {
  proposal: Proposal | null;
  open: boolean;
  onClose: () => void;
  onTag?: () => void;
  onSnooze?: () => void;
  onDismiss?: () => void;
}

const severityStyles: Record<string, { color: string; bg: string }> = {
  critical: { color: 'text-red-400', bg: 'bg-red-900/30' },
  high: { color: 'text-orange-400', bg: 'bg-orange-900/30' },
  medium: { color: 'text-amber-400', bg: 'bg-amber-900/30' },
  low: { color: 'text-[var(--grey-light)]', bg: 'bg-[var(--grey)]' },
};

// Signal type to label mapping (no emojis)
const signalTypeLabels: Record<string, string> = {
  deadline_overdue: 'OVERDUE',
  deadline_approaching: 'DUE SOON',
  ar_aging_risk: 'AR',
  client_health_declining: 'HEALTH',
  communication_gap: 'COMMS',
  data_quality_issue: 'DATA',
  hierarchy_violation: 'HIERARCHY',
  commitment_made: 'COMMITMENT',
  overdue: 'OVERDUE',
  approaching: 'DUE SOON',
  blocked: 'BLOCKED',
  health: 'HEALTH',
  financial: 'AR',
  process: 'PROCESS',
  other: 'OTHER',
};

// Signal type to color mapping
const signalTypeColors: Record<string, string> = {
  deadline_overdue: 'bg-red-500/20 text-red-400 border-red-500/30',
  deadline_approaching: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  ar_aging_risk: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  client_health_declining: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  communication_gap: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  data_quality_issue:
    'bg-[var(--grey-muted)]/20 text-[var(--grey-light)] border-[var(--grey-muted)]/30',
  hierarchy_violation: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  commitment_made: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  overdue: 'bg-red-500/20 text-red-400 border-red-500/30',
  approaching: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  blocked: 'bg-red-500/20 text-red-400 border-red-500/30',
  health: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  financial: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  process: 'bg-[var(--grey-muted)]/20 text-[var(--grey-light)] border-[var(--grey-muted)]/30',
  other: 'bg-[var(--grey-muted)]/20 text-[var(--grey-light)] border-[var(--grey-muted)]/30',
};

function getSignalLabel(signalType: string): string {
  if (!signalType) return 'OTHER';
  const lower = signalType.toLowerCase().replace(/\s+/g, '_');
  return (
    signalTypeLabels[lower] ||
    signalTypeLabels[signalType] ||
    signalType.replace(/_/g, ' ').toUpperCase()
  );
}

function getSignalColor(signalType: string): string {
  if (!signalType) return signalTypeColors.other;
  const lower = signalType.toLowerCase().replace(/\s+/g, '_');
  return signalTypeColors[lower] || signalTypeColors[signalType] || signalTypeColors.other;
}

// Format signal into actionable detail line
function formatSignalDetail(sig: SignalDetail): { primary: string; secondary?: string } {
  const v = sig.value || {};
  const type = sig.signal_type?.toLowerCase() || '';

  // Deadline overdue
  if (type.includes('deadline_overdue') || type === 'overdue') {
    const task = v.title || sig.task_title || 'Task';
    const days = v.days_overdue || sig.days_overdue || 0;
    const owner = v.owner || sig.assignee || 'Unassigned';
    return {
      primary: `${task}: ${days}d overdue`,
      secondary: owner !== 'Unassigned' ? owner : undefined,
    };
  }

  // Deadline approaching
  if (type.includes('deadline_approaching') || type === 'approaching') {
    const task = v.title || sig.task_title || 'Task';
    const days = v.days_until || sig.days_until || 0;
    const owner = v.owner || sig.assignee || 'Unassigned';
    return {
      primary: `${task}: due in ${days}d`,
      secondary: owner !== 'Unassigned' ? owner : undefined,
    };
  }

  // AR aging
  if (type.includes('ar_') || type === 'financial') {
    const amount = v.overdue_amount || v.ar_total || 0;
    const days = v.days_outstanding || 0;
    return {
      primary: `$${(amount / 1000).toFixed(0)}k overdue${days ? ` (${days}d)` : ''}`,
      secondary: v.client_name,
    };
  }

  // Communication gap
  if (type.includes('communication')) {
    const days = v.days_since_contact || 0;
    return {
      primary: `No contact: ${days} days`,
      secondary: v.client_name,
    };
  }

  // Health declining
  if (type.includes('health')) {
    const status = v.health_status || 'poor';
    const trend = v.trend || 'declining';
    return {
      primary: `Health: ${status}, Trend: ${trend}`,
      secondary: v.client_name,
    };
  }

  // Data quality
  if (type.includes('data_quality')) {
    return {
      primary: v.message || 'Data issue',
      secondary: v.tier ? `Tier ${v.tier}` : undefined,
    };
  }

  // Fallback - use description or value message
  return {
    primary:
      v.message || sig.description || sig.task_title || (type || '').replace(/_/g, ' ') || 'Signal',
    secondary: sig.assignee || undefined,
  };
}

const tierColors: Record<string, string> = {
  A: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  B: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  C: 'bg-[var(--grey-muted)]/20 text-[var(--grey-light)] border-[var(--grey-muted)]/30',
};

export function RoomDrawer({
  proposal,
  open,
  onClose,
  onTag,
  onSnooze,
  onDismiss,
}: RoomDrawerProps) {
  const [detail, setDetail] = useState<ProposalDetail | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch full detail when opened
  useEffect(() => {
    if (!open || !proposal) {
      setDetail(null);
      return;
    }

    setLoading(true);
    setDetail(null); // Clear previous detail

    fetchProposalDetailLegacy(proposal.proposal_id)
      .then((data) => {
        const detail = data as ProposalDetail;
        setDetail(detail);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load proposal detail:', err);
        // Fallback to basic proposal data without signals
        setDetail({ ...proposal, signals: [], total_signals: 0 } as ProposalDetail);
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Only refetch when proposal ID changes, not entire proposal object
  }, [open, proposal?.proposal_id]);

  // ESC key to close
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  // Lock body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [open]);

  const drawerRef = useRef<HTMLDivElement>(null);

  // Focus trap — keep focus within drawer
  useEffect(() => {
    if (!open || !drawerRef.current) return;

    // Focus first focusable element
    const firstFocusable = drawerRef.current.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    firstFocusable?.focus();

    // Trap focus within drawer
    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !drawerRef.current) return;

      const focusables = drawerRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };

    document.addEventListener('keydown', handleTab);
    return () => document.removeEventListener('keydown', handleTab);
  }, [open]);

  if (!open || !proposal) return null;

  const p = detail || proposal;
  const severityStyle = severityStyles[p.impact?.severity] || severityStyles.medium;
  const signals = detail?.signals || [];
  const totalSignals = detail?.total_signals || p.signal_count || p.impact?.signal_count || 0;
  const issuesUrl = detail?.issues_url;

  // Score color
  const getScoreColor = (score: number) => {
    if (score >= 100) return 'text-red-400';
    if (score >= 50) return 'text-orange-400';
    if (score >= 25) return 'text-amber-400';
    return 'text-[var(--grey-subtle)]';
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="room-drawer-title"
        className="absolute right-0 top-0 h-full w-full max-w-xl bg-[var(--black)] border-l border-[var(--grey)] shadow-2xl overflow-y-auto"
      >
        {/* Header with hierarchy */}
        <div className={`p-5 border-b border-[var(--grey)] ${severityStyle.bg}`}>
          <div className="flex items-center justify-between mb-3">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm">
              {p.client_name && (
                <>
                  <span className="text-[var(--grey-light)]">{p.client_name}</span>
                  {p.scope_name && p.scope_name !== p.client_name && (
                    <>
                      <span className="text-[var(--grey-mid)]">›</span>
                      <span className="text-[var(--grey-subtle)]">{p.scope_name}</span>
                    </>
                  )}
                </>
              )}
              {!p.client_name && p.scope_name && (
                <span className="text-[var(--grey-subtle)]">{p.scope_name}</span>
              )}
            </div>
            <button
              onClick={onClose}
              aria-label="Close drawer"
              className="text-[var(--grey-light)] hover:text-[var(--white)] p-1 rounded hover:bg-[var(--grey)]/50"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Title with badges */}
          <div className="flex items-start gap-3">
            <div className="flex-1">
              <h2 id="room-drawer-title" className="text-xl font-semibold text-[var(--white)]">
                {p.scope_name || p.headline?.split(':')[0] || 'Proposal'}
              </h2>
              <p className="text-sm text-[var(--grey-light)] mt-1">
                {totalSignals} issue{totalSignals !== 1 ? 's' : ''} requiring attention
              </p>
            </div>
            <div className="flex items-center gap-2">
              {p.client_tier && (
                <span
                  className={`px-2 py-1 text-xs font-medium rounded border ${tierColors[p.client_tier]}`}
                >
                  Tier {p.client_tier}
                </span>
              )}
              {p.engagement_type === 'retainer' && (
                <span className="px-2 py-1 text-xs bg-purple-500/20 text-purple-400 rounded">
                  Retainer
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Score Breakdown */}
        <div className="p-5 border-b border-[var(--grey)]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-xs text-[var(--grey-muted)] uppercase tracking-wide">
                Priority Score
              </div>
              <div className={`text-4xl font-bold ${getScoreColor(p.score)}`}>
                {p.score?.toFixed(0) || '0'}
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-[var(--grey-muted)] uppercase tracking-wide">Trend</div>
              <div
                className={`text-sm font-medium mt-1 px-2 py-1 rounded ${
                  p.trend === 'worsening'
                    ? 'bg-red-500/20 text-red-400'
                    : p.trend === 'improving'
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-[var(--grey)] text-[var(--grey-light)]'
                }`}
              >
                {p.trend === 'worsening'
                  ? 'WORSENING'
                  : p.trend === 'improving'
                    ? 'IMPROVING'
                    : 'STABLE'}
              </div>
            </div>
          </div>

          {/* Score breakdown visualization */}
          {p.score_breakdown && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-[var(--grey-muted)] w-16">Urgency</span>
                <div className="flex-1 h-2 bg-[var(--grey)] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-red-500/70 rounded-full"
                    style={{ width: `${(p.score_breakdown.urgency / 60) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-[var(--grey-light)] w-8 text-right">
                  {p.score_breakdown.urgency}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-[var(--grey-muted)] w-16">Breadth</span>
                <div className="flex-1 h-2 bg-[var(--grey)] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-500/70 rounded-full"
                    style={{ width: `${(p.score_breakdown.breadth / 40) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-[var(--grey-light)] w-8 text-right">
                  {p.score_breakdown.breadth}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-[var(--grey-muted)] w-16">Diversity</span>
                <div className="flex-1 h-2 bg-[var(--grey)] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500/70 rounded-full"
                    style={{ width: `${(p.score_breakdown.diversity / 30) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-[var(--grey-light)] w-8 text-right">
                  {p.score_breakdown.diversity}
                </span>
              </div>
              <div className="flex items-center gap-2 pt-1 border-t border-[var(--grey)]/50">
                <span className="text-xs text-[var(--grey-muted)] w-16">Multiplier</span>
                <span className="text-xs text-[var(--grey-subtle)]">
                  ×{p.score_breakdown.impact_multiplier?.toFixed(2)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Signal Summary */}
        {p.signal_summary?.by_category && (
          <div className="p-5 border-b border-[var(--grey)]">
            <div className="text-xs text-[var(--grey-muted)] uppercase tracking-wide mb-3">
              Issue Categories
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(p.signal_summary.by_category)
                .filter(([_, count]) => count > 0)
                .map(([cat, count]) => (
                  <span
                    key={cat}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded border text-xs font-medium ${getSignalColor(cat)}`}
                  >
                    <span>{getSignalLabel(cat)}</span>
                    <span className="opacity-70">{count}</span>
                  </span>
                ))}
            </div>
          </div>
        )}

        {/* Signals List */}
        <div className="p-5 border-b border-[var(--grey)]">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs text-[var(--grey-muted)] uppercase tracking-wide">
              Top Issues {signals.length > 0 && `(${signals.length} of ${totalSignals})`}
            </div>
            {loading && <span className="text-xs text-[var(--grey-muted)]">Loading...</span>}
          </div>

          {signals.length > 0 ? (
            <div className="space-y-2">
              {signals.map((sig) => {
                const detail = formatSignalDetail(sig);
                return (
                  <div
                    key={sig.signal_id}
                    className="p-3 bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)]/50"
                  >
                    <div className="flex items-start gap-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${getSignalColor(sig.signal_type)}`}
                      >
                        {getSignalLabel(sig.signal_type)}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-[var(--white)]">{detail.primary}</div>
                        {detail.secondary && (
                          <div className="text-xs text-[var(--grey-muted)] mt-0.5">
                            {detail.secondary}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-[var(--grey-muted)] text-center py-4">
              {loading ? 'Loading signals...' : 'No signal details available'}
            </div>
          )}

          {/* View all link */}
          {totalSignals > signals.length && issuesUrl && (
            <a
              href={issuesUrl}
              className="block mt-3 text-center text-sm text-blue-400 hover:text-blue-300"
            >
              View all {totalSignals} issues →
            </a>
          )}
        </div>

        {/* Timeline */}
        <div className="p-5 border-b border-[var(--grey)]">
          <div className="text-xs text-[var(--grey-muted)] uppercase tracking-wide mb-2">
            Timeline
          </div>
          <div className="flex items-center gap-6 text-sm text-[var(--grey-light)]">
            <div>
              <span className="text-[var(--grey-muted)]">First: </span>
              {new Date(p.first_seen_at).toLocaleDateString()}
            </div>
            <div>
              <span className="text-[var(--grey-muted)]">Last: </span>
              {new Date(p.last_seen_at).toLocaleDateString()}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="p-5 sticky bottom-0 bg-[var(--black)] border-t border-[var(--grey)]">
          <div className="flex items-center gap-2">
            <button
              onClick={onTag}
              aria-label="Tag and monitor this proposal"
              className="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Tag & Monitor
            </button>
            <button
              onClick={onSnooze}
              aria-label="Snooze this proposal"
              className="px-4 py-2.5 bg-[var(--grey)] hover:bg-[var(--grey-mid)] text-[var(--white)] text-sm rounded-lg transition-colors"
            >
              Snooze
            </button>
            <button
              onClick={onDismiss}
              aria-label="Dismiss this proposal"
              className="px-4 py-2.5 bg-[var(--grey-dim)] hover:bg-[var(--grey)] text-[var(--grey-light)] text-sm rounded-lg transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
