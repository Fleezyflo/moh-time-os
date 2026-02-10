/**
 * Proposal Domain Mapper
 */

import type { ProposalViewModel, ProposalSeverity, ProposalStatus } from './types';

interface ProposalDTO {
  id?: string | null;
  type?: string | null;
  title?: string | null;
  severity?: string | null;
  status?: string | null;
  client_id?: string | null;
  client_name?: string | null;
  created_at?: string | null;
}

export function mapProposal(dto: ProposalDTO): ProposalViewModel {
  const severity = normalizeSeverity(dto.severity);
  const status = normalizeStatus(dto.status);

  return {
    id: dto.id ?? 'unknown',
    type: dto.type ?? 'unknown',
    title: dto.title ?? 'Untitled Proposal',
    severity,
    severityLabel: getSeverityLabel(severity),
    severityColor: getSeverityColor(severity),
    status,
    clientId: dto.client_id ?? '',
    clientName: dto.client_name ?? 'Unknown Client',
    createdAt: dto.created_at ?? new Date().toISOString(),
    createdAtRelative: formatRelativeDate(dto.created_at),
    canDismiss: status === 'open',
    canSnooze: status === 'open',
    canTag: status === 'open',
  };
}

export function mapProposals(dtos: ProposalDTO[]): ProposalViewModel[] {
  return dtos.map(mapProposal);
}

function normalizeSeverity(s: string | null | undefined): ProposalSeverity {
  switch (s?.toLowerCase()) {
    case 'low':
      return 'low';
    case 'medium':
      return 'medium';
    case 'high':
      return 'high';
    case 'critical':
      return 'critical';
    default:
      return 'medium';
  }
}

function normalizeStatus(s: string | null | undefined): ProposalStatus {
  switch (s?.toLowerCase()) {
    case 'open':
      return 'open';
    case 'dismissed':
      return 'dismissed';
    case 'snoozed':
      return 'snoozed';
    case 'tagged':
      return 'tagged';
    default:
      return 'open';
  }
}

function getSeverityLabel(s: ProposalSeverity): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function getSeverityColor(s: ProposalSeverity): ProposalViewModel['severityColor'] {
  switch (s) {
    case 'low':
      return 'gray';
    case 'medium':
      return 'yellow';
    case 'high':
      return 'orange';
    case 'critical':
      return 'red';
  }
}

function formatRelativeDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Unknown';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}
