/**
 * Intelligence Skeleton Components
 *
 * PRECISE matches to actual component structures.
 * Same padding, same flex layouts, same dimensions.
 */

// =============================================================================
// BASE
// =============================================================================

function Bone({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-slate-700/50 rounded ${className}`} />;
}

// =============================================================================
// CARD SKELETONS — Match actual card components exactly
// =============================================================================

/**
 * Matches SignalCard (non-compact)
 * - Container: rounded-lg border p-4
 * - Badges row: SeverityBadge + entity_type
 * - Title line
 * - Entity name line
 * - Expand icon right
 */
export function SkeletonSignalCard() {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800">
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            {/* Badges row: SeverityBadge (px-2 py-0.5) + entity_type text */}
            <div className="flex items-center gap-2 mb-2">
              <Bone className="h-5 w-16 rounded" /> {/* SeverityBadge */}
              <Bone className="h-4 w-12" /> {/* entity_type */}
            </div>
            {/* Title: font-medium */}
            <Bone className="h-5 w-3/4" />
            {/* Entity name: text-sm mt-1 */}
            <Bone className="h-4 w-1/2 mt-1" />
          </div>
          {/* Expand icon */}
          <Bone className="h-3 w-3" />
        </div>
      </div>
    </div>
  );
}

/**
 * Matches ProposalCard (non-compact)
 * - Container: rounded-lg border p-4
 * - Badges row: #rank + UrgencyBadge + type
 * - Headline
 * - Entity type: name
 * - Right: score + expand
 */
export function SkeletonProposalCard() {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800">
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            {/* Badges row: #rank + UrgencyBadge + type */}
            <div className="flex items-center gap-2 mb-2">
              <Bone className="h-4 w-6" /> {/* #rank */}
              <Bone className="h-5 w-20 rounded" /> {/* UrgencyBadge */}
              <Bone className="h-4 w-16" /> {/* type */}
            </div>
            {/* Headline: font-medium */}
            <Bone className="h-5 w-4/5" />
            {/* Entity: text-sm mt-1 */}
            <Bone className="h-4 w-2/5 mt-1" />
          </div>
          {/* Right side */}
          <div className="text-right">
            <Bone className="h-6 w-8 mb-1" /> {/* Score: text-lg */}
            <Bone className="h-3 w-3 ml-auto" /> {/* Expand */}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Matches PatternCard (non-compact)
 * - Container: rounded-lg border p-4
 * - Badges row: PatternSeverityBadge + PatternTypeBadge
 * - Name
 * - Description (can wrap)
 */
export function SkeletonPatternCard() {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800">
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            {/* Badges row */}
            <div className="flex items-center gap-2 mb-2">
              <Bone className="h-5 w-20 rounded" /> {/* PatternSeverityBadge */}
              <Bone className="h-5 w-24 rounded" /> {/* PatternTypeBadge */}
            </div>
            {/* Name: font-medium */}
            <Bone className="h-5 w-2/3" />
            {/* Description: text-sm mt-1, can be 2 lines */}
            <Bone className="h-4 w-full mt-1" />
            <Bone className="h-4 w-3/4 mt-1" />
          </div>
          <Bone className="h-3 w-3" />
        </div>
      </div>
    </div>
  );
}

/**
 * Matches HealthScore (lg size)
 * - Container: bg-*-500/10 rounded-lg p-6 text-center
 * - Score: text-5xl font-bold
 * - Label: text-slate-400 mt-2
 */
export function SkeletonHealthScore() {
  return (
    <div className="bg-slate-800 rounded-lg p-6 text-center">
      <Bone className="h-12 w-16 mx-auto" /> {/* text-5xl score */}
      <Bone className="h-4 w-28 mx-auto mt-2" /> {/* label */}
    </div>
  );
}

/**
 * Matches CountBadge row (3 badges)
 * - px-3 py-1 rounded-full text-sm border
 */
export function SkeletonCountBadges() {
  return (
    <div className="flex flex-wrap gap-2">
      <Bone className="h-7 w-24 rounded-full" />
      <Bone className="h-7 w-24 rounded-full" />
      <Bone className="h-7 w-20 rounded-full" />
    </div>
  );
}

// =============================================================================
// SECTION SKELETONS
// =============================================================================

/**
 * Section header with title and optional link
 */
export function SkeletonSectionHeader({ width = 'w-32' }: { width?: string }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <Bone className={`h-6 ${width}`} />
      <Bone className="h-4 w-16" />
    </div>
  );
}

/**
 * Filter bar matching Signals/Proposals filters
 */
export function SkeletonFilterBar() {
  return (
    <div className="flex flex-wrap gap-4 bg-slate-800 rounded-lg p-4">
      <div>
        <Bone className="h-4 w-14 mb-1" /> {/* label */}
        <Bone className="h-9 w-28 rounded" /> {/* select */}
      </div>
      <div>
        <Bone className="h-4 w-20 mb-1" />
        <Bone className="h-9 w-28 rounded" />
      </div>
      <div className="flex items-end">
        <Bone className="h-4 w-28" /> {/* showing X of Y */}
      </div>
    </div>
  );
}

/**
 * Critical/Attention alert card (simpler than full proposal)
 */
export function SkeletonAlertCard() {
  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
      <Bone className="h-5 w-3/4 mb-2" /> {/* headline */}
      <Bone className="h-4 w-1/2 mb-2" /> {/* entity */}
      <Bone className="h-4 w-2/3" /> {/* action */}
    </div>
  );
}

// =============================================================================
// PAGE SKELETONS — Compose from above
// =============================================================================

/**
 * Command Center full page
 */
export function SkeletonCommandCenter() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Bone className="h-8 w-44" /> {/* "Command Center" */}
        <div className="flex gap-2">
          <Bone className="h-8 w-24 rounded" />
          <Bone className="h-8 w-28 rounded" />
        </div>
      </div>

      {/* Portfolio Health + Signal Summary row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SkeletonHealthScore />
        <div className="md:col-span-3 bg-slate-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <Bone className="h-4 w-28" /> {/* "Signal Summary" */}
            <Bone className="h-3 w-16" /> {/* "View all →" */}
          </div>
          <SkeletonCountBadges />
          <Bone className="h-3 w-40 mt-3" /> {/* "X active signals • Y new" */}
        </div>
      </div>

      {/* Critical section */}
      <div>
        <SkeletonSectionHeader width="w-28" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SkeletonAlertCard />
          <SkeletonAlertCard />
        </div>
      </div>

      {/* Attention section */}
      <div>
        <SkeletonSectionHeader width="w-40" />
        <div className="space-y-3">
          <SkeletonProposalCard />
          <SkeletonProposalCard />
        </div>
      </div>
    </div>
  );
}

/**
 * Signals page
 */
export function SkeletonSignalsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Bone className="h-8 w-36" /> {/* "Active Signals" */}
        <Bone className="h-4 w-16" /> {/* "X total" */}
      </div>

      <SkeletonFilterBar />

      <div className="space-y-4">
        <SkeletonSignalCard />
        <SkeletonSignalCard />
        <SkeletonSignalCard />
      </div>
    </div>
  );
}

/**
 * Patterns page
 */
export function SkeletonPatternsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Bone className="h-8 w-44" /> {/* "Detected Patterns" */}
        <Bone className="h-4 w-20" /> {/* "X detected" */}
      </div>

      {/* Structural section */}
      <div>
        <Bone className="h-6 w-28 mb-3" /> {/* "Structural (X)" */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SkeletonPatternCard />
          <SkeletonPatternCard />
        </div>
      </div>
    </div>
  );
}

/**
 * Proposals page
 */
export function SkeletonProposalsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Bone className="h-8 w-28" /> {/* "Proposals" */}
        <Bone className="h-4 w-24" /> {/* "X proposals" */}
      </div>

      <SkeletonFilterBar />

      <div className="space-y-4">
        <SkeletonProposalCard />
        <SkeletonProposalCard />
        <SkeletonProposalCard />
      </div>
    </div>
  );
}

/**
 * Briefing page
 */
export function SkeletonBriefingPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div>
        <Bone className="h-8 w-36 mb-2" /> {/* "Daily Briefing" */}
        <Bone className="h-4 w-52" /> {/* "Generated at..." */}
      </div>

      {/* Summary card */}
      <div className="bg-slate-800 rounded-lg p-6">
        <Bone className="h-5 w-full" />
      </div>

      {/* Top Priority */}
      <div className="bg-slate-800 border-l-4 border-slate-600 rounded-lg p-6">
        <Bone className="h-3 w-20 mb-2" /> {/* "Top Priority" */}
        <Bone className="h-5 w-3/4" />
      </div>

      {/* Critical section */}
      <div>
        <Bone className="h-6 w-24 mb-3" /> {/* "🚨 Critical (X)" */}
        <div className="space-y-3">
          <SkeletonAlertCard />
        </div>
      </div>

      {/* Attention section */}
      <div>
        <Bone className="h-6 w-40 mb-3" /> {/* "⚠️ Needs Attention (X)" */}
        <div className="space-y-3">
          <SkeletonAlertCard />
        </div>
      </div>

      {/* Portfolio Health */}
      <div className="bg-slate-800 rounded-lg p-6">
        <Bone className="h-3 w-28 mb-3" /> {/* "Portfolio Health" */}
        <div className="flex items-center gap-4">
          <Bone className="h-10 w-12" /> {/* score */}
          <div className="space-y-2">
            <Bone className="h-4 w-44" />
            <Bone className="h-3 w-24" />
          </div>
        </div>
      </div>
    </div>
  );
}
