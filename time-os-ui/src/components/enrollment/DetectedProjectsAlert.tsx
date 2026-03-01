// DetectedProjectsAlert — banner showing auto-detected projects from tasks (Phase 12)
import type { DetectedProject } from '../../lib/api';

interface DetectedProjectsAlertProps {
  detected: DetectedProject[];
  onDismiss: () => void;
}

export function DetectedProjectsAlert({ detected, onDismiss }: DetectedProjectsAlertProps) {
  if (detected.length === 0) return null;

  return (
    <div className="card p-4 border-l-4 border-l-yellow-400 bg-yellow-400/5 mb-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-medium text-yellow-300 mb-1">
            {detected.length} new project{detected.length !== 1 ? 's' : ''} detected
          </div>
          <p className="text-sm text-[var(--grey-light)] mb-3">
            These project names appear in tasks but haven&apos;t been enrolled yet. Review and
            enroll them to track work properly.
          </p>
          <div className="flex flex-wrap gap-2">
            {detected.slice(0, 8).map((p) => (
              <span
                key={p.name}
                className="px-2 py-1 text-xs rounded bg-yellow-400/10 text-yellow-300 border border-yellow-400/20"
              >
                {p.name}
                <span className="ml-1 text-yellow-400/60">
                  ({p.task_count} task{p.task_count !== 1 ? 's' : ''})
                </span>
              </span>
            ))}
            {detected.length > 8 && (
              <span className="px-2 py-1 text-xs text-[var(--grey-muted)]">
                +{detected.length - 8} more
              </span>
            )}
          </div>
        </div>
        <button
          onClick={onDismiss}
          className="text-[var(--grey-muted)] hover:text-[var(--white)] transition-colors p-1"
          aria-label="Dismiss detected projects alert"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default DetectedProjectsAlert;
