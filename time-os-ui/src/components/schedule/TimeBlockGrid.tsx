// TimeBlockGrid — renders a day's time blocks organized by lane
import { useMemo } from 'react';
import type { TimeBlock } from '../../lib/api';

interface TimeBlockGridProps {
  blocks: TimeBlock[];
  onBlockClick?: (block: TimeBlock) => void;
}

function laneColor(lane: string): string {
  const colors: Record<string, string> = {
    focus: 'var(--accent)',
    meetings: 'rgb(168 85 247)',
    admin: 'rgb(245 158 11)',
    buffer: 'var(--grey-light)',
  };
  return colors[lane.toLowerCase()] || 'var(--grey-muted)';
}

function formatTime(time: string): string {
  if (!time) return '';
  // Handle HH:MM or HH:MM:SS format
  const parts = time.split(':');
  const hour = parseInt(parts[0], 10);
  const minute = parts[1] || '00';
  const ampm = hour >= 12 ? 'PM' : 'AM';
  const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
  return `${displayHour}:${minute} ${ampm}`;
}

export function TimeBlockGrid({ blocks, onBlockClick }: TimeBlockGridProps) {
  const lanes = useMemo(() => {
    const laneMap = new Map<string, TimeBlock[]>();
    for (const block of blocks) {
      const lane = block.lane || 'default';
      const existing = laneMap.get(lane) ?? [];
      existing.push(block);
      laneMap.set(lane, existing);
    }
    return laneMap;
  }, [blocks]);

  if (blocks.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-[var(--grey-muted)]">
        No time blocks for this date
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {Array.from(lanes.entries()).map(([lane, laneBlocks]) => (
        <div key={lane}>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: laneColor(lane) }} />
            <span className="text-sm font-medium capitalize">{lane}</span>
            <span className="text-xs text-[var(--grey-light)]">
              {laneBlocks.length} block{laneBlocks.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="space-y-1">
            {laneBlocks.map((block) => (
              <button
                key={block.id}
                onClick={() => onBlockClick?.(block)}
                className="w-full text-left p-3 rounded-lg border transition-colors hover:border-[var(--accent)]"
                style={{
                  borderColor: block.is_available ? 'var(--grey)' : laneColor(lane),
                  backgroundColor: block.is_available
                    ? 'transparent'
                    : `color-mix(in srgb, ${laneColor(lane)} 10%, transparent)`,
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[var(--grey-light)]">
                      {formatTime(block.start_time)} &ndash; {formatTime(block.end_time)}
                    </span>
                    <span className="text-xs text-[var(--grey-muted)]">{block.duration_min}m</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {block.is_protected && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--grey)] text-[var(--grey-light)]">
                        Protected
                      </span>
                    )}
                    {block.is_buffer && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--grey)] text-[var(--grey-light)]">
                        Buffer
                      </span>
                    )}
                  </div>
                </div>
                {block.task_title && (
                  <div className="mt-1 text-sm">
                    {block.task_title}
                    {block.task_status && (
                      <span className="ml-2 text-xs text-[var(--grey-light)]">
                        ({block.task_status})
                      </span>
                    )}
                  </div>
                )}
                {block.is_available && !block.task_id && (
                  <div className="mt-1 text-xs text-[var(--grey-muted)] italic">Available</div>
                )}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
