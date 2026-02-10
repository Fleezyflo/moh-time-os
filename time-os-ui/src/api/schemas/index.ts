/**
 * Zod schemas for API response validation.
 * All API responses MUST be validated through these schemas.
 * 
 * This ensures:
 * 1. Runtime type safety - catch API contract violations early
 * 2. Drift detection - schema changes fail fast in tests
 * 3. Type inference - TS types derived from zod schemas
 */

import { z } from 'zod';

// ============================================================================
// Common Schemas
// ============================================================================

export const healthResponseSchema = z.object({
  status: z.enum(['healthy', 'unhealthy']),
  timestamp: z.string(),
  version: z.string().optional(),
  database: z.object({
    connected: z.boolean(),
    signals: z.number(),
    issues: z.number(),
    clients: z.number(),
  }).optional(),
  error: z.string().optional(),
});

export type HealthResponse = z.infer<typeof healthResponseSchema>;

// ============================================================================
// API Error Schema
// ============================================================================

export const apiErrorSchema = z.object({
  detail: z.string().optional(),
  error: z.string().optional(),
  message: z.string().optional(),
  code: z.string().optional(),
  request_id: z.string().optional(),
});

export type ApiErrorResponse = z.infer<typeof apiErrorSchema>;

// ============================================================================
// Core Entity Schemas
// ============================================================================

export const clientSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.string().optional(),
  tier: z.string().optional(),
  health_score: z.number().optional(),
  last_activity: z.string().optional(),
});

export type Client = z.infer<typeof clientSchema>;

export const proposalSchema = z.object({
  id: z.string(),
  type: z.string(),
  title: z.string().optional(),
  description: z.string().optional(),
  severity: z.string().optional(),
  client_id: z.string().optional(),
  client_name: z.string().optional(),
  created_at: z.string().optional(),
  status: z.string().optional(),
  evidence: z.unknown().optional(),
});

export type Proposal = z.infer<typeof proposalSchema>;

export const issueSchema = z.object({
  id: z.string(),
  type: z.string(),
  title: z.string().optional(),
  severity: z.string().optional(),
  state: z.string().optional(),
  client_id: z.string().optional(),
  client_name: z.string().optional(),
  created_at: z.string().optional(),
  tagged_at: z.string().optional(),
  resolved_at: z.string().optional(),
});

export type Issue = z.infer<typeof issueSchema>;

export const teamMemberSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string().optional(),
  role: z.string().optional(),
  workload: z.number().optional(),
});

export type TeamMember = z.infer<typeof teamMemberSchema>;

// ============================================================================
// List Response Schemas
// ============================================================================

export const createListSchema = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.object({
    items: z.array(itemSchema),
    total: z.number().optional(),
    limit: z.number().optional(),
    offset: z.number().optional(),
  });

export const clientListSchema = createListSchema(clientSchema);
export const proposalListSchema = createListSchema(proposalSchema);
export const issueListSchema = createListSchema(issueSchema);
export const teamMemberListSchema = createListSchema(teamMemberSchema);

// ============================================================================
// Mutation Response Schemas
// ============================================================================

export const mutationResponseSchema = z.object({
  success: z.boolean(),
  error: z.string().optional(),
  request_id: z.string().optional(),
});

export type MutationResponse = z.infer<typeof mutationResponseSchema>;

export const tagProposalResponseSchema = mutationResponseSchema.extend({
  issue: issueSchema.optional(),
});

export const resolveIssueResponseSchema = mutationResponseSchema.extend({
  issue_id: z.string().optional(),
  state: z.string().optional(),
});

// ============================================================================
// UI-Used Endpoints List (for contract enforcement)
// ============================================================================

/**
 * List of endpoints the UI actually uses.
 * Contract tests should ensure these NEVER loosen.
 */
export const UI_USED_ENDPOINTS = [
  '/api/health',
  '/api/v2/health',
  '/api/v2/proposals',
  '/api/v2/issues',
  '/api/v2/clients',
  '/api/v2/team',
  '/api/metrics',
] as const;

export type UiUsedEndpoint = (typeof UI_USED_ENDPOINTS)[number];
