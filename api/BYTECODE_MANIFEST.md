# Bytecode Manifest

Total functions: 140
Total SQL queries: 67

## Functions

### root (line 59)
- Args: []
- Bytecode: 54 bytes
- Doc: Serve the dashboard UI.

### ApprovalAction (line 67)
- Args: []
- Bytecode: 44 bytes
- Doc: ApprovalAction

### ModeChange (line 71)
- Args: []
- Bytecode: 44 bytes
- Doc: ModeChange

### get_overview (line 77)
- Args: []
- Bytecode: 756 bytes
- Doc: Get dashboard overview with priorities, calendar, decisions, anomalies.
- SQL queries: 3
  ```sql
  SELECT * FROM events WHERE date(start_time) = ? ORDER BY start_time
  ```
  ```sql
  SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC LIMIT 5
  ```
  ```sql
  SELECT * FROM insights WHERE type = 'anomaly' AND (expires_at IS NULL OR expires_at > datetime('now')) ORDER BY created_at DESC LIMIT 5
  ```

### get_time_blocks (line 125)
- Args: ['date', 'lane']
- Bytecode: 702 bytes
- Doc: Get time blocks for a given date.

### get_time_summary (line 163)
- Args: ['date']
- Bytecode: 246 bytes
- Doc: Get time summary for a date.

### get_time_brief (line 185)
- Args: ['date', 'format']
- Bytecode: 138 bytes
- Doc: Get a brief time overview.

### schedule_task (line 198)
- Args: ['task_id', 'block_id', 'date']
- Bytecode: 246 bytes
- Doc: Schedule a task into a time block.

### unschedule_task (line 217)
- Args: ['task_id']
- Bytecode: 96 bytes
- Doc: Unschedule a task from its time block.

### get_commitments (line 230)
- Args: ['status', 'limit']
- Bytecode: 418 bytes
- Doc: Get all commitments.

### get_untracked_commitments (line 259)
- Args: ['limit']
- Bytecode: 298 bytes
- Doc: Get commitments that aren't linked to tasks.

### get_commitments_due (line 283)
- Args: ['date']
- Bytecode: 388 bytes
- Doc: Get commitments due by a date.

### get_commitments_summary (line 312)
- Args: []
- Bytecode: 78 bytes
- Doc: Get commitments summary statistics.

### link_commitment (line 321)
- Args: ['commitment_id', 'task_id']
- Bytecode: 96 bytes
- Doc: Link a commitment to a task.

### mark_commitment_done (line 332)
- Args: ['commitment_id']
- Bytecode: 92 bytes
- Doc: Mark a commitment as done.

### get_capacity_lanes (line 345)
- Args: []
- Bytecode: 54 bytes
- Doc: Get capacity lanes configuration.

### get_capacity_utilization (line 354)
- Args: ['start_date', 'end_date']
- Bytecode: 292 bytes
- Doc: Get capacity utilization metrics.

### get_capacity_forecast (line 375)
- Args: ['days']
- Bytecode: 270 bytes
- Doc: Get capacity forecast for upcoming days.

### get_capacity_debt (line 392)
- Args: ['lane']
- Bytecode: 54 bytes
- Doc: Get capacity debt (overcommitments).

### accrue_debt (line 401)
- Args: ['hours']
- Bytecode: 54 bytes
- Doc: Record accrued capacity debt.

### resolve_debt (line 410)
- Args: ['debt_id']
- Bytecode: 60 bytes
- Doc: Resolve a capacity debt item.

### get_clients_health (line 421)
- Args: ['limit']
- Bytecode: 146 bytes
- Doc: Get client health overview.
- SQL queries: 1
  ```sql
  
        SELECT * FROM clients 
        ORDER BY 
            CASE relationship_health 
                WHEN 'critical' THEN 1 
                WHEN 'poor' THEN 2 
                WHEN 'needs_attentio
  ```

### get_at_risk_clients (line 443)
- Args: ['limit']
- Bytecode: 146 bytes
- Doc: Get clients that are at risk.
- SQL queries: 1
  ```sql
  
        SELECT * FROM clients 
        WHERE relationship_health IN ('poor', 'critical')
           OR (financial_ar_outstanding > 50000 AND financial_ar_aging IN ('60+', '90+'))
        ORDER BY 
  
  ```

