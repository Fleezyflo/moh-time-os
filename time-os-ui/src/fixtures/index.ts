// Contract-shaped fixtures derived from PROPOSAL_ISSUE_ROOM_CONTRACT.md
// NO invented data — shapes match backend contract exactly

export interface Proposal {
  proposal_id: string;
  proposal_type: 'risk' | 'opportunity' | 'request' | 'decision_needed' | 'anomaly' | 'compliance';
  headline: string;
  score: number;
  impact: {
    dimensions: {
      time?: { days_at_risk: number; deadline_at?: string };
      cash?: { amount: number; currency: string };
      reputation?: { severity: 'low' | 'medium' | 'high' };
    };
    deadline_at?: string;
  };
  top_hypotheses: Array<{
    label: string;
    confidence: number;
    supporting_signal_ids: string[];
    missing_confirmations?: string[];
  }>;
  proof: Array<{
    excerpt_id: string;
    text: string;
    source_type: string;
    source_ref: string;
  }>;
  missing_confirmations: string[];
  scope_refs: Array<{ type: string; id: string }>;
  trend: 'worsening' | 'improving' | 'flat';
  occurrence_count: number;
  status: 'open' | 'snoozed' | 'dismissed' | 'accepted';
  linkage_confidence: number;
  interpretation_confidence: number;
}

export interface Issue {
  issue_id: string;
  state: 'open' | 'monitoring' | 'awaiting' | 'blocked' | 'resolved' | 'closed';
  priority: 'critical' | 'high' | 'medium' | 'low';
  headline: string;
  primary_ref: string;
  resolution_criteria: string;
  last_activity_at: string;
  next_trigger?: string;
}

export interface Watcher {
  watcher_id: string;
  issue_id: string;
  next_check_at: string;
  trigger_condition: string;
}

export interface FixData {
  fix_data_id: string;
  fix_type: 'identity_conflict' | 'ambiguous_link' | 'missing_mapping';
  description: string;
  candidates: Array<{ label: string; match_score: number }>;
  impact_summary: string;
  affected_proposal_ids: string[];
}

export interface Coupling {
  coupling_id: string;
  anchor_type: string;
  anchor_id: string;
  coupled_type: string;
  coupled_id: string;
  coupled_label: string;
  strength: number;
  confidence: number;
  why_signals: Array<{ signal_type: string; description: string }>;
}

export interface Client {
  client_id: string;
  name: string;
  posture: 'critical' | 'attention' | 'healthy' | 'inactive';
  linkage_confidence: number;
}

export interface TeamMember {
  member_id: string;
  name: string;
  role: string;
  load_band: 'high' | 'medium' | 'low' | 'unknown';
  load_confidence: number;
  throughput_7d: number;
  avg_completion_days: number;
  responsiveness: {
    email: { band: 'fast' | 'normal' | 'slow'; confidence: number };
    slack: { band: 'fast' | 'normal' | 'slow'; confidence: number };
    task_updates: { band: 'fast' | 'normal' | 'slow'; confidence: number };
  };
}

// FIXTURES

