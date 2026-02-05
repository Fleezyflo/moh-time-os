"""
Cron task handlers for MOH Time OS.

These are called by Clawdbot cron jobs:
- morning_brief: Deliver daily brief (09:00)
- daily_sync: Sync from Xero/Asana (06:00)
- daily_backup: Create backup (03:00)
- health_check: Run health check (every 6h)
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from .health import health_check, self_heal
from .backup import create_backup, prune_backups
from .brief import generate_morning_brief, generate_status_summary
from .sync_xero import sync_xero_clients
from .sync_asana import sync_asana_projects
from .maintenance import fix_item_priorities, get_maintenance_report
from .classify import run_auto_classification

log = logging.getLogger("moh_time_os.cron")


def cron_morning_brief() -> str:
    """
    Generate morning brief for delivery.
    
    Called at 09:00 Dubai time.
    Returns formatted brief string.
    """
    log.info("Generating morning brief")
    
    # Run health check first
    report = health_check()
    if report.overall == "FAILED":
        return f"⚠️ **System Health: FAILED**\n\n{report.summary()}\n\nCannot generate brief until system is healthy."
    
    # Generate brief
    brief = generate_morning_brief()
    
    # Add health warning if degraded
    if report.overall == "DEGRADED":
        brief = f"⚠️ *System degraded: {report.summary()}*\n\n" + brief
    
    log.info("Morning brief generated")
    return brief


def cron_daily_sync() -> Dict:
    """
    Run daily data sync.
    
    Called at 06:00 Dubai time.
    Syncs Xero clients and Asana projects.
    """
    log.info("Starting daily sync")
    results = {}
    
    # Xero sync
    try:
        created, updated, skipped, errors = sync_xero_clients()
        results['xero'] = {
            'created': created,
            'updated': updated,
            'errors': len(errors)
        }
        log.info(f"Xero sync: {created} created, {updated} updated")
    except Exception as e:
        results['xero'] = {'error': str(e)}
        log.error(f"Xero sync failed: {e}")
    
    # Asana sync
    try:
        created, updated, matched, skipped, errors = sync_asana_projects()
        results['asana'] = {
            'created': created,
            'updated': updated,
            'matched': matched,
            'errors': len(errors)
        }
        log.info(f"Asana sync: {created} created, {updated} updated")
    except Exception as e:
        results['asana'] = {'error': str(e)}
        log.error(f"Asana sync failed: {e}")
    
    # Recalculate priorities
    try:
        count = fix_item_priorities()
        results['priorities_updated'] = count
    except Exception as e:
        results['priorities_error'] = str(e)
    
    # Run auto-classification
    try:
        class_results = run_auto_classification()
        results['classification'] = class_results['tiers']
    except Exception as e:
        results['classification_error'] = str(e)
    
    log.info("Daily sync complete")
    return results


def cron_daily_backup() -> Dict:
    """
    Run daily backup.
    
    Called at 03:00 Dubai time.
    """
    log.info("Starting daily backup")
    results = {}
    
    # Self-heal first
    heal_actions = self_heal()
    results['self_heal'] = heal_actions
    
    # Create backup
    success, path = create_backup(tag='daily')
    results['backup'] = {
        'success': success,
        'path': path if success else None,
        'error': None if success else path
    }
    
    if success:
        log.info(f"Backup created: {path}")
    else:
        log.error(f"Backup failed: {path}")
    
    # Prune old backups
    deleted = prune_backups(keep=7)
    results['pruned'] = deleted
    
    log.info("Daily backup complete")
    return results


def cron_health_check() -> Dict:
    """
    Run periodic health check.
    
    Called every 6 hours.
    Returns health status.
    """
    log.info("Running health check")
    
    report = health_check()
    
    result = {
        'status': report.overall,
        'checks': {c.name: c.status for c in report.checks},
        'timestamp': report.timestamp
    }
    
    # Self-heal if issues detected
    if report.overall != "HEALTHY":
        heal_actions = self_heal()
        result['heal_actions'] = heal_actions
        
        # Re-check
        report2 = health_check()
        result['status_after_heal'] = report2.overall
    
    log.info(f"Health check: {result['status']}")
    return result


def get_cron_config() -> Dict:
    """
    Get cron job configuration for Clawdbot.
    
    These can be added via the cron tool.
    """
    return {
        'morning_brief': {
            'schedule': '0 9 * * *',  # 09:00 daily
            'timezone': 'Asia/Dubai',
            'task': 'Generate and send morning brief',
            'handler': 'cron_morning_brief'
        },
        'daily_sync': {
            'schedule': '0 6 * * *',  # 06:00 daily
            'timezone': 'Asia/Dubai', 
            'task': 'Sync Xero and Asana data',
            'handler': 'cron_daily_sync'
        },
        'daily_backup': {
            'schedule': '0 3 * * *',  # 03:00 daily
            'timezone': 'Asia/Dubai',
            'task': 'Backup database and prune old backups',
            'handler': 'cron_daily_backup'
        },
        'health_check': {
            'schedule': '0 */6 * * *',  # Every 6 hours
            'timezone': 'Asia/Dubai',
            'task': 'Run health check and self-heal',
            'handler': 'cron_health_check'
        }
    }


def format_sync_report(results: Dict) -> str:
    """Format sync results for notification."""
    lines = ["**Daily Sync Complete**", ""]
    
    if 'xero' in results:
        x = results['xero']
        if 'error' in x:
            lines.append(f"❌ Xero: {x['error']}")
        else:
            lines.append(f"✅ Xero: {x['created']} new, {x['updated']} updated")
    
    if 'asana' in results:
        a = results['asana']
        if 'error' in a:
            lines.append(f"❌ Asana: {a['error']}")
        else:
            lines.append(f"✅ Asana: {a['created']} new, {a['updated']} updated, {a['matched']} linked")
    
    if 'classification' in results:
        c = results['classification']
        if c.get('applied', 0) > 0:
            lines.append(f"🏷️ Classified {c['applied']} clients")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print("=== Cron Configuration ===\n")
    config = get_cron_config()
    for name, cfg in config.items():
        print(f"{name}:")
        print(f"  Schedule: {cfg['schedule']}")
        print(f"  Task: {cfg['task']}")
        print()
