// Client Detail Page — Spec §3
// 5 Tabs: Overview, Engagements, Financials, Signals, Team

import { useState, useEffect, useCallback } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { TrajectorySparkline } from '../components/layout/TrajectorySparkline';
import * as api from '../lib/api';
import { useClientTrajectory } from '../intelligence/hooks';
import {
  useClientEmailParticipants,
  useClientAttachments,
  useClientInvoiceDetail,
} from '../lib/hooks';
import type { Tier, Severity } from '../types/spec';

// Types for this page
interface ClientDetail {
  id: string;
  name: string;
  tier: Tier;
  status: string;
  health_score: number;
  health_label: string;
  // Financials
  issued_ytd: number;
  issued_year: number;
  paid_ytd: number;
  paid_year: number;
  issued_lifetime: number;
  paid_lifetime: number;
  ar_outstanding: number;
  ar_overdue: number;
  ar_overdue_pct: number;
  // Engagements
  active_engagements: number;
  open_tasks: number;
  tasks_overdue: number;
  // Signals summary
  signals_good: number;
  signals_neutral: number;
  signals_bad: number;
  // Issues
  top_issues: ClientIssue[];
  // Recent signals
  recent_positive_signals: Signal[];
  // Brands/Engagements
  brands: Brand[];
  // Invoices
  invoices: Invoice[];
  ar_aging: ARBucket[];
  // Team
  team_members: TeamMember[];
  // Signals list
  signals: Signal[];
}

interface ClientIssue {
  id: string;
  type: string;
  severity: Severity;
  state: string;
  title: string;
  evidence: {
    display_text: string;
    url: string | null;
    source_system: string;
  };
  assigned_to?: { id: string; name: string };
  available_actions: string[];
}

interface Signal {
  id: string;
  sentiment: 'good' | 'neutral' | 'bad';
  source: string;
  summary: string;
  observed_at: string;
  evidence?: {
    url: string | null;
    display_text: string;
  };
}

interface Brand {
  id: string;
  name: string;
  engagements: Engagement[];
}

interface Engagement {
  id: string;
  name: string;
  type: 'project' | 'retainer';
  state: string;
  health_score: number | null;
  open_tasks: number;
  overdue_tasks: number;
  completed_tasks: number;
  asana_url?: string;
}

interface Invoice {
  id: string;
  number: string;
  issue_date: string;
  amount: number;
  status: string;
  days_overdue?: number;
}

interface ARBucket {
  bucket: string;
  amount: number;
  pct: number;
}

interface TeamMember {
  id: string;
  name: string;
  role: string;
  email?: string;
  open_tasks: number;
  overdue_tasks: number;
}

// Tab definitions
type TabId =
  | 'overview'
  | 'engagements'
  | 'financials'
  | 'signals'
  | 'team'
  | 'email-participants'
  | 'attachments'
  | 'invoice-detail';

const TABS: TabDef<TabId>[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'engagements', label: 'Engagements' },
  { id: 'financials', label: 'Financials' },
  { id: 'signals', label: 'Signals' },
  { id: 'team', label: 'Team' },
  { id: 'email-participants', label: 'Email Participants' },
  { id: 'attachments', label: 'Attachments' },
  { id: 'invoice-detail', label: 'Invoice Detail' },
];

// Severity colors
const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'bg-[var(--danger)] text-[var(--white)]',
  high: 'bg-orange-500 text-[var(--white)]',
  medium: 'bg-[var(--warning)] text-black',
  low: 'bg-[var(--info)] text-[var(--white)]',
  info: 'bg-[var(--grey-muted)] text-[var(--white)]',
};

// Issue type icons
const ISSUE_TYPE_ICONS: Record<string, string> = {
  financial: '💰',
  schedule_delivery: '⚠️',
  communication: '💬',
  risk: '🚨',
};

// Sentiment icons
const SENTIMENT_ICONS: Record<string, string> = {
  good: '🟢',
  neutral: '🟡',
  bad: '🔴',
};

function formatCurrency(amount: number, currency = 'AED'): string {
  return `${currency} ${amount.toLocaleString()}`;
}

function formatAge(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  return `${days}d ago`;
}

function getHealthColor(score: number): string {
  if (score >= 70) return 'text-[var(--success)]';
  if (score >= 40) return 'text-[var(--warning)]';
  return 'text-[var(--danger)]';
}

