// EmptyState — consistent empty state display across the app

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

const defaultIcons: Record<string, string> = {
  proposals: '📋',
  issues: '✅',
  clients: '🏢',
  team: '👥',
  tasks: '📝',
  watchers: '👁️',
  couplings: '🔗',
  evidence: '📎',
  default: '📭',
};

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  const displayIcon = icon || defaultIcons.default;

  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <span className="text-4xl mb-4" role="img" aria-hidden="true">
        {displayIcon}
      </span>
      <h3 className="text-lg font-medium text-slate-300 mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-slate-500 max-w-sm mb-4">{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

// Preset empty states for common scenarios
export function NoProposals() {
  return (
    <EmptyState
      icon={defaultIcons.proposals}
      title="No proposals"
      description="All caught up! No action items require your attention right now."
    />
  );
}

export function NoIssues() {
  return (
    <EmptyState
      icon={defaultIcons.issues}
      title="No active issues"
      description="No issues are currently being tracked."
    />
  );
}

export function NoClients() {
  return (
    <EmptyState
      icon={defaultIcons.clients}
      title="No clients found"
      description="No clients match your current filters."
    />
  );
}

export function NoTeamMembers() {
  return (
    <EmptyState
      icon={defaultIcons.team}
      title="No team members"
      description="No team members found."
    />
  );
}

export function NoTasks() {
  return (
    <EmptyState
      icon={defaultIcons.tasks}
      title="No tasks"
      description="No tasks assigned or matching filters."
    />
  );
}

export function NoWatchers() {
  return (
    <EmptyState
      icon={defaultIcons.watchers}
      title="No watchers triggered"
      description="All watchers are quiet. Nothing needs attention."
    />
  );
}

export function NoCouplings() {
  return (
    <EmptyState
      icon={defaultIcons.couplings}
      title="No couplings found"
      description="Select an entity to view its relationships."
    />
  );
}

export function NoEvidence() {
  return (
    <EmptyState
      icon={defaultIcons.evidence}
      title="No evidence"
      description="No supporting evidence available for this item."
    />
  );
}

export function NoResults({ query }: { query?: string }) {
  return (
    <EmptyState
      icon="🔍"
      title="No results"
      description={query ? `No results found for "${query}"` : "No results match your search."}
    />
  );
}
