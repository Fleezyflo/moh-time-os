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
      <h3 className="text-lg font-medium text-[var(--grey-subtle)] mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-[var(--grey-muted)] max-w-sm mb-4">{description}</p>
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
      description={query ? `No results found for "${query}"` : 'No results match your search.'}
    />
  );
}

// === Intelligence-specific empty states ===

export function NoSignals({ filtered }: { filtered?: boolean } = {}) {
  return (
    <EmptyState
      icon="📡"
      title={filtered ? 'No signals match filters' : 'No active signals'}
      description={
        filtered
          ? 'Try adjusting your filter criteria.'
          : 'All systems are operating normally. No signals require attention.'
      }
    />
  );
}

export function NoPatterns() {
  return (
    <EmptyState
      icon="🔗"
      title="No patterns detected"
      description="Select an entity to view relationship patterns."
    />
  );
}

export function NoBriefing() {
  return (
    <EmptyState
      icon="📋"
      title="No briefing available"
      description="The daily briefing will be generated once intelligence data is processed."
    />
  );
}

export function NoIntelData({ entityType }: { entityType?: string } = {}) {
  return (
    <EmptyState
      icon="📊"
      title="No data available"
      description={
        entityType
          ? `No intelligence data found for this ${entityType}.`
          : 'Intelligence data is not available at this time.'
      }
    />
  );
}

// === Positive/Success empty states (green variant) ===

interface SuccessStateProps {
  icon?: string;
  title: string;
  description?: string;
}

export function SuccessState({ icon = '✓', title, description }: SuccessStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-8 px-4 text-center bg-green-500/10 border border-green-500/30 rounded-lg">
      <span className="text-3xl mb-3 text-green-400" role="img" aria-hidden="true">
        {icon}
      </span>
      <h3 className="text-lg font-medium text-green-400 mb-1">{title}</h3>
      {description && <p className="text-sm text-[var(--grey-light)] max-w-sm">{description}</p>}
    </div>
  );
}

export function AllClear() {
  return (
    <SuccessState
      title="All Clear"
      description="No critical items, structural patterns, or attention items require action."
    />
  );
}

export function NoPatternsDetected() {
  return (
    <SuccessState
      title="No patterns detected"
      description="Portfolio structure looks healthy. No concerning patterns found."
    />
  );
}

export function NoActiveSignals() {
  return (
    <SuccessState
      icon="📡"
      title="No active signals"
      description="All systems operating normally."
    />
  );
}
