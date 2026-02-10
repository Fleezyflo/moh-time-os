/**
 * Issue Domain Mapper
 */

import type { IssueViewModel, IssueState, ProposalSeverity } from './types';

interface IssueDTO {
  id?: string | null;
  type?: string | null;
  title?: string | null;
  severity?: string | null;
  state?: string | null;
  client_id?: string | null;
  client_name?: string | null;
  resolution?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export function mapIssue(dto: IssueDTO): IssueViewModel {
  const severity = normalizeSeverity(dto.severity);
  const state = normalizeState(dto.state);

  return {
    id: dto.id ?? 'unknown',
    type: dto.type ?? 'unknown',
    title: dto.title ?? 'Untitled Issue',
    severity,
    severityLabel: getSeverityLabel(severity),
    severityColor: getSeverityColor(severity),
    state,
    stateLabel: getStateLabel(state),
    clientId: dto.client_id ?? '',
    clientName: dto.client_name ?? 'Unknown Client',
    resolution: dto.resolution ?? null,
    createdAt: dto.created_at ?? new Date().toISOString(),
    updatedAt: dto.updated_at ?? new Date().toISOString(),
    canResolve: state === 'open' || state === 'in-progress',
    canReopen: state === 'resolved' || state === 'closed',
  };
}

export function mapIssues(dtos: IssueDTO[]): IssueViewModel[] {
  return dtos.map(mapIssue);
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

function normalizeState(s: string | null | undefined): IssueState {
  switch (s?.toLowerCase()) {
    case 'open':
      return 'open';
    case 'in-progress':
    case 'in_progress':
      return 'in-progress';
    case 'resolved':
      return 'resolved';
    case 'closed':
      return 'closed';
    default:
      return 'open';
  }
}

function getSeverityLabel(s: ProposalSeverity): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function getSeverityColor(s: ProposalSeverity): IssueViewModel['severityColor'] {
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

function getStateLabel(s: IssueState): string {
  switch (s) {
    case 'open':
      return 'Open';
    case 'in-progress':
      return 'In Progress';
    case 'resolved':
      return 'Resolved';
    case 'closed':
      return 'Closed';
  }
}