export const proposals: Proposal[] = [
  {
    proposal_id: 'P-001',
    proposal_type: 'risk',
    headline: 'Acme Q1 Retainer at risk — budget concerns surfaced',
    score: 4.8,
    impact: {
      dimensions: {
        cash: { amount: 45000, currency: 'USD' },
        reputation: { severity: 'high' }
      },
      deadline_at: '2026-02-15'
    },
    top_hypotheses: [
      { label: 'Budget reallocation internally', confidence: 0.78, supporting_signal_ids: ['S-101', 'S-102', 'S-103'] },
      { label: 'Competitor proposal received', confidence: 0.62, supporting_signal_ids: ['S-104', 'S-105'] },
      { label: 'Scope concerns unaddressed', confidence: 0.51, supporting_signal_ids: ['S-106'] }
    ],
    proof: [
      { excerpt_id: 'E-001', text: '"We need to revisit the budget allocation for Q2..."', source_type: 'email', source_ref: 'gmail://msg/abc123' },
      { excerpt_id: 'E-002', text: '"Finance flagged this engagement for review"', source_type: 'slack_message', source_ref: 'slack://C123/p456' },
      { excerpt_id: 'E-003', text: 'Payment delayed - invoice #4521 overdue 14 days', source_type: 'xero_invoice', source_ref: 'xero://inv/4521' },
      { excerpt_id: 'E-004', text: '"Discussed concerns in leadership sync"', source_type: 'calendar', source_ref: 'gcal://evt/xyz' }
    ],
    missing_confirmations: ['Direct client confirmation', 'Finance team follow-up'],
    scope_refs: [{ type: 'client', id: 'C-001' }, { type: 'engagement', id: 'ENG-001' }],
    trend: 'worsening',
    occurrence_count: 3,
    status: 'open',
    linkage_confidence: 0.85,
    interpretation_confidence: 0.78
  },
  {
    proposal_id: 'P-002',
    proposal_type: 'opportunity',
    headline: 'Beta Corp expansion — upsell window detected',
    score: 4.2,
    impact: {
      dimensions: {
        cash: { amount: 120000, currency: 'USD' }
      }
    },
    top_hypotheses: [
      { label: 'New product launch requires support', confidence: 0.82, supporting_signal_ids: ['S-201', 'S-202', 'S-203'] },
      { label: 'Competitor contract ending', confidence: 0.67, supporting_signal_ids: ['S-204', 'S-205'] }
    ],
    proof: [
      { excerpt_id: 'E-010', text: '"Looking to expand our engagement scope..."', source_type: 'email', source_ref: 'gmail://msg/def456' },
      { excerpt_id: 'E-011', text: 'Meeting scheduled: "Q2 Planning Discussion"', source_type: 'calendar', source_ref: 'gcal://evt/abc' },
      { excerpt_id: 'E-012', text: '"Current vendor contract ends March 1"', source_type: 'email', source_ref: 'gmail://msg/ghi789' }
    ],
    missing_confirmations: ['Budget approval status'],
    scope_refs: [{ type: 'client', id: 'C-002' }],
    trend: 'improving',
    occurrence_count: 2,
    status: 'open',
    linkage_confidence: 0.92,
    interpretation_confidence: 0.82
  },
  {
    proposal_id: 'P-003',
    proposal_type: 'risk',
    headline: 'Resource bottleneck — delivery timeline at risk',
    score: 3.9,
    impact: {
      dimensions: {
        time: { days_at_risk: 12, deadline_at: '2026-02-20' },
        reputation: { severity: 'medium' }
      }
    },
    top_hypotheses: [
      { label: 'Key team member overloaded', confidence: 0.71, supporting_signal_ids: ['S-301', 'S-302'] },
      { label: 'Scope creep untracked', confidence: 0.58, supporting_signal_ids: ['S-303'] }
    ],
    proof: [
      { excerpt_id: 'E-020', text: '"Task blocked for 5 days - waiting on design"', source_type: 'asana_task', source_ref: 'asana://task/123' },
      { excerpt_id: 'E-021', text: '"Multiple deadlines converging this week"', source_type: 'slack_message', source_ref: 'slack://C456/p789' },
      { excerpt_id: 'E-022', text: 'Milestone pushed to next week', source_type: 'asana_task', source_ref: 'asana://task/456' }
    ],
    missing_confirmations: ['Client flexibility on deadline'],
    scope_refs: [{ type: 'client', id: 'C-001' }, { type: 'team_member', id: 'TM-001' }],
    trend: 'worsening',
    occurrence_count: 1,
    status: 'open',
    linkage_confidence: 0.76,
    interpretation_confidence: 0.71
  },
  {
    proposal_id: 'P-004',
    proposal_type: 'anomaly',
    headline: 'Unusual activity pattern — Gamma Inc communications',
    score: 3.1,
    impact: {
      dimensions: {
        reputation: { severity: 'low' }
      }
    },
    top_hypotheses: [
      { label: 'Key contact changed', confidence: 0.45, supporting_signal_ids: ['S-401'] }
    ],
    proof: [
      { excerpt_id: 'E-030', text: '"New point of contact for all requests"', source_type: 'email', source_ref: 'gmail://msg/jkl012' },
      { excerpt_id: 'E-031', text: 'Response times increased significantly', source_type: 'email', source_ref: 'gmail://msg/mno345' }
    ],
    missing_confirmations: ['Org change confirmation', 'Relationship status'],
    scope_refs: [{ type: 'client', id: 'C-003' }],
    trend: 'flat',
    occurrence_count: 1,
    status: 'open',
    linkage_confidence: 0.58,
    interpretation_confidence: 0.45
  }
];

