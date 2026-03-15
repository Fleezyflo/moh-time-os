"""
Command Center Views for MOH Time OS.

Provides three agency management views:
1. ClientHealthView - client-centric health indicators and status
2. TeamLoadView - team member capacity and workload analysis
3. DecisionQueueView - aggregated queue of items awaiting decision

All views use StateStore for database access and implement defensive querying
against the canonical tables (tasks, clients, projects, team_members, events,
calendar_attendees, commitments, signals, communications, sync_state).
"""

import logging
from datetime import datetime, timedelta, timezone

from lib.state_store import StateStore, get_store

logger = logging.getLogger(__name__)


class ClientHealthView:
    """
    Client-centric health monitoring.
    Provides raw health indicators for each client based on task status,
    meeting frequency, and commitment management. No scoring -- consumers
    interpret the raw data.
    """

    def __init__(self, store: StateStore | None = None):
        self.store = store or get_store()

    def get_client_health(self, days_lookback: int = 90) -> list[dict]:
        """
        Compute health indicators for each active client.

        For each client with active tasks:
        - total_tasks: count of active tasks in their projects
        - overdue_tasks: active tasks past due_date
        - tasks_completed_this_week: done tasks created in last 7 days
        - last_meeting: most recent calendar event mentioning client
        - days_since_last_meeting: computed from last_meeting
        - open_commitments: count of non-closed commitments for client

        Args:
            days_lookback: Filter out tasks older than this (default 90 days)

        Returns:
            List of client dicts sorted by overdue_tasks (descending).
        """
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_lookback)).isoformat()
        today = datetime.now(timezone.utc).isoformat()[:10]

        # Query all clients
        clients = self.store.query(
            "SELECT id, name, relationship_health FROM clients ORDER BY name"
        )

        if not clients:
            logger.debug("No clients found in database")
            return []

        health_data = []

        for client in clients:
            client_id = client.get("id")
            client_name = client.get("name", "Unknown")

            if not client_id:
                continue

            try:
                # Get active tasks for this client
                active_tasks = self.store.query(
                    """
                    SELECT t.id, t.title, t.due_date, t.status, t.created_at
                    FROM tasks t
                    JOIN projects p ON t.project_id = p.id
                    WHERE p.client_id = ? AND t.status IN ('active', 'in_progress')
                    AND t.created_at > ?
                    """,
                    [client_id, cutoff_date],
                )

                total_tasks = len(active_tasks)

                # Count overdue tasks
                overdue_tasks = sum(
                    1
                    for t in active_tasks
                    if t.get("due_date") and t["due_date"] < today and t.get("status") != "done"
                )

                # Get tasks completed this week
                week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
                completed_week = self.store.query(
                    """
                    SELECT COUNT(*) as c FROM tasks t
                    JOIN projects p ON t.project_id = p.id
                    WHERE p.client_id = ? AND t.status = 'done'
                    AND t.updated_at > ?
                    """,
                    [client_id, week_ago],
                )
                tasks_completed_this_week = completed_week[0].get("c", 0) if completed_week else 0

                # Get last meeting from events table (match client name)
                last_meeting = None
                days_since_last_meeting = None
                events = self.store.query(
                    """
                    SELECT start_time FROM events
                    WHERE (title LIKE ? OR summary LIKE ?)
                    ORDER BY start_time DESC LIMIT 1
                    """,
                    [f"%{client_name}%", f"%{client_name}%"],
                )
                if events and events[0].get("start_time"):
                    last_meeting = events[0]["start_time"]
                    try:
                        meeting_dt = datetime.fromisoformat(last_meeting.replace("Z", "+00:00"))
                        days_since_last_meeting = max(
                            0, (datetime.now(timezone.utc) - meeting_dt.replace(tzinfo=None)).days
                        )
                    except (ValueError, AttributeError):
                        days_since_last_meeting = None

                # Get open commitments
                commitments = self.store.query(
                    """
                    SELECT id FROM commitments
                    WHERE target = ? AND status NOT IN ('closed', 'resolved')
                    """,
                    [client_id],
                )
                open_commitments = len(commitments)

                health_data.append(
                    {
                        "client_id": client_id,
                        "client_name": client_name,
                        "total_tasks": total_tasks,
                        "overdue_tasks": overdue_tasks,
                        "tasks_completed_this_week": tasks_completed_this_week,
                        "last_meeting": last_meeting,
                        "days_since_last_meeting": days_since_last_meeting,
                        "open_commitments": open_commitments,
                    }
                )

            except Exception as e:
                logger.error(f"Error computing health for client {client_id} ({client_name}): {e}")
                continue

        # Sort by overdue_tasks descending
        health_data.sort(key=lambda x: -x["overdue_tasks"])

        return health_data

    def get_client_detail(self, client_id: str) -> dict:
        """
        Detailed view for a single client.

        Returns:
        {
            'client': {...client info...},
            'tasks': [...all tasks...],
            'team_members': [...people assigned...],
            'recent_activity': {...last 10 days...},
            'metrics': {...summary metrics...}
        }
        """
        try:
            client = self.store.query("SELECT * FROM clients WHERE id = ?", [client_id])
            if not client:
                logger.warning(f"Client {client_id} not found")
                return {"error": "Client not found", "client_id": client_id}

            client_dict = dict(client[0]) if client else {}

            # Get all tasks
            tasks = self.store.query(
                """
                SELECT t.* FROM tasks t
                JOIN projects p ON t.project_id = p.id
                WHERE p.client_id = ?
                ORDER BY t.due_date ASC
                """,
                [client_id],
            )
            tasks_list = [dict(t) for t in tasks]

            # Get team members assigned to this client
            team_members = self.store.query(
                """
                SELECT DISTINCT tm.id, tm.name, tm.email
                FROM team_members tm
                WHERE tm.id IN (
                    SELECT DISTINCT t.assignee FROM tasks t
                    JOIN projects p ON t.project_id = p.id
                    WHERE p.client_id = ?
                )
                ORDER BY tm.name
                """,
                [client_id],
            )
            team_list = [dict(tm) for tm in team_members]

            # Recent activity (last 10 days)
            ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
            recent = self.store.query(
                """
                SELECT t.id, t.title, t.status, t.updated_at
                FROM tasks t
                JOIN projects p ON t.project_id = p.id
                WHERE p.client_id = ? AND t.updated_at > ?
                ORDER BY t.updated_at DESC
                LIMIT 20
                """,
                [client_id, ten_days_ago],
            )
            recent_activity = [dict(r) for r in recent]

            # Summary metrics
            all_tasks_count = sum(1 for t in tasks_list)
            active_count = sum(
                1 for t in tasks_list if t.get("status") in ("active", "in_progress")
            )
            done_count = sum(1 for t in tasks_list if t.get("status") == "done")

            return {
                "client": client_dict,
                "tasks": tasks_list,
                "team_members": team_list,
                "recent_activity": recent_activity,
                "metrics": {
                    "total_tasks": all_tasks_count,
                    "active_tasks": active_count,
                    "completed_tasks": done_count,
                    "team_size": len(team_list),
                },
            }

        except Exception as e:
            logger.error(f"Error getting client detail for {client_id}: {e}")
            return {"error": str(e), "client_id": client_id}


