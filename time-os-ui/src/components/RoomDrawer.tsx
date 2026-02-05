// RoomDrawer — Universal detail drawer for proposals, issues, and entities
import { ConfidenceBadge } from './ConfidenceBadge';
import type { Proposal } from '../fixtures';
import { checkEligibility } from '../fixtures';

interface RoomDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  entity: {
    type: 'proposal' | 'issue' | 'client' | 'team_member';
    id: string;
    headline: string;
    coverage_summary?: string;
  };
  proposal?: Proposal;
  onTag?: () => void;
  onSnooze?: () => void;
  onDismiss?: () => void;
  onFixData?: () => void;
  children?: React.ReactNode;
}

export function RoomDrawer({ isOpen, onClose, entity, proposal, onTag, onSnooze, onDismiss, onFixData, children }: RoomDrawerProps) {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40 lg:bg-black/30"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[400px] bg-slate-900 border-l border-slate-700 shadow-drawer overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-slate-900/95 backdrop-blur border-b border-slate-700 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">
                {entity.type.replace('_', ' ')}
              </p>
              <h2 className="text-lg font-semibold text-slate-100 leading-tight">
                {entity.headline}
              </h2>
              {entity.coverage_summary && (
                <p className="text-sm text-slate-400 mt-1">
                  Coverage: {entity.coverage_summary}
                </p>
              )}
            </div>
            <button 
              onClick={onClose}
              className="p-2 hover:bg-slate-800 rounded transition-colors text-slate-400 hover:text-slate-200"
              aria-label="Close drawer"
            >
              ✕
            </button>
          </div>
        </div>
        
        {/* Content */}
        <div className="p-4">
          {proposal ? (
            <ProposalDrawerContent 
              proposal={proposal} 
              onTag={onTag}
              onSnooze={onSnooze}
              onDismiss={onDismiss}
              onFixData={onFixData}
            />
          ) : (
            children
          )}
        </div>
      </div>
    </>
  );
}

interface ProposalDrawerContentProps {
  proposal: Proposal;
  onTag?: () => void;
  onSnooze?: () => void;
  onDismiss?: () => void;
  onFixData?: () => void;
}

function ProposalDrawerContent({ proposal, onTag, onSnooze, onDismiss, onFixData }: ProposalDrawerContentProps) {
  const { is_eligible, gate_violations } = checkEligibility(proposal);
  
  return (
    <div className="space-y-6">
      {/* Confidence badges */}
      <div className="flex items-center gap-2">
        <ConfidenceBadge type="linkage" value={proposal.linkage_confidence} />
        <ConfidenceBadge type="interpretation" value={proposal.interpretation_confidence} />
      </div>
      
      {/* Gate violations banner (if ineligible) */}
      {!is_eligible && (
        <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-4">
          <div className="flex items-center gap-2 text-red-400 text-sm font-medium mb-2">
            <span>⚠️</span>
            <span>Ineligible for tagging</span>
          </div>
          <ul className="text-sm text-slate-300 space-y-1">
            {gate_violations.map((v, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="text-red-500">✗</span>
                {v.message}
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {/* What changed */}
      <section>
        <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-2">
          What changed
        </h3>
        <p className="text-slate-300">
          {proposal.trend === 'worsening' ? '📉 Situation worsening' : 
           proposal.trend === 'improving' ? '📈 Situation improving' : 
           '➡️ Situation stable'}
          {proposal.occurrence_count > 1 && ` — seen ${proposal.occurrence_count} times`}
        </p>
      </section>
      
      {/* Why likely (hypotheses) */}
      <section>
        <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-2">
          Why likely
        </h3>
        <div className="space-y-3">
          {proposal.top_hypotheses.map((hyp, i) => (
            <div key={i} className="bg-slate-800 rounded-lg p-3">
              <div className="flex items-start justify-between gap-2">
                <span className="text-slate-200">{i + 1}. {hyp.label}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  hyp.confidence >= 0.70 ? 'bg-green-900/50 text-green-400' :
                  hyp.confidence >= 0.55 ? 'bg-amber-900/50 text-amber-400' :
                  'bg-red-900/50 text-red-400'
                }`}>
                  {(hyp.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Supported by {hyp.supporting_signal_ids.length} signals
              </p>
              {hyp.missing_confirmations && hyp.missing_confirmations.length > 0 && (
                <p className="text-xs text-amber-400 mt-1">
                  Missing: {hyp.missing_confirmations.join(', ')}
                </p>
              )}
            </div>
          ))}
        </div>
      </section>
      
      {/* Proof */}
      <section>
        <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-2">
          Proof ({proposal.proof.length} excerpts)
        </h3>
        <div className="space-y-2">
          {proposal.proof.map((p, i) => (
            <div key={i} className="bg-slate-800/50 rounded-lg p-3 border-l-2 border-blue-500">
              <p className="text-sm text-slate-300">{p.text}</p>
              <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
                <span>📎 {p.source_type.replace('_', ' ')}</span>
                <a href={p.source_ref} className="text-blue-400 hover:underline">
                  Open source →
                </a>
              </div>
            </div>
          ))}
        </div>
      </section>
      
      {/* Missing confirmations */}
      {proposal.missing_confirmations.length > 0 && (
        <section>
          <h3 className="text-sm font-medium text-amber-400 uppercase tracking-wide mb-2">
            Missing confirmations
          </h3>
          <ul className="space-y-1">
            {proposal.missing_confirmations.map((mc, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-slate-300">
                <span className="text-amber-500">○</span>
                {mc}
              </li>
            ))}
          </ul>
        </section>
      )}
      
      {/* Actions */}
      <div className="flex items-center gap-2 pt-4 border-t border-slate-700">
        {is_eligible ? (
          <>
            <button 
              onClick={onTag}
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded transition-colors"
            >
              Tag & Monitor
            </button>
            <button 
              onClick={onSnooze}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded transition-colors"
            >
              Snooze
            </button>
            <button 
              onClick={onDismiss}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded transition-colors"
            >
              Dismiss
            </button>
          </>
        ) : (
          <button 
            onClick={onFixData}
            className="flex-1 px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium rounded transition-colors"
          >
            Fix Data →
          </button>
        )}
      </div>
    </div>
  );
}
