/**
 * Domain Types - Never-null view models for UI consumption.
 */

// ============================================================================
// Client Domain
// ============================================================================

export interface ClientViewModel {
  id: string;
  name: string;
  status: 'active' | 'inactive' | 'at-risk' | 'churned';
  tier: 'A' | 'B' | 'C' | 'D';
  healthScore: number;
  healthLabel: 'Healthy' | 'Warning' | 'Critical';
  healthColor: 'green' | 'yellow' | 'red';
  lastActivityDate: string;
  lastActivityRelative: string;
}

// ============================================================================
// Proposal Domain
// ============================================================================

export type ProposalSeverity = 'low' | 'medium' | 'high' | 'critical';
export type ProposalStatus = 'open' | 'dismissed' | 'snoozed' | 'tagged';

export interface ProposalViewModel {
  id: string;
  type: string;
  title: string;
  severity: ProposalSeverity;
  severityLabel: string;
  severityColor: 'gray' | 'yellow' | 'orange' | 'red';
  status: ProposalStatus;
  clientId: string;
  clientName: string;
  createdAt: string;
  createdAtRelative: string;
  canDismiss: boolean;
  canSnooze: boolean;
  canTag: boolean;
}

// ============================================================================
// Issue Domain
// ============================================================================

export type IssueState = 'open' | 'in-progress' | 'resolved' | 'closed';

export interface IssueViewModel {
  id: string;
  type: string;
  title: string;
  severity: ProposalSeverity;
  severityLabel: string;
  severityColor: 'gray' | 'yellow' | 'orange' | 'red';
  state: IssueState;
  stateLabel: string;
  clientId: string;
  clientName: string;
  resolution: string | null;
  createdAt: string;
  updatedAt: string;
  canResolve: boolean;
  canReopen: boolean;
}

// ============================================================================
// Health Factors
// ============================================================================

export interface HealthFactorsViewModel {
  overdueTasks: number;
  unpaidInvoices: number;
  recentActivity: boolean;
  daysSinceLastContact: number;
}
