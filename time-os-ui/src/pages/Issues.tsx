// Issues Inbox page with hierarchy view
import { useState, useMemo, useEffect } from 'react';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { IssueDrawer, SkeletonCardList } from '../components';
import type { IssueState } from '../lib/api';
import { priorityLabel, priorityBadgeClass, matchesPriorityFilter } from '../lib/priority';
import type { Issue } from '../types/api';
import { useIssues } from '../lib/hooks';
import { useDebounce } from '../lib/useDebounce';
import * as api from '../lib/api';
import { PageLayout } from '../components/layout/PageLayout';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';

const stateIcons: Record<string, { icon: string; color: string }> = {
  // v29 states
  detected: { icon: '◎', color: 'text-[var(--info)]' },
  surfaced: { icon: '○', color: 'text-[var(--info)]' },
  snoozed: { icon: '◷', color: 'text-amber-400' },
  acknowledged: { icon: '◉', color: 'text-purple-400' },
  addressing: { icon: '⊕', color: 'text-cyan-400' },
  awaiting_resolution: { icon: '◷', color: 'text-amber-400' },
  regression_watch: { icon: '◎', color: 'text-[var(--warning)]' },
  closed: { icon: '✓', color: 'text-[var(--success)]' },
  regressed: { icon: '⊘', color: 'text-[var(--danger)]' },
  // Legacy states (for backward compat)
  open: { icon: '○', color: 'text-[var(--info)]' },
  monitoring: { icon: '◉', color: 'text-purple-400' },
  awaiting: { icon: '◷', color: 'text-amber-400' },
  blocked: { icon: '⊘', color: 'text-[var(--danger)]' },
  resolved: { icon: '✓', color: 'text-[var(--success)]' },
};

// Convert v29 severity to legacy priority number
const severityToPriority = (severity: string | undefined): number => {
  switch (severity) {
    case 'critical':
      return 90;
    case 'high':
      return 70;
    case 'medium':
      return 50;
    case 'low':
      return 30;
    case 'info':
      return 10;
    default:
      return 50;
  }
};

// Get issue title (v29: title, legacy: headline)
const getIssueTitle = (issue: Issue): string => issue.title || issue.headline || '';

// Get issue ID (v29: id, legacy: issue_id)
const getIssueId = (issue: Issue): string => issue.id || issue.issue_id || '';

// Get issue priority (v29: severity→number, legacy: priority)
const getIssuePriority = (issue: Issue): number =>
  issue.priority ?? severityToPriority(issue.severity);

// Get last activity (v29: updated_at, legacy: last_activity_at)
const getIssueLastActivity = (issue: Issue): string =>
  issue.updated_at || issue.last_activity_at || '';

// Get issue type (v29: type, legacy: issue_type)
const getIssueType = (issue: Issue): string =>
  issue.type || (issue as unknown as { issue_type?: string }).issue_type || '';

interface IssuesSearch {
  state?: string;
  priority?: string;
  q?: string;
  view?: 'flat' | 'hierarchy';
  client_id?: string;
}

// Hierarchy node types
interface HierarchyNode {
  id: string;
  name: string;
  type: 'client' | 'project' | 'task';
  tier?: string;
  issues: Issue[];
  children: HierarchyNode[];
  totalIssues: number;
  maxPriority: number;
}

