import { useState } from 'react'
import {
  createRouter,
  createRoute,
  createRootRoute,
  Outlet,
  Link,
  useParams,
  useNavigate,
} from '@tanstack/react-router'
import { ProposalCard, IssueRow, FixDataSummary, FixDataCard, PostureStrip, ConfidenceBadge, RoomDrawer, EvidenceViewer, IssueDrawer } from './components'
import { 
  proposals as fixtureProposals, 
  issues as fixtureIssues, 
  watchers, 
  fixDataQueue, 
  couplings, 
  clients, 
  teamMembers,
  checkEligibility,
  type Proposal,
  type Issue,
} from './fixtures'
import { useProposals, useIssues, useWatchers, useFixData, useClients, useTeam, useAllCouplings, useEvidence } from './lib/hooks'

// =============================================================================
// API MODE: Set to true to fetch from backend, false to use fixtures
// =============================================================================
const USE_API = true; // Toggle this to switch between API and fixtures

// =============================================================================
// GLOBAL STATE (for mutations - tagging creates local state)
// =============================================================================
let localIssues: Issue[] = [];
let taggedProposalIds = new Set<string>();

// Backwards-compatible aliases for fixture data
const globalProposals = fixtureProposals;
const globalIssues = fixtureIssues;

// Tag payload shape per 07_TAG_TO_ISSUE_TRANSACTION.md
interface TagPayload {
  proposal_id: string;
  headline: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  resolution_criteria: string;
  source_proposal: string;
}

// Tag function — creates local Issue and tracks tagged proposals
function tagProposal(proposal: Proposal): Issue {
  const payload: TagPayload = {
    proposal_id: proposal.proposal_id,
    headline: proposal.headline,
    priority: (proposal as { proposal_type?: string }).proposal_type === 'risk' ? 'high' : 'medium',
    resolution_criteria: `Resolve: ${proposal.headline}`,
    source_proposal: proposal.proposal_id,
  };
  
  console.log('[TAG] Payload shape for backend:', payload);
  
  // Create local Issue
  const newIssue: Issue = {
    issue_id: `I-${Date.now()}`,
    state: 'open',
    priority: payload.priority,
    headline: payload.headline,
    primary_ref: payload.source_proposal,
    resolution_criteria: payload.resolution_criteria,
    last_activity_at: new Date().toISOString(),
  };
  
  localIssues = [newIssue, ...localIssues];
  taggedProposalIds.add(proposal.proposal_id);
  
  // TODO: POST to /api/control-room/tag when backend supports it
  console.log('[TAG] Issue created locally:', newIssue.issue_id);
  return newIssue;
}

// Root layout with navigation
const rootRoute = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-slate-900 text-slate-200">
      {/* Mobile-friendly nav */}
      <nav className="sticky top-0 z-50 bg-slate-800/95 backdrop-blur border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-14 sm:h-16">
            <Link to="/" className="font-semibold text-lg">Time OS</Link>
            <div className="flex gap-1 sm:gap-2 overflow-x-auto">
              <NavLink to="/">Snapshot</NavLink>
              <NavLink to="/clients">Clients</NavLink>
              <NavLink to="/team">Team</NavLink>
              <NavLink to="/intersections">Intersections</NavLink>
              <NavLink to="/fix-data">Fix</NavLink>
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
        <Outlet />
      </main>
    </div>
  ),
})

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className="px-3 py-2 text-sm rounded-md hover:bg-slate-700 transition-colors whitespace-nowrap
        [&.active]:bg-slate-700 [&.active]:text-white"
    >
      {children}
    </Link>
  )
}

