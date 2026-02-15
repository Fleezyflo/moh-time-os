/**
 * Intelligence Shared Components
 */

// Score display
export { HealthScore } from './HealthScore';
export { Scorecard } from './Scorecard';

// Badges
export {
  SeverityBadge,
  UrgencyBadge,
  PatternTypeBadge,
  PatternSeverityBadge,
  CategoryBadge,
  CountBadge,
} from './Badges';

// Entity references
export { EntityLink, EntityBadge, EntityList } from './EntityLink';

// Evidence
export { EvidenceList } from './EvidenceList';

// Cards
export { SignalCard } from './SignalCard';
export { PatternCard } from './PatternCard';
export { ProposalCard } from './ProposalCard';

// Profile components
export { ProfileHeader } from './ProfileHeader';
export { ProfileSection } from './ProfileSection';
export { ConnectedEntities } from './ConnectedEntities';
export { ProfileShell } from './ProfileShell';

// Chart components
export { Sparkline } from './Sparkline';
export { DimensionBar } from './DimensionBar';
export { BreakdownChart } from './BreakdownChart';
export { ActivityHeatmap } from './ActivityHeatmap';
export { DistributionChart } from './DistributionChart';
export { CommunicationChart } from './CommunicationChart';

// Skeleton components
export {
  SkeletonCommandCenter,
  SkeletonSignalsPage,
  SkeletonPatternsPage,
  SkeletonProposalsPage,
  SkeletonBriefingPage,
  SkeletonSignalCard,
  SkeletonPatternCard,
  SkeletonProposalCard,
  SkeletonAlertCard,
  SkeletonHealthScore,
  SkeletonCountBadges,
  SkeletonFilterBar,
  SkeletonSectionHeader,
} from './Skeletons';
