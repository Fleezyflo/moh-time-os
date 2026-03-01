// React hooks for data fetching from Control Room API
import { useState, useEffect, useCallback } from 'react';
import * as api from './api';

// Generic fetch hook with error recovery
function useFetch<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const doFetch = useCallback(() => {
    setLoading(true);
    return fetcher()
      .then((result) => {
        setData(result);
        setError(null);
        return result;
      })
      .catch((err) => {
        setError(err);
        // Only log once per error in dev mode
        if (retryCount === 0 && import.meta.env.DEV) {
          console.error('Fetch error:', err.message);
        }
        throw err;
      })
      .finally(() => {
        setLoading(false);
      });
  }, [fetcher, retryCount]);

  useEffect(() => {
    // Track if component unmounts during fetch (for future abort implementation)
    const controller = { cancelled: false };
    doFetch().catch(() => {
      // Error already handled in doFetch
      // Future: check controller.cancelled before state updates
    });
    return () => {
      controller.cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps spread is intentional for dynamic dependencies
  }, [...deps, retryCount]);

  // Refetch clears error and retries
  const refetch = useCallback(() => {
    setRetryCount((c) => c + 1);
  }, []);

  // Reset error without refetching (keeps last-good-data if present)
  const resetError = useCallback(() => {
    setError(null);
  }, []);

  return { data, loading, error, refetch, resetError };
}

// Proposals
export function useProposals(
  limit = 7,
  status = 'open',
  days = 7,
  clientId?: string,
  memberId?: string
) {
  return useFetch(
    () => api.fetchProposals(limit, status, days, clientId, memberId),
    [limit, status, days, clientId, memberId]
  );
}

// Issues
export function useIssues(limit = 5, days = 7, clientId?: string, memberId?: string) {
  return useFetch(
    () => api.fetchIssues(limit, days, clientId, memberId),
    [limit, days, clientId, memberId]
  );
}

// Watchers
export function useWatchers(hours = 24) {
  return useFetch(() => api.fetchWatchers(hours), [hours]);
}

// Fix Data
export function useFixData() {
  return useFetch(() => api.fetchFixData(), []);
}

// Couplings for specific anchor
export function useCouplings(anchorType: string, anchorId: string) {
  return useFetch(() => api.fetchCouplings(anchorType, anchorId), [anchorType, anchorId]);
}

// All couplings
export function useAllCouplings() {
  return useFetch(() => api.fetchAllCouplings(), []);
}

// System health
export function useHealth() {
  return useFetch(() => api.checkHealth(), []);
}

// Clients
export function useClients() {
  return useFetch(() => api.fetchClients(), []);
}

// Team
export function useTeam() {
  return useFetch(() => api.fetchTeam(), []);
}

// Tasks with optional filters
export function useTasks(assignee?: string, status?: string, project?: string, limit = 50) {
  return useFetch(
    () => api.fetchTasks(assignee, status, project, limit),
    [assignee, status, project, limit]
  );
}

// Evidence for an entity
export function useEvidence(entityType: string, entityId: string) {
  return useFetch(() => api.fetchEvidence(entityType, entityId), [entityType, entityId]);
}

// Client detail (full detail with nested sections)
export function useClientDetail(clientId: string) {
  return useFetch(() => api.fetchClientDetail(clientId), [clientId]);
}

// Client team involvement
export function useClientTeam(clientId: string) {
  return useFetch(() => api.fetchClientTeam(clientId), [clientId]);
}

// Client invoices
export function useClientInvoices(clientId: string) {
  return useFetch(() => api.fetchClientInvoices(clientId), [clientId]);
}

// Client AR aging
export function useClientARAging(clientId: string) {
  return useFetch(() => api.fetchClientARAging(clientId), [clientId]);
}

// Team workload distribution
export function useTeamWorkload() {
  return useFetch(() => api.fetchTeamWorkload(), []);
}

// Inbox items with filters
export function useInbox(filters: api.InboxFilters = {}) {
  return useFetch(
    () => api.fetchInbox(filters),
    [
      filters.state,
      filters.type,
      filters.severity,
      filters.client_id,
      filters.unread_only,
      filters.sort,
    ]
  );
}