### get_client_health (line 462)
- Args: ['client_id']
- Bytecode: 118 bytes
- Doc: Get detailed health for a specific client.

### get_client_projects (line 471)
- Args: ['client_id']
- Bytecode: 128 bytes
- Doc: Get projects for a client.
- SQL queries: 1
  ```sql
  SELECT * FROM projects WHERE client_id = ? ORDER BY updated_at DESC
  ```

### link_project_to_client (line 481)
- Args: ['project_id', 'client_id']
- Bytecode: 146 bytes
- Doc: Link a project to a client.

### get_linking_stats (line 488)
- Args: []
- Bytecode: 166 bytes
- Doc: Get statistics about project-client linking.

### get_tasks (line 505)
- Args: ['status', 'project', 'assignee', 'limit']
- Bytecode: 478 bytes
- Doc: Get tasks with optional filters.
- SQL queries: 1
  ```sql
  
        SELECT * FROM tasks 
        WHERE 
  ```

### TaskCreate (line 536)
- Args: []
- Bytecode: 76 bytes
- Doc: TaskCreate

### TaskUpdate (line 548)
- Args: []
- Bytecode: 76 bytes
- Doc: TaskUpdate

### get_task (line 559)
- Args: ['task_id']
- Bytecode: 118 bytes
- Doc: Get a specific task.

### create_task (line 568)
- Args: ['task']
- Bytecode: 760 bytes
- Doc: Create a new task.

### update_task (line 606)
- Args: ['task_id', 'task']
- Bytecode: 658 bytes
- Doc: Update a task.

### NoteAdd (line 631)
- Args: []
- Bytecode: 44 bytes
- Doc: NoteAdd

### add_task_note (line 635)
- Args: ['task_id', 'body']
- Bytecode: 510 bytes
- Doc: Add a note to a task.

### delete_task (line 660)
- Args: ['task_id']
- Bytecode: 532 bytes
- Doc: Delete (archive) a task.

### DelegateRequest (line 684)
- Args: []
- Bytecode: 52 bytes
- Doc: DelegateRequest

### EscalateRequest (line 690)
- Args: []
- Bytecode: 48 bytes
- Doc: EscalateRequest

### delegate_task (line 695)
- Args: ['task_id', 'body']
- Bytecode: 756 bytes
- Doc: Delegate a task to someone.

### escalate_task (line 729)
- Args: ['task_id', 'body']
- Bytecode: 774 bytes
- Doc: Escalate a task.

### recall_task (line 760)
- Args: ['task_id']
- Bytecode: 604 bytes
- Doc: Recall a delegated task.

### get_delegations (line 792)
- Args: []
- Bytecode: 142 bytes
- Doc: Get all delegated tasks.
- SQL queries: 1
  ```sql
  
        SELECT * FROM tasks 
        WHERE assignee IS NOT NULL AND assignee != '' 
        AND status NOT IN ('completed', 'done', 'cancelled', 'deleted')
        ORDER BY delegated_at DESC
    
  ```

### get_data_quality (line 810)
- Args: []
- Bytecode: 794 bytes
- Doc: Get data quality metrics and cleanup suggestions.
- SQL queries: 5
  ```sql
  
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-30 
  ```
  ```sql
  
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-14 
  ```
  ```sql
  
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now')
    
  ```
  ```sql
  
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status = 'pending' AND (due_date IS NULL OR due_date = '')
    
  ```
  ```sql
  
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status = 'pending' AND (project IS NULL OR project = '')
    
  ```

### _get_cleanup_suggestions (line 878)
- Args: ['store']
- Bytecode: 390 bytes
- Doc: Generate cleanup suggestions based on data quality issues.
- SQL queries: 2
  ```sql
  
        SELECT id, title FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-30 days')
  ```
  ```sql
  
        SELECT id, title FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-14 days')
  ```

### CleanupRequest (line 920)
- Args: []
- Bytecode: 52 bytes
- Doc: CleanupRequest

### cleanup_ancient_tasks (line 925)
- Args: ['confirm']
- Bytecode: 622 bytes
- Doc: Archive tasks that are >30 days overdue.
- SQL queries: 1
  ```sql
  
        SELECT id, title FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-30 days')
  ```

