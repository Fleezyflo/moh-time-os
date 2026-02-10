/**
 * Domain Mapper Tests
 *
 * Property tests ensuring null/undefined handling and type safety.
 */

import { describe, it, expect } from 'vitest';
import { mapClient, mapClients } from '../client';
import { mapProposal, mapProposals } from '../proposal';
import { mapIssue, mapIssues } from '../issue';

describe('Client Mapper', () => {
  it('maps a complete client DTO', () => {
    const dto = {
      id: 'client-001',
      name: 'Acme Corp',
      status: 'active',
      tier: 'A',
      health_score: 85,
      last_activity: '2024-01-15T10:00:00Z',
    };

    const result = mapClient(dto);

    expect(result.id).toBe('client-001');
    expect(result.name).toBe('Acme Corp');
    expect(result.status).toBe('active');
    expect(result.tier).toBe('A');
    expect(result.healthScore).toBe(85);
    expect(result.healthLabel).toBe('Healthy');
    expect(result.healthColor).toBe('green');
  });

  it('handles null/undefined fields with defaults', () => {
    const dto = {
      id: null,
      name: undefined,
      status: null,
      tier: null,
      health_score: null,
      last_activity: null,
    };

    const result = mapClient(dto);

    expect(result.id).toBe('unknown');
    expect(result.name).toBe('Unknown Client');
    expect(result.status).toBe('inactive');
    expect(result.tier).toBe('C');
    expect(result.healthScore).toBe(50);
    expect(result.healthLabel).toBe('Warning');
  });

  it('handles empty object', () => {
    const result = mapClient({});

    expect(result.id).toBe('unknown');
    expect(result.name).toBe('Unknown Client');
    expect(result.healthScore).toBe(50);
  });

  it('normalizes status variations', () => {
    expect(mapClient({ status: 'at_risk' }).status).toBe('at-risk');
    expect(mapClient({ status: 'AT-RISK' }).status).toBe('at-risk');
    expect(mapClient({ status: 'Active' }).status).toBe('active');
    expect(mapClient({ status: 'CHURNED' }).status).toBe('churned');
  });

  it('maps array of clients', () => {
    const dtos = [{ id: '1', name: 'A' }, { id: '2', name: 'B' }];
    const result = mapClients(dtos);

    expect(result).toHaveLength(2);
    expect(result[0].id).toBe('1');
    expect(result[1].id).toBe('2');
  });
});

describe('Proposal Mapper', () => {
  it('maps a complete proposal DTO', () => {
    const dto = {
      id: 'prop-001',
      type: 'overdue_task',
      title: 'Task overdue',
      severity: 'high',
      status: 'open',
      client_id: 'client-001',
      client_name: 'Acme Corp',
      created_at: '2024-01-15T10:00:00Z',
    };

    const result = mapProposal(dto);

    expect(result.id).toBe('prop-001');
    expect(result.severity).toBe('high');
    expect(result.severityColor).toBe('orange');
    expect(result.canDismiss).toBe(true);
    expect(result.canTag).toBe(true);
  });

  it('handles null fields', () => {
    const result = mapProposal({});

    expect(result.id).toBe('unknown');
    expect(result.title).toBe('Untitled Proposal');
    expect(result.severity).toBe('medium');
    expect(result.status).toBe('open');
  });

  it('disables actions for non-open proposals', () => {
    expect(mapProposal({ status: 'dismissed' }).canDismiss).toBe(false);
    expect(mapProposal({ status: 'snoozed' }).canSnooze).toBe(false);
    expect(mapProposal({ status: 'tagged' }).canTag).toBe(false);
  });
});

describe('Issue Mapper', () => {
  it('maps a complete issue DTO', () => {
    const dto = {
      id: 'issue-001',
      type: 'overdue_task',
      title: 'Critical issue',
      severity: 'critical',
      state: 'open',
      client_id: 'client-001',
      client_name: 'Acme Corp',
      resolution: null,
    };

    const result = mapIssue(dto);

    expect(result.id).toBe('issue-001');
    expect(result.severity).toBe('critical');
    expect(result.severityColor).toBe('red');
    expect(result.state).toBe('open');
    expect(result.canResolve).toBe(true);
    expect(result.canReopen).toBe(false);
  });

  it('handles null fields', () => {
    const result = mapIssue({});

    expect(result.id).toBe('unknown');
    expect(result.title).toBe('Untitled Issue');
    expect(result.state).toBe('open');
  });

  it('normalizes state variations', () => {
    expect(mapIssue({ state: 'in_progress' }).state).toBe('in-progress');
    expect(mapIssue({ state: 'IN-PROGRESS' }).state).toBe('in-progress');
    expect(mapIssue({ state: 'resolved' }).state).toBe('resolved');
  });

  it('sets correct action flags by state', () => {
    expect(mapIssue({ state: 'open' }).canResolve).toBe(true);
    expect(mapIssue({ state: 'open' }).canReopen).toBe(false);
    expect(mapIssue({ state: 'resolved' }).canResolve).toBe(false);
    expect(mapIssue({ state: 'resolved' }).canReopen).toBe(true);
  });

  it('maps array of issues', () => {
    const dtos = [{ id: '1' }, { id: '2' }];
    const result = mapIssues(dtos);

    expect(result).toHaveLength(2);
  });
});