// Inbox counts (cacheable, global scope)
export function useInboxCounts() {
  return useFetch(() => api.fetchInboxCounts(), []);
}

// Recently actioned inbox items
export function useInboxRecent(days = 7, type?: string) {
  return useFetch(() => api.fetchInboxRecent(days, type as api.InboxFilters['type']), [days, type]);
}

// Portfolio overview (tier breakdown, health, totals, overdue AR)
export function usePortfolioOverview() {
  return useFetch(() => api.fetchPortfolioOverview(), []);
}

// At-risk clients by health score threshold
export function usePortfolioRisks(threshold = 50) {
  return useFetch(() => api.fetchPortfolioRisks(threshold), [threshold]);
}

// Client health overview (counts by status)
export function useClientsHealth() {
  return useFetch(() => api.fetchClientsHealth(), []);
}

// ==== Task Management Hooks (Phase 6) ====

// Single task detail
export function useTaskDetail(taskId: string) {
  return useFetch(() => api.fetchTaskDetail(taskId), [taskId]);
}

// Delegations (by me / to me)
export function useDelegations() {
  return useFetch(() => api.fetchDelegations(), []);
}

// Priorities with advanced filtering
export function usePrioritiesAdvanced(filters: api.PriorityAdvancedFilters = {}) {
  return useFetch(
    () => api.fetchPrioritiesAdvanced(filters),
    [
      filters.q,
      filters.due,
      filters.assignee,
      filters.project,
      filters.status,
      filters.min_score,
      filters.max_score,
      filters.tags,
      filters.sort,
      filters.order,
      filters.limit,
      filters.offset,
    ]
  );
}

// Grouped priorities (by project, assignee, etc.)
export function usePrioritiesGrouped(groupBy = 'project', limit = 50) {
  return useFetch(() => api.fetchPrioritiesGrouped(groupBy, limit), [groupBy, limit]);
}

// Bundle detail
export function useBundleDetail(bundleId: string) {
  return useFetch(() => api.fetchBundleDetail(bundleId), [bundleId]);
}

// ==== Priorities Workspace Hooks (Phase 7) ====

// Filtered priorities (for Priorities page)
export function usePrioritiesFiltered(filters: api.PriorityFilteredParams = {}) {
  return useFetch(
    () => api.fetchPrioritiesFiltered(filters),
    [filters.due, filters.assignee, filters.source, filters.project, filters.q, filters.limit]
  );
}

// Saved filters
export function useSavedFilters() {
  return useFetch(() => api.fetchSavedFilters(), []);
}

// ==== Time & Capacity Hooks (Phase 8) ====

// Time blocks for a given date and optional lane
export function useTimeBlocks(date?: string, lane?: string) {
  return useFetch(() => api.fetchTimeBlocks(date, lane), [date, lane]);
}

// Time summary for a date
export function useTimeSummary(date?: string) {
  return useFetch(() => api.fetchTimeSummary(date), [date]);
}

// Events with optional date range
export function useEvents(startDate?: string, endDate?: string, limit = 50) {
  return useFetch(() => api.fetchEvents(startDate, endDate, limit), [startDate, endDate, limit]);
}

// Day view analysis
export function useDayView(date?: string) {
  return useFetch(() => api.fetchDayView(date), [date]);
}

// Week view analysis
export function useWeekView() {
  return useFetch(() => api.fetchWeekView(), []);
}

// Capacity lanes configuration
export function useCapacityLanes() {
  return useFetch(() => api.fetchCapacityLanes(), []);
}

// Capacity utilization metrics
export function useCapacityUtilization(laneId?: string, targetDate?: string) {
  return useFetch(() => api.fetchCapacityUtilization(laneId, targetDate), [laneId, targetDate]);
}

// Capacity forecast for upcoming days
export function useCapacityForecast(laneId = 'default', days = 7) {
  return useFetch(() => api.fetchCapacityForecast(laneId, days), [laneId, days]);
}

// Capacity debt report
export function useCapacityDebt(lane?: string) {
  return useFetch(() => api.fetchCapacityDebt(lane), [lane]);
}

