// Loading skeleton components for consistent loading states

interface SkeletonProps {
  className?: string;
}

// Base skeleton with animation
function SkeletonBase({ className = '' }: SkeletonProps) {
  return <div className={`animate-pulse bg-slate-700/50 rounded ${className}`} />;
}

// Single row skeleton (for issues, watchers, etc.)
export function SkeletonRow({ className = '' }: SkeletonProps) {
  return (
    <div className={`flex items-center gap-3 p-4 ${className}`}>
      <SkeletonBase className="w-6 h-6 rounded-full flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <SkeletonBase className="h-4 w-3/4" />
        <SkeletonBase className="h-3 w-1/2" />
      </div>
      <SkeletonBase className="w-16 h-6 rounded" />
    </div>
  );
}

// Card skeleton (for proposals, clients, team members)
export function SkeletonCard({ className = '' }: SkeletonProps) {
  return (
    <div className={`bg-slate-800 rounded-lg border border-slate-700 p-4 ${className}`}>
      <div className="flex items-start justify-between mb-3">
        <SkeletonBase className="h-5 w-2/3" />
        <SkeletonBase className="h-5 w-12 rounded" />
      </div>
      <div className="space-y-2">
        <SkeletonBase className="h-4 w-full" />
        <SkeletonBase className="h-4 w-4/5" />
      </div>
      <div className="flex gap-2 mt-4">
        <SkeletonBase className="h-8 w-20 rounded" />
        <SkeletonBase className="h-8 w-20 rounded" />
      </div>
    </div>
  );
}

// Panel skeleton (for sidebar sections)
export function SkeletonPanel({ rows = 3, className = '' }: SkeletonProps & { rows?: number }) {
  return (
    <div className={`bg-slate-800/50 rounded-lg border border-slate-700 p-4 ${className}`}>
      <SkeletonBase className="h-4 w-24 mb-3" />
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-2">
            <SkeletonBase className="w-4 h-4 rounded-full flex-shrink-0" />
            <SkeletonBase className="h-3 flex-1" />
          </div>
        ))}
      </div>
    </div>
  );
}

// List of cards skeleton
export function SkeletonCardList({
  count = 3,
  className = '',
}: SkeletonProps & { count?: number }) {
  return (
    <div className={`space-y-4 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

// Grid of cards skeleton (for portfolio pages)
export function SkeletonCardGrid({
  count = 6,
  className = '',
}: SkeletonProps & { count?: number }) {
  return (
    <div className={`grid gap-4 sm:grid-cols-2 lg:grid-cols-3 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
