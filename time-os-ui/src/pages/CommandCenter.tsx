// Agency Command Center — Executive dashboard for client health, team load, and decision queue
import { useState, useEffect } from 'react';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { TabContainer, type TabDef } from '../components/layout/TabContainer';
import { SkeletonCardGrid, SkeletonPanel } from '../components';

// Inline fetch utility for this component
async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Reusable fetch hook for command center endpoints
function useFetchCommand<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<T>(url)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [url]);

  return { data, loading, error };
}

// Type definitions
type CommandTab = 'health' | 'load' | 'decisions';

interface Client {
  client_name: string;
  total_tasks: number;
  overdue_tasks: number;
  last_meeting: string;
  days_since_last_meeting: number;
  health_status: 'critical' | 'warning' | 'healthy';
  health_reason: string;
}

interface ClientHealthResponse {
  clients: Client[];
  total: number;
  critical_count: number;
  warning_count: number;
}

interface TeamMember {
  member_name: string;
  member_email: string;
  active_tasks: number;
  overdue_tasks: number;
  meetings_this_week: number;
  load_status: 'overloaded' | 'heavy' | 'normal' | 'light';
  load_reason: string;
}

interface TeamLoadResponse {
  members: TeamMember[];
  total: number;
  overloaded_count: number;
  heavy_count: number;
}

interface DataFreshness {
  source: string;
  last_sync: string;
}

interface DecisionQueueItem {
  title?: string;
  name?: string;
}

interface DecisionQueueResponse {
  my_tasks: { count: number; items: DecisionQueueItem[] };
  my_overdue: { count: number; items: DecisionQueueItem[] };
  open_commitments: { count: number };
  critical_signals: { count: number; items: DecisionQueueItem[] };
  pending_responses: { count: number };
  resolution_items: { count: number };
  data_freshness: DataFreshness[];
  queue_summary: { total_attention_items: number; attention_flags: number };
}

const TABS: TabDef<CommandTab>[] = [
  { id: 'health', label: 'Client Health' },
  { id: 'load', label: 'Team Load' },
  { id: 'decisions', label: 'Decision Queue' },
];

function getHealthColor(status: string): string {
  switch (status) {
    case 'critical':
      return 'var(--danger)';
    case 'warning':
      return 'var(--warning)';
    case 'healthy':
      return 'var(--success)';
    default:
      return 'var(--grey)';
  }
}

function getHealthBgColor(status: string): string {
  switch (status) {
    case 'critical':
      return 'bg-[var(--danger)]/20';
    case 'warning':
      return 'bg-[var(--warning)]/20';
    case 'healthy':
      return 'bg-[var(--success)]/20';
    default:
      return 'bg-[var(--grey)]/20';
  }
}

function getLoadColor(status: string): string {
  switch (status) {
    case 'overloaded':
      return 'var(--danger)';
    case 'heavy':
      return 'var(--warning)';
    case 'normal':
      return 'var(--success)';
    case 'light':
      return 'var(--info)';
    default:
      return 'var(--grey)';
  }
}

function getLoadBgColor(status: string): string {
  switch (status) {
    case 'overloaded':
      return 'bg-[var(--danger)]/20';
    case 'heavy':
      return 'bg-[var(--warning)]/20';
    case 'normal':
      return 'bg-[var(--success)]/20';
    case 'light':
      return 'bg-[var(--info)]/20';
    default:
      return 'bg-[var(--grey)]/20';
  }
}

function getLoadLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