// ==== Commitments Hooks (Phase 9) ====

// All commitments, optionally filtered by status
export function useCommitments(status?: string, limit = 50) {
  return useFetch(() => api.fetchCommitments(status, limit), [status, limit]);
}

// Untracked commitments (not linked to tasks)
export function useUntrackedCommitments(limit = 50) {
  return useFetch(() => api.fetchUntrackedCommitments(limit), [limit]);
}

// Commitments due by a date
export function useCommitmentsDue(date?: string) {
  return useFetch(() => api.fetchCommitmentsDue(date), [date]);
}

// Commitments summary statistics
export function useCommitmentsSummary() {
  return useFetch(() => api.fetchCommitmentsSummary(), []);
}

// ==== Notifications, Digest & Email Hooks (Phase 10) ====

// Notifications list (optionally include dismissed)
export function useNotifications(includeDismissed = false, limit = 50) {
  return useFetch(() => api.fetchNotifications(includeDismissed, limit), [includeDismissed, limit]);
}

// Notification stats (total + unread count)
export function useNotificationStats() {
  return useFetch(() => api.fetchNotificationStats(), []);
}

// Weekly digest summary
export function useWeeklyDigest() {
  return useFetch(() => api.fetchWeeklyDigest(), []);
}

// Emails with optional filters
export function useEmails(actionableOnly = false, unreadOnly = false, limit = 30) {
  return useFetch(
    () => api.fetchEmails(actionableOnly, unreadOnly, limit),
    [actionableOnly, unreadOnly, limit]
  );
}

// ==== Governance & Admin Hooks (Phase 11) ====

// Governance status (config, domains, brake)
export function useGovernance() {
  return useFetch(() => api.fetchGovernance(), []);
}

// Governance action history
export function useGovernanceHistory(limit = 50) {
  return useFetch(() => api.fetchGovernanceHistory(limit), [limit]);
}

// Last calibration result
export function useCalibration() {
  return useFetch(() => api.fetchCalibration(), []);
}

// Bundles with optional filters
export function useBundles(status?: string, domain?: string, limit = 50) {
  return useFetch(() => api.fetchBundles(status, domain, limit), [status, domain, limit]);
}

// Rollbackable bundles
export function useRollbackable() {
  return useFetch(() => api.fetchRollbackable(), []);
}

// Bundle summary (counts by status/domain)
export function useBundleSummary() {
  return useFetch(() => api.fetchBundleSummary(), []);
}

// Pending approvals
export function useApprovals() {
  return useFetch(() => api.fetchApprovals(), []);
}

// Data quality health score and issues
export function useDataQuality() {
  return useFetch(() => api.fetchDataQuality(), []);
}

// Cleanup preview for a specific type
export function useCleanupPreview(cleanupType: string) {
  return useFetch(() => api.fetchCleanupPreview(cleanupType), [cleanupType]);
}

// Pending action proposals
export function usePendingActions(actionType?: string, limit = 50) {
  return useFetch(() => api.fetchPendingActions(actionType, limit), [actionType, limit]);
}

// Action history
export function useActionHistory(entityId?: string, actionType?: string, limit = 50) {
  return useFetch(
    () => api.fetchActionHistory(entityId, actionType, limit),
    [entityId, actionType, limit]
  );
}

// ==== Project Enrollment Hooks (Phase 12) ====

// Project candidates (candidate + proposed status)
export function useProjectCandidates() {
  return useFetch(() => api.fetchProjectCandidates(), []);
}

// Enrolled projects with client info and task counts
export function useProjectsEnrolled() {
  return useFetch(() => api.fetchProjectsEnrolled(), []);
}

// Detected projects from tasks not yet in projects table
export function useDetectedProjects() {
  return useFetch(() => api.fetchDetectedProjects(), []);
}

// Project detail
export function useProjectDetail(projectId: string | undefined) {
  return useFetch(
    () => (projectId ? api.fetchProjectDetail(projectId) : Promise.resolve(null)),
    [projectId]
  );
}

// Client-project linking statistics
export function useLinkingStats() {
  return useFetch(() => api.fetchLinkingStats(), []);
}