### cleanup_stale_tasks (line 962)
- Args: ['confirm']
- Bytecode: 626 bytes
- Doc: Archive tasks that are 14-30 days overdue.
- SQL queries: 1
  ```sql
  
        SELECT id, title FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-14 days')
  ```

### recalculate_priorities (line 1002)
- Args: []
- Bytecode: 468 bytes
- Doc: Recalculate priorities for all pending tasks.
- SQL queries: 1
  ```sql
  
        SELECT * FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
    
  ```

### _calculate_realistic_priority (line 1032)
- Args: ['task', 'today']
- Bytecode: 810 bytes
- Doc: Calculate a realistic priority score for a task.

### preview_cleanup (line 1083)
- Args: ['cleanup_type']
- Bytecode: 246 bytes
- Doc: Preview what would be affected by a cleanup operation.
- SQL queries: 2
  ```sql
  
            SELECT id, title, due_date, project, assignee FROM tasks
            WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
              AND due_date IS NOT NULL
             
  ```
  ```sql
  
            SELECT id, title, due_date, project, assignee FROM tasks
            WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
              AND due_date IS NOT NULL
             
  ```

### get_team (line 1117)
- Args: []
- Bytecode: 234 bytes
- Doc: Get team members.
- SQL queries: 1
  ```sql
  SELECT * FROM people ORDER BY name
  ```

### get_projects (line 1133)
- Args: ['client_id', 'include_archived', 'limit']
- Bytecode: 360 bytes
- Doc: Get projects list.
- SQL queries: 1
  ```sql
  
        SELECT * FROM projects 
        WHERE 
  ```

### api_calendar (line 1162)
- Args: ['start_date', 'end_date', 'view']
- Bytecode: 454 bytes
- Doc: Get calendar events.
- SQL queries: 1
  ```sql
  
        SELECT * FROM events 
        WHERE date(start_time) >= ? AND date(start_time) <= ?
        ORDER BY start_time
    
  ```

### api_delegations (line 1189)
- Args: []
- Bytecode: 50 bytes
- Doc: Get delegated tasks (alias).

### api_inbox (line 1195)
- Args: ['limit']
- Bytecode: 146 bytes
- Doc: Get inbox items (unprocessed communications, new tasks, etc.).
- SQL queries: 1
  ```sql
  
        SELECT * FROM communications 
        WHERE processed = 0 OR processed IS NULL
        ORDER BY received_at DESC
        LIMIT ?
    
  ```

### api_insights (line 1208)
- Args: ['limit']
- Bytecode: 146 bytes
- Doc: Get insights.
- SQL queries: 1
  ```sql
  
        SELECT * FROM insights 
        WHERE expires_at IS NULL OR expires_at > datetime('now')
        ORDER BY created_at DESC
        LIMIT ?
    
  ```

### api_decisions (line 1221)
- Args: ['limit']
- Bytecode: 146 bytes
- Doc: Get pending decisions.
- SQL queries: 1
  ```sql
  
        SELECT * FROM decisions 
        WHERE approved IS NULL
        ORDER BY created_at DESC
        LIMIT ?
    
  ```

### api_priority_complete (line 1234)
- Args: ['item_id']
- Bytecode: 560 bytes
- Doc: Complete a priority item (task).

### api_priority_snooze (line 1257)
- Args: ['item_id', 'days']
- Bytecode: 678 bytes
- Doc: Snooze a priority item.

### api_priority_delegate (line 1284)
- Args: ['item_id', 'to']
- Bytecode: 988 bytes
- Doc: Delegate a priority item.
- SQL queries: 2
  ```sql
  SELECT * FROM tasks WHERE id = ?
  ```
  ```sql
  SELECT id, name FROM people WHERE name = ?
  ```

### api_decision (line 1333)
- Args: ['decision_id', 'action']
- Bytecode: 688 bytes
- Doc: Process a decision (approve/reject).
- SQL queries: 1
  ```sql
  SELECT * FROM decisions WHERE id = ?
  ```

### api_bundles (line 1361)
- Args: ['status', 'domain', 'limit']
- Bytecode: 66 bytes
- Doc: Get change bundles.

### api_bundles_rollbackable (line 1368)
- Args: []
- Bytecode: 60 bytes
- Doc: Get bundles that can be rolled back.