export function Issues() {
  const navigate = useNavigate();
  const searchParams = useSearch({ from: '/issues' }) as IssuesSearch;

  // Initialize from URL or defaults
  const [stateFilter, setStateFilter] = useState<string>(searchParams.state || 'all');
  const [priorityFilter, setPriorityFilter] = useState<number | 'all'>(
    searchParams.priority ? parseInt(searchParams.priority, 10) : 'all'
  );
  const [search, setSearch] = useState(searchParams.q || '');
  const [viewMode, setViewMode] = useState<'flat' | 'hierarchy'>(searchParams.view || 'flat');
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // Sync filters to URL
  useEffect(() => {
    const params: Record<string, string> = {};
    if (stateFilter !== 'all') params.state = stateFilter;
    if (priorityFilter !== 'all') params.priority = String(priorityFilter);
    if (search) params.q = search;
    if (viewMode !== 'flat') params.view = viewMode;
    if (searchParams.client_id) params.client_id = searchParams.client_id;

    navigate({
      to: '/issues',
      search: Object.keys(params).length > 0 ? params : undefined,
      replace: true,
    });
  }, [stateFilter, priorityFilter, search, viewMode, navigate, searchParams.client_id]);

  const {
    data: apiIssues,
    loading,
    error,
    refetch: refetchIssues,
  } = useIssues(100, 30, searchParams.client_id, undefined);

  const handleResolveIssue = async (issue: Issue) => {
    const result = await api.resolveIssue(getIssueId(issue));
    if (result.success) {
      refetchIssues();
    } else {
      throw new Error(result.error || 'Failed to resolve');
    }
  };

  const handleAddIssueNote = async (issue: Issue, text: string) => {
    const result = await api.addIssueNote(getIssueId(issue), text);
    if (!result.success) {
      throw new Error(result.error || 'Failed to add note');
    }
  };

  const handleChangeIssueState = async (issue: Issue, newState: IssueState) => {
    const result = await api.changeIssueState(getIssueId(issue), newState);
    if (result.success) {
      refetchIssues();
    } else {
      throw new Error(result.error || 'Failed to change state');
    }
  };

  // Debounce search for performance
  const debouncedSearch = useDebounce(search, 300);

  // Memoize filtered list
  const allIssues = apiIssues?.items || [];
  const filteredIssues = useMemo(() => {
    const issues = apiIssues?.items || [];
    return issues
      .filter(
        (i: Issue) =>
          debouncedSearch === '' ||
          getIssueTitle(i).toLowerCase().includes(debouncedSearch.toLowerCase())
      )
      .filter((i: Issue) => stateFilter === 'all' || i.state === stateFilter)
      .filter((i: Issue) => {
        if (priorityFilter === 'all') return true;
        return matchesPriorityFilter(getIssuePriority(i), priorityFilter);
      })
      .sort((a: Issue, b: Issue) => {
        const priorityDiff = getIssuePriority(b) - getIssuePriority(a);
        if (priorityDiff !== 0) return priorityDiff;
        return (
          new Date(getIssueLastActivity(b)).getTime() - new Date(getIssueLastActivity(a)).getTime()
        );
      });
  }, [apiIssues?.items, debouncedSearch, stateFilter, priorityFilter]);

  // Build hierarchy from issues
  const hierarchy = useMemo(() => {
    const clientMap = new Map<string, HierarchyNode>();

    for (const issue of filteredIssues) {
      // Extract hierarchy from title/headline or ref
      // Format: "ClientName > ProjectName: Issue" or "ClientName: Issue"
      const title = getIssueTitle(issue);
      const parts = title
        .split(':')[0]
        .split('>')
        .map((s) => s.trim());
      const clientName = parts[0] || 'Unknown Client';
      const projectName = parts[1] || null;

      // Get or create client node
      if (!clientMap.has(clientName)) {
        clientMap.set(clientName, {
          id: `client-${clientName}`,
          name: clientName,
          type: 'client',
          issues: [],
          children: [],
          totalIssues: 0,
          maxPriority: 0,
        });
      }
      const clientNode = clientMap.get(clientName)!;

      if (projectName) {
        // Find or create project node under client
        let projectNode = clientNode.children.find((c) => c.name === projectName);
        if (!projectNode) {
          projectNode = {
            id: `project-${clientName}-${projectName}`,
            name: projectName,
            type: 'project',
            issues: [],
            children: [],
            totalIssues: 0,
            maxPriority: 0,
          };
          clientNode.children.push(projectNode);
        }
        projectNode.issues.push(issue);
        projectNode.totalIssues++;
        projectNode.maxPriority = Math.max(projectNode.maxPriority, getIssuePriority(issue));
      } else {
        // Client-level issue
        clientNode.issues.push(issue);
      }

      clientNode.totalIssues++;
      clientNode.maxPriority = Math.max(clientNode.maxPriority, getIssuePriority(issue));
    }

    // Sort clients by max priority
    return Array.from(clientMap.values()).sort((a, b) => b.maxPriority - a.maxPriority);
  }, [filteredIssues]);

  const toggleNode = (nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  // Summary stats from all issues (unfiltered)
  const criticalCount = allIssues.filter(
    (i: Issue) => getIssuePriority(i) >= 80 || i.severity === 'critical'
  ).length;
  const highCount = allIssues.filter(
    (i: Issue) => (getIssuePriority(i) >= 60 && getIssuePriority(i) < 80) || i.severity === 'high'
  ).length;
  const openCount = allIssues.filter(
    (i: Issue) => i.state === 'open' || i.state === 'surfaced' || i.state === 'detected'
  ).length;
  const blockedCount = allIssues.filter(
    (i: Issue) => i.state === 'blocked' || i.state === 'addressing'
  ).length;

  if (loading) return <SkeletonCardList count={5} />;
  if (error)
    return (
      <div className="text-[var(--danger)] p-8 text-center">
        Error loading issues: {error.message}
      </div>
    );

  // Render a single issue row
  const renderIssueRow = (issue: Issue, indent: number = 0) => {
    const stateConfig = stateIcons[issue.state] || stateIcons.open;
    const priority = getIssuePriority(issue);
    const pLabel = priorityLabel(priority);
    const pColor = priorityBadgeClass(priority);
    const title = getIssueTitle(issue);

    return (
      <div
        key={getIssueId(issue)}
        onClick={() => {
          setSelectedIssue(issue);
          setDrawerOpen(true);
        }}
        className="bg-[var(--grey-dim)]/50 rounded border border-[var(--grey)]/50 p-3 cursor-pointer hover:border-[var(--grey-light)] transition-colors"
        style={{ marginLeft: indent * 16 }}
      >
        <div className="flex items-center gap-2">
          <span className={`text-sm ${stateConfig.color}`}>{stateConfig.icon}</span>
          <span className="flex-1 text-sm text-[var(--grey-light)] truncate">
            {title.split(':').slice(1).join(':').trim() || title}
          </span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${pColor}`}>{pLabel}</span>
        </div>
      </div>
    );
  };

  // Render hierarchy node
  const renderHierarchyNode = (node: HierarchyNode, depth: number = 0) => {
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = node.children.length > 0 || node.issues.length > 0;
    const priorityColor =
      node.maxPriority >= 80
        ? 'text-[var(--danger)]'
        : node.maxPriority >= 60
          ? 'text-[var(--warning)]'
          : 'text-[var(--grey-light)]';

    return (
      <div key={node.id} className="mb-1">
        {/* Node header */}
        <div
          className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
            depth === 0
              ? 'bg-[var(--grey-dim)] hover:bg-[var(--grey)]'
              : 'bg-[var(--grey-dim)]/30 hover:bg-[var(--grey-dim)]/50'
          }`}
          style={{ marginLeft: depth * 16 }}
          onClick={() => hasChildren && toggleNode(node.id)}
        >
          {hasChildren && (
            <span className="text-[var(--grey)] w-4 text-center">{isExpanded ? '▼' : '▶'}</span>
          )}
          {!hasChildren && <span className="w-4" />}

          <span className="text-lg">
            {node.type === 'client' ? '🏢' : node.type === 'project' ? '📁' : '📋'}
          </span>

          <span
            className={`flex-1 font-medium ${depth === 0 ? 'text-[var(--white)]' : 'text-[var(--grey-light)]'}`}
          >
            {node.name}
          </span>

          {node.tier && (
            <span
              className={`px-1.5 py-0.5 text-xs rounded border ${
                node.tier === 'A'
                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                  : node.tier === 'B'
                    ? 'bg-[var(--info)]/20 text-[var(--info)] border-blue-500/30'
                    : 'bg-[var(--grey-muted)]/20 text-[var(--grey-light)] border-[var(--grey-muted)]/30'
              }`}
            >
              {node.tier}
            </span>
          )}

          <span className={`text-sm ${priorityColor}`}>
            {node.totalIssues} issue{node.totalIssues !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Children */}
        {isExpanded && (
          <div className="mt-1 space-y-1">
            {/* Render child nodes (projects) */}
            {node.children.map((child) => renderHierarchyNode(child, depth + 1))}

            {/* Render direct issues */}
            {node.issues.map((issue) => renderIssueRow(issue, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <PageLayout
      title="Issues Inbox"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {/* View toggle */}
          <div className="flex rounded overflow-hidden border border-[var(--grey)]">
            <button
              onClick={() => setViewMode('flat')}
              className={`px-3 py-1.5 text-xs ${viewMode === 'flat' ? 'bg-blue-600 text-[var(--white)]' : 'bg-[var(--grey-dim)] text-[var(--grey-light)] hover:bg-[var(--grey)]'}`}
            >
              Flat
            </button>
            <button
              onClick={() => setViewMode('hierarchy')}
              className={`px-3 py-1.5 text-xs ${viewMode === 'hierarchy' ? 'bg-blue-600 text-[var(--white)]' : 'bg-[var(--grey-dim)] text-[var(--grey-light)] hover:bg-[var(--grey)]'}`}
            >
              Hierarchy
            </button>
          </div>

          <input
            type="text"
            placeholder="Search issues..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-1.5 bg-[var(--grey-dim)] border border-[var(--grey)] rounded text-sm w-48"
          />
          <select
            className="px-2 py-1.5 bg-[var(--grey-dim)] border border-[var(--grey)] rounded text-sm"
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
          >
            <option value="all">All States</option>
            <option value="open">Open</option>
            <option value="monitoring">Monitoring</option>
            <option value="awaiting">Awaiting</option>
            <option value="blocked">Blocked</option>
          </select>
          <div className="flex gap-1">
            {[
              ['all', 'All'],
              [80, 'Critical'],
              [60, 'High'],
              [40, 'Medium'],
              [0, 'Low'],
            ].map(([value, label]) => (
              <button
                key={String(value)}
                onClick={() => setPriorityFilter(value as number | 'all')}
                className={`px-2 py-1 text-xs rounded ${priorityFilter === value ? 'bg-blue-600 text-[var(--white)]' : 'bg-[var(--grey)] text-[var(--grey-light)] hover:bg-[var(--grey-light)]'}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      }
    >
      <SummaryGrid>
        <MetricCard label="Total" value={allIssues.length} />
        <MetricCard
          label="Critical"
          value={criticalCount}
          severity={criticalCount > 0 ? 'danger' : undefined}
        />
        <MetricCard
          label="High"
          value={highCount}
          severity={highCount > 0 ? 'warning' : undefined}
        />
        <MetricCard label="Open" value={openCount} severity="info" />
        <MetricCard
          label="Blocked"
          value={blockedCount}
          severity={blockedCount > 0 ? 'warning' : undefined}
        />
      </SummaryGrid>

      {search || stateFilter !== 'all' || priorityFilter !== 'all' ? (
        <p className="text-sm text-[var(--grey)] mb-4">
          {filteredIssues.length} of {allIssues.length} issues
        </p>
      ) : null}

      {filteredIssues.length === 0 ? (
        <div className="bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)] p-8 text-center">
          <p className="text-[var(--grey-light)]">No issues match your filters</p>
        </div>
      ) : viewMode === 'hierarchy' ? (
        /* Hierarchy View */
        <div className="space-y-2">{hierarchy.map((node) => renderHierarchyNode(node))}</div>
      ) : (
        /* Flat View */
        <div className="space-y-3">
          {filteredIssues.map((issue: Issue) => {
            const stateConfig = stateIcons[issue.state] || stateIcons.open;
            const priority = getIssuePriority(issue);
            const pLabel = priorityLabel(priority);
            const pLabelCap = pLabel.charAt(0).toUpperCase() + pLabel.slice(1);
            const pColor = priorityBadgeClass(priority);
            const title = getIssueTitle(issue);
            const issueType = getIssueType(issue);
            const lastActivity = getIssueLastActivity(issue);

            return (
              <div
                key={getIssueId(issue)}
                onClick={() => {
                  setSelectedIssue(issue);
                  setDrawerOpen(true);
                }}
                className="bg-[var(--grey-dim)] rounded-lg border border-[var(--grey)] p-4 cursor-pointer hover:border-[var(--grey-light)] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className={`text-xl ${stateConfig.color}`}>{stateConfig.icon}</span>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-[var(--white)] truncate">{title}</h3>
                    <div className="flex items-center gap-2 mt-1 text-xs text-[var(--grey)]">
                      <span>{issueType}</span>
                      <span>•</span>
                      <span>
                        {lastActivity ? new Date(lastActivity).toLocaleDateString() : 'N/A'}
                      </span>
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded ${pColor}`}>{pLabelCap}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <IssueDrawer
        issue={selectedIssue}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedIssue(null);
        }}
        onResolve={selectedIssue ? () => handleResolveIssue(selectedIssue) : undefined}
        onAddNote={selectedIssue ? (text) => handleAddIssueNote(selectedIssue, text) : undefined}
        onChangeState={
          selectedIssue ? (newState) => handleChangeIssueState(selectedIssue, newState) : undefined
        }
      />
    </PageLayout>
  );
}

export default Issues;