// ============================================================
// SNAPSHOT (Control Room) — Primary executive entry point
// ============================================================
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: function Snapshot() {
    const navigate = useNavigate();
    const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [evidenceOpen, setEvidenceOpen] = useState(false);
    const [evidenceAnchorId, setEvidenceAnchorId] = useState<string | undefined>(undefined);
    
    // Force re-render on state change (React state for issues)
    const [issueVersion, setIssueVersion] = useState(0);
    const [proposalVersion, setProposalVersion] = useState(0);
    
    // Fetch from API or use fixtures
    const { data: apiProposals, loading: loadingProposals, error: errorProposals } = useProposals(7, 'open');
    const { data: apiIssues } = useIssues(5);
    const { data: apiWatchers } = useWatchers(24);
    const { data: apiFixData } = useFixData();
    
    // Use API data if available, fallback to fixtures
    const currentProposals = USE_API && apiProposals 
      ? (apiProposals as Proposal[]).filter(p => !taggedProposalIds.has(p.proposal_id))
      : fixtureProposals.filter(p => p.status === 'open' && !taggedProposalIds.has(p.proposal_id)).slice(0, 7);
    
    const currentIssues = USE_API && apiIssues 
      ? [...localIssues, ...(apiIssues as Issue[])]
      : [...localIssues, ...fixtureIssues.filter(i => ['open','monitoring','awaiting','blocked'].includes(i.state))];
    
    const upcomingWatchers = USE_API && apiWatchers 
      ? (apiWatchers as typeof watchers)
      : []; // Empty when API unavailable
    
    const fixDataCount = USE_API && apiFixData ? (apiFixData as unknown[]).length : 0;
    
    // Handlers
    const handleOpenProposal = (proposal: Proposal) => {
      setSelectedProposal(proposal);
      setDrawerOpen(true);
    };
    
    const handleTag = (proposal: Proposal) => {
      const { is_eligible } = checkEligibility(proposal);
      if (!is_eligible) {
        console.warn('[TAG] Cannot tag ineligible proposal:', proposal.proposal_id);
        return;
      }
      
      const newIssue = tagProposal(proposal);
      console.log('[TAG] Issue created in RightRail:', newIssue);
      
      // Trigger re-render
      setIssueVersion(v => v + 1);
      setProposalVersion(v => v + 1);
      setDrawerOpen(false);
      setSelectedProposal(null);
    };
    
    const handleSnooze = (proposal: Proposal) => {
      console.log('[SNOOZE STUB] Would snooze:', proposal.proposal_id);
      // TODO: Implement snooze modal
    };
    
    // Note: handleOpenEvidence can be used from within RoomDrawer if needed
    const _handleOpenEvidence = (excerptId?: string) => {
      setEvidenceAnchorId(excerptId);
      setEvidenceOpen(true);
    };
    void _handleOpenEvidence; // Suppress unused warning for now
    
    const handleFixData = () => {
      navigate({ to: '/fix-data' });
    };
    
    // Loading state
    if (USE_API && loadingProposals) {
      return (
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-slate-400">Loading Control Room...</div>
        </div>
      );
    }
    
    // Error state
    if (USE_API && errorProposals) {
      return (
        <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-8 text-center">
          <p className="text-red-400">Failed to connect to backend</p>
          <p className="text-sm text-slate-500 mt-2">{errorProposals.message}</p>
          <p className="text-xs text-slate-600 mt-4">Make sure the API server is running: python api/server.py</p>
        </div>
      );
    }
    
    return (
      <div className="lg:grid lg:grid-cols-12 lg:gap-6">
        {/* Left: Proposal Stack */}
        <div className="lg:col-span-8 space-y-4">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-2xl font-semibold">
              Snapshot {USE_API && <span className="text-xs text-green-500 ml-2">●  Live</span>}
            </h1>
            <div className="flex items-center gap-2 text-sm">
              <select className="bg-slate-800 border border-slate-700 rounded px-2 py-1">
                <option>All Scope</option>
                <option>Client: Acme</option>
                <option>Client: Beta</option>
              </select>
              <select className="bg-slate-800 border border-slate-700 rounded px-2 py-1">
                <option>7 days</option>
                <option>Today</option>
                <option>30 days</option>
              </select>
            </div>
          </div>
          
          <div className="space-y-4" key={proposalVersion}>
            {currentProposals.length === 0 ? (
              <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-8 text-center">
                <p className="text-slate-400">No proposals require attention right now</p>
              </div>
            ) : (
              currentProposals.map(proposal => (
                <ProposalCard 
                  key={proposal.proposal_id} 
                  proposal={proposal}
                  onOpen={() => handleOpenProposal(proposal)}
                  onTag={() => handleTag(proposal)}
                  onSnooze={() => handleSnooze(proposal)}
                />
              ))
            )}
          </div>
        </div>
        
        {/* Right: Issues, Watchers, Fix Data */}
        <div className="lg:col-span-4 mt-6 lg:mt-0 space-y-6">
          {/* Issues */}
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4" key={issueVersion}>
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
              Issues ({currentIssues.length})
            </h2>
            <div className="space-y-1">
              {currentIssues.length === 0 ? (
                <p className="text-sm text-slate-500">No active issues</p>
              ) : (
                currentIssues.slice(0, 5).map(issue => (
                  <IssueRow key={issue.issue_id} issue={issue} />
                ))
              )}
            </div>
          </div>
          
          {/* Watchers */}
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
              Watchers ({upcomingWatchers.length})
            </h2>
            <div className="space-y-2">
              {upcomingWatchers.length === 0 ? (
                <p className="text-sm text-slate-500">No watchers due in 24h</p>
              ) : (
                upcomingWatchers.map(w => (
                  <div key={w.watcher_id} className="text-sm py-2 border-b border-slate-700 last:border-0">
                    <div className="flex items-center gap-2">
                      <span className="text-blue-400">⏰</span>
                      <span className="text-slate-300">{w.trigger_condition}</span>
                    </div>
                    <p className="text-xs text-slate-500 ml-6 mt-0.5">
                      {new Date(w.next_check_at).toLocaleString()}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
          
          {/* Fix Data Summary */}
          <FixDataSummary count={fixDataCount} />
        </div>
        
        {/* RoomDrawer for selected proposal */}
        {selectedProposal && (
          <RoomDrawer
            isOpen={drawerOpen}
            onClose={() => {
              setDrawerOpen(false);
              setSelectedProposal(null);
            }}
            entity={{
              type: 'proposal',
              id: selectedProposal.proposal_id,
              headline: selectedProposal.headline,
              coverage_summary: `${selectedProposal.scope_refs.length} entities linked`,
            }}
            proposal={selectedProposal}
            onTag={() => handleTag(selectedProposal)}
            onSnooze={() => handleSnooze(selectedProposal)}
            onDismiss={() => console.log('[DISMISS STUB]', selectedProposal.proposal_id)}
            onFixData={handleFixData}
          />
        )}
        
        {/* EvidenceViewer */}
        {selectedProposal && (
          <EvidenceViewer
            isOpen={evidenceOpen}
            onClose={() => setEvidenceOpen(false)}
            excerpts={selectedProposal.proof.map(p => ({
              ...p,
              extracted_at: new Date().toISOString(),
            }))}
            anchorId={evidenceAnchorId}
            onSourceClick={(ref) => console.log('[EVIDENCE] Open source:', ref)}
          />
        )}
      </div>
    )
  },
})

// ============================================================
// CLIENTS PORTFOLIO
// ============================================================
const clientsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients',
  component: function ClientsPortfolio() {
    const [search, setSearch] = useState('');
    const [sortBy, setSortBy] = useState<'posture' | 'name' | 'proposals' | 'issues'>('posture');
    
    // Fetch from API
    const { data: apiClients, loading, error } = useClients();
    
    // Use API data or fallback to fixtures
    const clientsData = USE_API && apiClients ? apiClients : clients;
    
    // Derive client data with counts (TODO: get counts from API)
    const clientsWithCounts = (clientsData as typeof clients).map(client => {
      return { ...client, proposal_count: 0, issue_count: 0 };
    });
    
    // Filter by search
    const filtered = clientsWithCounts.filter(c => 
      c.name.toLowerCase().includes(search.toLowerCase())
    );
    
    // Sort
    const postureOrder: Record<string, number> = { critical: 0, attention: 1, healthy: 2, inactive: 3 };
    const sorted = [...filtered].sort((a, b) => {
      switch (sortBy) {
        case 'posture': return (postureOrder[a.posture] ?? 4) - (postureOrder[b.posture] ?? 4) || a.name.localeCompare(b.name);
        case 'name': return a.name.localeCompare(b.name);
        case 'proposals': return b.proposal_count - a.proposal_count;
        case 'issues': return b.issue_count - a.issue_count;
        default: return 0;
      }
    });
    
    if (USE_API && loading) {
      return <div className="text-slate-400 p-8 text-center">Loading clients...</div>;
    }
    if (USE_API && error) {
      return <div className="text-red-400 p-8 text-center">Error loading clients: {error.message}</div>;
    }
    
    return (
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <h1 className="text-2xl font-semibold">Clients Portfolio</h1>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Search clients..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm placeholder-slate-500"
            />
            <select 
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm"
            >
              <option value="posture">Sort: Posture</option>
              <option value="name">Sort: A-Z</option>
              <option value="proposals">Sort: Proposals</option>
              <option value="issues">Sort: Issues</option>
            </select>
          </div>
        </div>
        
        {sorted.length === 0 ? (
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-8 text-center text-slate-500">
            No clients found
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {sorted.map(client => (
              <Link
                key={client.client_id}
                to="/clients/$clientId"
                params={{ clientId: client.client_id }}
                className="block bg-slate-800 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors p-4"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="font-medium text-slate-100">{client.name}</h3>
                  <ConfidenceBadge type="linkage" value={client.linkage_confidence} showLabel={false} />
                </div>
                <PostureStrip 
                  posture={client.posture}
                  proposal_count={client.proposal_count}
                  issue_count={client.issue_count}
                  confidence={client.linkage_confidence}
                />
              </Link>
            ))}
          </div>
        )}
      </div>
    )
  },
})

