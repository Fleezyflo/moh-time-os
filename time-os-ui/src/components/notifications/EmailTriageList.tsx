// EmailTriageList — renders email items with actionable/dismiss actions (Phase 10)
import type { EmailItem } from '../../lib/api';

function formatDate(iso: string | null): string {
  if (!iso) return '';
  return iso.slice(0, 10);
}

interface EmailTriageListProps {
  emails: EmailItem[];
  onMarkActionable: (id: string) => void;
  onDismiss: (id: string) => void;
}

export function EmailTriageList({ emails, onMarkActionable, onDismiss }: EmailTriageListProps) {
  if (emails.length === 0) {
    return <div className="text-center py-8 text-[var(--grey-light)]">No emails to triage</div>;
  }

  return (
    <div className="space-y-2">
      {emails.map((email) => (
        <div
          key={email.id}
          className="flex items-start gap-3 p-3 rounded-lg bg-[var(--grey-dim)] border border-[var(--grey)] hover:border-[var(--grey-light)] transition-colors"
        >
          {/* Status indicator */}
          <span className="flex-shrink-0 mt-1.5">
            {email.actionable ? (
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ backgroundColor: 'var(--warning)' }}
                title="Actionable"
              />
            ) : (
              <span
                className="inline-block w-2 h-2 rounded-full bg-[var(--grey)]"
                title="Unprocessed"
              />
            )}
          </span>

          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{email.subject ?? '(no subject)'}</div>
            <div className="flex items-center gap-3 mt-1 text-xs text-[var(--grey-light)]">
              {email.sender && <span>From: {email.sender}</span>}
              {email.received_at && <span>{formatDate(email.received_at)}</span>}
            </div>
            {email.body && (
              <div className="text-xs text-[var(--grey-muted)] mt-1 line-clamp-2">
                {email.body.slice(0, 200)}
              </div>
            )}
          </div>

          <div className="flex gap-1 flex-shrink-0">
            {!email.actionable && (
              <button
                onClick={() => onMarkActionable(email.id)}
                className="text-xs px-2 py-1 rounded bg-[var(--accent)]/20 text-[var(--accent)] hover:bg-[var(--accent)]/30 transition-colors"
                aria-label={`Mark actionable: ${email.subject ?? 'email'}`}
              >
                Actionable
              </button>
            )}
            {!email.processed && (
              <button
                onClick={() => onDismiss(email.id)}
                className="text-xs px-2 py-1 rounded bg-[var(--grey)] hover:bg-[var(--grey-light)] transition-colors"
                aria-label={`Dismiss: ${email.subject ?? 'email'}`}
              >
                Dismiss
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
