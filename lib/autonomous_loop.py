"""
Autonomous Loop - The heart of MOH TIME OS.
This is the MAIN WIRING - connects all components into one running system.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import argparse

from .state_store import StateStore, get_store
from .collectors import CollectorOrchestrator
from .analyzers import AnalyzerOrchestrator
from .governance import GovernanceEngine, get_governance
from .reasoner import ReasonerEngine
from .executor import ExecutorEngine
from .notifier import NotificationEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('AutonomousLoop')


class AutonomousLoop:
    """
    Main autonomous execution loop.
    
    THIS IS THE COMPLETE WIRING:
    
    1. COLLECT: External Systems → State Store
    2. ANALYZE: State Store → Insights → Cache
    3. REASON: Insights → Decisions (via Governance)
    4. NOTIFY: Decisions → User (via Clawdbot)
    
    User interacts via CLI/Dashboard, NOT via chat.
    """
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or str(Path(__file__).parent.parent / "config")
        
        # Initialize all components - THIS IS THE WIRING
        self.store = get_store()
        self.collectors = CollectorOrchestrator(self.config_path, self.store)
        self.analyzers = AnalyzerOrchestrator(store=self.store)
        self.governance = get_governance(store=self.store)
        self.reasoner = ReasonerEngine(store=self.store, governance=self.governance)
        self.executor = ExecutorEngine(store=self.store, governance=self.governance)
        self.notifier = NotificationEngine(self.store, self._load_notification_config())
        
        self.cycle_count = 0
        self.running = False
    
    def _load_notification_config(self) -> dict:
        """Load notification config from governance.yaml."""
        import yaml
        config_file = Path(self.config_path) / "governance.yaml"
        if config_file.exists():
            with open(config_file) as f:
                config = yaml.safe_load(f)
                return config.get('notification_settings', {})
        return {}
    
    def run_cycle(self) -> Dict[str, Any]:
        """
        Run one complete autonomous cycle.
        This is what runs every N minutes.
        """
        cycle_start = datetime.now()
        self.cycle_count += 1
        
        logger.info(f"═══════════════════════════════════════")
        logger.info(f"  CYCLE {self.cycle_count} STARTING")
        logger.info(f"═══════════════════════════════════════")
        
        results = {
            'cycle': self.cycle_count,
            'started_at': cycle_start.isoformat(),
            'phases': {}
        }
        
        try:
            # ═══════════════════════════════════════
            # PHASE 1: COLLECT
            # External Systems → State Store
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1: COLLECT")
            collect_results = self.collectors.sync_all()
            results['phases']['collect'] = collect_results
            
            collected_count = sum(
                r.get('stored', 0) for r in collect_results.values() 
                if isinstance(r, dict) and r.get('success')
            )
            logger.info(f"  Collected {collected_count} items from {len(collect_results)} sources")
            
            # ═══════════════════════════════════════
            # PHASE 1a2: DATA NORMALIZATION
            # Derive link statuses per MASTER_SPEC §4
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a2: DATA NORMALIZATION")
            normalization_results = self._normalize_data()
            results['phases']['normalization'] = normalization_results
            total_normalized = sum([
                normalization_results.get('tasks_updated', 0),
                normalization_results.get('projects_updated', 0),
                normalization_results.get('communications_updated', 0),
                normalization_results.get('invoices_updated', 0)
            ])
            if total_normalized > 0:
                logger.info(f"  Normalized {total_normalized} records")
            
            # ═══════════════════════════════════════
            # PHASE 1a2a: COMMITMENT EXTRACTION
            # Extract promises/requests from communications
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a2a: COMMITMENT EXTRACTION")
            try:
                from .commitment_extractor import extract_from_communications
                commit_results = extract_from_communications(limit=100)
                results['phases']['commitment_extraction'] = commit_results
                if commit_results.get('commitments_extracted', 0) > 0:
                    logger.info(f"  Extracted {commit_results['commitments_extracted']} commitments")
            except Exception as e:
                logger.warning(f"  Commitment extraction skipped: {e}")
                results['phases']['commitment_extraction'] = {'error': str(e)}
            
            # ═══════════════════════════════════════
            # PHASE 1a2b: LANE ASSIGNMENT
            # Categorize tasks into capacity lanes
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a2b: LANE ASSIGNMENT")
            try:
                from .lane_assigner import run_assignment
                lane_results = run_assignment()
                results['phases']['lane_assignment'] = lane_results
                if lane_results.get('changed', 0) > 0:
                    logger.info(f"  Reassigned {lane_results['changed']} tasks to lanes")
            except Exception as e:
                logger.error(f"Lane assignment error: {e}")
                results['phases']['lane_assignment'] = {'error': str(e)}
            
            # ═══════════════════════════════════════
            # PHASE 1a3: GATE CHECK
            # Evaluate gates, determine blocking per §6.3
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a3: GATE CHECK")
            gate_results = self._check_gates()
            results['phases']['gates'] = gate_results
            
            # Log gate status
            passed = [g for g, v in gate_results.items() if v is True and not g.endswith('_pct')]
            failed = [g for g, v in gate_results.items() if v is False and not g.endswith('_pct')]
            logger.info(f"  Gates: {len(passed)} passed, {len(failed)} failed")
            if failed:
                logger.warning(f"  Failed gates: {', '.join(failed)}")
            
            # Check blocking gates per §6.3
            # data_integrity fails → skip analyze/surface/reason/execute
            # project_brand_required/consistency fails → skip all truth modules
            data_integrity_ok = gate_results.get('data_integrity', False)
            project_gates_ok = (gate_results.get('project_brand_required', False) and 
                               gate_results.get('project_brand_consistency', False))
            
            blocking_failed = []
            if not data_integrity_ok:
                blocking_failed.append('data_integrity')
            if not project_gates_ok:
                if not gate_results.get('project_brand_required', False):
                    blocking_failed.append('project_brand_required')
                if not gate_results.get('project_brand_consistency', False):
                    blocking_failed.append('project_brand_consistency')
            
            if blocking_failed:
                logger.warning(f"  BLOCKING gates failed: {blocking_failed}")
                results['phases']['blocked'] = True
                results['blocked_by'] = blocking_failed
            
            # ═══════════════════════════════════════
            # PHASE 1a4: RESOLUTION QUEUE
            # Populate queue with items needing attention
            # (runs regardless of gates - always surface issues)
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a4: RESOLUTION QUEUE")
            queue_results = self._populate_resolution_queue()
            results['phases']['resolution_queue'] = queue_results
            total_queued = sum(queue_results.get('counts', {}).values())
            if total_queued > 0:
                logger.info(f"  Queued {total_queued} items for resolution")
            
            # ═══════════════════════════════════════
            # PHASE 1b-1e: TRUTH MODULES
            # SKIP if project_brand_required or project_brand_consistency fails
            # ═══════════════════════════════════════
            if not project_gates_ok:
                logger.warning("  SKIPPING truth modules (project gates failed)")
                results['phases']['time_truth'] = {'skipped': True, 'reason': 'project_gates_failed'}
                results['phases']['commitment_truth'] = {'skipped': True, 'reason': 'project_gates_failed'}
                results['phases']['capacity_truth'] = {'skipped': True, 'reason': 'project_gates_failed'}
                results['phases']['client_truth'] = {'skipped': True, 'reason': 'project_gates_failed'}
            else:
                # PHASE 1b: TIME TRUTH (Tier 0)
                logger.info("▶ Phase 1b: TIME TRUTH")
                time_truth_results = self._process_time_truth()
                results['phases']['time_truth'] = time_truth_results
                logger.info(f"  Blocks: {time_truth_results.get('blocks_total', 0)}, Scheduled: {time_truth_results.get('tasks_scheduled', 0)}")
                
                # PHASE 1c: COMMITMENT TRUTH (Tier 1)
                logger.info("▶ Phase 1c: COMMITMENT TRUTH")
                commitment_results = self._process_commitment_truth()
                results['phases']['commitment_truth'] = commitment_results
                logger.info(f"  Extracted: {commitment_results.get('extracted', 0)}, Untracked: {commitment_results.get('untracked', 0)}")
                
                # PHASE 1d: CAPACITY TRUTH (Tier 2)
                logger.info("▶ Phase 1d: CAPACITY TRUTH")
                capacity_results = self._process_capacity_truth()
                results['phases']['capacity_truth'] = capacity_results
                logger.info(f"  Utilization: {capacity_results.get('overall_utilization', 0)}%, Overloaded: {len(capacity_results.get('overloaded_lanes', []))}")
                
                # PHASE 1e: CLIENT TRUTH (Tier 3)
                logger.info("▶ Phase 1e: CLIENT TRUTH")
                client_results = self._process_client_truth()
                results['phases']['client_truth'] = client_results
                logger.info(f"  At-risk clients: {client_results.get('at_risk_count', 0)}, Alerts: {client_results.get('alerts_created', 0)}")
            
            # ═══════════════════════════════════════
            # PHASE 2-5: ANALYZE/SURFACE/REASON/EXECUTE
            # SKIP if data_integrity fails
            # ═══════════════════════════════════════
            if not data_integrity_ok:
                logger.warning("  SKIPPING analyze/surface/reason/execute (data_integrity failed)")
                results['phases']['analyze'] = {'skipped': True, 'reason': 'data_integrity_failed'}
                results['phases']['surface'] = {'skipped': True, 'reason': 'data_integrity_failed'}
                results['phases']['reason'] = {'skipped': True, 'reason': 'data_integrity_failed'}
                results['phases']['execute'] = {'skipped': True, 'reason': 'data_integrity_failed'}
            else:
                # PHASE 2: ANALYZE
                logger.info("▶ Phase 2: ANALYZE")
                analyze_results = self.analyzers.analyze_all()
                results['phases']['analyze'] = analyze_results
                
                priority_count = analyze_results.get('priority', {}).get('total_items', 0)
                anomaly_count = analyze_results.get('anomalies', {}).get('total', 0)
                logger.info(f"  Priority queue: {priority_count} items")
                logger.info(f"  Anomalies detected: {anomaly_count}")
                
                # PHASE 3: SURFACE
                logger.info("▶ Phase 3: SURFACE")
                surface_results = self._surface_critical_items(analyze_results)
                results['phases']['surface'] = surface_results
                logger.info(f"  Created {surface_results.get('notifications', 0)} notifications")
                
                # PHASE 3b: SEND NOTIFICATIONS
                logger.info("▶ Phase 3b: SEND NOTIFICATIONS")
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                send_results = loop.run_until_complete(self.notifier.process_pending())
                sent_count = len([r for r in send_results if r.get('status') == 'sent'])
                results['phases']['surface']['sent'] = sent_count
                logger.info(f"  Sent {sent_count} notifications")
                
                # PHASE 4: REASON
                logger.info("▶ Phase 4: REASON")
                reason_results = self.reasoner.process_cycle()
                results['phases']['reason'] = reason_results
                logger.info(f"  Created {reason_results.get('decisions_created', 0)} decisions")
            
            # ═══════════════════════════════════════
            # PHASE 5: EXECUTE
            # Process approved actions
            # ═══════════════════════════════════════
            logger.info("▶ Phase 5: EXECUTE")
            execute_results = self.executor.process_pending_actions()
            results['phases']['execute'] = {
                'processed': len(execute_results),
                'succeeded': len([r for r in execute_results if r.get('status') == 'done']),
                'failed': len([r for r in execute_results if r.get('status') == 'failed'])
            }
            logger.info(f"  Executed {len(execute_results)} actions")
            
            # ═══════════════════════════════════════
            # PHASE 6: SNAPSHOT & MOVES
            # Generate dashboard snapshot with exec moves
            # ═══════════════════════════════════════
            logger.info("▶ Phase 6: SNAPSHOT & MOVES")
            snapshot_results = self._generate_snapshot()
            results['phases']['snapshot'] = snapshot_results
            moves_count = snapshot_results.get('moves_count', 0)
            logger.info(f"  Generated snapshot with {moves_count} moves")
            
            # ═══════════════════════════════════════
            # SUCCESS
            # ═══════════════════════════════════════
            results['success'] = True
            
        except Exception as e:
            logger.error(f"Cycle failed: {e}", exc_info=True)
            results['success'] = False
            results['error'] = str(e)
        
        # Calculate duration
        results['completed_at'] = datetime.now().isoformat()
        results['duration_ms'] = (datetime.now() - cycle_start).total_seconds() * 1000
        
        # Store cycle log
        self.store.insert('cycle_logs', {
            'id': f"cycle_{self.cycle_count}_{cycle_start.strftime('%Y%m%d_%H%M%S')}",
            'cycle_number': self.cycle_count,
            'phase': 'complete',
            'data': json.dumps(results),
            'duration_ms': results['duration_ms'],
            'created_at': cycle_start.isoformat()
        })
        
        logger.info(f"═══════════════════════════════════════")
        logger.info(f"  CYCLE {self.cycle_count} COMPLETE ({results['duration_ms']:.0f}ms)")
        logger.info(f"═══════════════════════════════════════\n")
        
        return results
    
    def _process_client_truth(self) -> Dict:
        """
        Process Tier 3: Client Truth.
        
        - Compute health for key clients
        - Surface at-risk clients
        - Generate alerts for declining health
        """
        results = {
            'clients_processed': 0,
            'at_risk_count': 0,
            'declining_count': 0,
            'alerts_created': 0
        }
        
        try:
            from lib.client_truth import HealthCalculator
            
            calc = HealthCalculator(self.store)
            
            # Get top-tier clients to monitor
            top_clients = self.store.query("""
                SELECT id, name, tier FROM clients
                WHERE tier IN ('enterprise', 'premium', 'key')
                LIMIT 20
            """)
            
            # If no tiered clients, get clients with recent activity
            if not top_clients:
                top_clients = self.store.query("""
                    SELECT DISTINCT c.id, c.name, c.tier FROM clients c
                    JOIN tasks t ON t.client_id = c.id
                    WHERE t.created_at >= date('now', '-30 days')
                    LIMIT 20
                """)
            
            for client in top_clients:
                health = calc.compute_health_score(client['id'])
                results['clients_processed'] += 1
                
                if health.at_risk:
                    results['at_risk_count'] += 1
                    
                    # Create alert for at-risk client
                    self._create_notification(
                        title=f"⚠️ Client '{health.client_name}' at risk (health: {health.health_score})",
                        body=f"Health score dropped below 50. Factors: {health.factors}",
                        priority='high',
                        type='alert',
                        data={'client_name': health.client_name, 'health_score': health.health_score}
                    )
                    results['alerts_created'] += 1
                
                if health.trend == 'declining':
                    results['declining_count'] += 1
            
        except Exception as e:
            logger.error(f"Client Truth error: {e}")
            results['error'] = str(e)
        
        return results
    
    def _process_capacity_truth(self) -> Dict:
        """
        Process Tier 2: Capacity Truth.
        
        - Calculate lane utilization
        - Check for overloaded lanes
        - Surface capacity alerts at 90%+
        """
        from datetime import date
        
        results = {
            'date': date.today().isoformat(),
            'overall_utilization': 0,
            'overloaded_lanes': [],
            'high_util_lanes': [],
            'alerts_created': 0
        }
        
        try:
            from lib.capacity_truth import CapacityCalculator
            
            calc = CapacityCalculator(self.store)
            summary = calc.get_capacity_summary()
            
            results['overall_utilization'] = summary.get('overall_utilization_pct', 0)
            results['overloaded_lanes'] = summary.get('overloaded_lanes', [])
            results['high_util_lanes'] = summary.get('high_utilization_lanes', [])
            results['lanes'] = summary.get('lanes', [])
            
            # Generate alerts for lanes at 90%+ utilization
            for lane_data in summary.get('lanes', []):
                util_pct = float(lane_data.get('utilization_pct', 0) or 0)
                lane_name = lane_data.get('lane', 'unknown')
                
                if util_pct >= 100:
                    # Critical: overloaded
                    self._create_notification(
                        title=f"🚨 Lane '{lane_name}' overloaded ({util_pct}%)",
                        body=f"The {lane_name} lane is at {util_pct}% capacity. Tasks may not fit.",
                        priority='critical',
                        type='alert',
                        data={'lane': lane_name, 'utilization': util_pct}
                    )
                    results['alerts_created'] += 1
                elif util_pct >= 90:
                    # Warning: high utilization
                    self._create_notification(
                        title=f"⚠️ Lane '{lane_name}' near capacity ({util_pct}%)",
                        body=f"The {lane_name} lane is at {util_pct}% utilization. Consider redistributing work.",
                        priority='high',
                        type='alert',
                        data={'lane': lane_name, 'utilization': util_pct}
                    )
                    results['alerts_created'] += 1
            
        except Exception as e:
            logger.error(f"Capacity Truth error: {e}")
            results['error'] = str(e)
        
        return results
    
    def _process_commitment_truth(self) -> Dict:
        """
        Process Tier 1: Commitment Truth.
        
        - Extract commitments from recent emails
        - Track untracked commitments
        """
        results = {
            'extracted': 0,
            'untracked': 0,
            'emails_processed': 0
        }
        
        try:
            from lib.commitment_truth import CommitmentManager
            
            manager = CommitmentManager(self.store)
            
            # Get recent unprocessed emails (last 24h)
            emails = self.store.query("""
                SELECT * FROM communications 
                WHERE source = 'email' 
                AND processed = 0
                AND created_at >= datetime('now', '-1 day')
                LIMIT 50
            """)
            
            for email in emails:
                email_id = email['id']
                text = f"{email.get('subject', '')} {email.get('snippet', '')}"
                sender = email.get('from_email', '')
                
                # Extract commitments
                commitments = manager.extract_commitments_from_email(
                    email_id=email_id,
                    email_text=text,
                    sender=sender
                )
                
                results['extracted'] += len(commitments)
                results['emails_processed'] += 1
                
                # Mark email as processed
                self.store.query(
                    "UPDATE communications SET processed = 1 WHERE id = ?",
                    [email_id]
                )
            
            # Count untracked
            results['untracked'] = len(manager.get_untracked_commitments())
            
        except Exception as e:
            logger.error(f"Commitment Truth error: {e}")
            results['error'] = str(e)
        
        return results
    
    def _normalize_data(self) -> Dict:
        """
        Normalize cross-table references per MASTER_SPEC.md §4.
        
        Uses lib/normalizer.py to derive:
        - projects.client_id (from brand, NULL if internal)
        - tasks.brand_id, client_id, project_link_status, client_link_status
        - communications.from_domain, client_id, link_status
        - invoices.aging_bucket (for valid AR)
        """
        from .normalizer import Normalizer
        
        results = {
            'tasks_updated': 0,
            'projects_updated': 0,
            'communications_updated': 0,
            'invoices_updated': 0
        }
        
        try:
            normalizer = Normalizer()
            norm_results = normalizer.run()
            
            results['tasks_updated'] = norm_results.get('tasks', 0)
            results['projects_updated'] = norm_results.get('projects', 0)
            results['communications_updated'] = norm_results.get('communications', 0)
            results['invoices_updated'] = norm_results.get('invoices', 0)
            
        except Exception as e:
            logger.error(f"Data normalization error: {e}")
            results['error'] = str(e)
        
        return results
    
    def _check_gates(self) -> Dict:
        """
        Evaluate all gates per MASTER_SPEC.md §6.
        
        Returns gate results dict with pass/fail for each gate.
        """
        from .gates import GateEvaluator
        
        try:
            evaluator = GateEvaluator()
            return evaluator.evaluate_all()
        except Exception as e:
            logger.error(f"Gate check error: {e}")
            return {'error': str(e), 'data_integrity': False}
    
    def _populate_resolution_queue(self) -> Dict:
        """
        Populate resolution queue per MASTER_SPEC.md §5.
        
        Surfaces entities needing manual resolution.
        """
        from .resolution_queue import ResolutionQueue
        
        try:
            queue = ResolutionQueue()
            counts = queue.populate()
            summary = queue.get_summary()
            return {
                'counts': counts,
                'summary': summary
            }
        except Exception as e:
            logger.error(f"Resolution queue error: {e}")
            return {'error': str(e)}
    
    def _process_time_truth(self) -> Dict:
        """
        Process Tier 0: Time Truth.
        
        - Generate time blocks for today
        - Run auto-scheduler for unscheduled tasks
        - Validate schedule invariants
        """
        from datetime import date
        from lib.time_truth import CalendarSync, Scheduler
        
        today = date.today().isoformat()
        results = {
            'date': today,
            'blocks_created': 0,
            'blocks_total': 0,
            'tasks_scheduled': 0,
            'validation_issues': 0
        }
        
        try:
            # Generate blocks for today
            calendar_sync = CalendarSync(self.store)
            blocks = calendar_sync.generate_available_blocks(today)
            results['blocks_total'] = len(blocks)
            
            # Run scheduler
            scheduler = Scheduler(self.store)
            schedule_results = scheduler.schedule_unscheduled(today)
            results['tasks_scheduled'] = len([r for r in schedule_results if r.success])
            
            # Validate
            validation = scheduler.validate_schedule(today)
            results['validation_issues'] = len(validation.issues)
            results['valid'] = validation.valid
            
        except Exception as e:
            logger.error(f"Time Truth error: {e}")
            results['error'] = str(e)
        
        return results
    
    def _surface_critical_items(self, analysis: Dict) -> Dict:
        """Create notifications for items that need attention."""
        notifications_created = 0
        
        # Critical anomalies
        anomalies = analysis.get('anomalies', {}).get('items', [])
        for anomaly in anomalies:
            if anomaly.get('severity') in ('critical', 'high'):
                self._create_notification(
                    title=anomaly.get('title', 'Alert'),
                    body=anomaly.get('description', ''),
                    priority='high' if anomaly.get('severity') == 'critical' else 'normal',
                    type='anomaly',
                    data=anomaly
                )
                notifications_created += 1
        
        # High priority items (top 3 if score > 85)
        top_priorities = analysis.get('priority', {}).get('top_5', [])
        for item in top_priorities[:3]:
            if float(item.get('score', 0) or 0) >= 85:
                self._create_notification(
                    title=f"High priority: {item.get('title', '')[:50]}",
                    body=', '.join(item.get('reasons', [])),
                    priority='normal',
                    type='priority',
                    data=item
                )
                notifications_created += 1
        
        return {'notifications': notifications_created}
    
    def _create_notification(self, title: str, body: str, priority: str, type: str, data: Dict):
        """Create a notification record."""
        from uuid import uuid4
        
        self.store.insert('notifications', {
            'id': f"notif_{uuid4().hex[:8]}",
            'type': type,
            'priority': priority,
            'title': title,
            'body': body,
            'action_data': json.dumps(data),
            'channels': json.dumps(['push']),
            'created_at': datetime.now().isoformat()
        })
    
    def _generate_snapshot(self) -> Dict:
        """
        Generate agency snapshot per Page 0/1 locked specs.
        
        Produces agency_snapshot.json with:
        - meta, trust, narrative, tiles
        - heatstrip_projects, constraints, exceptions
        - delivery_command (Page 1 data)
        - drawers
        """
        results = {
            'success': False,
            'snapshot_path': None,
            'moves_count': 0
        }
        
        try:
            # Try new agency snapshot generator first
            try:
                from .agency_snapshot import AgencySnapshotGenerator
                from .agency_snapshot.scoring import Mode, Horizon
                
                generator = AgencySnapshotGenerator(
                    mode=Mode.OPS_HEAD,
                    horizon=Horizon.TODAY,
                    scope={"include_internal": False}
                )
                snapshot = generator.generate()
                
                # Count moves/exceptions
                results['moves_count'] = len(snapshot.get('exceptions', []))
                
                # Save snapshot
                path = generator.save(snapshot)
                results['snapshot_path'] = str(path)
                results['success'] = True
                
                # Copy to dashboard directory for serving
                from shutil import copy
                dashboard_dir = Path(__file__).parent.parent / "dashboard"
                if dashboard_dir.exists():
                    copy(path, dashboard_dir / "agency_snapshot.json")
                
            except ImportError as ie:
                # Fallback to old aggregator if new one not available
                logger.warning(f"Agency snapshot not available, falling back: {ie}")
                from .aggregator import SnapshotAggregator
                from .moves import add_moves_to_snapshot
                
                aggregator = SnapshotAggregator()
                snapshot = aggregator.generate()
                snapshot = add_moves_to_snapshot(snapshot)
                results['moves_count'] = len(snapshot.get('moves', []))
                
                path = aggregator.save(snapshot)
                results['snapshot_path'] = str(path)
                results['success'] = True
                
                from shutil import copy
                dashboard_dir = Path(__file__).parent.parent / "dashboard"
                if dashboard_dir.exists():
                    copy(path, dashboard_dir / "snapshot.json")
            
        except Exception as e:
            logger.error(f"Snapshot generation error: {e}")
            results['error'] = str(e)
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        # Get latest cycle
        latest_cycle = self.store.query(
            "SELECT * FROM cycle_logs ORDER BY created_at DESC LIMIT 1"
        )
        
        # Get collector status
        collector_status = self.collectors.get_status()
        
        # Get governance status
        governance_status = self.governance.get_status()
        
        # Get counts
        task_count = self.store.count('tasks', "status != 'done'")
        email_count = self.store.count('communications', "requires_response = 1 AND processed = 0")
        event_count = self.store.count('events', "datetime(start_time) >= datetime('now') AND datetime(start_time) <= datetime('now', '+24 hours')")
        pending_decisions = self.store.count('decisions', "approved IS NULL")
        
        return {
            'running': self.running,
            'cycles_completed': self.cycle_count,
            'last_cycle': latest_cycle[0] if latest_cycle else None,
            'collectors': collector_status,
            'governance': governance_status,
            'counts': {
                'pending_tasks': task_count,
                'pending_emails': email_count,
                'events_today': event_count,
                'pending_decisions': pending_decisions
            }
        }


def run_once():
    """Run a single autonomous cycle."""
    loop = AutonomousLoop()
    result = loop.run_cycle()
    return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='MOH TIME OS Autonomous Loop')
    parser.add_argument('command', choices=['run', 'status', 'sync'], 
                        help='Command to run')
    parser.add_argument('--source', help='Specific source to sync')
    
    args = parser.parse_args()
    
    loop = AutonomousLoop()
    
    if args.command == 'run':
        result = loop.run_cycle()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get('success') else 1)
    
    elif args.command == 'status':
        status = loop.get_status()
        print(json.dumps(status, indent=2))
    
    elif args.command == 'sync':
        result = loop.collectors.force_sync(args.source)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