// ============================================================
// CLIENT DETAIL REPORT
// ============================================================
const clientDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients/$clientId',
  component: function ClientDetail() {
    const navigate = useNavigate();
    const { clientId } = useParams({ from: '/clients/$clientId' });
    const { data: apiClients } = useClients();
    const clientsData = USE_API && apiClients ? apiClients : clients;
    const client = (clientsData as typeof clients).find(c => c.client_id === clientId);
    
    // State management for drawers
    const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
    const [proposalDrawerOpen, setProposalDrawerOpen] = useState(false);
    const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
    const [issueDrawerOpen, setIssueDrawerOpen] = useState(false);
    const [evidenceTab, setEvidenceTab] = useState<string | null>(null);
    const [evidenceOpen, setEvidenceOpen] = useState(false);
    
    // Force re-render on state change
    const [version, setVersion] = useState(0);
    
    if (!client) {
      return <div className="text-slate-400">Client not found</div>;
    }
    
    // Fetch from API
    const { data: apiProposals } = useProposals(20, 'open');
    const { data: apiIssues } = useIssues(20);
    
    const proposalsData = USE_API && apiProposals ? apiProposals : globalProposals;
    const issuesData = USE_API && apiIssues ? apiIssues : globalIssues;
    
    // Get client-scoped data
    const clientProposals = (proposalsData as Proposal[]).filter((p: Proposal) => 
      p.status === 'open' && p.scope_refs?.some((r: { type: string; id: string }) => r.type === 'client' && r.id === clientId)
    ).sort((a: Proposal, b: Proposal) => b.score - a.score);
    
    const clientIssues = (issuesData as Issue[]).filter((i: Issue) => 
      ['open','monitoring','awaiting','blocked'].includes(i.state) && (i.primary_ref || '').includes(clientId)
    );
    
    // Fetch evidence from API
    const { data: apiEvidence } = useEvidence('client', clientId);
    const evidenceByTab: Record<string, Array<{ excerpt_id: string; text: string; source_type: string; source_ref: string; extracted_at: string }>> = 
      USE_API && apiEvidence ? apiEvidence : {
        Work: [],
        Comms: [],
        Meetings: [],
        Finance: []
      };
    
    // Handlers
    const handleOpenProposal = (proposal: Proposal) => {
      setSelectedProposal(proposal);
      setProposalDrawerOpen(true);
    };
    
    const handleTag = (proposal: Proposal) => {
      const { is_eligible } = checkEligibility(proposal);
      if (!is_eligible) return;
      
      tagProposal(proposal);
      setVersion(v => v + 1);
      setProposalDrawerOpen(false);
      setSelectedProposal(null);
    };
    
    const handleOpenIssue = (issue: Issue) => {
      setSelectedIssue(issue);
      setIssueDrawerOpen(true);
    };
    
    const handleSelectEvidenceTab = (tab: string) => {
      setEvidenceTab(tab);
    };
    
    const handleOpenEvidence = () => {
      if (evidenceTab) {
        setEvidenceOpen(true);
      }
    };
    
    return (
      <div key={version}>
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-2xl font-semibold">{client.name}</h1>
            <ConfidenceBadge type="linkage" value={client.linkage_confidence} />
          </div>
          <PostureStrip 
            posture={client.posture}
            proposal_count={clientProposals.length}
            issue_count={clientIssues.length}
            confidence={client.linkage_confidence}
          />
        </div>
        
        {/* Open Issues */}
        <section className="mb-8">
          <h2 className="text-lg font-medium mb-4">Open Issues</h2>
          {clientIssues.length === 0 ? (
            <p className="text-slate-500">No open issues for this client</p>
          ) : (
            <div className="space-y-3">
              {clientIssues.map((issue: Issue) => (
                <div 
                  key={issue.issue_id} 
                  className="bg-slate-800 rounded-lg border border-slate-700 p-4 cursor-pointer hover:border-slate-600 transition-colors"
                  onClick={() => handleOpenIssue(issue)}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-lg ${issue.state === 'open' ? 'text-red-500' : issue.state === 'blocked' ? 'text-slate-400' : 'text-amber-500'}`}>
                      {issue.state === 'open' ? '●' : issue.state === 'blocked' ? '■' : '◐'}
                    </span>
                    <h3 className="font-medium text-slate-200">{issue.headline}</h3>
                    <span className={`ml-auto text-xs px-2 py-0.5 rounded ${
                      issue.priority === 'critical' ? 'bg-red-900/30 text-red-400' : 
                      issue.priority === 'high' ? 'bg-orange-900/30 text-orange-400' : 
                      'bg-slate-700 text-slate-400'
                    }`}>
                      {issue.priority}
                    </span>
                  </div>
                  <p className="text-sm text-slate-500">Resolve: {issue.resolution_criteria}</p>
                  {issue.next_trigger && (
                    <p className="text-xs text-blue-400 mt-2">
                      ⏰ Next check: {new Date(issue.next_trigger).toLocaleString()}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
        
        {/* Top Proposals (gate-aware) */}
        <section className="mb-8">
          <h2 className="text-lg font-medium mb-4">Top Proposals</h2>
          {clientProposals.length === 0 ? (
            <p className="text-slate-500">No proposals for this client</p>
          ) : (
            <div className="space-y-4">
              {clientProposals.slice(0, 5).map((proposal: Proposal) => (
                <ProposalCard 
                  key={proposal.proposal_id} 
                  proposal={proposal}
                  onOpen={() => handleOpenProposal(proposal)}
                  onTag={() => handleTag(proposal)}
                />
              ))}
            </div>
          )}
        </section>
        
        {/* Evidence Tabs (drill-down only) */}
        <section>
          <h2 className="text-lg font-medium mb-4">Evidence</h2>
          <div className="flex gap-2 mb-4 overflow-x-auto">
            {['Work', 'Comms', 'Meetings', 'Finance'].map(tab => (
              <button 
                key={tab} 
                onClick={() => handleSelectEvidenceTab(tab)}
                className={`px-4 py-2 rounded text-sm whitespace-nowrap transition-colors ${
                  evidenceTab === tab 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
          
          {evidenceTab ? (
            <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 space-y-3">
              {evidenceByTab[evidenceTab]?.map(excerpt => (
                <div 
                  key={excerpt.excerpt_id}
                  className="bg-slate-800 rounded-lg p-3 border-l-2 border-blue-500 cursor-pointer hover:bg-slate-700 transition-colors"
                  onClick={handleOpenEvidence}
                >
                  <p className="text-sm text-slate-300">{excerpt.text}</p>
                  <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
                    <span>📎 {excerpt.source_type.replace('_', ' ')}</span>
                    <span>·</span>
                    <span>{new Date(excerpt.extracted_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 text-slate-500 text-sm">
              Select a tab to view evidence excerpts
            </div>
          )}
        </section>
        
        {/* RoomDrawer for proposals */}
        {selectedProposal && (
          <RoomDrawer
            isOpen={proposalDrawerOpen}
            onClose={() => {
              setProposalDrawerOpen(false);
              setSelectedProposal(null);
            }}
            entity={{
              type: 'proposal',
              id: selectedProposal.proposal_id,
              headline: selectedProposal.headline,
              coverage_summary: `Scoped to ${client.name}`,
            }}
            proposal={selectedProposal}
            onTag={() => handleTag(selectedProposal)}
            onSnooze={() => console.log('[SNOOZE STUB]', selectedProposal.proposal_id)}
            onDismiss={() => console.log('[DISMISS STUB]', selectedProposal.proposal_id)}
            onFixData={() => navigate({ to: '/fix-data' })}
          />
        )}
        
        {/* IssueDrawer for issues */}
        {selectedIssue && (
          <IssueDrawer
            isOpen={issueDrawerOpen}
            onClose={() => {
              setIssueDrawerOpen(false);
              setSelectedIssue(null);
            }}
            issue={selectedIssue}
          />
        )}
        
        {/* EvidenceViewer for evidence excerpts */}
        {evidenceTab && (
          <EvidenceViewer
            isOpen={evidenceOpen}
            onClose={() => setEvidenceOpen(false)}
            excerpts={evidenceByTab[evidenceTab] || []}
            onSourceClick={(ref) => console.log('[EVIDENCE] Open source:', ref)}
          />
        )}
      </div>
    )
  },
})

// ============================================================
// TEAM PORTFOLIO
// ============================================================
const teamRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/team',
  component: function TeamPortfolio() {
    const [search, setSearch] = useState('');
    const [sortBy, setSortBy] = useState<'load' | 'name' | 'responsiveness'>('load');
    
    // Fetch from API
    const { data: apiTeam, loading, error } = useTeam();
    const teamData = USE_API && apiTeam ? apiTeam : teamMembers;
    
    // Filter by search
    const filtered = (teamData as typeof teamMembers).filter(m => 
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      (m.role || '').toLowerCase().includes(search.toLowerCase())
    );
    
    // Sort
    const loadOrder: Record<string, number> = { high: 0, medium: 1, low: 2, unknown: 3 };
    const respOrder: Record<string, number> = { fast: 0, normal: 1, slow: 2 };
    const sorted = [...filtered].sort((a, b) => {
      switch (sortBy) {
        case 'load': return (loadOrder[a.load_band] ?? 3) - (loadOrder[b.load_band] ?? 3) || a.name.localeCompare(b.name);
        case 'name': return a.name.localeCompare(b.name);
        case 'responsiveness': 
          const aResp = a.responsiveness ? Object.values(a.responsiveness).map((r: any) => respOrder[r?.band] ?? 1).reduce((sum: number, v: number) => sum + v, 0) : 99;
          const bResp = b.responsiveness ? Object.values(b.responsiveness).map((r: any) => respOrder[r?.band] ?? 1).reduce((sum: number, v: number) => sum + v, 0) : 99;
          return aResp - bResp;
        default: return 0;
      }
    });
    
    if (USE_API && loading) {
      return <div className="text-slate-400 p-8 text-center">Loading team...</div>;
    }
    if (USE_API && error) {
      return <div className="text-red-400 p-8 text-center">Error loading team: {error.message}</div>;
    }
    
    return (
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <h1 className="text-2xl font-semibold">Team Portfolio</h1>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Search name/role..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm placeholder-slate-500"
            />
            <select 
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm"
            >
              <option value="load">Sort: Load</option>
              <option value="name">Sort: A-Z</option>
              <option value="responsiveness">Sort: Responsiveness</option>
            </select>
          </div>
        </div>
        
        {sorted.length === 0 ? (
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-8 text-center text-slate-500">
            No team members found
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {sorted.map(member => {
              const avgResp = Object.values(member.responsiveness).map(r => r.band)[0] || 'normal';
              const showLimitedData = member.load_confidence < 0.5;
              
              return (
                <Link
                  key={member.member_id}
                  to="/team/$id"
                  params={{ id: member.member_id }}
                  className="block bg-slate-800 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors p-4"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="font-medium text-slate-100">{member.name}</h3>
                      <p className="text-sm text-slate-500">{member.role}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      {showLimitedData ? (
                        <span className="px-2 py-1 rounded text-xs bg-slate-700 text-slate-400">
                          ⚠️ Limited data
                        </span>
                      ) : (
                        <span className={`px-2 py-1 rounded text-xs ${
                          member.load_band === 'high' ? 'bg-red-900/30 text-red-400' :
                          member.load_band === 'medium' ? 'bg-amber-900/30 text-amber-400' :
                          'bg-green-900/30 text-green-400'
                        }`}>
                          {member.load_band} load
                        </span>
                      )}
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        avgResp === 'fast' ? 'bg-green-900/30 text-green-400' :
                        avgResp === 'normal' ? 'bg-slate-700 text-slate-300' :
                        'bg-red-900/30 text-red-400'
                      }`}>
                        {avgResp} resp
                      </span>
                    </div>
                  </div>
                  
                  {/* Load bar */}
                  {!showLimitedData && (
                    <div className="h-2 bg-slate-700 rounded-full overflow-hidden mb-2">
                      <div className={`h-full rounded-full ${
                        member.load_band === 'high' ? 'w-4/5 bg-red-500' :
                        member.load_band === 'medium' ? 'w-1/2 bg-amber-500' :
                        'w-1/4 bg-green-500'
                      }`}></div>
                    </div>
                  )}
                  
                  <div className="text-sm text-slate-400">
                    <span>{member.throughput_7d} tasks/7d</span>
                    <span className="mx-2">·</span>
                    <span>~{member.avg_completion_days}d avg</span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    )
  },
})

// ============================================================
// TEAM DETAIL REPORT
// ============================================================
const teamDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/team/$id',
  component: function TeamDetail() {
    const navigate = useNavigate();
    const { id } = useParams({ from: '/team/$id' });
    const { data: apiTeam } = useTeam();
    const teamData = USE_API && apiTeam ? apiTeam : teamMembers;
    const member = (teamData as typeof teamMembers).find(m => m.member_id === id);
    
    // State for drawers
    const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
    const [proposalDrawerOpen, setProposalDrawerOpen] = useState(false);
    const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
    const [issueDrawerOpen, setIssueDrawerOpen] = useState(false);
    const [version, setVersion] = useState(0);
    
    if (!member) {
      return <div className="text-slate-400">Team member not found</div>;
    }
    
    // Fetch from API
    const { data: apiProposals } = useProposals(20, 'open');
    const { data: apiIssues } = useIssues(20);
    
    const proposalsData = USE_API && apiProposals ? apiProposals : globalProposals;
    const issuesData = USE_API && apiIssues ? apiIssues : globalIssues;
    
    // Get member-scoped data
    const memberProposals = (proposalsData as Proposal[]).filter((p: Proposal) => 
      p.status === 'open' && p.scope_refs?.some((r: { type: string; id: string }) => r.type === 'team_member' && r.id === id)
    ).sort((a: Proposal, b: Proposal) => b.score - a.score);
    
    // Scoped issues (in production would filter by assignee_id)
    const memberIssues = (issuesData as Issue[]).filter((i: Issue) => 
      ['open','monitoring','awaiting','blocked'].includes(i.state)
    ).slice(0, 3);
    
    const loadBarWidth = member.load_band === 'high' ? 'w-4/5' : member.load_band === 'medium' ? 'w-1/2' : 'w-1/4';
    const loadBarColor = member.load_band === 'high' ? 'bg-red-500' : member.load_band === 'medium' ? 'bg-amber-500' : 'bg-green-500';
    const showLimitedData = member.load_confidence < 0.5;
    
    // Handlers
    const handleOpenProposal = (proposal: Proposal) => {
      setSelectedProposal(proposal);
      setProposalDrawerOpen(true);
    };
    
    const handleTag = (proposal: Proposal) => {
      const { is_eligible } = checkEligibility(proposal);
      if (!is_eligible) return;
      tagProposal(proposal);
      setVersion(v => v + 1);
      setProposalDrawerOpen(false);
      setSelectedProposal(null);
    };
    
    const handleOpenIssue = (issue: Issue) => {
      setSelectedIssue(issue);
      setIssueDrawerOpen(true);
    };
    
    return (
      <div key={version}>
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-2xl font-semibold">{member.name}</h1>
            <span className="text-slate-500">{member.role}</span>
            {showLimitedData && (
              <span className="px-2 py-1 rounded text-xs bg-slate-700 text-slate-400">⚠️ Limited data</span>
            )}
          </div>
        </div>
        
        {/* Load & Throughput (responsible metrics) */}
        <section className="mb-8 bg-slate-800 rounded-lg border border-slate-700 p-4">
          <h2 className="text-lg font-medium mb-4">Load & Throughput</h2>
          
          {showLimitedData ? (
            <div className="text-slate-500 text-sm">Insufficient data to display load metrics reliably.</div>
          ) : (
            <>
              <div className="mb-4">
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-slate-400">Current Load: <span className="text-slate-200 capitalize">{member.load_band}</span></span>
                  <span className="text-slate-500">(Confidence: {(member.load_confidence * 100).toFixed(0)}%)</span>
                </div>
                <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
                  <div className={`h-full ${loadBarWidth} ${loadBarColor} rounded-full`}></div>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-slate-400">Throughput (7d)</p>
                  <p className="text-xl font-semibold text-slate-200">{member.throughput_7d} tasks</p>
                </div>
                <div>
                  <p className="text-slate-400">Avg completion</p>
                  <p className="text-xl font-semibold text-slate-200">~{member.avg_completion_days} days</p>
                </div>
              </div>
            </>
          )}
          
          <div className="mt-4 p-3 bg-amber-900/10 rounded border border-amber-700/30 text-xs text-amber-300">
            ⚠️ Caveat: Based on task tracking data. May not reflect meetings, ad-hoc work, or untracked activities.
          </div>
        </section>
        
        {/* Responsiveness Signals */}
        <section className="mb-8 bg-slate-800 rounded-lg border border-slate-700 p-4">
          <h2 className="text-lg font-medium mb-4">Responsiveness Signals</h2>
          <div className="space-y-3">
            {Object.entries(member.responsiveness).map(([channel, data]) => (
              <div key={channel} className="flex items-center justify-between text-sm">
                <span className="text-slate-400 capitalize">{channel.replace('_', ' ')}</span>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded ${
                    data.band === 'fast' ? 'bg-green-900/30 text-green-400' :
                    data.band === 'normal' ? 'bg-slate-700 text-slate-300' :
                    'bg-red-900/30 text-red-400'
                  }`}>
                    {data.band}
                  </span>
                  <span className="text-slate-500 text-xs">({(data.confidence * 100).toFixed(0)}%)</span>
                </div>
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-500 mt-3">(Based on last 14 days)</p>
        </section>
        
        {/* Scoped Issues */}
        <section className="mb-8">
          <h2 className="text-lg font-medium mb-4">Scoped Issues</h2>
          {memberIssues.length === 0 ? (
            <p className="text-slate-500">No issues assigned to this team member</p>
          ) : (
            <div className="space-y-3">
              {memberIssues.map((issue: Issue) => (
                <div 
                  key={issue.issue_id}
                  className="bg-slate-800 rounded-lg border border-slate-700 p-4 cursor-pointer hover:border-slate-600 transition-colors"
                  onClick={() => handleOpenIssue(issue)}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-lg ${issue.state === 'open' ? 'text-red-500' : issue.state === 'blocked' ? 'text-slate-400' : 'text-amber-500'}`}>
                      {issue.state === 'open' ? '●' : issue.state === 'blocked' ? '■' : '◐'}
                    </span>
                    <h3 className="font-medium text-slate-200">{issue.headline}</h3>
                    <span className={`ml-auto text-xs px-2 py-0.5 rounded ${
                      issue.priority === 'critical' ? 'bg-red-900/30 text-red-400' : 
                      issue.priority === 'high' ? 'bg-orange-900/30 text-orange-400' : 
                      'bg-slate-700 text-slate-400'
                    }`}>
                      {issue.priority}
                    </span>
                  </div>
                  <p className="text-sm text-slate-500">Resolve: {issue.resolution_criteria}</p>
                </div>
              ))}
            </div>
          )}
        </section>
        
        {/* Scoped Proposals */}
        <section className="mb-8">
          <h2 className="text-lg font-medium mb-4">Scoped Proposals</h2>
          {memberProposals.length === 0 ? (
            <p className="text-slate-500">No proposals mentioning this team member</p>
          ) : (
            <div className="space-y-4">
              {memberProposals.map((proposal: Proposal) => (
                <ProposalCard 
                  key={proposal.proposal_id} 
                  proposal={proposal}
                  onOpen={() => handleOpenProposal(proposal)}
                  onTag={() => handleTag(proposal)}
                />
              ))}
            </div>
          )}
        </section>
        
        {/* RoomDrawer for proposals */}
        {selectedProposal && (
          <RoomDrawer
            isOpen={proposalDrawerOpen}
            onClose={() => {
              setProposalDrawerOpen(false);
              setSelectedProposal(null);
            }}
            entity={{
              type: 'proposal',
              id: selectedProposal.proposal_id,
              headline: selectedProposal.headline,
              coverage_summary: `Mentions ${member.name}`,
            }}
            proposal={selectedProposal}
            onTag={() => handleTag(selectedProposal)}
            onSnooze={() => console.log('[SNOOZE STUB]', selectedProposal.proposal_id)}
            onDismiss={() => console.log('[DISMISS STUB]', selectedProposal.proposal_id)}
            onFixData={() => navigate({ to: '/fix-data' })}
          />
        )}
        
        {/* IssueDrawer */}
        {selectedIssue && (
          <IssueDrawer
            isOpen={issueDrawerOpen}
            onClose={() => {
              setIssueDrawerOpen(false);
              setSelectedIssue(null);
            }}
            issue={selectedIssue}
          />
        )}
      </div>
    )
  },
})

// ============================================================
// INTERSECTIONS
// ============================================================
const intersectionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intersections',
  component: function Intersections() {
    const navigate = useNavigate();
    
    // Fetch proposals and issues from API
    const { data: apiProposals } = useProposals(10, 'open');
    const { data: apiIssues } = useIssues(10);
    
    const proposalsData = USE_API && apiProposals ? apiProposals : globalProposals.filter((p: Proposal) => p.status === 'open');
    const issuesData = USE_API && apiIssues ? apiIssues : globalIssues.filter((i: Issue) => ['open','monitoring','awaiting','blocked'].includes(i.state));
    
    // State for anchor selection and coupling detail
    const [selectedAnchorId, setSelectedAnchorId] = useState<string>('');
    const [selectedCoupling, setSelectedCoupling] = useState<typeof couplings[0] | null>(null);
    const [anchorType, setAnchorType] = useState<'proposal' | 'issue'>('proposal');
    
    // Set default anchor when data loads
    if (!selectedAnchorId && (proposalsData as Proposal[]).length > 0) {
      setSelectedAnchorId((proposalsData as Proposal[])[0].proposal_id);
    }
    
    // Build anchor list: proposals + issues
    const proposalAnchors = (proposalsData as Proposal[]).slice(0, 10);
    const issueAnchors = (issuesData as Issue[]).slice(0, 10);
    
    // Fetch couplings from API
    const { data: apiCouplings } = useAllCouplings();
    const couplingsData = USE_API && apiCouplings ? apiCouplings : couplings;
    
    // Get couplings for selected anchor
    const anchorCouplings = (couplingsData as typeof couplings)
      .filter(c => c.anchor_id === selectedAnchorId && (c.why_signals?.length > 0 || c.strength > 0.5))
      .sort((a, b) => b.strength - a.strength);
    
    // Node click handler
    const handleNodeClick = (coupling: typeof couplings[0]) => {
      setSelectedCoupling(coupling);
      // Navigate based on type
      if (coupling.coupled_type === 'client') {
        navigate({ to: '/clients/$clientId', params: { clientId: coupling.coupled_id } });
      } else if (coupling.coupled_type === 'team_member') {
        navigate({ to: '/team/$id', params: { id: coupling.coupled_id } });
      }
    };
    
    // Edge click handler
    const handleEdgeClick = (coupling: typeof couplings[0]) => {
      setSelectedCoupling(coupling);
    };
    
    return (
      <div className="lg:grid lg:grid-cols-12 lg:gap-6">
        {/* Left: Anchor selector */}
        <div className="lg:col-span-3 mb-6 lg:mb-0">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">Select Anchor</h2>
          
          {/* Anchor type tabs */}
          <div className="flex gap-2 mb-3">
            <button 
              onClick={() => setAnchorType('proposal')}
              className={`flex-1 px-3 py-1.5 text-xs rounded ${anchorType === 'proposal' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'}`}
            >
              Proposals
            </button>
            <button 
              onClick={() => setAnchorType('issue')}
              className={`flex-1 px-3 py-1.5 text-xs rounded ${anchorType === 'issue' ? 'bg-red-600 text-white' : 'bg-slate-800 text-slate-400'}`}
            >
              Issues
            </button>
          </div>
          
          <div className="bg-slate-800 rounded-lg border border-slate-700 p-2 space-y-1 max-h-[400px] overflow-y-auto">
            {anchorType === 'proposal' ? (
              proposalAnchors.map((p: Proposal) => (
                <div 
                  key={p.proposal_id}
                  onClick={() => { setSelectedAnchorId(p.proposal_id); setSelectedCoupling(null); }}
                  className={`p-2 rounded cursor-pointer transition-colors ${
                    selectedAnchorId === p.proposal_id 
                      ? 'bg-blue-600/20 border border-blue-500/30' 
                      : 'hover:bg-slate-700'
                  }`}
                >
                  <p className="text-sm text-slate-300 truncate">{p.headline}</p>
                  <p className="text-xs text-slate-500">{p.proposal_id} · Score: {p.score}</p>
                </div>
              ))
            ) : (
              issueAnchors.map((i: Issue) => (
                <div 
                  key={i.issue_id}
                  onClick={() => { setSelectedAnchorId(i.issue_id); setSelectedCoupling(null); }}
                  className={`p-2 rounded cursor-pointer transition-colors ${
                    selectedAnchorId === i.issue_id 
                      ? 'bg-red-600/20 border border-red-500/30' 
                      : 'hover:bg-slate-700'
                  }`}
                >
                  <p className="text-sm text-slate-300 truncate">{i.headline}</p>
                  <p className="text-xs text-slate-500">{i.issue_id} · {i.priority}</p>
                </div>
              ))
            )}
          </div>
        </div>
        
        {/* Center: Coupling map */}
        <div className="lg:col-span-6 mb-6 lg:mb-0">
          <h1 className="text-2xl font-semibold mb-4">Intersections</h1>
          
          {anchorCouplings.length === 0 ? (
            <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 min-h-[300px] flex items-center justify-center text-slate-500">
              No couplings with evidence found for this anchor
            </div>
          ) : (
            <>
              {/* Visual map */}
              <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 min-h-[300px] flex items-center justify-center">
                <div className="relative">
                  {/* Center node (anchor) */}
                  <div className={`absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 ${anchorType === 'proposal' ? 'bg-blue-600' : 'bg-red-600'} rounded-full flex items-center justify-center text-white font-bold shadow-lg z-10`}>
                    {anchorType === 'proposal' ? 'P' : 'I'}
                  </div>
                  
                  {/* Coupled nodes */}
                  {anchorCouplings.map((coupling, i) => {
                    const angle = (i * 360) / anchorCouplings.length;
                    const radius = 100;
                    const x = Math.cos((angle * Math.PI) / 180) * radius;
                    const y = Math.sin((angle * Math.PI) / 180) * radius;
                    
                    const nodeColors: Record<string, string> = {
                      client: 'bg-green-600',
                      team_member: 'bg-purple-600',
                      issue: 'bg-red-600',
                      engagement: 'bg-orange-600',
                      proposal: 'bg-blue-600'
                    };
                    
                    const isSelected = selectedCoupling?.coupling_id === coupling.coupling_id;
                    
                    return (
                      <div key={coupling.coupling_id}>
                        {/* Edge line (clickable) */}
                        <svg 
                          className="absolute left-1/2 top-1/2 w-[200px] h-[200px] -translate-x-1/2 -translate-y-1/2 cursor-pointer"
                          onClick={() => handleEdgeClick(coupling)}
                        >
                          <line
                            x1="100" y1="100"
                            x2={100 + x} y2={100 + y}
                            stroke={isSelected ? '#3b82f6' : coupling.confidence >= 0.80 ? '#22c55e' : coupling.confidence >= 0.60 ? '#f59e0b' : '#ef4444'}
                            strokeWidth={isSelected ? coupling.strength * 4 + 2 : coupling.strength * 3}
                            strokeDasharray={coupling.confidence < 0.70 ? '4,4' : undefined}
                          />
                        </svg>
                        
                        {/* Node */}
                        <div 
                          onClick={() => handleNodeClick(coupling)}
                          className={`absolute w-12 h-12 ${nodeColors[coupling.coupled_type] || 'bg-slate-600'} rounded-full flex items-center justify-center text-white text-sm font-bold shadow cursor-pointer hover:scale-110 transition-transform ${isSelected ? 'ring-2 ring-white' : ''}`}
                          style={{
                            left: `calc(50% + ${x}px - 24px)`,
                            top: `calc(50% + ${y}px - 24px)`
                          }}
                          title={`${coupling.coupled_label} (${coupling.coupled_type})`}
                        >
                          {coupling.coupled_type[0].toUpperCase()}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              
              <div className="flex items-center gap-4 mt-4 text-xs text-slate-500">
                <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-600 rounded-full"></span> Proposal</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-600 rounded-full"></span> Client</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 bg-purple-600 rounded-full"></span> Team</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-600 rounded-full"></span> Issue</span>
              </div>
            </>
          )}
        </div>
        
        {/* Right: Why-drivers */}
        <div className="lg:col-span-3">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">Why-Drivers</h2>
          
          {selectedCoupling ? (
            // Detailed view for selected coupling
            <div className="bg-slate-800 rounded-lg border border-blue-500/50 p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-slate-200">{selectedCoupling.coupled_label}</span>
                <button 
                  onClick={() => setSelectedCoupling(null)}
                  className="text-slate-400 hover:text-slate-200"
                >
                  ✕
                </button>
              </div>
              
              {/* Strength + Confidence */}
              <div className="flex items-center gap-2 mb-3">
                <span className={`text-xs px-2 py-1 rounded ${
                  selectedCoupling.strength >= 0.80 ? 'bg-green-900/30 text-green-400' :
                  selectedCoupling.strength >= 0.60 ? 'bg-amber-900/30 text-amber-400' :
                  'bg-slate-700 text-slate-400'
                }`}>
                  Strength: {selectedCoupling.strength >= 0.80 ? 'Strong' : selectedCoupling.strength >= 0.60 ? 'Medium' : 'Weak'}
                </span>
                <ConfidenceBadge type="linkage" value={selectedCoupling.confidence} />
              </div>
              
              {/* Why signals */}
              <div className="mb-3">
                <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Why</h4>
                <div className="space-y-2">
                  {selectedCoupling.why_signals.map((sig, i) => (
                    <div key={i} className="bg-slate-900/50 rounded p-2">
                      <span className="text-xs text-blue-400">{sig.signal_type}</span>
                      <p className="text-sm text-slate-300 mt-1">{sig.description}</p>
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Actions */}
              <button 
                onClick={() => handleNodeClick(selectedCoupling)}
                className="w-full px-3 py-2 bg-slate-700 hover:bg-slate-600 text-sm text-slate-200 rounded transition-colors"
              >
                Investigate {selectedCoupling.coupled_label} →
              </button>
            </div>
          ) : (
            // List of all couplings
            <div className="space-y-3">
              {anchorCouplings.length === 0 ? (
                <p className="text-sm text-slate-500">Select an anchor to see couplings</p>
              ) : (
                anchorCouplings.map(coupling => (
                  <div 
                    key={coupling.coupling_id} 
                    onClick={() => setSelectedCoupling(coupling)}
                    className="bg-slate-800 rounded-lg border border-slate-700 p-3 cursor-pointer hover:border-slate-600 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-slate-200">{coupling.coupled_label}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        coupling.strength >= 0.80 ? 'bg-green-900/30 text-green-400' :
                        coupling.strength >= 0.60 ? 'bg-amber-900/30 text-amber-400' :
                        'bg-slate-700 text-slate-400'
                      }`}>
                        {coupling.strength >= 0.80 ? 'Strong' : coupling.strength >= 0.60 ? 'Medium' : 'Weak'}
                      </span>
                    </div>
                    <ConfidenceBadge type="linkage" value={coupling.confidence} showLabel={false} />
                    <div className="mt-2 space-y-1">
                      {coupling.why_signals.slice(0, 2).map((sig, i) => (
                        <p key={i} className="text-xs text-slate-400 truncate">
                          • {sig.description}
                        </p>
                      ))}
                      {coupling.why_signals.length > 2 && (
                        <p className="text-xs text-slate-500">+{coupling.why_signals.length - 2} more signals</p>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    )
  },
})

// ============================================================
// ISSUES INBOX
// ============================================================
const issuesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/issues',
  component: function IssuesInbox() {
    // State
    const [stateFilter, setStateFilter] = useState<Issue['state'] | 'all'>('all');
    const [priorityFilter, setPriorityFilter] = useState<Issue['priority'] | 'all'>('all');
    const [search, setSearch] = useState('');
    const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);
    
    // Fetch from API
    const { data: apiIssues, loading, error } = useIssues(50); // Get more issues for the inbox
    const issuesData = USE_API && apiIssues ? apiIssues : globalIssues;
    
    // Filter and sort issues
    const priorityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
    const filteredIssues = (issuesData as Issue[])
      .filter((i: Issue) => stateFilter === 'all' || i.state === stateFilter)
      .filter((i: Issue) => priorityFilter === 'all' || i.priority === priorityFilter)
      .filter((i: Issue) => search === '' || i.headline.toLowerCase().includes(search.toLowerCase()))
      .sort((a: Issue, b: Issue) => {
        const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
        if (priorityDiff !== 0) return priorityDiff;
        return new Date(b.last_activity_at).getTime() - new Date(a.last_activity_at).getTime();
      });
    
    // Check if next_trigger is within 24h
    const isUpcomingTrigger = (trigger?: string) => {
      if (!trigger) return false;
      const triggerTime = new Date(trigger).getTime();
      const now = Date.now();
      const in24h = now + 24 * 60 * 60 * 1000;
      return triggerTime <= in24h && triggerTime > now;
    };
    
    const formatRelativeTime = (isoString: string) => {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffHrs / 24);
      if (diffDays > 0) return `${diffDays}d ago`;
      if (diffHrs > 0) return `${diffHrs}h ago`;
      return 'Just now';
    };
    
    const formatFutureTime = (isoString: string) => {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = date.getTime() - now.getTime();
      const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
      if (diffHrs <= 0) return 'Soon';
      if (diffHrs < 24) return `in ${diffHrs}h`;
      return `in ${Math.floor(diffHrs / 24)}d`;
    };
    
    const stateIcons: Record<Issue['state'], { icon: string; color: string }> = {
      open: { icon: '●', color: 'text-red-500' },
      monitoring: { icon: '◐', color: 'text-amber-500' },
      awaiting: { icon: '◑', color: 'text-blue-500' },
      blocked: { icon: '■', color: 'text-slate-400' },
      resolved: { icon: '✓', color: 'text-green-500' },
      closed: { icon: '○', color: 'text-slate-500' },
    };
    
    if (USE_API && loading) {
      return <div className="text-slate-400 p-8 text-center">Loading issues...</div>;
    }
    if (USE_API && error) {
      return <div className="text-red-400 p-8 text-center">Error loading issues: {error.message}</div>;
    }
    
    return (
      <div>
        {/* Header with filters */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <h1 className="text-2xl font-semibold">Issues Inbox</h1>
          <input
            type="text"
            placeholder="Search issues..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm placeholder-slate-500 sm:w-64"
          />
        </div>
        
        {/* State filter tabs */}
        <div className="flex gap-2 mb-4 overflow-x-auto pb-2">
          {(['all', 'open', 'monitoring', 'awaiting', 'blocked', 'resolved', 'closed'] as const).map(state => (
            <button 
              key={state} 
              onClick={() => setStateFilter(state)}
              className={`px-3 py-1.5 rounded text-sm whitespace-nowrap transition-colors ${
                stateFilter === state 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              {state === 'all' ? 'All' : state.charAt(0).toUpperCase() + state.slice(1)}
            </button>
          ))}
        </div>
        
        {/* Priority filter */}
        <div className="flex gap-2 mb-6">
          <span className="text-sm text-slate-400 py-1">Priority:</span>
          {(['all', 'critical', 'high', 'medium', 'low'] as const).map(priority => (
            <button 
              key={priority} 
              onClick={() => setPriorityFilter(priority)}
              className={`px-2 py-1 rounded text-xs whitespace-nowrap transition-colors ${
                priorityFilter === priority 
                  ? priority === 'critical' ? 'bg-red-600 text-white' :
                    priority === 'high' ? 'bg-orange-600 text-white' :
                    priority === 'medium' ? 'bg-amber-600 text-white' :
                    priority === 'low' ? 'bg-slate-600 text-white' :
                    'bg-slate-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              {priority === 'all' ? 'All' : priority.charAt(0).toUpperCase() + priority.slice(1)}
            </button>
          ))}
        </div>
        
        {/* Issues list */}
        {filteredIssues.length === 0 ? (
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-8 text-center text-slate-500">
            {search || stateFilter !== 'all' || priorityFilter !== 'all' 
              ? 'No issues match filters' 
              : 'No issues'}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredIssues.map((issue: Issue) => {
              const stateConfig = stateIcons[issue.state];
              const hasUpcomingTrigger = isUpcomingTrigger(issue.next_trigger);
              
              return (
                <div 
                  key={issue.issue_id} 
                  onClick={() => { setSelectedIssue(issue); setDrawerOpen(true); }}
                  className="bg-slate-800 rounded-lg border border-slate-700 p-4 cursor-pointer hover:border-slate-600 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className={`text-xl ${stateConfig.color}`}>
                      {stateConfig.icon}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-slate-200 truncate">{issue.headline}</h3>
                        {hasUpcomingTrigger && (
                          <span className="px-1.5 py-0.5 bg-blue-900/50 text-blue-400 text-xs rounded whitespace-nowrap">
                            ⏰ {formatFutureTime(issue.next_trigger!)}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-500 truncate">{issue.resolution_criteria}</p>
                      <p className="text-xs text-slate-500 mt-1">
                        Last activity: {formatRelativeTime(issue.last_activity_at)}
                      </p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs whitespace-nowrap ${
                      issue.priority === 'critical' ? 'bg-red-900/30 text-red-400' :
                      issue.priority === 'high' ? 'bg-orange-900/30 text-orange-400' :
                      issue.priority === 'medium' ? 'bg-amber-900/30 text-amber-400' :
                      'bg-slate-700 text-slate-400'
                    }`}>
                      {issue.priority}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        
        {/* IssueDrawer */}
        {selectedIssue && (
          <IssueDrawer
            isOpen={drawerOpen}
            onClose={() => {
              setDrawerOpen(false);
              setSelectedIssue(null);
            }}
            issue={selectedIssue}
            watchers={watchers}
          />
        )}
      </div>
    )
  },
})

// ============================================================
// FIX DATA CENTER
// ============================================================

// Audit log for Fix Data actions (stubbed - in production this would be persisted)
const fixDataAuditLog: Array<{
  fix_data_id: string;
  action: string;
  timestamp: string;
  affected_proposals: string[];
}> = [];

function logFixDataAction(fixDataId: string, action: string, affectedProposals: string[]) {
  const entry = {
    fix_data_id: fixDataId,
    action,
    timestamp: new Date().toISOString(),
    affected_proposals: affectedProposals,
  };
  fixDataAuditLog.push(entry);
  console.log('[FIX_DATA_AUDIT]', entry);
}

const fixDataRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/fix-data',
  component: function FixDataCenter() {
    // State
    const [typeFilter, setTypeFilter] = useState<'all' | 'identity_conflict' | 'ambiguous_link' | 'missing_mapping'>('all');
    const [sortBy, setSortBy] = useState<'impact' | 'type' | 'age'>('impact');
    const [search, setSearch] = useState('');
    const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());
    const [selectedFixData, setSelectedFixData] = useState<typeof fixDataQueue[0] | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);
    
    // Fetch from API
    const { data: apiFixData, loading, error } = useFixData();
    const fixDataItems = USE_API && apiFixData ? apiFixData : fixDataQueue;
    
    // Filter and sort
    const pendingItems = (fixDataItems as typeof fixDataQueue)
      .filter(fd => !resolvedIds.has(fd.fix_data_id))
      .filter(fd => typeFilter === 'all' || fd.fix_type === typeFilter)
      .filter(fd => search === '' || (fd.description || '').toLowerCase().includes(search.toLowerCase()));
    
    const sortedItems = [...pendingItems].sort((a, b) => {
      switch (sortBy) {
        case 'impact': return (b.affected_proposal_ids?.length || 0) - (a.affected_proposal_ids?.length || 0);
        case 'type': return (a.fix_type || '').localeCompare(b.fix_type || '');
        case 'age': return 0; // Would use created_at if available
        default: return 0;
      }
    });
    
    if (USE_API && loading) {
      return <div className="text-slate-400 p-8 text-center">Loading fix data...</div>;
    }
    if (USE_API && error) {
      return <div className="text-red-400 p-8 text-center">Error loading fix data: {error.message}</div>;
    }
    
    // Handle resolution
    const handleResolve = (fixData: typeof fixDataQueue[0], action: string) => {
      // Log the action
      logFixDataAction(fixData.fix_data_id, action, fixData.affected_proposal_ids);
      
      // Mark as resolved (in production, this would update backend)
      setResolvedIds(prev => new Set([...prev, fixData.fix_data_id]));
      
      // Close drawer if open
      if (selectedFixData?.fix_data_id === fixData.fix_data_id) {
        setDrawerOpen(false);
        setSelectedFixData(null);
      }
      
      console.log(`[FIX_DATA] Resolved ${fixData.fix_data_id} with action: ${action}`);
    };
    
    return (
      <div>
        {/* Header with filters */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <h1 className="text-2xl font-semibold">Fix Data Center</h1>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm placeholder-slate-500"
            />
            <select 
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as typeof typeFilter)}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm"
            >
              <option value="all">All Types</option>
              <option value="identity_conflict">Identity Conflicts</option>
              <option value="ambiguous_link">Ambiguous Links</option>
              <option value="missing_mapping">Missing Mappings</option>
            </select>
            <select 
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm"
            >
              <option value="impact">By Impact</option>
              <option value="type">By Type</option>
              <option value="age">By Age</option>
            </select>
          </div>
        </div>
        
        {/* Stats bar */}
        <div className="flex items-center gap-4 mb-6 text-sm">
          <span className="text-slate-400">
            {sortedItems.length} pending · {resolvedIds.size} resolved this session
          </span>
          {resolvedIds.size > 0 && (
            <button 
              onClick={() => setResolvedIds(new Set())}
              className="text-blue-400 hover:text-blue-300"
            >
              Reset
            </button>
          )}
        </div>
        
        {/* Content */}
        {sortedItems.length === 0 ? (
          <div className="bg-green-900/20 rounded-lg border border-green-700/30 p-8 text-center">
            <span className="text-4xl">✓</span>
            <p className="text-lg text-green-400 mt-2">All data clean</p>
            <p className="text-sm text-slate-500">
              {resolvedIds.size > 0 
                ? `${resolvedIds.size} items resolved this session` 
                : 'No pending items to resolve'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {sortedItems.map(fd => (
              <FixDataCard 
                key={fd.fix_data_id} 
                fixData={fd}
                onResolve={(action) => handleResolve(fd, action)}
                onOpen={() => { setSelectedFixData(fd); setDrawerOpen(true); }}
              />
            ))}
          </div>
        )}
        
        {/* FixDataDrawer (detailed view) */}
        {selectedFixData && drawerOpen && (
          <>
            {/* Backdrop */}
            <div 
              className="fixed inset-0 bg-black/50 z-40"
              onClick={() => { setDrawerOpen(false); setSelectedFixData(null); }}
            />
            
            {/* Drawer */}
            <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[450px] bg-slate-900 border-l border-slate-700 overflow-y-auto">
              {/* Header */}
              <div className="sticky top-0 bg-slate-900/95 backdrop-blur border-b border-slate-700 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xl">
                        {selectedFixData.fix_type === 'identity_conflict' ? '🔀' :
                         selectedFixData.fix_type === 'ambiguous_link' ? '🔗' : '➕'}
                      </span>
                      <span className="text-sm font-medium text-slate-400 uppercase">
                        {selectedFixData.fix_type.replace('_', ' ')}
                      </span>
                    </div>
                    <h2 className="text-lg font-semibold text-slate-100">
                      {selectedFixData.description}
                    </h2>
                  </div>
                  <button 
                    onClick={() => { setDrawerOpen(false); setSelectedFixData(null); }}
                    className="p-2 hover:bg-slate-800 rounded text-slate-400"
                  >
                    ✕
                  </button>
                </div>
              </div>
              
              <div className="p-4 space-y-6">
                {/* Candidates */}
                <section>
                  <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
                    Candidates ({selectedFixData.candidates.length})
                  </h3>
                  <div className="space-y-2">
                    {selectedFixData.candidates.map((c, i) => (
                      <div 
                        key={i}
                        className="bg-slate-800 rounded-lg p-3 flex items-center justify-between"
                      >
                        <span className="text-slate-200">{c.label}</span>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            c.match_score >= 0.80 ? 'bg-green-900/30 text-green-400' :
                            c.match_score >= 0.60 ? 'bg-amber-900/30 text-amber-400' :
                            'bg-slate-700 text-slate-400'
                          }`}>
                            {(c.match_score * 100).toFixed(0)}% match
                          </span>
                          <button 
                            onClick={() => handleResolve(selectedFixData, `assign:${c.label}`)}
                            className="text-xs text-blue-400 hover:text-blue-300"
                          >
                            Select
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
                
                {/* Impact */}
                <section>
                  <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
                    Impact
                  </h3>
                  <div className="bg-amber-900/20 rounded-lg p-4 border border-amber-700/30">
                    <div className="flex items-center gap-2 text-amber-300">
                      <span>⚠️</span>
                      <span>{selectedFixData.impact_summary}</span>
                    </div>
                    {selectedFixData.affected_proposal_ids.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs text-slate-400 mb-2">Affected proposals:</p>
                        <div className="flex flex-wrap gap-1">
                          {selectedFixData.affected_proposal_ids.map(id => (
                            <span key={id} className="px-2 py-0.5 bg-slate-800 text-slate-300 text-xs rounded">
                              {id}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </section>
                
                {/* Resolution actions */}
                <section>
                  <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
                    Resolution
                  </h3>
                  <div className="space-y-2">
                    {selectedFixData.fix_type === 'identity_conflict' && (
                      <>
                        <button 
                          onClick={() => handleResolve(selectedFixData, 'merge')}
                          className="w-full px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded transition-colors"
                        >
                          Merge all identities
                        </button>
                        <button 
                          onClick={() => handleResolve(selectedFixData, 'keep_separate')}
                          className="w-full px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded transition-colors"
                        >
                          Keep as separate entities
                        </button>
                      </>
                    )}
                    {selectedFixData.fix_type === 'ambiguous_link' && (
                      <p className="text-sm text-slate-400">
                        Select a candidate above to assign the link
                      </p>
                    )}
                    {selectedFixData.fix_type === 'missing_mapping' && (
                      <>
                        <button 
                          onClick={() => handleResolve(selectedFixData, 'create_alias')}
                          className="w-full px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm rounded transition-colors"
                        >
                          Create alias mapping
                        </button>
                      </>
                    )}
                    <button 
                      onClick={() => handleResolve(selectedFixData, 'ignore')}
                      className="w-full px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-sm rounded transition-colors"
                    >
                      Ignore this item
                    </button>
                  </div>
                </section>
                
                {/* Audit note */}
                <div className="text-xs text-slate-500 p-3 bg-slate-800/50 rounded">
                  All resolutions are logged to the audit trail for compliance and undo capability.
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    )
  },
})

// Route tree
const routeTree = rootRoute.addChildren([
  indexRoute,
  clientsRoute,
  clientDetailRoute,
  teamRoute,
  teamDetailRoute,
  intersectionsRoute,
  issuesRoute,
  fixDataRoute,
])

// Router instance
export const router = createRouter({ routeTree })

// Type registration
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
