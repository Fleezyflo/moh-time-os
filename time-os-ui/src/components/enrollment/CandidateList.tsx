// CandidateList — renders project candidates with enroll/reject/snooze actions (Phase 12)
import type { ProjectCandidate } from '../../lib/api';

interface CandidateListProps {
  candidates: ProjectCandidate[];
  onEnroll: (projectId: string) => void;
  onReject: (projectId: string) => void;
  onSnooze: (projectId: string) => void;
}

const STATUS_DOT: Record<string, string> = {
  candidate: 'bg-yellow-400',
  proposed: 'bg-blue-400',
};

export function CandidateList({ candidates, onEnroll, onReject, onSnooze }: CandidateListProps) {
  if (candidates.length === 0) {
    return (
      <div className="text-center py-8 text-[var(--grey-muted)]">
        No project candidates found. All projects are enrolled or detected projects have been
        processed.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {candidates.map((c) => (
        <div key={c.id} className="card p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${STATUS_DOT[c.enrollment_status] || 'bg-[var(--grey-muted)]'}`}
            />
            <div className="min-w-0">
              <div className="font-medium truncate">{c.name}</div>
              <div className="text-xs text-[var(--grey-light)] flex gap-2 mt-0.5">
                {c.client_name && <span>{c.client_name}</span>}
                <span className="capitalize">{c.enrollment_status}</span>
                {c.involvement_type && <span className="capitalize">{c.involvement_type}</span>}
              </div>
            </div>
          </div>

          <div className="flex gap-2 shrink-0">
            <button
              onClick={() => onEnroll(c.id)}
              className="px-3 py-1.5 text-xs font-medium rounded bg-green-600 hover:bg-green-500 text-white transition-colors"
              aria-label={`Enroll ${c.name}`}
            >
              Enroll
            </button>
            <button
              onClick={() => onSnooze(c.id)}
              className="px-3 py-1.5 text-xs font-medium rounded bg-[var(--grey)] hover:bg-[var(--grey-mid)] text-[var(--white)] transition-colors"
              aria-label={`Snooze ${c.name}`}
            >
              Snooze
            </button>
            <button
              onClick={() => onReject(c.id)}
              className="px-3 py-1.5 text-xs font-medium rounded bg-red-600/20 hover:bg-red-600/40 text-red-400 transition-colors"
              aria-label={`Reject ${c.name}`}
            >
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

export default CandidateList;