### get_bundles_summary (line 1375)
- Args: []
- Bytecode: 316 bytes
- Doc: Get summary of bundle activity.
- SQL queries: 1
  ```sql
  
        SELECT * FROM change_bundles 
        ORDER BY created_at DESC 
        LIMIT 10
    
  ```

### rollback_last_bundle (line 1400)
- Args: ['domain']
- Bytecode: 146 bytes
- Doc: Rollback the most recent bundle.

### api_bundle_get (line 1417)
- Args: ['bundle_id']
- Bytecode: 78 bytes
- Doc: Get a specific bundle.

### api_bundle_rollback (line 1426)
- Args: ['bundle_id']
- Bytecode: 112 bytes
- Doc: Rollback a specific bundle.

### api_calibration_last (line 1442)
- Args: []
- Bytecode: 50 bytes
- Doc: Get last calibration results.

### api_calibration_run (line 1448)
- Args: []
- Bytecode: 54 bytes
- Doc: Run calibration.

### FeedbackRequest (line 1457)
- Args: []
- Bytecode: 48 bytes
- Doc: FeedbackRequest

### api_feedback (line 1463)
- Args: ['feedback']
- Bytecode: 274 bytes
- Doc: Submit feedback on a recommendation or action.

### get_priorities (line 1484)
- Args: ['limit', 'context']
- Bytecode: 184 bytes
- Doc: Get prioritized items.

### complete_item (line 1494)
- Args: ['item_id']
- Bytecode: 52 bytes
- Doc: Complete a priority item.

### snooze_item (line 1500)
- Args: ['item_id', 'hours']
- Bytecode: 374 bytes
- Doc: Snooze a priority item.

### DelegateAction (line 1517)
- Args: []
- Bytecode: 48 bytes
- Doc: DelegateAction

### delegate_item (line 1522)
- Args: ['item_id', 'body']
- Bytecode: 308 bytes
- Doc: Delegate a priority item.

### get_priorities_filtered (line 1541)
- Args: ['project', 'assignee', 'status', 'min_score', 'max_score', 'limit']
- Bytecode: 1022 bytes
- Doc: Get filtered priority items.

### BulkAction (line 1578)
- Args: []
- Bytecode: 48 bytes
- Doc: BulkAction

### bulk_action (line 1584)
- Args: ['body']
- Bytecode: 1634 bytes
- Doc: Perform bulk actions on priority items.

### SavedFilter (line 1629)
- Args: []
- Bytecode: 44 bytes
- Doc: SavedFilter

### get_saved_filters (line 1634)
- Args: []
- Bytecode: 120 bytes
- Doc: Get saved filters.
- SQL queries: 1
  ```sql
  SELECT * FROM saved_filters ORDER BY name
  ```

### advanced_filter (line 1641)
- Args: ['q', 'project', 'assignee', 'status', 'min_score', 'max_score', 'tags', 'due_range', 'sort', 'order', 'limit', 'offset']
- Bytecode: 2708 bytes
- Doc: Advanced priority filtering with more options.

### advanced_filter.has_tags (line 1707)
- Args: ['item']
- Bytecode: 424 bytes
- Doc: tags

### archive_stale (line 1739)
- Args: ['days_threshold']
- Bytecode: 348 bytes
- Doc: Archive stale priority items.
- SQL queries: 1
  ```sql
  
        SELECT id, title FROM tasks
        WHERE status = 'pending' 
        AND updated_at < ?
        AND snoozed_until IS NULL
    
  ```

### get_events (line 1759)
- Args: ['hours']
- Bytecode: 326 bytes
- Doc: Get upcoming events.
- SQL queries: 1
  ```sql
  
        SELECT * FROM events 
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time
    
  ```

### get_day_analysis (line 1776)
- Args: ['date', 'context']
- Bytecode: 50 bytes
- Doc: Get analysis for a specific day.

### get_week_analysis (line 1784)
- Args: []
- Bytecode: 46 bytes
- Doc: Get analysis for the current week.

### get_emails (line 1792)
- Args: ['actionable_only', 'unread_only', 'limit']
- Bytecode: 290 bytes
- Doc: Get emails from communications.
- SQL queries: 1
  ```sql
  
        SELECT * FROM communications 
        WHERE 
  ```

