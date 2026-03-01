// NotificationBadge — shows unread notification count in nav (Phase 10)
import { useNotificationStats } from '../../lib/hooks';

export function NotificationBadge() {
  const { data } = useNotificationStats();

  const unread = data?.unread ?? 0;
  if (unread === 0) return null;

  return (
    <span
      className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold rounded-full bg-[var(--danger)] text-white"
      aria-label={`${unread} unread notification${unread !== 1 ? 's' : ''}`}
    >
      {unread > 99 ? '99+' : unread}
    </span>
  );
}
