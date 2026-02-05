"""
Time OS V4 - Pipeline Orchestrator

Runs the complete V4 pipeline:
1. Ingest new data → Artifacts
2. Resolve identities
3. Link entities
4. Run detectors → Signals
5. Bundle signals → Proposals
6. Evaluate watchers on Issues
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any

from .artifact_service import get_artifact_service
from .identity_service import get_identity_service
from .entity_link_service import get_entity_link_service
from .signal_service import get_signal_service
from .proposal_service import get_proposal_service
from .issue_service import get_issue_service
from .coupling_service import get_coupling_service
from .report_service import get_report_service
from .policy_service import get_policy_service
from .collector_hooks import get_hooks
from .detectors import DeadlineDetector, HealthDetector, CommitmentDetector, AnomalyDetector

log = logging.getLogger("moh_time_os.v4.orchestrator")


class V4Orchestrator:
    """
    Orchestrates the complete V4 pipeline.
    
    Can be run as:
    - Full cycle (all stages)
    - Specific stages only
    - Background daemon mode
    """
    
    def __init__(self):
        # Services - M1
        self.artifact_svc = get_artifact_service()
        self.identity_svc = get_identity_service()
        self.link_svc = get_entity_link_service()
        # Services - M2
        self.signal_svc = get_signal_service()
        self.proposal_svc = get_proposal_service()
        # Services - M3
        self.issue_svc = get_issue_service()
        # Services - M4
        self.coupling_svc = get_coupling_service()
        self.report_svc = get_report_service()
        self.policy_svc = get_policy_service()
        # Hooks
        self.hooks = get_hooks()
        
        # Detectors
        self.detectors = [
            DeadlineDetector(),
            HealthDetector(),
            CommitmentDetector(),
            AnomalyDetector()
        ]
        
        # Register signal types
        self._register_signal_types()
    
    def _register_signal_types(self):
        """Register all signal type definitions."""
        signal_defs = [
            # Deadline signals
            ('deadline_approaching', 'Task or deliverable approaching deadline', 'deadline', ['task'], 1.5),
            ('deadline_overdue', 'Task or deliverable past due date', 'deadline', ['task'], 2.0),
            ('deadline_cluster', 'Multiple items due in short window', 'deadline', ['task'], 1.2),
            ('deadline_at_risk', 'High-priority deadline at risk', 'deadline', ['task'], 2.5),
            
            # Health signals
            ('client_health_declining', 'Client relationship health is declining', 'health', ['client'], 2.0),
            ('communication_gap', 'No recent communication with client', 'health', ['client'], 1.5),
            ('ar_aging_risk', 'Accounts receivable aging concern', 'health', ['invoice'], 1.8),
            ('project_health_at_risk', 'Project showing signs of trouble', 'health', ['project'], 1.5),
            
            # Commitment signals
            ('commitment_made', 'Commitment detected in communication', 'commitment', ['message'], 1.0),
            ('commitment_at_risk', 'Commitment may be missed', 'commitment', ['commitment'], 1.5),
            ('commitment_overdue', 'Commitment past due', 'commitment', ['commitment'], 2.0),
            
            # Anomaly signals
            ('activity_spike', 'Unusual increase in activity', 'anomaly', ['artifact'], 1.0),
            ('activity_drop', 'Unusual decrease in activity', 'anomaly', ['artifact'], 1.0),
            ('data_quality_issue', 'Missing or inconsistent data', 'protocol', ['entity'], 0.8),
            ('hierarchy_violation', 'Domain model violation', 'protocol', ['entity'], 1.0),
        ]
        
        for signal_type, desc, category, evidence_types, weight in signal_defs:
            self.signal_svc.register_signal_type(
                signal_type=signal_type,
                description=desc,
                category=category,
                required_evidence_types=evidence_types,
                priority_weight=weight
            )
    
    def run_full_cycle(self) -> Dict[str, Any]:
        """
        Run the complete V4 pipeline cycle.
        
        Returns:
            Cycle statistics
        """
        start_time = time.time()
        stats = {
            'started_at': datetime.now().isoformat(),
            'stages': {}
        }
        
        log.info("Starting V4 pipeline cycle")
        
        # Stage 1: Sync from existing DB tables
        log.info("Stage 1: Syncing artifacts from DB")
        stage_start = time.time()
        try:
            sync_stats = self.hooks.sync_all_from_db()
            stats['stages']['sync'] = {
                'status': 'completed',
                'duration_ms': int((time.time() - stage_start) * 1000),
                **sync_stats
            }
        except Exception as e:
            log.error(f"Sync stage failed: {e}")
            stats['stages']['sync'] = {'status': 'failed', 'error': str(e)}
        
        # Stage 2: Run detectors
        log.info("Stage 2: Running detectors")
        stage_start = time.time()
        detector_results = []
        for detector in self.detectors:
            try:
                result = detector.run({})
                detector_results.append({
                    'detector_id': detector.detector_id,
                    'signals_created': result['signals_created']
                })
            except Exception as e:
                log.error(f"Detector {detector.detector_id} failed: {e}")
                detector_results.append({
                    'detector_id': detector.detector_id,
                    'error': str(e)
                })
        
        stats['stages']['detect'] = {
            'status': 'completed',
            'duration_ms': int((time.time() - stage_start) * 1000),
            'detectors': detector_results,
            'total_signals': sum(d.get('signals_created', 0) for d in detector_results)
        }
        
        # Stage 3: Generate proposals
        log.info("Stage 3: Generating proposals")
        stage_start = time.time()
        try:
            proposal_stats = self.proposal_svc.generate_proposals_from_signals()
            stats['stages']['proposals'] = {
                'status': 'completed',
                'duration_ms': int((time.time() - stage_start) * 1000),
                **proposal_stats
            }
        except Exception as e:
            log.error(f"Proposal generation failed: {e}")
            stats['stages']['proposals'] = {'status': 'failed', 'error': str(e)}
        
        # Stage 4: Evaluate watchers
        log.info("Stage 4: Evaluating watchers")
        stage_start = time.time()
        try:
            watcher_stats = self.issue_svc.evaluate_watchers()
            stats['stages']['watchers'] = {
                'status': 'completed',
                'duration_ms': int((time.time() - stage_start) * 1000),
                **watcher_stats
            }
        except Exception as e:
            log.error(f"Watcher evaluation failed: {e}")
            stats['stages']['watchers'] = {'status': 'failed', 'error': str(e)}
        
        # Stage 5: Discover couplings
        log.info("Stage 5: Discovering couplings")
        stage_start = time.time()
        try:
            coupling_stats = self.coupling_svc.discover_couplings()
            stats['stages']['couplings'] = {
                'status': 'completed',
                'duration_ms': int((time.time() - stage_start) * 1000),
                **coupling_stats
            }
        except Exception as e:
            log.error(f"Coupling discovery failed: {e}")
            stats['stages']['couplings'] = {'status': 'failed', 'error': str(e)}
        
        # Final stats
        stats['total_duration_ms'] = int((time.time() - start_time) * 1000)
        stats['completed_at'] = datetime.now().isoformat()
        
        log.info(f"V4 cycle completed in {stats['total_duration_ms']}ms")
        
        return stats
    
    def run_detectors_only(self, scope: Dict = None) -> Dict[str, Any]:
        """Run only the detection stage."""
        results = []
        for detector in self.detectors:
            try:
                result = detector.run(scope or {})
                results.append(result)
            except Exception as e:
                results.append({'detector_id': detector.detector_id, 'error': str(e)})
        return {'detectors': results}
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            'artifacts': self.artifact_svc.get_stats(),
            'identities': self.identity_svc.get_stats(),
            'links': self.link_svc.get_stats(),
            'signals': self.signal_svc.get_stats(),
            'proposals': self.proposal_svc.get_stats(),
            'issues': self.issue_svc.get_stats(),
            'couplings': self.coupling_svc.get_stats(),
            'reports': self.report_svc.get_stats(),
            'policy': self.policy_svc.get_stats(),
            'detectors': [
                {'id': d.detector_id, 'version': d.version}
                for d in self.detectors
            ]
        }
    
    def get_executive_brief(self) -> Dict[str, Any]:
        """
        Generate an executive brief of current state.
        
        Returns proposals, issues, and key metrics.
        """
        # Get surfaceable proposals
        proposals = self.proposal_svc.get_surfaceable_proposals(limit=10)
        
        # Get open issues
        issues = self.issue_svc.get_open_issues(limit=10)
        
        # Get key signals by severity
        critical_signals = self.signal_svc.find_signals(
            severity='critical', status='active', limit=5
        )
        high_signals = self.signal_svc.find_signals(
            severity='high', status='active', limit=5
        )
        
        # Summary stats
        signal_stats = self.signal_svc.get_stats()
        proposal_stats = self.proposal_svc.get_stats()
        issue_stats = self.issue_svc.get_stats()
        
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'active_signals': sum(signal_stats.get('by_status', {}).values()) - signal_stats.get('by_status', {}).get('consumed', 0),
                'critical_signals': signal_stats.get('active_by_severity', {}).get('critical', 0),
                'high_signals': signal_stats.get('active_by_severity', {}).get('high', 0),
                'open_proposals': sum(proposal_stats.get('by_status', {}).values()) - proposal_stats.get('by_status', {}).get('dismissed', 0),
                'surfaceable_proposals': proposal_stats.get('open_by_exposure', {}).get('briefable', 0),
                'open_issues': sum(v for k, v in issue_stats.get('by_state', {}).items() if k not in ('resolved', 'handed_over')),
                'active_watchers': issue_stats.get('active_watchers', 0)
            },
            'proposals': proposals,
            'issues': issues,
            'critical_signals': critical_signals,
            'high_signals': high_signals
        }


# Singleton
_orchestrator = None

def get_orchestrator() -> V4Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = V4Orchestrator()
    return _orchestrator


def run_cycle() -> Dict[str, Any]:
    """Convenience function to run a full cycle."""
    return get_orchestrator().run_full_cycle()


def get_brief() -> Dict[str, Any]:
    """Convenience function to get executive brief."""
    return get_orchestrator().get_executive_brief()
