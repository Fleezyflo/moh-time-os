/**
 * TanStack Query hooks for API data fetching.
 * 
 * Standardized query keys and hooks for all API endpoints.
 * Features:
 * - Consistent stale times and retry policies
 * - Type-safe through zod schema inference
 * - Automatic cache invalidation patterns
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { get, post, patch } from '../http';
import {
  healthResponseSchema,
  clientListSchema,
  proposalListSchema,
  issueListSchema,
  teamMemberListSchema,
  mutationResponseSchema,
  tagProposalResponseSchema,
  resolveIssueResponseSchema,
  type HealthResponse,
  type Client,
  type Proposal,
  type Issue,
  type TeamMember,
} from '../schemas';
import { z } from 'zod';

// ============================================================================
// Query Keys - Standardized and type-safe
// ============================================================================

export const queryKeys = {
  health: ['health'] as const,
  clients: () => ['clients'] as const,
  client: (id: string) => ['clients', id] as const,
  proposals: (params?: { status?: string; limit?: number }) => ['proposals', params] as const,
  issues: (params?: { limit?: number }) => ['issues', params] as const,
  issue: (id: string) => ['issues', id] as const,
  team: () => ['team'] as const,
  teamMember: (id: string) => ['team', id] as const,
};

// ============================================================================
// Default Query Options
// ============================================================================

const DEFAULT_STALE_TIME = 30 * 1000; // 30 seconds
const DEFAULT_RETRY = 2;

// ============================================================================
// Health Hook
// ============================================================================

export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: queryKeys.health,
    queryFn: () => get('/health', healthResponseSchema),
    staleTime: 10 * 1000, // 10 seconds for health
    retry: 1,
  });
}

// ============================================================================
// Clients Hooks
// ============================================================================

type ClientListResponse = z.infer<typeof clientListSchema>;

export function useClients() {
  return useQuery<ClientListResponse>({
    queryKey: queryKeys.clients(),
    queryFn: () => get('/clients', clientListSchema),
    staleTime: DEFAULT_STALE_TIME,
    retry: DEFAULT_RETRY,
  });
}

// ============================================================================
// Proposals Hooks
// ============================================================================

type ProposalListResponse = z.infer<typeof proposalListSchema>;

interface UseProposalsOptions {
  status?: string;
  limit?: number;
  enabled?: boolean;
}

export function useProposals(options: UseProposalsOptions = {}) {
  const { status = 'open', limit = 10, enabled = true } = options;

  return useQuery<ProposalListResponse>({
    queryKey: queryKeys.proposals({ status, limit }),
    queryFn: () => get(`/proposals?status=${status}&limit=${limit}`, proposalListSchema),
    staleTime: DEFAULT_STALE_TIME,
    retry: DEFAULT_RETRY,
    enabled,
  });
}

// ============================================================================
// Issues Hooks
// ============================================================================

type IssueListResponse = z.infer<typeof issueListSchema>;

interface UseIssuesOptions {
  limit?: number;
  enabled?: boolean;
}

export function useIssues(options: UseIssuesOptions = {}) {
  const { limit = 10, enabled = true } = options;

  return useQuery<IssueListResponse>({
    queryKey: queryKeys.issues({ limit }),
    queryFn: () => get(`/issues?limit=${limit}`, issueListSchema),
    staleTime: DEFAULT_STALE_TIME,
    retry: DEFAULT_RETRY,
    enabled,
  });
}

// ============================================================================
// Team Hooks
// ============================================================================

type TeamListResponse = z.infer<typeof teamMemberListSchema>;

export function useTeam() {
  return useQuery<TeamListResponse>({
    queryKey: queryKeys.team(),
    queryFn: () => get('/team', teamMemberListSchema),
    staleTime: DEFAULT_STALE_TIME,
    retry: DEFAULT_RETRY,
  });
}

// ============================================================================
// Mutation Hooks
// ============================================================================

export function useTagProposal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (proposalId: string) =>
      post(`/issues`, { proposal_id: proposalId }, tagProposalResponseSchema),
    onSuccess: () => {
      // Invalidate proposals and issues queries
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['issues'] });
    },
  });
}

export function useResolveIssue() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ issueId, resolution }: { issueId: string; resolution?: string }) =>
      patch(`/issues/${issueId}/resolve`, { resolution: resolution || 'resolved' }, resolveIssueResponseSchema),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['issues'] });
    },
  });
}

export function useDismissProposal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ proposalId, reason }: { proposalId: string; reason?: string }) =>
      post(`/proposals/${proposalId}/dismiss`, { reason: reason || 'Dismissed' }, mutationResponseSchema),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
    },
  });
}

export function useSnoozeProposal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ proposalId, days }: { proposalId: string; days?: number }) =>
      post(`/proposals/${proposalId}/snooze`, { days: days || 7 }, mutationResponseSchema),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
    },
  });
}
