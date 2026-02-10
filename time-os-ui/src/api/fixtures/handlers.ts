/**
 * MSW Request Handlers for API Mocking.
 * 
 * These handlers provide consistent mock responses for testing.
 * Fixtures are validated against zod schemas to ensure contract compliance.
 */

import { http, HttpResponse } from 'msw';
import {
  healthResponseSchema,
  clientListSchema,
  proposalListSchema,
  issueListSchema,
  teamMemberListSchema,
} from '../schemas';

// ============================================================================
// Fixture Data
// ============================================================================

export const fixtures = {
  health: {
    status: 'healthy' as const,
    timestamp: new Date().toISOString(),
    version: '1.0.0',
    database: {
      connected: true,
      signals: 42,
      issues: 5,
      clients: 12,
    },
  },

  clients: {
    items: [
      { id: 'client-1', name: 'Acme Corp', status: 'active', tier: 'A', health_score: 85 },
      { id: 'client-2', name: 'Tech Inc', status: 'active', tier: 'B', health_score: 72 },
      { id: 'client-3', name: 'StartupCo', status: 'at-risk', tier: 'B', health_score: 45 },
    ],
    total: 3,
  },

  proposals: {
    items: [
      { id: 'prop-1', type: 'overdue_task', title: 'Task overdue by 3 days', severity: 'high', client_id: 'client-1', client_name: 'Acme Corp', status: 'open' },
      { id: 'prop-2', type: 'at_risk', title: 'Client health declining', severity: 'medium', client_id: 'client-3', client_name: 'StartupCo', status: 'open' },
    ],
    total: 2,
  },

  issues: {
    items: [
      { id: 'issue-1', type: 'overdue_task', title: 'Critical task overdue', severity: 'high', state: 'open', client_id: 'client-1', client_name: 'Acme Corp' },
    ],
    total: 1,
  },

  team: {
    items: [
      { id: 'member-1', name: 'Alice', email: 'alice@example.com', role: 'developer', workload: 0.8 },
      { id: 'member-2', name: 'Bob', email: 'bob@example.com', role: 'designer', workload: 0.6 },
    ],
    total: 2,
  },
};

// ============================================================================
// Fixture Validation
// ============================================================================

/**
 * Validate all fixtures against their schemas.
 * Call this at test setup to catch schema drift.
 */
export function validateFixtures(): void {
  const validations = [
    { name: 'health', schema: healthResponseSchema, data: fixtures.health },
    { name: 'clients', schema: clientListSchema, data: fixtures.clients },
    { name: 'proposals', schema: proposalListSchema, data: fixtures.proposals },
    { name: 'issues', schema: issueListSchema, data: fixtures.issues },
    { name: 'team', schema: teamMemberListSchema, data: fixtures.team },
  ];

  for (const { name, schema, data } of validations) {
    const result = schema.safeParse(data);
    if (!result.success) {
      throw new Error(`Fixture '${name}' validation failed: ${result.error.message}`);
    }
  }
}

// ============================================================================
// MSW Handlers
// ============================================================================

export const handlers = [
  // Health
  http.get('*/api/health', () => {
    return HttpResponse.json(fixtures.health);
  }),
  http.get('*/api/v2/health', () => {
    return HttpResponse.json(fixtures.health);
  }),

  // Clients
  http.get('*/api/v2/clients', () => {
    return HttpResponse.json(fixtures.clients);
  }),

  // Proposals
  http.get('*/api/v2/proposals', () => {
    return HttpResponse.json(fixtures.proposals);
  }),

  // Issues
  http.get('*/api/v2/issues', () => {
    return HttpResponse.json(fixtures.issues);
  }),

  // Team
  http.get('*/api/v2/team', () => {
    return HttpResponse.json(fixtures.team);
  }),

  // Metrics
  http.get('*/api/metrics', () => {
    return new HttpResponse(
      '# HELP api_requests_total Total API requests\n# TYPE api_requests_total counter\napi_requests_total 0\n',
      { headers: { 'Content-Type': 'text/plain' } }
    );
  }),
];

export default handlers;
