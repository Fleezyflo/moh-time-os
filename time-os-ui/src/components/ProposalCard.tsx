// ProposalCard — primary attention unit with eligibility gate enforcement
import { ConfidenceBadge } from './ConfidenceBadge';
import type { Proposal } from '../fixtures';
import { checkEligibility } from '../fixtures';

interface ProposalCardProps {
  proposal: Proposal;
  onTag?: () => void;
  onSnooze?: () => void;
  onOpen?: () => void;
}

export function ProposalCard({ proposal, onTag, onSnooze, onOpen }: ProposalCardProps) {
  const { is_eligible, gate_violations } = checkEligibility(proposal);
  
  const trendIcon = {
    worsening: '📉',
    improving: '📈',
    flat: '➡️'
  }[proposal.trend];
  
  const impactBadges = [];
  if (proposal.impact.dimensions.time) {
    impactBadges.push({ icon: '⏱️', text: `${proposal.impact.dimensions.time.days_at_risk}d at risk`, color: 'text-orange-400' });
  }
  if (proposal.impact.dimensions.cash) {
    impactBadges.push({ icon: '💰', text: `$${(proposal.impact.dimensions.cash.amount / 1000).toFixed(0)}k`, color: 'text-green-400' });
  }
  if (proposal.impact.dimensions.reputation) {
    const severity = proposal.impact.dimensions.reputation.severity;
    impactBadges.push({ icon: '⭐', text: severity, color: severity === 'high' ? 'text-red-400' : severity === 'medium' ? 'text-amber-400' : 'text-slate-400' });
  }
  
  return (
    <div 
      className={`bg-slate-800 rounded-lg border transition-colors cursor-pointer ${
        is_eligible ? 'border-slate-700 hover:border-slate-600' : 'border-red-900/50 opacity-75'
      }`}
      onClick={onOpen}
    >
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            {!is_eligible && (
              <div className="flex items-center gap-2 text-red-400 text-xs mb-2">
                <span>⚠️</span>
                <span>Ineligible</span>
              </div>
            )}
            <h3 className="font-medium text-slate-100 leading-tight">{proposal.headline}</h3>
            <div className="flex items-center gap-3 mt-2 text-sm">
              <span className="text-slate-400">Score: {proposal.score.toFixed(1)}</span>
              <span className="text-slate-500">{trendIcon} {proposal.trend}</span>
              {proposal.occurrence_count > 1 && (
                <span className="text-slate-500">×{proposal.occurrence_count}</span>
              )}
            </div>
          </div>
          <span className={`px-2 py-1 rounded text-xs ${
            proposal.proposal_type === 'risk' ? 'bg-red-900/50 text-red-300' :
            proposal.proposal_type === 'opportunity' ? 'bg-green-900/50 text-green-300' :
            'bg-slate-700 text-slate-300'
          }`}>
            {proposal.proposal_type}
          </span>
        </div>
        
        {/* Impact strip */}
        {impactBadges.length > 0 && (
          <div className="flex items-center gap-3 mt-3">
            {impactBadges.map((badge, i) => (
              <span key={i} className={`text-sm ${badge.color}`}>
                {badge.icon} {badge.text}
              </span>
            ))}
            {proposal.impact.deadline_at && (
              <span className="text-sm text-slate-500">
                Due: {new Date(proposal.impact.deadline_at).toLocaleDateString()}
              </span>
            )}
          </div>
        )}
        
        {/* Confidence badges */}
        <div className="flex items-center gap-2 mt-3">
          <ConfidenceBadge type="linkage" value={proposal.linkage_confidence} />
          <ConfidenceBadge type="interpretation" value={proposal.interpretation_confidence} />
        </div>
      </div>
      
      {/* Hypotheses */}
      <div className="p-4 border-b border-slate-700">
        <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Why this matters</h4>
        <div className="space-y-2">
          {proposal.top_hypotheses.slice(0, 3).map((hyp, i) => (
            <div key={i} className="flex items-start gap-2 text-sm">
              <span className="text-slate-500 w-4">{i + 1}.</span>
              <div className="flex-1">
                <span className="text-slate-200">{hyp.label}</span>
                <span className={`ml-2 text-xs ${hyp.confidence >= 0.70 ? 'text-green-400' : hyp.confidence >= 0.55 ? 'text-amber-400' : 'text-red-400'}`}>
                  ({(hyp.confidence * 100).toFixed(0)}%)
                </span>
                <span className="ml-2 text-xs text-slate-500">
                  {hyp.supporting_signal_ids.length} signals
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Proof excerpts */}
      <div className="p-4 border-b border-slate-700">
        <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">
          Proof ({proposal.proof.length} excerpts)
        </h4>
        <div className="space-y-2">
          {proposal.proof.slice(0, 3).map((p, i) => (
            <div key={i} className="flex items-start gap-2 text-sm">
              <span className="text-blue-400">●</span>
              <div className="flex-1 min-w-0">
                <p className="text-slate-300 truncate">{p.text}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  📎 {p.source_type.replace('_', ' ')}
                </p>
              </div>
            </div>
          ))}
          {proposal.proof.length > 3 && (
            <p className="text-xs text-slate-500 pl-5">+{proposal.proof.length - 3} more</p>
          )}
        </div>
      </div>
      
      {/* Missing confirmations */}
      {proposal.missing_confirmations.length > 0 && (
        <div className="p-4 border-b border-slate-700 bg-amber-900/10">
          <h4 className="text-xs font-medium text-amber-400 uppercase tracking-wide mb-2">Missing confirmations</h4>
          <ul className="text-sm text-slate-300 space-y-1">
            {proposal.missing_confirmations.map((mc, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="text-amber-500">○</span>
                {mc}
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Gate violations (if ineligible) */}
      {!is_eligible && (
        <div className="p-4 border-b border-slate-700 bg-red-900/10">
          <h4 className="text-xs font-medium text-red-400 uppercase tracking-wide mb-2">Gate violations</h4>
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
      
      {/* Actions */}
      <div className="p-4 flex items-center gap-2">
        {is_eligible ? (
          <>
            <button 
              onClick={(e) => { e.stopPropagation(); onTag?.(); }}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded transition-colors"
            >
              Tag & Monitor
            </button>
            <button 
              onClick={(e) => { e.stopPropagation(); onSnooze?.(); }}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded transition-colors"
            >
              Snooze
            </button>
          </>
        ) : (
          <button 
            onClick={(e) => { e.stopPropagation(); }}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium rounded transition-colors"
          >
            Fix Data →
          </button>
        )}
      </div>
    </div>
  );
}