### mark_email_actionable (line 1812)
- Args: ['email_id']
- Bytecode: 142 bytes
- Doc: Mark an email as actionable.

### get_insights (line 1819)
- Args: ['category']
- Bytecode: 296 bytes
- Doc: Get insights.
- SQL queries: 1
  ```sql
  
        SELECT * FROM insights 
        WHERE 
  ```

### get_anomalies (line 1838)
- Args: []
- Bytecode: 142 bytes
- Doc: Get anomalies.
- SQL queries: 1
  ```sql
  
        SELECT * FROM insights 
        WHERE type = 'anomaly' 
        AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY severity DESC, created_at DESC
    
  ```

### get_notifications (line 1851)
- Args: ['include_dismissed', 'limit']
- Bytecode: 240 bytes
- Doc: Get notifications.
- SQL queries: 1
  ```sql
  
        SELECT * FROM notifications 
        WHERE 
  ```

### get_notification_stats (line 1868)
- Args: []
- Bytecode: 110 bytes
- Doc: Get notification statistics.

### dismiss_notification (line 1877)
- Args: ['notif_id']
- Bytecode: 142 bytes
- Doc: Dismiss a notification.

### dismiss_all_notifications (line 1884)
- Args: []
- Bytecode: 238 bytes
- Doc: Dismiss all notifications.
- SQL queries: 1
  ```sql
  SELECT id FROM notifications WHERE dismissed = 0 OR dismissed IS NULL
  ```

### get_approvals (line 1898)
- Args: []
- Bytecode: 142 bytes
- Doc: Get pending approvals.
- SQL queries: 1
  ```sql
  SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC
  ```

### process_approval (line 1905)
- Args: ['decision_id', 'action']
- Bytecode: 52 bytes
- Doc: Process an approval.

### ModifyApproval (line 1911)
- Args: []
- Bytecode: 44 bytes
- Doc: ModifyApproval

### modify_approval (line 1915)
- Args: ['decision_id', 'body']
- Bytecode: 300 bytes
- Doc: Modify and approve a decision.

### get_governance_status (line 1934)
- Args: []
- Bytecode: 134 bytes
- Doc: Get governance configuration and status.

### set_governance_mode (line 1944)
- Args: ['domain', 'body']
- Bytecode: 214 bytes
- Doc: Set governance mode for a domain.

### ThresholdUpdate (line 1955)
- Args: []
- Bytecode: 44 bytes
- Doc: ThresholdUpdate

### set_governance_threshold (line 1959)
- Args: ['domain', 'body']
- Bytecode: 108 bytes
- Doc: Set confidence threshold for a domain.

### get_governance_history (line 1966)
- Args: ['limit']
- Bytecode: 146 bytes
- Doc: Get governance action history.
- SQL queries: 1
  ```sql
  
        SELECT * FROM governance_history 
        ORDER BY created_at DESC 
        LIMIT ?
    
  ```

### activate_emergency_brake (line 1978)
- Args: ['reason']
- Bytecode: 68 bytes
- Doc: Activate emergency brake.

### release_emergency_brake (line 1985)
- Args: []
- Bytecode: 62 bytes
- Doc: Release emergency brake.

### get_sync_status (line 1994)
- Args: []
- Bytecode: 50 bytes
- Doc: Get sync status for all collectors.

### force_sync (line 2000)
- Args: ['source']
- Bytecode: 58 bytes
- Doc: Force a sync operation.

### run_analysis (line 2007)
- Args: []
- Bytecode: 54 bytes
- Doc: Run analysis.

### run_cycle (line 2014)
- Args: []
- Bytecode: 106 bytes
- Doc: Run a full autonomous cycle.

### get_status (line 2022)
- Args: []
- Bytecode: 168 bytes
- Doc: Get system status.

### health_check (line 2033)
- Args: []
- Bytecode: 88 bytes
- Doc: Health check endpoint.

### get_summary (line 2039)
- Args: []
- Bytecode: 434 bytes
- Doc: Get a comprehensive summary.
- SQL queries: 1
  ```sql
  
        SELECT COUNT(*) as cnt FROM tasks 
        WHERE status = 'pending' AND due_date < date('now')
    
  ```

