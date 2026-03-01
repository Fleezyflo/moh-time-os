// NotificationList — renders notification items with type icons and dismiss action (Phase 10)
import type { Notification } from '../../lib/api';

const TYPE_ICONS: Record<string, string> = {
  delegation: '\u{1F4E4}',
  escalation: '\u{1F6A8}',
  escalation_notice: '\u{1F514}',
  delegation_approved: '\u2705',
  escalation_approved: '\u2705',
  reminder: '\u23F0',
  system: '\u2699\uFE0F',
};

function typeIcon(type: string): string {
  return TYPE_ICONS[type] ?? '\u{1F4AC}';
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

interface NotificationListProps {
  notifications: Notification[];
  onDismiss: (id: string) => void;
}

export function NotificationList({ notifications, onDismiss }: NotificationListProps) {
  if (notifications.length === 0) {
    return <div className="text-center py-8 text-[var(--grey-light)]">No notifications</div>;
  }

  return (
    <div className="space-y-2">
      {notifications.map((n) => (
        <div
          key={n.id}
          className="flex items-start gap-3 p-3 rounded-lg bg-[var(--grey-dim)] border border-[var(--grey)] hover:border-[var(--grey-light)] transition-colors"
        >
          <span className="text-lg flex-shrink-0 mt-0.5" aria-hidden="true">
            {typeIcon(n.type)}
          </span>
          <div className="flex-1 min-w-0">
            <div className="text-sm">{n.message}</div>
            <div className="flex items-center gap-3 mt-1 text-xs text-[var(--grey-light)]">
              <span className="capitalize">{n.type.replace(/_/g, ' ')}</span>
              <span>{formatRelativeTime(n.created_at)}</span>
            </div>
          </div>
          {!n.dismissed && (
            <button
              onClick={() => onDismiss(n.id)}
              className="text-xs px-2 py-1 rounded bg-[var(--grey)] hover:bg-[var(--grey-light)] transition-colors flex-shrink-0"
              aria-label={`Dismiss notification: ${n.message}`}
            >
              Dismiss
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