export const issues: Issue[] = [
  {
    issue_id: 'I-001',
    state: 'open',
    priority: 'critical',
    headline: 'Acme invoice payment blocked',
    primary_ref: 'P-001',
    resolution_criteria: 'Payment received or payment plan agreed',
    last_activity_at: '2026-02-05T14:30:00Z',
    next_trigger: '2026-02-06T09:00:00Z'
  },
  {
    issue_id: 'I-002',
    state: 'monitoring',
    priority: 'high',
    headline: 'Beta Corp contract renewal pending',
    primary_ref: 'C-002',
    resolution_criteria: 'Contract signed or declined',
    last_activity_at: '2026-02-05T10:15:00Z',
    next_trigger: '2026-02-07T09:00:00Z'
  },
  {
    issue_id: 'I-003',
    state: 'awaiting',
    priority: 'medium',
    headline: 'Design review feedback overdue',
    primary_ref: 'ENG-001',
    resolution_criteria: 'Client feedback received',
    last_activity_at: '2026-02-04T16:00:00Z'
  },
  {
    issue_id: 'I-004',
    state: 'blocked',
    priority: 'high',
    headline: 'API integration stalled — vendor dependency',
    primary_ref: 'ENG-003',
    resolution_criteria: 'Vendor API access granted',
    last_activity_at: '2026-02-03T11:00:00Z'
  },
  {
    issue_id: 'I-005',
    state: 'open',
    priority: 'low',
    headline: 'Documentation update pending',
    primary_ref: 'ENG-002',
    resolution_criteria: 'Docs updated and reviewed',
    last_activity_at: '2026-02-02T09:00:00Z'
  }
];

export const watchers: Watcher[] = [
  { watcher_id: 'W-001', issue_id: 'I-001', next_check_at: '2026-02-06T09:00:00Z', trigger_condition: 'Payment status check' },
  { watcher_id: 'W-002', issue_id: 'I-002', next_check_at: '2026-02-07T09:00:00Z', trigger_condition: 'Contract decision due' },
  { watcher_id: 'W-003', issue_id: 'I-003', next_check_at: '2026-02-06T14:00:00Z', trigger_condition: '48h feedback deadline' }
];

export const fixDataQueue: FixData[] = [
  {
    fix_data_id: 'FD-001',
    fix_type: 'identity_conflict',
    description: '"John Smith" appears with multiple identifiers',
    candidates: [
      { label: 'john.smith@acme.com (Asana)', match_score: 0.95 },
      { label: 'jsmith (Slack)', match_score: 0.88 },
      { label: 'john.s@acme.com (Email)', match_score: 0.82 }
    ],
    impact_summary: 'Blocks 3 proposals (weak linkage)',
    affected_proposal_ids: ['P-001', 'P-003', 'P-004']
  },
  {
    fix_data_id: 'FD-002',
    fix_type: 'ambiguous_link',
    description: 'Task "Website redesign" could belong to multiple engagements',
    candidates: [
      { label: 'Acme Q1 Retainer', match_score: 0.65 },
      { label: 'Acme Website Project', match_score: 0.72 }
    ],
    impact_summary: 'Blocks 1 proposal (scope uncertainty)',
    affected_proposal_ids: ['P-003']
  },
  {
    fix_data_id: 'FD-003',
    fix_type: 'missing_mapping',
    description: 'Email domain "partner.co" has no client mapping',
    candidates: [
      { label: 'Partner Corp (suggested)', match_score: 0.78 }
    ],
    impact_summary: '5 emails unlinked',
    affected_proposal_ids: []
  }
];