class TeamLoadView:
    """
    Team capacity and workload analysis.
    Provides raw workload indicators per team member. No scoring -- consumers
    interpret the raw data.
    """

    def __init__(self, store: StateStore | None = None):
        self.store = store or get_store()

    def get_team_load(self) -> list[dict]:
        """
        Compute workload indicators for each team member.

        For each team member:
        - member_id, member_name, member_email
        - active_tasks: count of tasks with status='active' or 'in_progress'
        - overdue_tasks: count of active tasks past due_date
        - meetings_this_week: count of calendar events this week

        Returns:
            List of team member dicts sorted by overdue_tasks (desc),
            then active_tasks (desc).
        """
        today = datetime.now(timezone.utc).isoformat()[:10]
        week_start = (
            datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())
        ).isoformat()[:10]
        week_end = (
            datetime.now(timezone.utc) + timedelta(days=6 - datetime.now(timezone.utc).weekday())
        ).isoformat()[:10]

        # Get all team members
        team_members = self.store.query(
            "SELECT id, name, email, default_lane FROM team_members ORDER BY name"
        )

        if not team_members:
            logger.debug("No team members found in database")
            return []

        load_data = []

        for member in team_members:
            member_id = member.get("id")
            member_name = member.get("name", "Unknown")
            member_email = member.get("email", "")

            if not member_id:
                continue

            try:
                # Count active tasks (by assignee name string, not ID)
                active_tasks = self.store.query(
                    """
                    SELECT id, due_date FROM tasks
                    WHERE assignee = ? AND status IN ('active', 'in_progress')
                    """,
                    [member_name],
                )
                active_count = len(active_tasks)

                # Count overdue tasks
                overdue_count = sum(
                    1 for t in active_tasks if t.get("due_date") and t["due_date"] < today
                )

                # Count meetings this week
                meetings = self.store.query(
                    """
                    SELECT e.id FROM events e
                    JOIN calendar_attendees ca ON ca.event_id = e.id
                    WHERE ca.email = ?
                    AND date(e.start_time) >= ? AND date(e.start_time) <= ?
                    """,
                    [member_email, week_start, week_end],
                )
                meetings_this_week = len(meetings)

                load_data.append(
                    {
                        "member_id": member_id,
                        "member_name": member_name,
                        "member_email": member_email,
                        "active_tasks": active_count,
                        "overdue_tasks": overdue_count,
                        "meetings_this_week": meetings_this_week,
                    }
                )

            except Exception as e:
                logger.error(
                    f"Error computing load for team member {member_id} ({member_name}): {e}"
                )
                continue

        # Sort by overdue_tasks desc, then active_tasks desc
        load_data.sort(key=lambda x: (-x["overdue_tasks"], -x["active_tasks"]))

        return load_data

    def get_member_detail(self, member_name: str) -> dict:
        """
        Detailed view for a single team member.

        Returns:
        {
            'member': {...team member info...},
            'tasks_by_project': {...grouped by project...},
            'overdue_items': [...],
            'calendar_this_week': [...],
            'metrics': {...summary...}
        }
        """
        try:
            # Get team member
            members = self.store.query("SELECT * FROM team_members WHERE name = ?", [member_name])
            if not members:
                logger.warning(f"Team member {member_name} not found")
                return {"error": "Team member not found", "member_name": member_name}

            member_dict = dict(members[0])

            # Get all tasks
            all_tasks = self.store.query(
                """
                SELECT t.*, p.name as project_name FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.assignee = ?
                ORDER BY t.due_date ASC
                """,
                [member_name],
            )
            all_tasks_list = [dict(t) for t in all_tasks]

            # Group tasks by project
            tasks_by_project = {}
            for task in all_tasks_list:
                project_name = task.get("project_name", "No Project")
                if project_name not in tasks_by_project:
                    tasks_by_project[project_name] = []
                tasks_by_project[project_name].append(task)

            # Get overdue items
            today = datetime.now(timezone.utc).isoformat()[:10]
            overdue = [t for t in all_tasks_list if t.get("due_date") and t["due_date"] < today]

            # Get calendar events this week
            week_start = (
                datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())
            ).isoformat()[:10]
            week_end = (
                datetime.now(timezone.utc)
                + timedelta(days=6 - datetime.now(timezone.utc).weekday())
            ).isoformat()[:10]
            email = member_dict.get("email", "")
            calendar_events = []
            if email:
                calendar_events_rows = self.store.query(
                    """
                    SELECT e.* FROM events e
                    JOIN calendar_attendees ca ON ca.event_id = e.id
                    WHERE ca.email = ?
                    AND date(e.start_time) >= ? AND date(e.start_time) <= ?
                    ORDER BY e.start_time
                    """,
                    [email, week_start, week_end],
                )
                calendar_events = [dict(e) for e in calendar_events_rows]

            # Metrics
            total_tasks = len(all_tasks_list)
            active_tasks = sum(
                1 for t in all_tasks_list if t.get("status") in ("active", "in_progress")
            )
            done_tasks = sum(1 for t in all_tasks_list if t.get("status") == "done")

            return {
                "member": member_dict,
                "tasks_by_project": tasks_by_project,
                "overdue_items": overdue,
                "calendar_this_week": calendar_events,
                "metrics": {
                    "total_tasks": total_tasks,
                    "active_tasks": active_tasks,
                    "completed_tasks": done_tasks,
                    "overdue_count": len(overdue),
                    "meetings_this_week": len(calendar_events),
                },
            }

        except Exception as e:
            logger.error(f"Error getting member detail for {member_name}: {e}")
            return {"error": str(e), "member_name": member_name}


