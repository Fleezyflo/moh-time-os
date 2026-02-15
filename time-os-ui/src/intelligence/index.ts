/**
 * Intelligence Layer UI Module
 *
 * Exports API client, hooks, and components for intelligence views.
 */

// API Client (types and fetch functions)
export * from './api';

// Hooks
export * from './hooks';

// Components (rename Scorecard component to ScorecardCard to avoid conflict with Scorecard type from api)
export {
  HealthScore,
  Scorecard as ScorecardCard,
  SeverityBadge,
  UrgencyBadge,
  PatternTypeBadge,
  PatternSeverityBadge,
  CategoryBadge,
  CountBadge,
  EntityLink,
  EntityBadge,
  EntityList,
  EvidenceList,
  SignalCard,
  PatternCard,
  ProposalCard,
  // Profile components
  ProfileHeader,
  ProfileSection,
  ConnectedEntities,
  ProfileShell,
  // Chart components
  Sparkline,
  DimensionBar,
  BreakdownChart,
  ActivityHeatmap,
  DistributionChart,
  CommunicationChart,
} from './components';