export const couplings: Coupling[] = [
  {
    coupling_id: 'CP-001',
    anchor_type: 'proposal',
    anchor_id: 'P-001',
    coupled_type: 'client',
    coupled_id: 'C-001',
    coupled_label: 'Acme Corp',
    strength: 0.92,
    confidence: 0.88,
    why_signals: [
      { signal_type: 'overdue_payment', description: 'Invoice linked to Acme Corp' },
      { signal_type: 'budget_discussion', description: 'Email thread about budget' }
    ]
  },
  {
    coupling_id: 'CP-002',
    anchor_type: 'proposal',
    anchor_id: 'P-001',
    coupled_type: 'team_member',
    coupled_id: 'TM-001',
    coupled_label: 'Sarah Chen',
    strength: 0.75,
    confidence: 0.82,
    why_signals: [
      { signal_type: 'task_assignment', description: 'Multiple tasks assigned' },
      { signal_type: 'communication_volume', description: 'High email/slack activity' }
    ]
  },
  {
    coupling_id: 'CP-003',
    anchor_type: 'proposal',
    anchor_id: 'P-001',
    coupled_type: 'issue',
    coupled_id: 'I-001',
    coupled_label: 'Invoice blocked',
    strength: 0.95,
    confidence: 0.91,
    why_signals: [
      { signal_type: 'direct_reference', description: 'Proposal originated from issue' }
    ]
  }
];

export const clients: Client[] = [
  { client_id: 'C-001', name: 'Acme Corp', posture: 'attention', linkage_confidence: 0.85 },
  { client_id: 'C-002', name: 'Beta Corp', posture: 'healthy', linkage_confidence: 0.92 },
  { client_id: 'C-003', name: 'Gamma Inc', posture: 'inactive', linkage_confidence: 0.58 }
];

export const teamMembers: TeamMember[] = [
  {
    member_id: 'TM-001',
    name: 'Sarah Chen',
    role: 'Senior Designer',
    load_band: 'high',
    load_confidence: 0.78,
    throughput_7d: 8,
    avg_completion_days: 2.5,
    responsiveness: {
      email: { band: 'normal', confidence: 0.82 },
      slack: { band: 'fast', confidence: 0.91 },
      task_updates: { band: 'slow', confidence: 0.68 }
    }
  },
  {
    member_id: 'TM-002',
    name: 'Mike Johnson',
    role: 'Developer',
    load_band: 'medium',
    load_confidence: 0.85,
    throughput_7d: 12,
    avg_completion_days: 1.8,
    responsiveness: {
      email: { band: 'slow', confidence: 0.75 },
      slack: { band: 'fast', confidence: 0.88 },
      task_updates: { band: 'fast', confidence: 0.92 }
    }
  }
];

// Eligibility check helper (per 06_PROPOSALS_BRIEFINGS.md gates)
export function checkEligibility(proposal: Proposal): {
  is_eligible: boolean;
  gate_violations: Array<{ gate: string; message: string }>;
} {
  const violations: Array<{ gate: string; message: string }> = [];
  
  // Gate 1: Proof density (≥3 excerpts)
  if (proposal.proof.length < 3) {
    violations.push({ gate: 'proof_density', message: `Needs more evidence (${proposal.proof.length}/3 required)` });
  }
  
  // Gate 2: Scope coverage (min link confidence ≥ 0.70)
  if (proposal.linkage_confidence < 0.70) {
    violations.push({ gate: 'scope_coverage', message: `Weak linkage (${(proposal.linkage_confidence * 100).toFixed(0)}%)` });
  }
  
  // Gate 3: Reasoning (≥1 hypothesis with confidence ≥ 0.55, ≥2 signals)
  const validHypothesis = proposal.top_hypotheses.find(
    h => h.confidence >= 0.55 && h.supporting_signal_ids.length >= 2
  );
  if (!validHypothesis) {
    violations.push({ gate: 'reasoning', message: 'Weak hypothesis — insufficient signal support' });
  }
  
  return {
    is_eligible: violations.length === 0,
    gate_violations: violations
  };
}
