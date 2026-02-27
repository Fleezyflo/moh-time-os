/**
 * CommunicationChart — Composite display for communication pattern data
 */

import { DistributionChart } from './DistributionChart';

interface Participant {
  person_id?: number | string;
  name: string;
  volume: number;
}

interface CommunicationData {
  by_channel?: { email?: number; chat?: number; meeting?: number };
  direction_balance?: number;
  total_sent?: number;
  total_received?: number;
  participants?: Participant[];
}

interface CommunicationChartProps {
  data: CommunicationData;
}

export function CommunicationChart({ data = {} }: CommunicationChartProps) {
  const byChannel = data.by_channel || {};
  const channelSegments = [
    { label: 'Email', value: byChannel.email || 0, color: 'rgb(59 130 246)' },
    { label: 'Chat', value: byChannel.chat || 0, color: 'rgb(16 185 129)' },
    { label: 'Meetings', value: byChannel.meeting || 0, color: 'rgb(168 85 247)' },
  ].filter((s) => s.value > 0);

  const totalSent = data.total_sent || 0;
  const totalReceived = data.total_received || 0;
  const totalComm = totalSent + totalReceived;
  const sentPct = totalComm > 0 ? (totalSent / totalComm) * 100 : 50;

  const balance = data.direction_balance || 1.0;
  const isImbalanced = balance < 0.5 || balance > 1.5;

  const participants = data.participants || [];
  const topParticipants = participants.slice(0, 5);
  const maxParticipantVolume = Math.max(1, ...topParticipants.map((p) => p.volume));

  return (
    <div className="flex flex-col gap-5">
      {/* Channel distribution */}
      {channelSegments.length > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-[var(--grey-light)] uppercase tracking-wide mb-2">
            By Channel
          </h5>
          <DistributionChart segments={channelSegments} height={28} />
        </div>
      )}

      {/* Direction balance */}
      {totalComm > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-[var(--grey-light)] uppercase tracking-wide mb-2">
            Direction Balance
            {isImbalanced && (
              <span className="text-amber-400 normal-case tracking-normal"> — Imbalanced</span>
            )}
          </h5>
          <div className="flex h-7 rounded overflow-hidden">
            <div
              className="bg-blue-500 flex items-center justify-center"
              style={{ width: `${Math.max(20, sentPct)}%` }}
            >
              <span className="text-[10px] text-white font-medium whitespace-nowrap">
                Sent ({totalSent})
              </span>
            </div>
            <div
              className="bg-purple-500 flex items-center justify-center"
              style={{ width: `${Math.max(20, 100 - sentPct)}%` }}
            >
              <span className="text-[10px] text-white font-medium whitespace-nowrap">
                Received ({totalReceived})
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Top participants */}
      {topParticipants.length > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-[var(--grey-light)] uppercase tracking-wide mb-2">
            Top Participants
          </h5>
          <div className="flex flex-col gap-2">
            {topParticipants.map((p) => (
              <div
                key={p.person_id || p.name}
                className="grid grid-cols-[120px_1fr_40px] gap-2 items-center"
              >
                <span className="text-sm text-[var(--grey-light)] truncate">{p.name}</span>
                <div className="h-1.5 bg-[var(--grey)]/50 rounded-full">
                  <div
                    className="h-full bg-purple-500 rounded-full transition-all"
                    style={{ width: `${(p.volume / maxParticipantVolume) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-[var(--grey-muted)] text-right">{p.volume}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
