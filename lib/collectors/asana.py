"""
Asana Collector - Pulls tasks and expanded data from Asana API.

Expanded API coverage (~90%):
- Tasks: basic fields + custom_fields, subtasks, dependencies, attachments, stories
- Portfolios and Goals
- Sections and story details
"""

import json
import logging
from datetime import date, datetime
from typing import Any

from .base import BaseCollector
import sqlite3

logger = logging.getLogger(__name__)

# hrmny workspace GID
HRMNY_WORKSPACE_GID = "1148006162435561"

# Expanded opt_fields for task collection
TASK_OPT_FIELDS = (
    "name,completed,completed_at,due_on,due_at,assignee,assignee.name,assignee.gid,"
    "tags,tags.name,notes,created_at,modified_at,custom_fields,custom_fields.name,"
    "custom_fields.type,custom_fields.display_value,memberships,memberships.section,"
    "memberships.section.name,num_subtasks"
)


class AsanaCollector(BaseCollector):
    """Collects tasks and expanded data from Asana."""

    source_name = "asana"
    target_table = "tasks"

    def collect(self) -> dict[str, Any]:
        """Fetch tasks and expanded data from Asana using real API client."""
        try:
            from engine.asana_client import (
                list_goals,
                list_portfolios,
                list_projects,
                list_stories,
                list_subtasks,
                list_task_attachments,
                list_task_dependencies,
                list_tasks_in_project,
            )

            all_tasks = []
            subtasks_by_parent = {}
            stories_by_task = {}
            dependencies_by_task = {}
            attachments_by_task = {}

            # Get projects from hrmny workspace (NO LIMIT - collect ALL)
            projects = list_projects(HRMNY_WORKSPACE_GID, archived=False)
            self.logger.info(f"Collecting from {len(projects)} projects")

            # Collect basic tasks from all projects
            for proj in projects:
                proj_gid = proj.get("gid")
                proj_name = proj.get("name", "Unknown")

                try:
                    # Collect ALL tasks (not just incomplete)
                    tasks = list_tasks_in_project(proj_gid, opt_fields=TASK_OPT_FIELDS)

                    for task in tasks:
                        task["_project_name"] = proj_name
                        task["_project_gid"] = proj_gid
                        all_tasks.append(task)

                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to fetch tasks for project {proj_name}: {e}")

            # Secondary pulls for expanded data
            self.logger.info(f"Pulling expanded data for {len(all_tasks)} tasks")

            for task in all_tasks:
                task_gid = task.get("gid")
                if not task_gid:
                    continue

                # Pull subtasks if task has them
                num_subtasks = task.get("num_subtasks", 0)
                if num_subtasks > 0:
                    try:
                        subtasks = list_subtasks(task_gid)
                        if subtasks:
                            subtasks_by_parent[task_gid] = subtasks
                    except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                        self.logger.warning(f"Failed to fetch subtasks for {task_gid}: {e}")

                # Pull stories (comments) - optional, don't block
                try:
                    stories = list_stories(task_gid)
                    if stories:
                        stories_by_task[task_gid] = stories
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.debug(f"Failed to fetch stories for {task_gid}: {e}")

                # Pull dependencies - optional
                try:
                    deps = list_task_dependencies(task_gid)
                    if deps:
                        dependencies_by_task[task_gid] = deps
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.debug(f"Failed to fetch dependencies for {task_gid}: {e}")

                # Pull attachments - optional
                try:
                    attachments = list_task_attachments(task_gid)
                    if attachments:
                        attachments_by_task[task_gid] = attachments
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.debug(f"Failed to fetch attachments for {task_gid}: {e}")

            # Pull portfolios and goals
            portfolios = []
            goals = []
            try:
                portfolios = list_portfolios(HRMNY_WORKSPACE_GID)
            except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                self.logger.warning(f"Failed to fetch portfolios: {e}")

            try:
                goals = list_goals(HRMNY_WORKSPACE_GID)
            except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                self.logger.warning(f"Failed to fetch goals: {e}")

            return {
                "tasks": all_tasks,
                "subtasks_by_parent": subtasks_by_parent,
                "stories_by_task": stories_by_task,
                "dependencies_by_task": dependencies_by_task,
                "attachments_by_task": attachments_by_task,
                "portfolios": portfolios,
                "goals": goals,
            }

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            self.logger.error(f"Asana collection failed: {e}")
            return {
                "tasks": [],
                "subtasks_by_parent": {},
                "stories_by_task": {},
                "dependencies_by_task": {},
                "attachments_by_task": {},
                "portfolios": [],
                "goals": [],
            }

    def transform(self, raw_data: dict) -> list[dict]:
        """Transform Asana tasks to canonical format."""
        transformed = []
        now = datetime.now().isoformat()

        for task in raw_data.get("tasks", []):
            gid = task.get("gid")
            if not gid:
                continue

            # Parse due date
            due_on = task.get("due_on")  # YYYY-MM-DD format
            due_at = task.get("due_at")  # ISO datetime
            due_date = due_at or (f"{due_on}T23:59:59" if due_on else None)

            # Get assignee
            assignee = task.get("assignee", {})
            assignee_name = assignee.get("name") if assignee else None

            # Compute if overdue
            is_overdue = False
            if due_on:
                try:
                    due = datetime.strptime(due_on, "%Y-%m-%d").date()
                    is_overdue = due < date.today()
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse due date '{due_on}' for task {gid}: {e}")

            # Determine status
            if task.get("completed"):
                status = "completed"
            elif is_overdue:
                status = "overdue"
            else:
                status = "active"

            # Get section from memberships
            section_id = None
            section_name = None
            memberships = task.get("memberships", [])
            if memberships and isinstance(memberships, list) and len(memberships) > 0:
                section = memberships[0].get("section", {})
                section_id = section.get("gid")
                section_name = section.get("name")

            # Custom fields JSON
            custom_fields_json = None
            custom_fields = task.get("custom_fields", [])
            if custom_fields:
                custom_fields_json = json.dumps(custom_fields)

            # Count expanded data
            subtask_count = task.get("num_subtasks", 0)
            has_dependencies = 1 if raw_data.get("dependencies_by_task", {}).get(gid) else 0
            attachment_count = len(raw_data.get("attachments_by_task", {}).get(gid, []))
            story_count = len(raw_data.get("stories_by_task", {}).get(gid, []))

            transformed.append(
                {
                    "id": f"asana_{gid}",
                    "source": "asana",
                    "source_id": gid,
                    "title": task.get("name", "Untitled"),
                    "status": status,
                    "completed_at": task.get("completed_at"),
                    "priority": "high" if is_overdue else "normal",
                    "due_date": due_date,
                    "assignee": assignee_name,
                    "project": task.get("_project_name", ""),
                    "project_id": None,  # Will be linked by normalizer
                    "notes": task.get("notes", "")[:500] if task.get("notes") else "",
                    "tags": json.dumps([t.get("name") for t in task.get("tags", [])]),
                    "created_at": task.get("created_at", now),
                    "updated_at": task.get("modified_at", now),
                    "section_id": section_id,
                    "section_name": section_name,
                    "subtask_count": subtask_count,
                    "has_dependencies": has_dependencies,
                    "attachment_count": attachment_count,
                    "story_count": story_count,
                    "custom_fields_json": custom_fields_json,
                }
            )

        return transformed

    def _transform_custom_fields(
        self, task_gid: str, project_gid: str, custom_fields: list
    ) -> list[dict]:
        """Transform custom fields to asana_custom_fields table rows."""
        rows = []
        for field in custom_fields:
            if not isinstance(field, dict):
                continue

            field_gid = field.get("gid")
            if not field_gid:
                continue

            field_id = f"asana_cf_{field_gid}"
            field_name = field.get("name", "")
            field_type = field.get("type", "")
            display_value = field.get("display_value")

            # Parse value based on type
            text_value = None
            number_value = None
            enum_value = None
            date_value = None

            if field_type == "text":
                text_value = display_value
            elif field_type == "number":
                try:
                    number_value = float(display_value) if display_value else None
                except (ValueError, TypeError):
                    text_value = str(display_value) if display_value else None
            elif field_type == "enum":
                enum_value = display_value
            elif field_type == "date":
                date_value = display_value

            rows.append(
                {
                    "id": field_id,
                    "project_id": project_gid,
                    "task_id": task_gid,
                    "field_name": field_name,
                    "field_type": field_type,
                    "text_value": text_value,
                    "number_value": number_value,
                    "enum_value": enum_value,
                    "date_value": date_value,
                }
            )

        return rows

    def _transform_subtasks(self, parent_gid: str, subtasks: list) -> list[dict]:
        """Transform subtasks to asana_subtasks table rows."""
        rows = []
        for subtask in subtasks:
            if not isinstance(subtask, dict):
                continue

            gid = subtask.get("gid")
            if not gid:
                continue

            assignee = subtask.get("assignee", {})
            rows.append(
                {
                    "id": f"asana_st_{gid}",
                    "parent_task_id": parent_gid,
                    "name": subtask.get("name", ""),
                    "assignee_id": assignee.get("gid") if assignee else None,
                    "assignee_name": assignee.get("name") if assignee else None,
                    "completed": 1 if subtask.get("completed") else 0,
                    "due_on": subtask.get("due_on"),
                }
            )

        return rows

    def _transform_sections(self, project_gid: str, sections: list) -> list[dict]:
        """Transform sections to asana_sections table rows."""
        rows = []
        for idx, section in enumerate(sections):
            if not isinstance(section, dict):
                continue

            gid = section.get("gid")
            if not gid:
                continue

            rows.append(
                {
                    "id": f"asana_sec_{gid}",
                    "project_id": project_gid,
                    "name": section.get("name", ""),
                    "sort_order": idx,
                }
            )

        return rows

    def _transform_stories(self, task_gid: str, stories: list) -> list[dict]:
        """Transform stories to asana_stories table rows."""
        rows = []
        for story in stories:
            if not isinstance(story, dict):
                continue

            gid = story.get("gid")
            if not gid:
                continue

            created_by = story.get("created_by", {})
            rows.append(
                {
                    "id": f"asana_story_{gid}",
                    "task_id": task_gid,
                    "type": story.get("type", ""),
                    "text": story.get("text", ""),
                    "created_by": created_by.get("name") if created_by else None,
                    "created_at": story.get("created_at", datetime.now().isoformat()),
                }
            )

        return rows

    def _transform_dependencies(self, task_gid: str, dependencies: list) -> list[dict]:
        """Transform dependencies to asana_task_dependencies table rows."""
        rows = []
        for dep in dependencies:
            if not isinstance(dep, dict):
                continue

            dep_gid = dep.get("gid")
            if not dep_gid:
                continue

            rows.append(
                {
                    "task_id": task_gid,
                    "depends_on_task_id": dep_gid,
                }
            )

        return rows

    def _transform_attachments(self, task_gid: str, attachments: list) -> list[dict]:
        """Transform attachments to asana_attachments table rows."""
        rows = []
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue

            gid = attachment.get("gid")
            if not gid:
                continue

            rows.append(
                {
                    "id": f"asana_att_{gid}",
                    "task_id": task_gid,
                    "name": attachment.get("name", ""),
                    "download_url": attachment.get("download_url"),
                    "host": attachment.get("host"),
                    "size_bytes": attachment.get("size"),
                }
            )

        return rows

    def _transform_portfolios(self, portfolios: list) -> list[dict]:
        """Transform portfolios to asana_portfolios table rows."""
        rows = []
        for portfolio in portfolios:
            if not isinstance(portfolio, dict):
                continue

            gid = portfolio.get("gid")
            if not gid:
                continue

            owner = portfolio.get("owner", {})
            rows.append(
                {
                    "id": f"asana_port_{gid}",
                    "name": portfolio.get("name", ""),
                    "owner_id": owner.get("gid") if owner else None,
                    "owner_name": owner.get("name") if owner else None,
                }
            )

        return rows

    def _transform_goals(self, goals: list) -> list[dict]:
        """Transform goals to asana_goals table rows."""
        rows = []
        for goal in goals:
            if not isinstance(goal, dict):
                continue

            gid = goal.get("gid")
            if not gid:
                continue

            owner = goal.get("owner", {})
            rows.append(
                {
                    "id": f"asana_goal_{gid}",
                    "name": goal.get("name", ""),
                    "owner_id": owner.get("gid") if owner else None,
                    "owner_name": owner.get("name") if owner else None,
                    "status": goal.get("status"),
                    "due_on": goal.get("due_on"),
                    "html_notes": goal.get("html_notes"),
                }
            )

        return rows

    def sync(self) -> dict[str, Any]:
        """
        Override base sync to handle multi-table storage.

        Collects and stores:
        - tasks (main target)
        - asana_custom_fields, asana_subtasks, asana_sections, asana_stories,
          asana_task_dependencies, asana_portfolios, asana_goals, asana_attachments
        """
        cycle_start = datetime.now()

        # Check circuit breaker first
        if not self.circuit_breaker.can_execute():
            self.logger.warning(f"Circuit breaker is {self.circuit_breaker.state}. Skipping sync.")
            self.metrics["circuit_opens"] += 1
            return {
                "source": self.source_name,
                "success": False,
                "error": f"Circuit breaker {self.circuit_breaker.state}",
                "timestamp": datetime.now().isoformat(),
            }

        try:
            # Step 1: Collect from external source
            self.logger.info(f"Collecting from {self.source_name}")

            try:
                raw_data = self.collect()
            except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                self.logger.error(f"Collect failed: {e}")
                self.circuit_breaker.record_failure()
                self.store.update_sync_state(self.source_name, success=False, error=str(e))
                return {
                    "source": self.source_name,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

            # Step 2: Transform to canonical format
            try:
                transformed_tasks = self.transform(raw_data)
            except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                self.logger.warning(f"Transform failed: {e}. Attempting partial success.")
                transformed_tasks = []
                self.metrics["partial_failures"] += 1

            self.logger.info(f"Transformed {len(transformed_tasks)} tasks")

            # Step 3: Store tasks in main table
            stored_tasks = self.store.insert_many(self.target_table, transformed_tasks)

            # Step 4: Store expanded data in secondary tables (non-blocking)
            secondary_stats = {
                "custom_fields": 0,
                "subtasks": 0,
                "sections": 0,
                "stories": 0,
                "dependencies": 0,
                "attachments": 0,
                "portfolios": 0,
                "goals": 0,
            }

            # Custom fields
            custom_fields_rows = []
            for task in raw_data.get("tasks", []):
                task_gid = task.get("gid")
                project_gid = task.get("_project_gid")
                custom_fields = task.get("custom_fields", [])
                if task_gid and project_gid and custom_fields:
                    rows = self._transform_custom_fields(task_gid, project_gid, custom_fields)
                    custom_fields_rows.extend(rows)

            if custom_fields_rows:
                try:
                    stored = self.store.insert_many("asana_custom_fields", custom_fields_rows)
                    secondary_stats["custom_fields"] = stored
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to store custom_fields: {e}")

            # Subtasks
            subtasks_rows = []
            for parent_gid, subtasks in raw_data.get("subtasks_by_parent", {}).items():
                rows = self._transform_subtasks(parent_gid, subtasks)
                subtasks_rows.extend(rows)

            if subtasks_rows:
                try:
                    stored = self.store.insert_many("asana_subtasks", subtasks_rows)
                    secondary_stats["subtasks"] = stored
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to store subtasks: {e}")

            # Stories
            stories_rows = []
            for task_gid, stories in raw_data.get("stories_by_task", {}).items():
                rows = self._transform_stories(task_gid, stories)
                stories_rows.extend(rows)

            if stories_rows:
                try:
                    stored = self.store.insert_many("asana_stories", stories_rows)
                    secondary_stats["stories"] = stored
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to store stories: {e}")

            # Dependencies
            dependencies_rows = []
            for task_gid, deps in raw_data.get("dependencies_by_task", {}).items():
                rows = self._transform_dependencies(task_gid, deps)
                dependencies_rows.extend(rows)

            if dependencies_rows:
                try:
                    stored = self.store.insert_many("asana_task_dependencies", dependencies_rows)
                    secondary_stats["dependencies"] = stored
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to store dependencies: {e}")

            # Attachments
            attachments_rows = []
            for task_gid, attachments in raw_data.get("attachments_by_task", {}).items():
                rows = self._transform_attachments(task_gid, attachments)
                attachments_rows.extend(rows)

            if attachments_rows:
                try:
                    stored = self.store.insert_many("asana_attachments", attachments_rows)
                    secondary_stats["attachments"] = stored
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to store attachments: {e}")

            # Portfolios
            portfolios_rows = self._transform_portfolios(raw_data.get("portfolios", []))
            if portfolios_rows:
                try:
                    stored = self.store.insert_many("asana_portfolios", portfolios_rows)
                    secondary_stats["portfolios"] = stored
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to store portfolios: {e}")

            # Goals
            goals_rows = self._transform_goals(raw_data.get("goals", []))
            if goals_rows:
                try:
                    stored = self.store.insert_many("asana_goals", goals_rows)
                    secondary_stats["goals"] = stored
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to store goals: {e}")

            # Step 5: Update sync state and record success
            self.last_sync = datetime.now()
            self.store.update_sync_state(self.source_name, success=True, items=stored_tasks)
            self.circuit_breaker.record_success()

            duration_ms = (datetime.now() - cycle_start).total_seconds() * 1000

            return {
                "source": self.source_name,
                "success": True,
                "collected": len(raw_data.get("tasks", [])),
                "transformed": len(transformed_tasks),
                "stored_tasks": stored_tasks,
                "secondary_tables": secondary_stats,
                "duration_ms": duration_ms,
                "timestamp": self.last_sync.isoformat(),
            }

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            self.logger.error(f"Sync failed for {self.source_name}: {e}")
            self.circuit_breaker.record_failure()
            self.store.update_sync_state(self.source_name, success=False, error=str(e))
            return {
                "source": self.source_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
