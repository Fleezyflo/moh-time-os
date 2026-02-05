"""
Collector Orchestrator - Manages all collectors and coordinates syncing.
This is the WIRING that connects external data to the state store.
"""

import yaml
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from .tasks import TasksCollector
from .calendar import CalendarCollector
from .gmail import GmailCollector
from .asana import AsanaCollector
from .xero import XeroCollector
from ..state_store import StateStore, get_store


class CollectorOrchestrator:
    """
    Orchestrates all data collectors.
    
    This is WIRING POINT #1:
    External Systems → Collectors → State Store
    """
    
    def __init__(self, config_path: str = None, store: StateStore = None):
        self.config_path = config_path or str(Path(__file__).parent.parent.parent / "config")
        self.store = store or get_store()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.config = self._load_config()
        self.collectors: Dict[str, Any] = {}
        
        self._init_collectors()
    
    def _load_config(self) -> Dict:
        """Load source configuration."""
        config_file = Path(self.config_path) / "sources.yaml"
        if config_file.exists():
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        return {'sources': {}}
    
    def _init_collectors(self):
        """Initialize enabled collectors."""
        # Map config names to collector classes
        collector_map = {
            'tasks': TasksCollector,      # Google Tasks
            'calendar': CalendarCollector,
            'gmail': GmailCollector,
            'asana': AsanaCollector,
            'xero': XeroCollector,
        }
        
        sources = self.config.get('sources', {})
        
        # Always enable core collectors
        core_sources = {
            'tasks': {'enabled': True, 'sync_interval': 300},
            'calendar': {'enabled': True, 'sync_interval': 60},
            'gmail': {'enabled': True, 'sync_interval': 120},
            'asana': {'enabled': True, 'sync_interval': 300},
            'xero': {'enabled': True, 'sync_interval': 300},  # AR/Invoice sync
        }
        
        # Merge config with core
        for name, default_cfg in core_sources.items():
            if name not in sources:
                sources[name] = default_cfg
            elif not sources[name].get('enabled'):
                sources[name]['enabled'] = True
        
        for source_name, source_config in sources.items():
            if not source_config.get('enabled', False):
                continue
            
            collector_class = collector_map.get(source_name)
            if collector_class:
                try:
                    self.collectors[source_name] = collector_class(source_config, self.store)
                    self.logger.info(f"Initialized collector: {source_name}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize {source_name}: {e}")
    
    def sync_all(self) -> Dict[str, Any]:
        """
        Sync all collectors that need syncing.
        Returns results from each collector.
        """
        results = {}
        
        for name, collector in self.collectors.items():
            if collector.should_sync():
                self.logger.info(f"Syncing {name}")
                try:
                    result = collector.sync()
                    results[name] = result
                except Exception as e:
                    self.logger.error(f"Sync failed for {name}: {e}")
                    results[name] = {'success': False, 'error': str(e)}
            else:
                results[name] = {'skipped': True, 'reason': 'Not due for sync'}
        
        return results
    
    def force_sync(self, source: str = None) -> Dict[str, Any]:
        """Force sync regardless of schedule."""
        results = {}
        
        collectors_to_sync = (
            {source: self.collectors[source]} if source and source in self.collectors
            else self.collectors
        )
        
        for name, collector in collectors_to_sync.items():
            self.logger.info(f"Force syncing {name}")
            try:
                result = collector.sync()
                results[name] = result
            except Exception as e:
                self.logger.error(f"Force sync failed for {name}: {e}")
                results[name] = {'success': False, 'error': str(e)}
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all collectors."""
        sync_states = self.store.get_sync_states()
        
        status = {}
        for name, collector in self.collectors.items():
            state = sync_states.get(name, {})
            status[name] = {
                'enabled': True,
                'last_sync': state.get('last_sync'),
                'last_success': state.get('last_success'),
                'items_synced': state.get('items_synced', 0),
                'error': state.get('error'),
                'healthy': state.get('error') is None,
                'sync_interval': collector.sync_interval
            }
        
        return status
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all collectors."""
        results = {}
        for name, collector in self.collectors.items():
            try:
                results[name] = collector.health_check()
            except Exception:
                results[name] = False
        return results


def main():
    """CLI entry point."""
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python -m lib.collectors.orchestrator <sync|status>")
        sys.exit(1)
    
    command = sys.argv[1]
    orchestrator = CollectorOrchestrator()
    
    if command == 'sync':
        results = orchestrator.sync_all()
        print(json.dumps(results, indent=2, default=str))
    elif command == 'status':
        status = orchestrator.get_status()
        print(json.dumps(status, indent=2, default=str))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
