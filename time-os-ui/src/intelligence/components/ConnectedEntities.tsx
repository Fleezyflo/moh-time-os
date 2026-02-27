/**
 * ConnectedEntities — Grid of cross-linked entities at bottom of any profile
 *
 * Renders non-empty entity categories as titled subsections.
 * Empty categories are hidden automatically.
 */

import { Link } from '@tanstack/react-router';
import { HealthScore } from './HealthScore';

interface ConnectedPerson {
  person_id: number | string;
  name: string;
  role?: string | null;
  task_count?: number;
  communication_volume?: number;
}

interface ConnectedProject {
  project_id: number | string;
  name: string;
  status?: string;
  health_score?: number;
  task_count?: number;
}

interface ConnectedClient {
  client_id: number | string;
  name: string;
  task_count?: number;
  communication_volume?: number;
}

interface ConnectedInvoice {
  invoice_id: number | string;
  amount: number;
  status: string;
  date: string;
}

interface ConnectedEntitiesProps {
  persons?: ConnectedPerson[] | null;
  projects?: ConnectedProject[] | null;
  clients?: ConnectedClient[] | null;
  invoices?: ConnectedInvoice[] | null;
}

const STATUS_STYLES: Record<string, string> = {
  paid: 'text-green-400',
  sent: 'text-[var(--grey-light)]',
  overdue: 'text-red-400',
  draft: 'text-[var(--grey-muted)]',
};

export function ConnectedEntities({
  persons,
  projects,
  clients,
  invoices,
}: ConnectedEntitiesProps) {
  const hasPersons = persons && persons.length > 0;
  const hasProjects = projects && projects.length > 0;
  const hasClients = clients && clients.length > 0;
  const hasInvoices = invoices && invoices.length > 0;
  const hasAny = hasPersons || hasProjects || hasClients || hasInvoices;

  if (!hasAny) return null;

  return (
    <div className="mt-8 pt-6 border-t-2 border-[var(--grey)]">
      <h3 className="text-lg font-bold text-white mb-5">Connected Entities</h3>

      {/* Persons */}
      {hasPersons && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-[var(--grey-light)] mb-3">
            People ({persons!.length})
          </h4>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {persons!.map((p) => (
              <Link
                key={p.person_id}
                to="/team/$id"
                params={{ id: String(p.person_id) }}
                className="p-3 bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg hover:bg-[var(--grey)]/50 transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-white font-medium flex items-center gap-1.5">
                    <span>👤</span>
                    {p.name}
                  </span>
                </div>
                <div className="flex gap-2 flex-wrap text-xs text-[var(--grey-muted)]">
                  {p.role && <span className="italic">{p.role}</span>}
                  {p.task_count != null && <span>{p.task_count} tasks</span>}
                  {p.communication_volume != null && <span>{p.communication_volume} msgs</span>}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Projects */}
      {hasProjects && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-[var(--grey-light)] mb-3">
            Projects ({projects!.length})
          </h4>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {projects!.map((p) => (
              <div
                key={p.project_id}
                className="p-3 bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-white font-medium flex items-center gap-1.5">
                    <span>📁</span>
                    {p.name}
                  </span>
                  {p.health_score != null && <HealthScore score={p.health_score} size="sm" />}
                </div>
                <div className="flex gap-2 flex-wrap text-xs text-[var(--grey-muted)]">
                  {p.status && <span>{p.status}</span>}
                  {p.task_count != null && <span>{p.task_count} tasks</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Clients */}
      {hasClients && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-[var(--grey-light)] mb-3">
            Clients ({clients!.length})
          </h4>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {clients!.map((c) => (
              <Link
                key={c.client_id}
                to="/clients/$clientId"
                params={{ clientId: String(c.client_id) }}
                className="p-3 bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg hover:bg-[var(--grey)]/50 transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-white font-medium flex items-center gap-1.5">
                    <span>🏢</span>
                    {c.name}
                  </span>
                </div>
                <div className="flex gap-2 flex-wrap text-xs text-[var(--grey-muted)]">
                  {c.task_count != null && <span>{c.task_count} tasks</span>}
                  {c.communication_volume != null && <span>{c.communication_volume} msgs</span>}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Invoices */}
      {hasInvoices && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-[var(--grey-light)] mb-3">
            Invoices ({invoices!.length})
          </h4>
          <div className="flex flex-col gap-1">
            {invoices!.map((inv) => (
              <div
                key={inv.invoice_id}
                className="grid grid-cols-4 gap-3 items-center py-2 px-3 text-sm border-b border-[var(--grey)]/50 last:border-0"
              >
                <span className="text-[var(--grey-muted)]">#{inv.invoice_id}</span>
                <span className="text-white font-medium">${inv.amount.toLocaleString()}</span>
                <span
                  className={STATUS_STYLES[inv.status.toLowerCase()] || 'text-[var(--grey-light)]'}
                >
                  {inv.status}
                </span>
                <span className="text-[var(--grey-muted)]">{inv.date}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