// Tab 1: Client Health
function ClientHealthTab({
  data,
  loading,
}: {
  data: ClientHealthResponse | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-[var(--grey-dim)] rounded animate-pulse" />
          ))}
        </div>
        <SkeletonCardGrid count={3} />
      </div>
    );
  }

  if (!data || data.clients.length === 0) {
    return (
      <div className="bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)] p-8 text-center">
        <p className="text-[var(--grey-light)]">No client data available</p>
      </div>
    );
  }

  const healthyCount = data.total - data.critical_count - data.warning_count;
  const sortedClients = [...data.clients].sort((a, b) => {
    const statusOrder = { critical: 0, warning: 1, healthy: 2 };
    if (
      statusOrder[a.health_status as keyof typeof statusOrder] !==
      statusOrder[b.health_status as keyof typeof statusOrder]
    ) {
      return (
        statusOrder[a.health_status as keyof typeof statusOrder] -
        statusOrder[b.health_status as keyof typeof statusOrder]
      );
    }
    return (b.overdue_tasks || 0) - (a.overdue_tasks || 0);
  });

  return (
    <div className="space-y-6">
      {/* Summary Metrics */}
      <SummaryGrid>
        <MetricCard
          label="Critical"
          value={data.critical_count}
          severity={data.critical_count > 0 ? 'danger' : 'success'}
        />
        <MetricCard
          label="Warning"
          value={data.warning_count}
          severity={data.warning_count > 0 ? 'warning' : 'success'}
        />
        <MetricCard label="Healthy" value={healthyCount} severity="success" />
        <MetricCard label="Total Clients" value={data.total} />
      </SummaryGrid>

      {/* Client Cards */}
      <div className="space-y-3">
        {sortedClients.map((client) => (
          <div
            key={client.client_name}
            className="bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)] p-4 hover:border-[var(--grey-light)] transition-colors"
          >
            <div className="flex items-start justify-between gap-4 mb-3">
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-[var(--white)] truncate">{client.client_name}</h3>
                <p className="text-sm text-[var(--grey)] mt-1">{client.health_reason}</p>
              </div>
              <span
                className={`px-2.5 py-1 rounded text-xs font-medium shrink-0 ${getHealthBgColor(client.health_status)}`}
                style={{ color: getHealthColor(client.health_status) }}
              >
                {client.health_status.charAt(0).toUpperCase() + client.health_status.slice(1)}
              </span>
            </div>

            <div className="grid grid-cols-4 gap-2">
              <div className="text-center p-2 bg-[var(--black)]/50 rounded">
                <div className="text-lg font-semibold text-[var(--white)]">
                  {client.total_tasks}
                </div>
                <div className="text-xs text-[var(--grey)]">Total</div>
              </div>
              <div
                className={`text-center p-2 rounded ${
                  client.overdue_tasks > 0 ? 'bg-[var(--danger)]/30' : 'bg-[var(--black)]/50'
                }`}
              >
                <div
                  className={`text-lg font-semibold ${
                    client.overdue_tasks > 0 ? 'text-[var(--danger)]' : 'text-[var(--white)]'
                  }`}
                >
                  {client.overdue_tasks}
                </div>
                <div className="text-xs text-[var(--grey)]">Overdue</div>
              </div>
              <div className="text-center p-2 bg-[var(--black)]/50 rounded">
                <div className="text-lg font-semibold text-[var(--white)]">
                  {client.days_since_last_meeting}
                </div>
                <div className="text-xs text-[var(--grey)]">Days</div>
              </div>
              <div className="text-center p-2 bg-[var(--black)]/50 rounded">
                <div className="text-sm font-semibold text-[var(--white)] truncate">
                  {client.last_meeting}
                </div>
                <div className="text-xs text-[var(--grey)]">Last Mtg</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Tab 2: Team Load
function TeamLoadTab({ data, loading }: { data: TeamLoadResponse | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-[var(--grey-dim)] rounded animate-pulse" />
          ))}
        </div>
        <SkeletonCardGrid count={6} />
      </div>
    );
  }

  if (!data || data.members.length === 0) {
    return (
      <div className="bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)] p-8 text-center">
        <p className="text-[var(--grey-light)]">No team data available</p>
      </div>
    );
  }

  const normalCount = data.total - data.overloaded_count - data.heavy_count;
  const sortedMembers = [...data.members].sort(
    (a, b) => (b.overdue_tasks || 0) - (a.overdue_tasks || 0)
  );

  return (
    <div className="space-y-6">
      {/* Summary Metrics */}
      <SummaryGrid>
        <MetricCard
          label="Overloaded"
          value={data.overloaded_count}
          severity={data.overloaded_count > 0 ? 'danger' : 'success'}
        />
        <MetricCard
          label="Heavy Load"
          value={data.heavy_count}
          severity={data.heavy_count > 0 ? 'warning' : 'success'}
        />
        <MetricCard label="Normal" value={normalCount} severity="success" />
        <MetricCard label="Total Members" value={data.total} />
      </SummaryGrid>

      {/* Team Member Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sortedMembers.map((member) => {
          const hasOverdue = (member.overdue_tasks || 0) > 0;

          return (
            <div
              key={member.member_email}
              className={`bg-[var(--grey-dim)] rounded-lg border transition-colors p-4 ${
                hasOverdue
                  ? 'border-[var(--danger)]/50 hover:border-[var(--danger)]'
                  : 'border-[var(--grey)] hover:border-[var(--grey-light)]'
              }`}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-[var(--white)] truncate">{member.member_name}</h3>
                  <p className="text-xs text-[var(--grey)] truncate">{member.member_email}</p>
                </div>
                <span
                  className={`px-2.5 py-1 rounded text-xs font-medium shrink-0 ${getLoadBgColor(member.load_status)}`}
                  style={{ color: getLoadColor(member.load_status) }}
                >
                  {getLoadLabel(member.load_status)}
                </span>
              </div>

              {/* Reason */}
              <p className="text-xs text-[var(--grey)] mb-3">{member.load_reason}</p>

              {/* Stats Grid */}
              <div className="grid grid-cols-3 gap-2">
                <div className="text-center p-2 bg-[var(--black)]/50 rounded">
                  <div className="text-lg font-semibold text-[var(--white)]">
                    {member.active_tasks}
                  </div>
                  <div className="text-xs text-[var(--grey)]">Active</div>
                </div>
                <div
                  className={`text-center p-2 rounded ${
                    hasOverdue ? 'bg-[var(--danger)]/30' : 'bg-[var(--black)]/50'
                  }`}
                >
                  <div
                    className={`text-lg font-semibold ${hasOverdue ? 'text-[var(--danger)]' : 'text-[var(--white)]'}`}
                  >
                    {member.overdue_tasks}
                  </div>
                  <div className="text-xs text-[var(--grey)]">Overdue</div>
                </div>
                <div className="text-center p-2 bg-[var(--black)]/50 rounded">
                  <div className="text-lg font-semibold text-[var(--info)]">
                    {member.meetings_this_week}
                  </div>
                  <div className="text-xs text-[var(--grey)]">Meetings</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Tab 3: Decision Queue
function DecisionQueueTab({
  data,
  loading,
}: {
  data: DecisionQueueResponse | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-16 bg-[var(--grey-dim)] rounded animate-pulse" />
        {Array.from({ length: 3 }).map((_, i) => (
          <SkeletonPanel key={i} rows={2} />
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)] p-8 text-center">
        <p className="text-[var(--grey-light)]">No decision queue data available</p>
      </div>
    );
  }

  const attentionLevel =
    data.queue_summary.total_attention_items > 0
      ? data.queue_summary.total_attention_items === 1
        ? '1 item'
        : `${data.queue_summary.total_attention_items} items`
      : 'nothing';

  return (
    <div className="space-y-6">
      {/* Attention Summary */}
      <div
        className="rounded-lg border p-4"
        style={{
          backgroundColor:
            data.queue_summary.total_attention_items > 0 ? 'var(--danger)' : 'var(--success)',
          borderColor: 'currentColor',
          opacity: 0.2,
        }}
      >
        <p
          className="text-lg font-semibold"
          style={{
            color:
              data.queue_summary.total_attention_items > 0 ? 'var(--danger)' : 'var(--success)',
          }}
        >
          {attentionLevel} need{data.queue_summary.total_attention_items === 1 ? 's' : ''} your
          attention
        </p>
      </div>

      {/* My Overdue Tasks */}
      {data.my_overdue.count > 0 && (
        <div className="bg-[var(--grey-dim)] rounded-lg border border-[var(--danger)]/50 p-4">
          <h3 className="font-medium text-[var(--danger)] mb-3">
            My Overdue Tasks ({data.my_overdue.count})
          </h3>
          <ul className="space-y-2">
            {data.my_overdue.items.map((item, idx) => (
              <li key={idx} className="text-sm text-[var(--white)] flex items-start gap-2">
                <span className="text-[var(--danger)] mt-0.5">•</span>
                <span>{item.title || item.name || 'Untitled task'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Critical Signals */}
      {data.critical_signals.count > 0 && (
        <div className="bg-[var(--grey-dim)] rounded-lg border border-[var(--warning)]/50 p-4">
          <h3 className="font-medium text-[var(--warning)] mb-3">
            Critical Signals ({data.critical_signals.count})
          </h3>
          <ul className="space-y-2">
            {data.critical_signals.items.map((item, idx) => (
              <li key={idx} className="text-sm text-[var(--white)] flex items-start gap-2">
                <span className="text-[var(--warning)] mt-0.5">▲</span>
                <span>{item.title || item.name || 'Unknown signal'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Open Commitments */}
      <div className="bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)] p-4">
        <h3 className="font-medium text-[var(--white)] mb-2">Open Commitments</h3>
        <p className="text-2xl font-semibold text-[var(--info)]">{data.open_commitments.count}</p>
      </div>

      {/* Pending Responses */}
      <div className="bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)] p-4">
        <h3 className="font-medium text-[var(--white)] mb-2">Pending Responses</h3>
        <p className="text-2xl font-semibold text-[var(--info)]">{data.pending_responses.count}</p>
      </div>

      {/* Resolution Items */}
      <div className="bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)] p-4">
        <h3 className="font-medium text-[var(--white)] mb-2">Resolution Items</h3>
        <p className="text-2xl font-semibold text-[var(--success)]">
          {data.resolution_items.count}
        </p>
      </div>

      {/* Data Freshness */}
      {data.data_freshness.length > 0 && (
        <div className="bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)] p-4">
          <h3 className="font-medium text-[var(--white)] mb-3">Data Freshness</h3>
          <div className="space-y-2">
            {data.data_freshness.map((item) => (
              <div key={item.source} className="flex items-center justify-between text-sm">
                <span className="text-[var(--grey)]">{item.source}</span>
                <span className="text-[var(--grey-light)]">{item.last_sync}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Main Component
export default function CommandCenter() {
  const clientHealthData = useFetchCommand<ClientHealthResponse>('/api/command/client-health');
  const teamLoadData = useFetchCommand<TeamLoadResponse>('/api/command/team-load');
  const decisionQueueData = useFetchCommand<DecisionQueueResponse>('/api/command/decisions');

  return (
    <PageLayout
      title="Agency Command Center"
      subtitle="Executive dashboard for operations oversight"
    >
      <TabContainer tabs={TABS} defaultTab="health">
        {(activeTab) => {
          switch (activeTab) {
            case 'health':
              return (
                <ClientHealthTab data={clientHealthData.data} loading={clientHealthData.loading} />
              );
            case 'load':
              return <TeamLoadTab data={teamLoadData.data} loading={teamLoadData.loading} />;
            case 'decisions':
              return (
                <DecisionQueueTab
                  data={decisionQueueData.data}
                  loading={decisionQueueData.loading}
                />
              );
            default:
              return null;
          }
        }}
      </TabContainer>
    </PageLayout>
  );
}
