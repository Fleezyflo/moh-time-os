// Data Access Layer — Query functions per CONTROL_ROOM_QUERIES.md
// All queries return contract-shaped data from PROPOSAL_ISSUE_ROOM_CONTRACT.md

import {
  proposals,
  issues,
  watchers,
  fixDataQueue,
  couplings,
  clients,
  teamMembers,
  checkEligibility,
  type Proposal,
  type Issue,
  type Watcher,
  type FixData,
  type Coupling,
  type Client,
  type TeamMember,
} from '../fixtures';

// =============================================================================
// SNAPSHOT QUERIES (CONTROL_ROOM_QUERIES.md L14-19)
// =============================================================================

/**
 * L15: proposals WHERE status='open' ORDER BY score DESC LIMIT 7
 */
export function getSnapshotProposals(scope?: { type: string; id: string }, _horizon?: string): Proposal[] {
  // _horizon param reserved for future time-window filtering
  let filtered = proposals.filter(p => p.status === 'open');
  
  // Apply scope filter if provided
  if (scope) {
    filtered = filtered.filter(p => 
      p.scope_refs.some(r => r.type === scope.type && r.id === scope.id)
    );
  }
  
  // Sort by score DESC (deterministic per 06_PROPOSALS_BRIEFINGS.md L141)
  filtered.sort((a, b) => b.score - a.score);
  
  return filtered.slice(0, 7);
}

/**
 * L16: issues WHERE state IN ('open','monitoring','awaiting','blocked') ORDER BY priority DESC LIMIT 5
 */
export function getSnapshotIssues(): Issue[] {
  const activeStates = ['open', 'monitoring', 'awaiting', 'blocked'];
  const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  
  return issues
    .filter(i => activeStates.includes(i.state))
    .sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority])
    .slice(0, 5);
}

/**
 * L17: issue_watchers WHERE active=1 AND next_check_at <= now()+24h ORDER BY next_check_at ASC
 */
export function getSnapshotWatchers(): Watcher[] {
  const now = new Date();
  const in24h = new Date(now.getTime() + 24 * 60 * 60 * 1000);
  
  return watchers
    .filter(w => new Date(w.next_check_at) <= in24h)
    .sort((a, b) => new Date(a.next_check_at).getTime() - new Date(b.next_check_at).getTime())
    .slice(0, 5);
}

/**
 * L18: resolution_queue COUNT WHERE status='pending'
 */
export function getFixDataCount(): number {
  return fixDataQueue.length;
}

// =============================================================================
// CLIENT/TEAM QUERIES (CONTROL_ROOM_QUERIES.md L25-27)
// =============================================================================

/**
 * Derived: clients with proposal/issue counts and posture
 */
export function getClients(): Client[] {
  // Sort by posture priority, then name
  const postureOrder = { critical: 0, attention: 1, healthy: 2, inactive: 3 };
  return [...clients].sort((a, b) => {
    const postureDiff = postureOrder[a.posture] - postureOrder[b.posture];
    if (postureDiff !== 0) return postureDiff;
    return a.name.localeCompare(b.name);
  });
}

/**
 * L26: proposals + issues scoped to client
 */
export function getClientDetail(clientId: string): { 
  client: Client | undefined; 
  proposals: Proposal[]; 
  issues: Issue[];
} {
  const client = clients.find(c => c.client_id === clientId);
  
  const clientProposals = proposals
    .filter(p => 
      p.status === 'open' && 
      p.scope_refs.some(r => r.type === 'client' && r.id === clientId)
    )
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
  
  const activeStates = ['open', 'monitoring', 'awaiting', 'blocked'];
  const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  const clientIssues = issues
    .filter(i => activeStates.includes(i.state))
    .sort((a, b) => {
      const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
      if (priorityDiff !== 0) return priorityDiff;
      return new Date(b.last_activity_at).getTime() - new Date(a.last_activity_at).getTime();
    });
  
  return { client, proposals: clientProposals, issues: clientIssues };
}