### search_items (line 2070)
- Args: ['q', 'limit']
- Bytecode: 510 bytes
- Doc: Search across tasks, projects, and clients.
- SQL queries: 3
  ```sql
  
        SELECT 'task' as type, id, title, status, project FROM tasks 
        WHERE title LIKE ? OR description LIKE ?
        LIMIT ?
    
  ```
  ```sql
  
        SELECT 'project' as type, id, name as title, status FROM projects 
        WHERE name LIKE ?
        LIMIT ?
    
  ```
  ```sql
  
        SELECT 'client' as type, id, name as title, tier FROM clients 
        WHERE name LIKE ?
        LIMIT ?
    
  ```

### get_team_workload (line 2102)
- Args: []
- Bytecode: 142 bytes
- Doc: Get team workload distribution.
- SQL queries: 1
  ```sql
  
        SELECT 
            assignee,
            COUNT(*) as total,
            SUM(CASE WHEN due_date < date('now') THEN 1 ELSE 0 END) as overdue,
            MAX(priority) as max_priority
        
  ```

### get_grouped_priorities (line 2123)
- Args: ['group_by', 'limit']
- Bytecode: 266 bytes
- Doc: Get priorities grouped by a field.

### get_clients (line 2156)
- Args: ['tier', 'health', 'ar_status', 'active_only', 'limit']
- Bytecode: 1116 bytes
- Doc: Get clients with filters.
- SQL queries: 4
  ```sql
  
            SELECT DISTINCT client_id FROM tasks 
            WHERE client_id IS NOT NULL 
            AND (updated_at >= date('now', '-90 days') OR status = 'pending')
            UNION
            
  ```
  ```sql
  
        SELECT * FROM clients 
        WHERE 
  ```
  ```sql
  SELECT COUNT(*) as cnt FROM projects WHERE client_id = ? AND enrollment_status = 'enrolled'
  ```
  ```sql
  SELECT COUNT(*) as cnt FROM tasks WHERE client_id = ? AND status = 'pending'
  ```

### get_client_portfolio (line 2234)
- Args: []
- Bytecode: 530 bytes
- Doc: Get client portfolio overview.
- SQL queries: 5
  ```sql
  
        SELECT 
            tier,
            COUNT(*) as count,
            SUM(financial_ar_outstanding) as total_ar,
            SUM(CASE WHEN relationship_health IN ('poor', 'critical') THEN 1 EL
  ```
  ```sql
  
        SELECT 
            relationship_health as health,
            COUNT(*) as count
        FROM clients
        WHERE relationship_health IS NOT NULL
        GROUP BY relationship_health
    
  ```
  ```sql
  
        SELECT * FROM clients 
        WHERE (tier IN ('A', 'B') AND relationship_health IN ('poor', 'critical'))
           OR (financial_ar_outstanding > 100000 AND financial_ar_aging = '90+')
    
  ```
  ```sql
  
        SELECT 
            COUNT(*) as total_clients,
            SUM(financial_ar_outstanding) as total_ar,
            SUM(financial_annual_value) as total_annual_value
        FROM clients
    
  ```
  ```sql
  
        SELECT 
            COUNT(*) as count,
            COALESCE(SUM(financial_ar_outstanding), 0) as total
        FROM clients
        WHERE financial_ar_outstanding > 0 
        AND financial_a
  ```

### get_client_detail (line 2292)
- Args: ['client_id']
- Bytecode: 470 bytes
- Doc: Get detailed client information.
- SQL queries: 3
  ```sql
  SELECT * FROM projects WHERE client_id = ? ORDER BY updated_at DESC
  ```
  ```sql
  SELECT * FROM tasks WHERE client_id = ? AND status = 'pending' ORDER BY priority DESC LIMIT 20
  ```
  ```sql
  SELECT * FROM communications WHERE client_id = ? ORDER BY received_at DESC LIMIT 10
  ```

### ClientUpdate (line 2325)
- Args: []
- Bytecode: 64 bytes
- Doc: ClientUpdate

### update_client (line 2333)
- Args: ['client_id', 'body']
- Bytecode: 350 bytes
- Doc: Update client information.

### get_projects (line 2348)
- Args: ['client_id', 'include_archived', 'limit']
- Bytecode: 360 bytes
- Doc: Get projects with filters.
- SQL queries: 1
  ```sql
  
        SELECT * FROM projects 
        WHERE 
  ```