function getHealthBg(score: number): string {
  if (score >= 70) return 'bg-[var(--success)]';
  if (score >= 40) return 'bg-[var(--warning)]';
  return 'bg-[var(--danger)]';
}

export function ClientDetailSpec() {
  const { clientId } = useParams({ from: '/clients/$clientId' });
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [client, setClient] = useState<ClientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Trajectory data for sparkline (from intelligence API) — must be before early returns
  const { data: trajectoryData } = useClientTrajectory(clientId);
  const trajectoryPoints = (trajectoryData?.windows || []).map((w) => ({
    date: w.start,
    value: w.metrics?.composite_score ?? w.metrics?.health_score ?? 0,
  }));

  // Email Participants data hook
  const { data: emailParticipantsData } = useClientEmailParticipants(clientId);

  // Attachments data hook
  const { data: attachmentsData } = useClientAttachments(clientId);

  // Invoice Detail data hook
  const { data: invoiceDetailData } = useClientInvoiceDetail(clientId);

  const loadClient = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.fetchClientDetail(clientId);

      // Transform nested API response to flat structure expected by UI
      const financials = (data.financials || {}) as Record<string, unknown>;
      const overview = (data.overview || {}) as Record<string, unknown>;
      const signals = (data.signals || {}) as Record<string, unknown>;
      const engagements = (data.engagements || {}) as Record<string, unknown>;
      const brands = (engagements.brands || []) as Brand[];

      const transformed: ClientDetail = {
        ...(data as unknown as ClientDetail),
        // Flatten financials
        issued_ytd: (financials.issued_ytd as number) || 0,
        issued_year: (financials.issued_prior_year as number) || 0,
        paid_ytd: (financials.paid_ytd as number) || 0,
        paid_year: (financials.paid_prior_year as number) || 0,
        issued_lifetime: (financials.issued_lifetime as number) || 0,
        paid_lifetime: (financials.paid_lifetime as number) || 0,
        ar_outstanding: (financials.ar_outstanding as number) || 0,
        ar_overdue: (financials.ar_overdue as number) || 0,
        ar_overdue_pct: (financials.ar_overdue_pct as number) || 0,
        // Flatten overview
        top_issues: (overview.top_issues as ClientIssue[]) || [],
        recent_positive_signals: (overview.recent_positive_signals as Signal[]) || [],
        // Flatten signals summary
        signals_good: (signals.good as number) || 0,
        signals_neutral: (signals.neutral as number) || 0,
        signals_bad: (signals.bad as number) || 0,
        // Flatten engagements
        brands,
        active_engagements: brands.reduce(
          (sum: number, b: Brand) => sum + (b.engagements?.length || 0),
          0
        ),
        // Defaults for other fields
        open_tasks: 0,
        tasks_overdue: 0,
        invoices: [],
        ar_aging: [],
        team_members: [],
        signals: [],
      };

      setClient(transformed);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    loadClient();
  }, [loadClient]);

  // Execute issue action via typed API
  const executeIssueAction = async (issueId: string, action: string) => {
    try {
      await api.changeIssueState(issueId, action as api.IssueState);
      loadClient();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Action failed');
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-32 bg-[var(--grey-dim)] rounded animate-pulse" />
        <div className="h-64 bg-[var(--grey-dim)] rounded animate-pulse" />
      </div>
    );
  }

  if (error || !client) {
    return (
      <div className="p-8 text-center">
        <p className="text-[var(--danger)]">{error || 'Client not found'}</p>
        <Link to="/clients" className="mt-4 text-[var(--info)] hover:underline">
          ← Back to Clients
        </Link>
      </div>
    );
  }

  const healthScore = client.health_score ?? 0;

  const actions = (
    <Link to="/clients" className="text-sm text-[var(--grey-light)] hover:text-[var(--white)]">
      ← Back to Index
    </Link>
  );

  return (
    <PageLayout
      title={client.name}
      subtitle={client.tier ? `Tier: ${client.tier}` : undefined}
      actions={actions}
    >
      <SummaryGrid>
        <MetricCard
          label="Health Score"
          value={healthScore.toString()}
          severity={healthScore >= 70 ? 'success' : healthScore >= 40 ? 'warning' : 'danger'}
        />
        <MetricCard label="AR Outstanding" value={formatCurrency(client.ar_outstanding || 0)} />
        <MetricCard
          label="Active Engagements"
          value={(client.active_engagements || 0).toString()}
        />
        <MetricCard
          label="Open Issues"
          value={(client.top_issues?.length ?? 0).toString()}
          severity={(client.top_issues?.length ?? 0) > 0 ? 'danger' : undefined}
        />
      </SummaryGrid>

      {/* Health bar with trajectory sparkline */}
      <div className="bg-[var(--grey-dim)] rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-[var(--grey-light)]">Health Progress</span>
          <div className="flex items-center gap-3">
            {trajectoryPoints.length >= 2 && (
              <TrajectorySparkline data={trajectoryPoints} width={120} height={28} showArea />
            )}
            <span className={`font-medium ${getHealthColor(healthScore)}`}>
              {healthScore}
              <span className="text-[var(--grey)]"> ({client.health_label || 'provisional'})</span>
            </span>
          </div>
        </div>
        <div className="h-2 bg-[var(--grey)] rounded-full overflow-hidden">
          <div
            className={`h-full ${getHealthBg(healthScore)}`}
            style={{ width: `${Math.min(100, healthScore)}%` }}
          />
        </div>
      </div>

      {/* Tabs */}
      <TabContainer tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab}>
        {(tab) => {
          switch (tab) {
            case 'overview':
              return <OverviewTab client={client} onIssueAction={executeIssueAction} />;
            case 'engagements':
              return <EngagementsTab brands={client.brands || []} />;
            case 'financials':
              return <FinancialsTab client={client} />;
            case 'signals':
              return (
                <SignalsTab
                  signals={client.signals || []}
                  summary={{
                    good: client.signals_good || 0,
                    neutral: client.signals_neutral || 0,
                    bad: client.signals_bad || 0,
                  }}
                />
              );
            case 'team':
              return <TeamTab members={client.team_members || []} />;
            case 'email-participants':
              return <EmailParticipantsTab data={emailParticipantsData ?? undefined} />;
            case 'attachments':
              return <AttachmentsTab data={attachmentsData ?? undefined} />;
            case 'invoice-detail':
              return <InvoiceDetailTab data={invoiceDetailData ?? undefined} />;
            default:
              return null;
          }
        }}
      </TabContainer>
    </PageLayout>
  );
}