class DecisionQueueView:
    """
    Aggregated decision queue for leadership.
    Shows everything awaiting decision/action by Molham.
    """

    def __init__(self, store: StateStore | None = None):
        self.store = store or get_store()

    def get_queue(self, assignee: str = "Molham Homsi") -> dict:
        """
        Aggregate all items awaiting decision.

        Returns:
        {
            'assignee': str,
            'my_tasks': {
                'count': int,
                'items': [...active tasks...],
            },
            'my_overdue': {
                'count': int,
                'items': [...],
            },
            'open_commitments': {
                'count': int,
                'sample': [...first 5...],
            },
            'critical_signals': {
                'count': int,
                'items': [...],
            },
            'pending_responses': {
                'count': int,
                'sample': [...],
            },
            'data_freshness': {
                'source': 'last_sync_time',
                ...
            },
            'queue_summary': {
                'total_items': int,
                'actionable_count': int,
                'overdue_count': int,
            }
        }
        """
        try:
            today = datetime.now(timezone.utc).isoformat()[:10]

            # My tasks (active)
            my_tasks = self.store.query(
                """
                SELECT id, title, due_date, project_id, status
                FROM tasks
                WHERE assignee IN (?, 'me') AND status IN ('active', 'in_progress')
                ORDER BY due_date ASC
                """,
                [assignee],
            )
            my_tasks_list = [dict(t) for t in my_tasks]

            # My overdue
            my_overdue = [t for t in my_tasks_list if t.get("due_date") and t["due_date"] < today]

            # Open commitments
            open_commitments = self.store.query(
                """
                SELECT id, type, speaker, target, deadline, status
                FROM commitments
                WHERE status IN ('open', 'pending', 'active')
                ORDER BY deadline ASC
                LIMIT 20
                """,
            )
            open_commitments_list = [dict(c) for c in open_commitments]
            open_commitments_count = len(open_commitments_list)

            # Critical signals
            critical_signals = self.store.query(
                """
                SELECT signal_key, signal_type, severity, detected_at, resolved_at
                FROM signals
                WHERE severity = 'critical' AND resolved_at IS NULL
                ORDER BY detected_at DESC
                LIMIT 20
                """,
            )
            critical_signals_list = [dict(s) for s in critical_signals]

            # Pending responses (communications)
            pending_responses = self.store.query(
                """
                SELECT id, requires_response, created_at
                FROM communications
                WHERE requires_response = 1
                ORDER BY created_at ASC
                LIMIT 10
                """,
            )
            pending_responses_list = [dict(p) for p in pending_responses]

            # Data freshness (sync state)
            sync_states = self.store.query("SELECT source, last_sync, last_success FROM sync_state")
            freshness = {}
            for row in sync_states:
                freshness[row.get("source", "unknown")] = {
                    "last_sync": row.get("last_sync"),
                    "last_success": row.get("last_success"),
                }

            # Compute queue summary
            total_items = (
                len(my_tasks_list)
                + open_commitments_count
                + len(critical_signals_list)
                + len(pending_responses_list)
            )
            overdue_count = len(my_overdue)
            actionable_count = len([t for t in my_tasks_list if t.get("status") == "active"])

            return {
                "assignee": assignee,
                "my_tasks": {
                    "count": len(my_tasks_list),
                    "items": my_tasks_list,
                },
                "my_overdue": {
                    "count": len(my_overdue),
                    "items": my_overdue,
                },
                "open_commitments": {
                    "count": open_commitments_count,
                    "sample": open_commitments_list[:5],
                },
                "critical_signals": {
                    "count": len(critical_signals_list),
                    "items": critical_signals_list,
                },
                "pending_responses": {
                    "count": len(pending_responses_list),
                    "sample": pending_responses_list[:3],
                },
                "data_freshness": freshness,
                "queue_summary": {
                    "total_items": total_items,
                    "actionable_count": actionable_count,
                    "overdue_count": overdue_count,
                    "requires_attention": overdue_count > 0 or len(critical_signals_list) > 0,
                },
            }

        except Exception as e:
            logger.error(f"Error building decision queue: {e}")
            return {
                "error": str(e),
                "assignee": assignee,
                "queue_summary": {"total_items": 0, "actionable_count": 0, "overdue_count": 0},
            }