### get_project_candidates (line 2373)
- Args: []
- Bytecode: 142 bytes
- Doc: Get projects that could be enrolled.
- SQL queries: 1
  ```sql
  
        SELECT * FROM projects 
        WHERE (enrollment_status IS NULL OR enrollment_status = 'candidate')
        ORDER BY updated_at DESC
    
  ```

### get_enrolled_projects (line 2385)
- Args: []
- Bytecode: 142 bytes
- Doc: Get enrolled projects.
- SQL queries: 1
  ```sql
  
        SELECT * FROM projects 
        WHERE enrollment_status = 'enrolled'
        ORDER BY updated_at DESC
    
  ```

### EnrollmentAction (line 2397)
- Args: []
- Bytecode: 52 bytes
- Doc: EnrollmentAction

### process_enrollment (line 2403)
- Args: ['project_id', 'body']
- Bytecode: 548 bytes
- Doc: Process project enrollment action.

### detect_new_projects (line 2431)
- Args: ['force']
- Bytecode: 142 bytes
- Doc: Detect new projects from tasks.
- SQL queries: 1
  ```sql
  
        SELECT DISTINCT project as name, COUNT(*) as task_count
        FROM tasks 
        WHERE project IS NOT NULL AND project != ''
        AND project NOT IN (SELECT name FROM projects)
        
  ```

### get_project_detail (line 2447)
- Args: ['project_id']
- Bytecode: 296 bytes
- Doc: Get detailed project information.
- SQL queries: 1
  ```sql
  SELECT * FROM tasks WHERE project = ? ORDER BY priority DESC
  ```

### sync_xero (line 2467)
- Args: []
- Bytecode: 58 bytes
- Doc: Sync with Xero.

### bulk_link_tasks (line 2474)
- Args: []
- Bytecode: 22 bytes
- Doc: Bulk link tasks to projects/clients.

### propose_project (line 2481)
- Args: ['name', 'client_id', 'type']
- Bytecode: 226 bytes
- Doc: Propose a new project.

### get_email_queue (line 2504)
- Args: ['limit']
- Bytecode: 538 bytes
- Doc: Get email queue.
- SQL queries: 1
  ```sql
  
        SELECT * FROM communications 
        WHERE type = 'email' AND (processed = 0 OR processed IS NULL)
        ORDER BY received_at DESC
        LIMIT ?
    
  ```

### dismiss_email (line 2530)
- Args: ['email_id']
- Bytecode: 72 bytes
- Doc: Dismiss an email.

### get_weekly_digest (line 2537)
- Args: []
- Bytecode: 676 bytes
- Doc: Get weekly digest.
- SQL queries: 3
  ```sql
  
        SELECT * FROM tasks 
        WHERE status = 'completed' AND updated_at >= ?
        ORDER BY updated_at DESC
    
  ```
  ```sql
  
        SELECT * FROM tasks 
        WHERE status = 'pending' AND due_date < date('now') AND due_date >= ?
        ORDER BY due_date ASC
    
  ```
  ```sql
  
        SELECT COUNT(*) as cnt FROM tasks 
        WHERE status = 'archived' AND updated_at >= ?
    
  ```

### BlockerRequest (line 2583)
- Args: []
- Bytecode: 44 bytes
- Doc: BlockerRequest

### add_blocker (line 2587)
- Args: ['task_id', 'body']
- Bytecode: 576 bytes
- Doc: Add a blocker to a task.

### remove_blocker (line 2613)
- Args: ['task_id', 'blocker_id']
- Bytecode: 428 bytes
- Doc: Remove a blocker from a task.

### get_dependencies (line 2635)
- Args: []
- Bytecode: 598 bytes
- Doc: Get task dependency graph.
- SQL queries: 1
  ```sql
  
        SELECT * FROM tasks 
        WHERE status = 'pending' AND blockers IS NOT NULL AND blockers != '' AND blockers != '[]'
        ORDER BY priority DESC
    
  ```

### spa_fallback (line 2674)
- Args: ['path']
- Bytecode: 126 bytes
- Doc: Serve the SPA for all non-API routes.

### main (line 2684)
- Args: []
- Bytecode: 64 bytes
- Doc: Run the server.