// ==== Tab: Overview (§3.2) ====

interface OverviewTabProps {
  client: ClientDetail;
  onIssueAction: (issueId: string, action: string) => void;
}

function OverviewTab({ client, onIssueAction }: OverviewTabProps) {
  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div>
        <h3 className="text-lg font-semibold mb-3">Key Metrics</h3>
        <div className="bg-[var(--black)] rounded p-4 space-y-3">
          {/* Issued / Paid */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-[var(--grey-light)] text-xs mb-1">ISSUED</div>
              <div>Prior Yr: {formatCurrency(client.issued_year || 0)}</div>
              <div>YTD: {formatCurrency(client.issued_ytd || 0)}</div>
            </div>
            <div>
              <div className="text-[var(--grey-light)] text-xs mb-1">PAID</div>
              <div>Prior Yr: {formatCurrency(client.paid_year || 0)}</div>
              <div>YTD: {formatCurrency(client.paid_ytd || 0)}</div>
            </div>
          </div>

          <div className="border-t border-[var(--grey)] pt-3 grid grid-cols-2 gap-4 text-sm">
            <div>AR Outstanding: {formatCurrency(client.ar_outstanding || 0)}</div>
            <div>AR Overdue: {formatCurrency(client.ar_overdue || 0)}</div>
          </div>

          <div className="border-t border-[var(--grey)] pt-3 grid grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-[var(--grey-light)] text-xs">Engagements</div>
              <div className="text-lg font-medium">{client.active_engagements || 0}</div>
            </div>
            <div>
              <div className="text-[var(--grey-light)] text-xs">Open Tasks</div>
              <div className="text-lg font-medium">{client.open_tasks || 0}</div>
            </div>
            <div>
              <div className="text-[var(--grey-light)] text-xs">Overdue</div>
              <div className="text-lg font-medium text-[var(--danger)]">
                {client.tasks_overdue || 0}
              </div>
            </div>
            <div>
              <div className="text-[var(--grey-light)] text-xs">Signals (30d)</div>
              <div className="text-sm">
                <span className="text-[var(--success)]">{client.signals_good || 0}↑</span>{' '}
                <span className="text-[var(--grey-light)]">{client.signals_neutral || 0}→</span>{' '}
                <span className="text-[var(--danger)]">{client.signals_bad || 0}↓</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Top Issues */}
      {(client.top_issues?.length ?? 0) > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Top Issues (high/critical)</h3>
          <div className="space-y-2">
            {client.top_issues.slice(0, 5).map((issue) => (
              <IssueCard key={issue.id} issue={issue} onAction={onIssueAction} />
            ))}
          </div>
        </div>
      )}

      {/* Recent Positive Signals */}
      {(client.recent_positive_signals?.length ?? 0) > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Recent Positive Signals</h3>
          <div className="bg-[var(--black)] rounded p-3 space-y-2">
            {client.recent_positive_signals.slice(0, 3).map((signal) => (
              <div key={signal.id} className="flex items-start gap-2 text-sm">
                <span>🟢</span>
                <div className="flex-1">
                  <span className="text-[var(--white)]">{signal.summary}</span>
                </div>
                <span className="text-[var(--grey)]">{formatAge(signal.observed_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Issue Card for Overview
function IssueCard({
  issue,
  onAction,
}: {
  issue: ClientIssue;
  onAction: (id: string, action: string) => void;
}) {
  return (
    <div className="bg-[var(--black)] rounded p-3">
      <div className="flex items-start gap-2">
        <span className="text-xl">{ISSUE_TYPE_ICONS[issue.type] || '⚠️'}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs uppercase text-[var(--grey-light)]">{issue.type}</span>
            <span>—</span>
            <span className="text-[var(--white)]">{issue.title}</span>
            <span
              className={`px-1.5 py-0.5 rounded text-xs ${SEVERITY_COLORS[issue.severity || 'medium']}`}
            >
              {issue.severity || 'medium'}
            </span>
          </div>
          <div className="text-sm text-[var(--grey-light)] mb-2">
            Issue State: {issue.state}
            {issue.assigned_to && ` (assigned to ${issue.assigned_to.name})`}
          </div>
          {issue.evidence && (
            <div className="text-sm text-[var(--grey-light)] mb-2">
              Evidence: {issue.evidence.display_text}
              {issue.evidence.url && (
                <a
                  href={issue.evidence.url}
                  target="_blank"
                  rel="noopener"
                  className="ml-1 text-[var(--info)]"
                >
                  ↗
                </a>
              )}
            </div>
          )}
          <div className="flex gap-2">
            {issue.available_actions.map((action) => (
              <button
                key={action}
                onClick={() => onAction(issue.id, action)}
                className="px-2 py-1 bg-[var(--grey)] hover:bg-[var(--grey-light)] rounded text-xs"
              >
                {action.charAt(0).toUpperCase() + action.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ==== Tab: Engagements (§3.3) ====

function EngagementsTab({ brands }: { brands: Brand[] }) {
  if (brands.length === 0) {
    return <div className="text-center py-8 text-[var(--grey-light)]">No engagements</div>;
  }

  return (
    <div className="space-y-6">
      {brands.map((brand) => (
        <div key={brand.id}>
          <h3 className="text-lg font-semibold mb-3">{brand.name}</h3>
          <div className="space-y-2">
            {brand.engagements.map((eng) => (
              <div key={eng.id} className="bg-[var(--black)] rounded p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-[var(--white)]">{eng.name}</span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs ${
                      eng.type === 'retainer' ? 'bg-blue-600' : 'bg-[var(--success)]'
                    }`}
                  >
                    {eng.type.toUpperCase()}
                  </span>
                </div>
                <div className="text-sm text-[var(--grey-light)] mb-2">State: {eng.state}</div>
                <div className="text-sm text-[var(--grey-light)] mb-2">
                  Tasks: {eng.open_tasks} open · {eng.overdue_tasks} overdue · {eng.completed_tasks}{' '}
                  completed
                </div>
                {eng.health_score !== null && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-[var(--grey-light)]">Health:</span>
                    <div className="flex-1 h-2 bg-[var(--grey)] rounded-full overflow-hidden max-w-32">
                      <div
                        className={`h-full ${getHealthBg(eng.health_score)}`}
                        style={{ width: `${eng.health_score}%` }}
                      />
                    </div>
                    <span className={`text-sm ${getHealthColor(eng.health_score)}`}>
                      {eng.health_score}
                    </span>
                  </div>
                )}
                {eng.asana_url && (
                  <a
                    href={eng.asana_url}
                    target="_blank"
                    rel="noopener"
                    className="text-sm text-[var(--info)] mt-2 inline-block"
                  >
                    View in Asana ↗
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ==== Tab: Financials (§3.4) ====

function FinancialsTab({ client }: { client: ClientDetail }) {
  return (
    <div className="space-y-6">
      {/* Summary */}
      <div>
        <h3 className="text-lg font-semibold mb-3">Summary</h3>
        <div className="bg-[var(--black)] rounded p-4 grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-[var(--grey-light)] text-xs mb-1">ISSUED</div>
            <div>Prior Yr: {formatCurrency(client.issued_year || 0)}</div>
            <div>YTD: {formatCurrency(client.issued_ytd || 0)}</div>
            <div>Lifetime: {formatCurrency(client.issued_lifetime || 0)}</div>
          </div>
          <div>
            <div className="text-[var(--grey-light)] text-xs mb-1">PAID</div>
            <div>Prior Yr: {formatCurrency(client.paid_year || 0)}</div>
            <div>YTD: {formatCurrency(client.paid_ytd || 0)}</div>
            <div>Lifetime: {formatCurrency(client.paid_lifetime || 0)}</div>
          </div>
        </div>
      </div>

      {/* AR Aging */}
      <div>
        <h3 className="text-lg font-semibold mb-3">AR Aging</h3>
        <div className="bg-[var(--black)] rounded p-4">
          <div className="text-lg font-medium mb-3">
            Total Outstanding: {formatCurrency(client.ar_outstanding || 0)}
          </div>
          <div className="space-y-2">
            {(client.ar_aging || []).map((bucket) => (
              <div key={bucket.bucket} className="flex items-center gap-2 text-sm">
                <div className="w-32 text-[var(--grey-light)]">{bucket.bucket}:</div>
                <div className="w-24">{formatCurrency(bucket.amount)}</div>
                <div className="flex-1 h-3 bg-[var(--grey)] rounded overflow-hidden">
                  <div className="h-full bg-[var(--info)]" style={{ width: `${bucket.pct}%` }} />
                </div>
                <div className="w-12 text-right">{bucket.pct}%</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Invoices */}
      <div>
        <h3 className="text-lg font-semibold mb-3">Invoices</h3>
        <div className="bg-[var(--black)] rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--grey-dim)]">
              <tr>
                <th className="text-left p-3">Invoice</th>
                <th className="text-left p-3">Issue Date</th>
                <th className="text-right p-3">Amount</th>
                <th className="text-left p-3">Status</th>
                <th className="text-right p-3">Aging</th>
              </tr>
            </thead>
            <tbody>
              {(client.invoices || []).slice(0, 10).map((inv) => (
                <tr key={inv.id} className="border-t border-[var(--grey)]">
                  <td className="p-3">{inv.number}</td>
                  <td className="p-3">{inv.issue_date}</td>
                  <td className="p-3 text-right">{formatCurrency(inv.amount)}</td>
                  <td className="p-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        inv.status === 'paid'
                          ? 'bg-[var(--success)]'
                          : inv.status === 'overdue'
                            ? 'bg-[var(--danger)]'
                            : 'bg-[var(--grey-light)]'
                      }`}
                    >
                      {inv.status.toUpperCase()}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    {inv.days_overdue ? `${inv.days_overdue}d` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ==== Tab: Signals (§3.5) ====

function SignalsTab({
  signals,
  summary,
}: {
  signals: Signal[];
  summary: { good: number; neutral: number; bad: number };
}) {
  const [filter, setFilter] = useState<string>('all');

  const filtered = filter === 'all' ? signals : signals.filter((s) => s.sentiment === filter);

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="bg-[var(--black)] rounded p-4">
        <h4 className="text-sm text-[var(--grey-light)] mb-2">Signal Summary (Last 30 Days)</h4>
        <div className="flex gap-6 text-lg">
          <span>🟢 Good: {summary.good}</span>
          <span>🟡 Neutral: {summary.neutral}</span>
          <span>🔴 Bad: {summary.bad}</span>
        </div>
      </div>

      {/* Filter */}
      <div className="flex gap-2">
        {['all', 'good', 'neutral', 'bad'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded text-sm ${
              filter === f ? 'bg-[var(--grey-light)]' : 'bg-[var(--grey-dim)]'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Signals List */}
      <div className="space-y-2">
        {filtered.length === 0 ? (
          <div className="text-center py-8 text-[var(--grey-light)]">No signals</div>
        ) : (
          filtered.map((signal) => (
            <div key={signal.id} className="bg-[var(--black)] rounded p-3">
              <div className="flex items-start gap-2">
                <span className="text-lg">{SENTIMENT_ICONS[signal.sentiment]}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-sm text-[var(--grey-light)] mb-1">
                    <span className="uppercase">{signal.sentiment}</span>
                    <span>—</span>
                    <span>Source: {signal.source}</span>
                    <span className="ml-auto">{formatAge(signal.observed_at)}</span>
                  </div>
                  <div className="text-[var(--white)]">{signal.summary}</div>
                  {signal.evidence?.url && (
                    <a
                      href={signal.evidence.url}
                      target="_blank"
                      rel="noopener"
                      className="text-sm text-[var(--info)] mt-1 inline-block"
                    >
                      View ↗
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ==== Tab: Team (§3.6) ====

function TeamTab({ members }: { members: TeamMember[] }) {
  if (members.length === 0) {
    return <div className="text-center py-8 text-[var(--grey-light)]">No team members</div>;
  }

  return (
    <div className="space-y-2">
      {members.map((member) => (
        <div key={member.id} className="bg-[var(--black)] rounded p-3 flex items-center gap-4">
          <div className="w-10 h-10 bg-[var(--grey)] rounded-full flex items-center justify-center text-lg">
            {member.name.charAt(0)}
          </div>
          <div className="flex-1">
            <div className="font-medium text-[var(--white)]">{member.name}</div>
            <div className="text-sm text-[var(--grey-light)]">{member.role}</div>
            {member.email && <div className="text-sm text-[var(--grey)]">{member.email}</div>}
          </div>
          <div className="text-sm text-right">
            <div>{member.open_tasks} open tasks</div>
            {member.overdue_tasks > 0 && (
              <div className="text-[var(--danger)]">{member.overdue_tasks} overdue</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ==== Tab: Email Participants (§3.7) ====

function EmailParticipantsTab({ data }: { data?: api.ClientEmailParticipantsResponse }) {
  if (!data || (!data.participants?.length && !data.labels?.length)) {
    return (
      <div className="text-center py-8 text-[var(--grey-light)]">
        No email participant data available. Run the Gmail collector to populate.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Participants Table */}
      {data.participants && data.participants.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Participants</h3>
          <div className="bg-[var(--black)] rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--grey-dim)]">
                <tr>
                  <th className="text-left p-3">Email</th>
                  <th className="text-left p-3">Name</th>
                  <th className="text-left p-3">Role</th>
                  <th className="text-right p-3">Messages</th>
                </tr>
              </thead>
              <tbody>
                {data.participants.map((participant) => (
                  <tr key={participant.email} className="border-t border-[var(--grey)]">
                    <td className="p-3 text-[var(--info)]">{participant.email}</td>
                    <td className="p-3">{participant.name}</td>
                    <td className="p-3 text-[var(--grey-light)]">{participant.role}</td>
                    <td className="p-3 text-right">{participant.message_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Labels Section */}
      {data.labels && data.labels.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Labels</h3>
          <div className="bg-[var(--black)] rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--grey-dim)]">
                <tr>
                  <th className="text-left p-3">Label</th>
                  <th className="text-right p-3">Messages</th>
                </tr>
              </thead>
              <tbody>
                {data.labels.map((label) => (
                  <tr key={label.label_name} className="border-t border-[var(--grey)]">
                    <td className="p-3">{label.label_name}</td>
                    <td className="p-3 text-right">{label.message_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ==== Tab: Attachments (§3.8) ====

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

function AttachmentsTab({ data }: { data?: api.ClientAttachmentsResponse }) {
  if (!data || !data.attachments?.length) {
    return (
      <div className="text-center py-8 text-[var(--grey-light)]">
        No attachment data available. Run the Gmail collector to populate.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      {(data.total !== undefined || data.total_size_bytes !== undefined) && (
        <div className="bg-[var(--black)] rounded p-4 grid grid-cols-2 gap-4 text-sm">
          {data.total !== undefined && (
            <div>
              <div className="text-[var(--grey-light)] text-xs mb-1">Total Count</div>
              <div className="text-lg font-medium">{data.total}</div>
            </div>
          )}
          {data.total_size_bytes !== undefined && (
            <div>
              <div className="text-[var(--grey-light)] text-xs mb-1">Total Size</div>
              <div className="text-lg font-medium">{formatFileSize(data.total_size_bytes)}</div>
            </div>
          )}
        </div>
      )}

      {/* Attachments Table */}
      <div className="bg-[var(--black)] rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--grey-dim)]">
            <tr>
              <th className="text-left p-3">Filename</th>
              <th className="text-left p-3">MIME Type</th>
              <th className="text-right p-3">Size</th>
              <th className="text-left p-3">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.attachments.map((attachment, idx) => (
              <tr key={`${attachment.filename}-${idx}`} className="border-t border-[var(--grey)]">
                <td className="p-3">{attachment.filename}</td>
                <td className="p-3 text-[var(--grey-light)]">{attachment.mime_type}</td>
                <td className="p-3 text-right">{formatFileSize(attachment.size_bytes ?? 0)}</td>
                <td className="p-3 text-[var(--grey-light)]">{formatAge(attachment.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ==== Tab: Invoice Detail (§3.9) ====

function InvoiceDetailTab({ data }: { data?: api.ClientInvoiceDetailResponse }) {
  if (!data || (!data.line_items?.length && !data.credit_notes?.length)) {
    return (
      <div className="text-center py-8 text-[var(--grey-light)]">
        No invoice detail data available. Run the Xero collector to populate.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Line Items Table */}
      {data.line_items && data.line_items.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Line Items</h3>
          <div className="bg-[var(--black)] rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--grey-dim)]">
                <tr>
                  <th className="text-left p-3">Invoice ID</th>
                  <th className="text-left p-3">Description</th>
                  <th className="text-right p-3">Quantity</th>
                  <th className="text-right p-3">Unit Amount</th>
                  <th className="text-right p-3">Line Amount</th>
                  <th className="text-left p-3">Tax Type</th>
                </tr>
              </thead>
              <tbody>
                {data.line_items.map((item, idx) => (
                  <tr key={`${item.invoice_id}-${idx}`} className="border-t border-[var(--grey)]">
                    <td className="p-3 text-[var(--info)]">{item.invoice_id}</td>
                    <td className="p-3">{item.description}</td>
                    <td className="p-3 text-right">{item.quantity}</td>
                    <td className="p-3 text-right">{formatCurrency(item.unit_amount ?? 0)}</td>
                    <td className="p-3 text-right font-medium">
                      {formatCurrency(item.line_amount ?? 0)}
                    </td>
                    <td className="p-3 text-[var(--grey-light)]">{item.tax_type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Credit Notes Table */}
      {data.credit_notes && data.credit_notes.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Credit Notes</h3>
          <div className="bg-[var(--black)] rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--grey-dim)]">
                <tr>
                  <th className="text-left p-3">Date</th>
                  <th className="text-left p-3">Status</th>
                  <th className="text-right p-3">Total</th>
                  <th className="text-left p-3">Currency</th>
                  <th className="text-right p-3">Remaining Credit</th>
                </tr>
              </thead>
              <tbody>
                {data.credit_notes.map((note, idx) => (
                  <tr key={`${note.date}-${idx}`} className="border-t border-[var(--grey)]">
                    <td className="p-3 text-[var(--grey-light)]">{note.date}</td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          note.status === 'submitted'
                            ? 'bg-[var(--success)]'
                            : note.status === 'draft'
                              ? 'bg-[var(--grey-light)]'
                              : 'bg-[var(--info)]'
                        }`}
                      >
                        {(note.status ?? 'unknown').toUpperCase()}
                      </span>
                    </td>
                    <td className="p-3 text-right font-medium">
                      {formatCurrency(note.total ?? 0)}
                    </td>
                    <td className="p-3 text-[var(--grey-light)]">{note.currency_code}</td>
                    <td className="p-3 text-right">{formatCurrency(note.remaining_credit ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default ClientDetailSpec;