/**
 * Derived: team_members with metrics
 */
export function getTeamMembers(): TeamMember[] {
  // Sort by load_band priority, then name
  const loadOrder = { high: 0, medium: 1, low: 2, unknown: 3 };
  return [...teamMembers].sort((a, b) => {
    const loadDiff = loadOrder[a.load_band] - loadOrder[b.load_band];
    if (loadDiff !== 0) return loadDiff;
    return a.name.localeCompare(b.name);
  });
}

/**
 * L26: proposals + issues scoped to member
 */
export function getTeamDetail(memberId: string): {
  member: TeamMember | undefined;
  proposals: Proposal[];
  issues: Issue[];
} {
  const member = teamMembers.find(m => m.member_id === memberId);
  
  const memberProposals = proposals
    .filter(p => 
      p.status === 'open' && 
      p.scope_refs.some(r => r.type === 'team_member' && r.id === memberId)
    )
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
  
  const activeStates = ['open', 'monitoring', 'awaiting', 'blocked'];
  const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  const memberIssues = issues
    .filter(i => activeStates.includes(i.state))
    .sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);
  
  return { member, proposals: memberProposals, issues: memberIssues };
}

// =============================================================================
// INTERSECTIONS QUERIES (CONTROL_ROOM_QUERIES.md L29-31)
// =============================================================================

interface Anchor {
  type: 'proposal' | 'issue';
  id: string;
  label: string;
  score: number;
}

/**
 * Derived: recent proposals + issues for anchor selection
 */
export function getAnchors(): Anchor[] {
  const proposalAnchors: Anchor[] = proposals
    .filter(p => p.status === 'open')
    .map(p => ({ type: 'proposal' as const, id: p.proposal_id, label: p.headline, score: p.score }));
  
  const priorityScore = { critical: 4, high: 3, medium: 2, low: 1 };
  const issueAnchors: Anchor[] = issues
    .filter(i => ['open', 'monitoring', 'awaiting', 'blocked'].includes(i.state))
    .map(i => ({ type: 'issue' as const, id: i.issue_id, label: i.headline, score: priorityScore[i.priority] }));
  
  return [...proposalAnchors, ...issueAnchors]
    .sort((a, b) => b.score - a.score)
    .slice(0, 20);
}

/**
 * L30-31: couplings for anchor
 */
export function getCouplings(anchorType: string, anchorId: string): Coupling[] {
  return couplings
    .filter(c => c.anchor_type === anchorType && c.anchor_id === anchorId)
    .sort((a, b) => b.strength - a.strength);
}

// =============================================================================
// ISSUES QUERY
// =============================================================================

interface IssueFilters {
  state?: Issue['state'];
  priority?: Issue['priority'];
}

/**
 * L16 extended: issues with state/priority filters
 */
export function getIssues(filters?: IssueFilters): Issue[] {
  const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  
  let filtered = [...issues];
  
  if (filters?.state) {
    filtered = filtered.filter(i => i.state === filters.state);
  }
  if (filters?.priority) {
    filtered = filtered.filter(i => i.priority === filters.priority);
  }
  
  return filtered.sort((a, b) => {
    const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
    if (priorityDiff !== 0) return priorityDiff;
    return new Date(b.last_activity_at).getTime() - new Date(a.last_activity_at).getTime();
  });
}

// =============================================================================
// FIX DATA QUERY
// =============================================================================

/**
 * L18-19: resolution_queue OR entity_links with confidence < 0.70
 */
export function getFixDataQueue(): FixData[] {
  return [...fixDataQueue].sort((a, b) => {
    // Sort by affected_count DESC, then created_at ASC
    const countDiff = b.affected_proposal_ids.length - a.affected_proposal_ids.length;
    if (countDiff !== 0) return countDiff;
    return 0; // No created_at in fixture, maintain order
  });
}

// =============================================================================
// ELIGIBILITY HELPER (re-export)
// =============================================================================
export { checkEligibility };
