"""
Capacity Command Engine - Page 7 LOCKED SPEC (v1)

Lane Reality + Delegation Control. Operating system for time.

Hard rule: no calendar clone, no raw task browsing. Capacity is surfaced as
constraints + moves, with drill-down evidence.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from lib import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.db_path()


# ==============================================================================
# ENUMS & TYPES (per spec)
# ==============================================================================


class Mode(StrEnum):
    OPS_HEAD = "Ops Head"
    CO_FOUNDER = "Co-Founder"
    ARTIST = "Artist"


class Horizon(StrEnum):
    NOW = "NOW"
    TODAY = "TODAY"
    THIS_WEEK = "THIS WEEK"


class MoveType(StrEnum):
    """Move types per §Zone D (immutable)"""

    LANE_BOTTLENECK = "LANE_BOTTLENECK"
    PERSON_OVERLOAD = "PERSON_OVERLOAD"
    MEETING_OVERLOAD = "MEETING_OVERLOAD"
    FRAGMENTATION = "FRAGMENTATION"
    DELEGATION_NEEDED = "DELEGATION_NEEDED"
    SCHEDULE_GAP = "SCHEDULE_GAP"
    UNKNOWN_TRIAGE = "UNKNOWN_TRIAGE"


class RiskBand(StrEnum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class ActionRisk(StrEnum):
    AUTO = "auto"
    PROPOSE = "propose"
    APPROVAL = "approval"


# ==============================================================================
# DATACLASSES
# ==============================================================================


@dataclass
class LaneData:
    """Per-lane capacity data"""

    lane: str
    weekly_hours: float
    buffer_pct: float
    effective_capacity: float  # weekly_hours * (1 - buffer_pct)
    hours_available: float
    hours_needed: float
    gap_hours: float
    gap_ratio: float
    confidence: Confidence
    why_low: list[str]


@dataclass
class PersonData:
    """Per-person capacity data"""

    person_id: str
    name: str
    lane: str
    hours_needed: float
    hours_available: float
    gap_hours: float
    risk_band: RiskBand
    confidence: Confidence
    why_low: list[str]


@dataclass
class CapacityMove:
    """A capacity move/action card"""

    move_id: str
    type: MoveType
    label: str
    score: float
    time_to_consequence_hours: float | None
    impact_hours: float
    confidence: Confidence
    why_low: list[str]
    primary_action: dict
    secondary_actions: list[dict]
    evidence_ids: list[str]
    # For internal scoring
    impact: float = 0.0
    urgency: float = 0.0
    controllability: float = 0.0


# ==============================================================================
# ENGINE
# ==============================================================================


class CapacityCommandPage7Engine:
    """
    Generates Capacity Command snapshot per Page 7 LOCKED SPEC.

    Scoring formula (§5.5):
    BaseScore = w_I*Impact + w_U*Urgency + w_C*Controllability + w_Q*Confidence
    Weights: w_I=0.35, w_U=0.25, w_C=0.25, w_Q=0.15
    """

    # Hard caps per §8.2
    MAX_MOVES = 7
    MAX_LANES = 6
    MAX_PEOPLE = 5
    MAX_DRAWER_EVIDENCE = 7
    MAX_FIXES_ACTIONS = 5

    # Scoring weights per §5.5 (LOCKED)
    W_I = 0.35  # Impact
    W_U = 0.25  # Urgency
    W_C = 0.25  # Controllability
    W_Q = 0.15  # Confidence

    # Mode multipliers per §5.6 (LOCKED)
    MODE_MULTIPLIERS = {
        Mode.OPS_HEAD: {
            MoveType.LANE_BOTTLENECK: 1.15,
            MoveType.SCHEDULE_GAP: 1.10,
            MoveType.DELEGATION_NEEDED: 1.05,
            MoveType.MEETING_OVERLOAD: 0.95,
        },
        Mode.CO_FOUNDER: {
            MoveType.DELEGATION_NEEDED: 1.15,
            MoveType.LANE_BOTTLENECK: 1.05,
            MoveType.MEETING_OVERLOAD: 1.05,
            MoveType.SCHEDULE_GAP: 0.95,
        },
        Mode.ARTIST: {
            MoveType.FRAGMENTATION: 1.20,
            MoveType.SCHEDULE_GAP: 1.10,
            MoveType.MEETING_OVERLOAD: 1.00,
            MoveType.DELEGATION_NEEDED: 0.85,
        },
    }

    # Default lanes (fallback if no task lanes found)
    DEFAULT_LANES = ["ops", "finance", "client", "creative", "production", "growth"]

    def _discover_lanes_from_tasks(self) -> list[str]:
        """Discover actual lanes used in tasks, ordered by task count."""
        rows = self._query_all("""
            SELECT lane_id AS lane, COUNT(*) as cnt FROM tasks
            WHERE lane_id IS NOT NULL AND lane_id != ''
            AND status NOT IN ('done', 'completed')
            GROUP BY lane_id
            ORDER BY cnt DESC
            LIMIT 10
        """)
        task_lanes = [r["lane"] for r in rows if r.get("lane")]

        # Use actual task lanes, or defaults if none found
        if task_lanes:
            return task_lanes[: self.MAX_LANES]
        return self.DEFAULT_LANES[: self.MAX_LANES]

    # Buffer percentage default
    DEFAULT_BUFFER_PCT = 0.20

    def __init__(
        self,
        db_path: Path = DB_PATH,
        mode: Mode = Mode.OPS_HEAD,
        horizon: Horizon = Horizon.TODAY,
    ):
        self.db_path = db_path
        self.mode = mode
        self.horizon = horizon
        self.now = datetime.now()
        self.today = date.today()

        # Trust state
        self.data_integrity = True
        self.capacity_baseline = True
        self.tasks_lane_coverage_pct = 100.0
        self.duration_missing_pct = 0.0
        self.calendar_last_sync_at: str | None = None
        self.reality_gap_confidence = Confidence.HIGH

        # Cache
        self._lanes_cache: dict[str, LaneData] = {}
        self._people_cache: dict[str, PersonData] = {}
        self._tasks_cache: list[dict] = []
        self._events_cache: list[dict] = []

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def _query_one(self, sql: str, params: tuple = ()) -> dict | None:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        except sqlite3.OperationalError:
            return None
        finally:
            conn.close()

    def _query_scalar(self, sql: str, params: tuple = ()) -> Any:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row[0] if row else None
        except sqlite3.OperationalError:
            return None
        finally:
            conn.close()

    # ==========================================================================
    # TRUST & GATES (§1.2)
    # ==========================================================================

    def _load_trust_state(self):
        """Load trust state and validate capacity baseline."""
        # Check if capacity_lanes table exists and has valid data
        lanes = self._query_all("""
            SELECT name AS lane, weekly_hours, buffer_pct
            FROM capacity_lanes
            WHERE weekly_hours > 0
        """)

        if not lanes:
            # Try to get lanes from tasks
            task_lanes = self._query_all("""
                SELECT DISTINCT lane_id AS lane FROM tasks WHERE lane_id IS NOT NULL AND lane_id != ''
            """)
            self.capacity_baseline = len(task_lanes) > 0
        else:
            # Validate all lanes have weekly_hours > 0
            self.capacity_baseline = all(lane.get("weekly_hours", 0) > 0 for lane in lanes)

        # Calendar sync
        last_sync = self._query_one("""
            SELECT MAX(synced_at) as last_sync FROM calendar_events
        """)
        if last_sync and last_sync.get("last_sync"):
            self.calendar_last_sync_at = last_sync["last_sync"]

        # Lane coverage
        total_tasks = (
            self._query_scalar("""
            SELECT COUNT(*) FROM tasks WHERE status NOT IN ('done', 'completed')
        """)
            or 0
        )

        tasks_with_lane = (
            self._query_scalar("""
            SELECT COUNT(*) FROM tasks
            WHERE status NOT IN ('done', 'completed')
            AND (lane_id IS NOT NULL AND lane_id != '')
        """)
            or 0
        )

        if total_tasks > 0:
            self.tasks_lane_coverage_pct = (tasks_with_lane / total_tasks) * 100

        # Duration missing
        tasks_with_duration = (
            self._query_scalar("""
            SELECT COUNT(*) FROM tasks
            WHERE status NOT IN ('done', 'completed')
            AND duration_min IS NOT NULL AND duration_min > 0
        """)
            or 0
        )

        if total_tasks > 0:
            self.duration_missing_pct = ((total_tasks - tasks_with_duration) / total_tasks) * 100

        # Reality gap confidence per §5.4
        self._compute_reality_gap_confidence()

    def _compute_reality_gap_confidence(self):
        """Compute reality gap confidence per §5.4."""
        why_low = []

        if not self.capacity_baseline:
            why_low.append("capacity baseline invalid")
            self.reality_gap_confidence = Confidence.LOW
            return

        # Check calendar recency
        if self.calendar_last_sync_at:
            try:
                sync_time = datetime.fromisoformat(
                    self.calendar_last_sync_at.replace("Z", "+00:00")
                )
                hours_ago = (self.now - sync_time.replace(tzinfo=None)).total_seconds() / 3600
                if hours_ago > 24:
                    why_low.append(f"calendar stale ({hours_ago:.0f}h)")
            except (ValueError, TypeError, AttributeError) as e:
                # Internal metadata - malformed value indicates bug
                logger.warning(f"Invalid calendar_last_sync_at value: {e}")
                why_low.append("calendar sync time invalid")
        else:
            why_low.append("no calendar sync")

        if self.tasks_lane_coverage_pct < 50:
            why_low.append(f"lane coverage {self.tasks_lane_coverage_pct:.0f}% < 50%")
        elif self.tasks_lane_coverage_pct < 80:
            why_low.append(f"lane coverage {self.tasks_lane_coverage_pct:.0f}% < 80%")

        if self.duration_missing_pct > 10:
            why_low.append(f"duration missing {self.duration_missing_pct:.0f}%")

        # Determine confidence level
        if not self.capacity_baseline or self.tasks_lane_coverage_pct < 50:
            self.reality_gap_confidence = Confidence.LOW
        elif len(why_low) > 0:
            self.reality_gap_confidence = Confidence.MED
        else:
            self.reality_gap_confidence = Confidence.HIGH

        self._why_low = why_low[:3]

    def _get_trust_dict(self) -> dict:
        """Build trust dict for snapshot."""
        return {
            "data_integrity": self.data_integrity,
            "capacity_baseline": self.capacity_baseline,
            "tasks_lane_coverage_pct": round(self.tasks_lane_coverage_pct, 1),
            "duration_missing_pct": round(self.duration_missing_pct, 1),
            "calendar_last_sync_at": self.calendar_last_sync_at,
            "reality_gap_confidence": self.reality_gap_confidence.value,
            "why_low": getattr(self, "_why_low", []),
        }

    # ==========================================================================
    # LANE COMPUTATIONS (§2.1, §2.2, §2.3)
    # ==========================================================================

    def _get_lane_baselines(self) -> dict[str, dict]:
        """Get lane baseline configurations from discovered task lanes.

        Priority:
        1. Real calendar data from team_capacity + team_members
        2. Static config from capacity_lanes
        3. Default 40h
        """
        # Discover lanes from actual tasks (ordered by task count)
        discovered_lanes = self._discover_lanes_from_tasks()

        # Get REAL capacity from team calendars
        real_capacity = {}
        calendar_rows = self._query_all("""
            SELECT
                tm.default_lane as lane,
                COUNT(*) as people,
                SUM(tc.available_hours) as available_hours,
                SUM(tc.meeting_hours) as meeting_hours
            FROM team_members tm
            JOIN team_capacity tc ON tm.email = tc.email
            GROUP BY tm.default_lane
        """)
        for row in calendar_rows:
            lane = row.get("lane", "").lower()
            if lane:
                real_capacity[lane] = {
                    "weekly_hours": row.get("available_hours", 0) or 0,
                    "buffer_pct": 0,  # Already accounts for meetings
                    "from_calendar": True,
                    "people_count": row.get("people", 0),
                }

        # Get configured lanes from capacity_lanes table (fallback)
        configured = {}
        config_rows = self._query_all("""
            SELECT name AS lane, weekly_hours, buffer_pct
            FROM capacity_lanes
        """)
        for row in config_rows:
            configured[row["lane"].lower()] = {
                "weekly_hours": row.get("weekly_hours", 40) or 40,
                "buffer_pct": row.get("buffer_pct", self.DEFAULT_BUFFER_PCT)
                or self.DEFAULT_BUFFER_PCT,
            }

        # Build baselines: prefer real calendar data
        baselines = {}
        for lane in discovered_lanes:
            lane_key = lane.lower()
            if lane_key in real_capacity:
                baselines[lane] = real_capacity[lane_key]
            elif lane_key in configured:
                baselines[lane] = configured[lane_key]
            else:
                baselines[lane] = {
                    "weekly_hours": 40,
                    "buffer_pct": self.DEFAULT_BUFFER_PCT,
                }

        return baselines

    def _get_horizon_multiplier(self) -> float:
        """Get multiplier for converting weekly to horizon-specific hours."""
        if self.horizon == Horizon.NOW:
            return 4 / 40  # 4 hours of a 40-hour week
        if self.horizon == Horizon.TODAY:
            return 1 / 5  # 1 day of 5-day week
        # THIS_WEEK
        return 1.0

    def _resolve_task_lane(self, task: dict) -> str:
        """Resolve lane for a task using inheritance chain per §2.1."""
        # 1. task.lane (direct assignment)
        if task.get("lane") and task["lane"].strip():
            return task["lane"]

        # 2. project.lane_mapping (if task has project_id)
        # NOTE: projects table has no lane column yet; skip this fallback.
        # When a lane column is added to projects, uncomment and query it.

        # 3. assignee.default_lane
        if task.get("assignee"):
            person = self._query_one(
                """
                SELECT default_lane FROM team_members WHERE name = ? OR id = ?
            """,
                (task["assignee"], task["assignee"]),
            )
            if person and person.get("default_lane"):
                return person["default_lane"]

        # 4. fallback: "ops" (lowercase to match actual data)
        return "ops"

    def _load_tasks_for_horizon(self) -> list[dict]:
        """Load tasks relevant to current horizon.

        Only includes tasks with actual due dates in the horizon window.
        Tasks without due dates are NOT included (they're backlog).
        Overdue tasks ARE included as they need to be done.
        """
        if self.horizon == Horizon.NOW:
            # Next 4 hours - urgent tasks due today or overdue
            end_date = self.today.isoformat()
            sql = """
                SELECT t.id, t.title, t.lane_id AS lane, t.project_id, t.assignee, t.duration_min, t.due_date, t.status,
                       COALESCE(p.name, t.project) as project
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.status NOT IN ('done', 'completed')
                AND t.due_date IS NOT NULL
                AND t.due_date <= ?
            """
            params = (end_date,)
        elif self.horizon == Horizon.TODAY:
            # Today's tasks - due today or overdue (need to catch up)
            end_date = self.today.isoformat()
            sql = """
                SELECT t.id, t.title, t.lane_id AS lane, t.project_id, t.assignee, t.duration_min, t.due_date, t.status,
                       COALESCE(p.name, t.project) as project
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.status NOT IN ('done', 'completed')
                AND t.due_date IS NOT NULL
                AND t.due_date <= ?
            """
            params = (end_date,)
        else:  # THIS_WEEK
            # This week's tasks - due within 7 days or overdue
            end_date = (self.today + timedelta(days=7)).isoformat()
            sql = """
                SELECT t.id, t.title, t.lane_id AS lane, t.project_id, t.assignee, t.duration_min, t.due_date, t.status,
                       COALESCE(p.name, t.project) as project
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.status NOT IN ('done', 'completed')
                AND t.due_date IS NOT NULL
                AND t.due_date <= ?
            """
            params = (end_date,)

        tasks = self._query_all(sql, params)

        # Resolve lanes and add to cache
        for task in tasks:
            task["resolved_lane"] = self._resolve_task_lane(task)

        self._tasks_cache = tasks
        return tasks

    def _load_calendar_events(self) -> tuple[float, float, float, int, int]:
        """Load calendar events and compute meeting/focus hours."""
        # Get events for horizon
        if self.horizon == Horizon.NOW:
            start = self.now
            end = self.now + timedelta(hours=4)
        elif self.horizon == Horizon.TODAY:
            start = datetime.combine(self.today, datetime.min.time())
            end = datetime.combine(self.today, datetime.max.time())
        else:
            start = datetime.combine(self.today, datetime.min.time())
            end = datetime.combine(self.today + timedelta(days=7), datetime.max.time())

        events = self._query_all(
            """
            SELECT id, title, start_time, end_time, event_type, is_focus_block
            FROM calendar_events
            WHERE start_time >= ? AND end_time <= ?
        """,
            (start.isoformat(), end.isoformat()),
        )

        self._events_cache = events

        meeting_hours = 0.0
        focus_hours = 0.0
        meeting_count = 0
        focus_count = 0

        for event in events:
            try:
                start_dt = datetime.fromisoformat(event["start_time"])
                end_dt = datetime.fromisoformat(event["end_time"])
                duration_hours = (end_dt - start_dt).total_seconds() / 3600

                if event.get("is_focus_block"):
                    focus_hours += duration_hours
                    focus_count += 1
                else:
                    meeting_hours += duration_hours
                    meeting_count += 1
            except (ValueError, TypeError, KeyError) as e:
                logger.debug(f"Could not parse event times: {e}")

        # Compute largest contiguous focus window
        largest_focus = self._compute_largest_contiguous_focus(events, start, end)

        return meeting_hours, focus_hours, largest_focus, meeting_count, focus_count

    def _compute_largest_contiguous_focus(
        self, events: list[dict], start: datetime, end: datetime
    ) -> float:
        """Compute largest contiguous focus window in hours."""
        if not events:
            # If no events, entire window is free
            return (end - start).total_seconds() / 3600

        # Sort events by start time
        sorted_events = []
        for e in events:
            if not e.get("is_focus_block"):  # Only consider non-focus events as blockers
                try:
                    sorted_events.append(
                        {
                            "start": datetime.fromisoformat(e["start_time"]),
                            "end": datetime.fromisoformat(e["end_time"]),
                        }
                    )
                except (ValueError, TypeError, KeyError) as exc:
                    logger.debug(f"Could not parse event for focus window calc: {exc}")

        if not sorted_events:
            return (end - start).total_seconds() / 3600

        sorted_events.sort(key=lambda x: x["start"])

        # Find gaps between events
        gaps = []
        current = start

        for event in sorted_events:
            if event["start"] > current:
                gap = (event["start"] - current).total_seconds() / 3600
                gaps.append(gap)
            current = max(current, event["end"])

        # Final gap after last event
        if current < end:
            gaps.append((end - current).total_seconds() / 3600)

        return max(gaps) if gaps else 0.0

    def build_lanes(self) -> list[LaneData]:
        """Build lane data with availability and demand."""
        baselines = self._get_lane_baselines()
        tasks = self._load_tasks_for_horizon()
        meeting_hours, focus_hours, _, _, _ = self._load_calendar_events()

        horizon_mult = self._get_horizon_multiplier()

        lanes = []
        for lane_name, config in baselines.items():
            weekly = config["weekly_hours"]
            buffer = config["buffer_pct"]
            from_calendar = config.get("from_calendar", False)

            if from_calendar:
                # Calendar data already accounts for meetings - weekly_hours IS available hours
                # Only apply horizon multiplier
                hours_available = weekly * horizon_mult
                effective = hours_available  # No buffer needed
            else:
                # Static config - apply buffer and meeting deduction
                effective = weekly * (1 - buffer) * horizon_mult
                num_lanes = len(baselines)
                meeting_deduction = meeting_hours / num_lanes if num_lanes > 0 else 0
                hours_available = max(0, effective - meeting_deduction)

            # Hours needed from tasks (excluding tracking items, using smart duration)
            from ..task_classification import is_tracking_item
            from ..task_duration import estimate_duration

            lane_tasks = [t for t in tasks if t.get("resolved_lane") == lane_name]
            # Only count actual work, not tracking items
            work_tasks = [t for t in lane_tasks if not is_tracking_item(t)]
            hours_needed = sum(
                estimate_duration(t.get("title", ""), lane_name) / 60 for t in work_tasks
            )

            gap_hours = hours_needed - hours_available
            gap_ratio = (
                gap_hours / hours_available
                if hours_available > 0
                else (1.0 if hours_needed > 0 else 0.0)
            )

            # Confidence
            why_low = []
            if config["weekly_hours"] <= 0:
                why_low.append("invalid weekly hours")
            if len(lane_tasks) == 0 and hours_needed == 0:
                why_low.append("no tasks assigned")
            if not from_calendar:
                why_low.append("no calendar sync - using static baseline")

            confidence = Confidence.HIGH if from_calendar else Confidence.MED
            if why_low:
                confidence = Confidence.LOW
            elif self.tasks_lane_coverage_pct < 80:
                confidence = Confidence.MED
                why_low.append("lane coverage < 80%")

            lane_data = LaneData(
                lane=lane_name,
                weekly_hours=weekly,
                buffer_pct=buffer,
                effective_capacity=effective,
                hours_available=hours_available,
                hours_needed=hours_needed,
                gap_hours=gap_hours,
                gap_ratio=gap_ratio,
                confidence=confidence,
                why_low=why_low[:3],
            )
            lanes.append(lane_data)
            self._lanes_cache[lane_name] = lane_data

        # Sort by gap_ratio descending (worst first)
        lanes.sort(key=lambda x: -x.gap_ratio)

        return lanes[: self.MAX_LANES]

    # ==========================================================================
    # PEOPLE COMPUTATIONS
    # ==========================================================================

    def build_people_overview(self) -> list[PersonData]:
        """Build per-person capacity overview."""
        tasks = self._tasks_cache or self._load_tasks_for_horizon()

        # Group tasks by assignee
        by_person = {}
        for task in tasks:
            assignee = task.get("assignee")
            if not assignee:
                continue
            if assignee not in by_person:
                by_person[assignee] = {
                    "tasks": [],
                    "lane": task.get("resolved_lane", "Ops"),
                }
            by_person[assignee]["tasks"].append(task)

        people = []
        horizon_mult = self._get_horizon_multiplier()

        for person_id, data in by_person.items():
            from ..task_classification import is_tracking_item
            from ..task_duration import estimate_duration

            # Only count actual work, not tracking items
            work_tasks = [t for t in data["tasks"] if not is_tracking_item(t)]
            hours_needed = sum(
                estimate_duration(t.get("title", ""), t.get("resolved_lane")) / 60
                for t in work_tasks
            )

            # Default per-person availability (40h/week with buffer)
            hours_available = 40 * (1 - self.DEFAULT_BUFFER_PCT) * horizon_mult

            gap_hours = hours_needed - hours_available

            # Risk band per §6.5-like logic
            if gap_hours >= 4:
                risk_band = RiskBand.HIGH
            elif gap_hours >= 2:
                risk_band = RiskBand.MED
            else:
                risk_band = RiskBand.LOW

            people.append(
                PersonData(
                    person_id=person_id,
                    name=person_id,
                    lane=data["lane"],
                    hours_needed=hours_needed,
                    hours_available=hours_available,
                    gap_hours=gap_hours,
                    risk_band=risk_band,
                    confidence=Confidence.MED,
                    why_low=["default capacity assumed"]
                    if hours_available == 40 * (1 - self.DEFAULT_BUFFER_PCT) * horizon_mult
                    else [],
                )
            )

        # Sort by gap descending
        people.sort(key=lambda p: -p.gap_hours)

        return people[: self.MAX_PEOPLE]

    # ==========================================================================
    # TILES (§Zone B)
    # ==========================================================================

    def build_tiles(self, lanes: list[LaneData]) -> dict:
        """Build status tiles."""
        meeting_hours, focus_hours, _, _, _ = self._load_calendar_events()

        # Hours available (sum across lanes)
        total_available = sum(lane.hours_available for lane in lanes)

        # Hours needed
        total_needed = sum(lane.hours_needed for lane in lanes)

        # Reality gap per §2.4
        scheduled_work_hours = focus_hours
        reality_gap = total_needed - scheduled_work_hours

        # Time debt per §2.4
        time_debt = max(0, total_needed - (total_available - meeting_hours))

        # Status for available
        if total_available < total_needed * 0.5:
            status = "RED"
        elif total_available < total_needed:
            status = "YELLOW"
        else:
            status = "GREEN"

        return {
            "hours_available": {
                "hours": round(total_available, 1),
                "status": status,
                "confidence": self.reality_gap_confidence.value,
                "why_low": getattr(self, "_why_low", []),
            },
            "hours_needed": {
                "hours": round(total_needed, 1),
            },
            "reality_gap": {
                "hours": round(max(0, reality_gap), 1),
            },
            "time_debt": {
                "hours": round(time_debt, 1),
            },
        }

    # ==========================================================================
    # MOVES (§Zone D, §4, §5)
    # ==========================================================================

    def build_moves(
        self, lanes: list[LaneData], people: list[PersonData], tiles: dict
    ) -> list[CapacityMove]:
        """Build capacity moves with eligibility + scoring + ranking."""
        moves = []

        meeting_hours, focus_hours, largest_focus, _, _ = self._load_calendar_events()
        time_debt = tiles["time_debt"]["hours"]
        reality_gap = tiles["reality_gap"]["hours"]

        # Generate candidate moves

        # 1. Lane bottleneck moves
        for lane in lanes:
            if lane.gap_hours > 0:
                move = self._create_lane_bottleneck_move(lane)
                if move and self._is_move_eligible(
                    move, time_debt, reality_gap, meeting_hours, largest_focus, lanes
                ):
                    moves.append(move)

        # 2. Person overload moves
        for person in people:
            if person.gap_hours > 0:
                move = self._create_person_overload_move(person)
                if move and self._is_move_eligible(
                    move, time_debt, reality_gap, meeting_hours, largest_focus, lanes
                ):
                    moves.append(move)

        # 3. Meeting overload move
        threshold = self._get_meeting_threshold()
        if meeting_hours > threshold:
            move = self._create_meeting_overload_move(meeting_hours, threshold)
            if move and self._is_move_eligible(
                move, time_debt, reality_gap, meeting_hours, largest_focus, lanes
            ):
                moves.append(move)

        # 4. Fragmentation move (if no large focus blocks)
        if largest_focus < 1.5:  # Less than 90 minutes contiguous
            move = self._create_fragmentation_move(largest_focus)
            if move and self._is_move_eligible(
                move, time_debt, reality_gap, meeting_hours, largest_focus, lanes
            ):
                moves.append(move)

        # 5. Schedule gap move
        if reality_gap > 2:
            move = self._create_schedule_gap_move(reality_gap)
            if move and self._is_move_eligible(
                move, time_debt, reality_gap, meeting_hours, largest_focus, lanes
            ):
                moves.append(move)

        # 6. Unknown triage (tasks missing lane/duration)
        missing_count = self._get_missing_data_count()
        if missing_count > 0:
            move = self._create_unknown_triage_move(missing_count)
            if move:
                moves.append(move)

        # Score all moves
        for move in moves:
            self._score_move(move)

        # Sort by score descending
        moves.sort(key=lambda m: -m.score)

        return moves[: self.MAX_MOVES]

    def _get_meeting_threshold(self) -> float:
        """Get meeting overload threshold based on horizon."""
        if self.horizon == Horizon.NOW:
            return 1.5
        if self.horizon == Horizon.TODAY:
            return 4.0
        # 30% of effective capacity
        total_available = sum(lane.effective_capacity for lane in self._lanes_cache.values())
        return total_available * 0.30

    def _is_move_eligible(
        self,
        move: CapacityMove,
        time_debt: float,
        reality_gap: float,
        meeting_hours: float,
        largest_focus: float,
        lanes: list[LaneData],
    ) -> bool:
        """Check move eligibility per §4."""
        if self.horizon == Horizon.NOW:
            # Eligible if any:
            if time_debt > 0:
                return True
            if largest_focus < 1.5:  # No 90-min focus window
                return True
            if any(lane.gap_hours >= 2 for lane in lanes):
                return True
            # Person overload check would be in the move itself
            return move.type == MoveType.PERSON_OVERLOAD and move.impact_hours >= 2

        if self.horizon == Horizon.TODAY:
            if time_debt >= 2:
                return True
            if reality_gap >= 2:
                return True
            if meeting_hours >= 4:
                return True
            return bool(any(lane.gap_hours >= 3 for lane in lanes))

        # THIS_WEEK
        if time_debt >= 6:
            return True
        if any(lane.gap_ratio >= 0.25 for lane in lanes):
            return True
        total_capacity = sum(lane.effective_capacity for lane in lanes)
        if meeting_hours >= total_capacity * 0.30:
            return True
        # Top 2 people overload combined
        return False

        return True  # Default eligible for unknown

    def _create_lane_bottleneck_move(self, lane: LaneData) -> CapacityMove:
        """Create a lane bottleneck move."""
        return CapacityMove(
            move_id=f"move-lane-{lane.lane.lower().replace(' ', '-')}",
            type=MoveType.LANE_BOTTLENECK,
            label=f"{lane.lane} capacity gap",
            score=0.0,
            time_to_consequence_hours=None,
            impact_hours=lane.gap_hours,
            confidence=lane.confidence,
            why_low=lane.why_low,
            primary_action={
                "risk": ActionRisk.PROPOSE.value,
                "label": "Redistribute work",
                "idempotency_key": f"action-redistribute-{lane.lane}",
                "payload": {"lane": lane.lane},
                "why": f"Lane has {lane.gap_hours:.1f}h gap",
            },
            secondary_actions=[
                {
                    "risk": ActionRisk.PROPOSE.value,
                    "label": "Delegate tasks",
                    "idempotency_key": f"action-delegate-{lane.lane}",
                    "payload": {"lane": lane.lane},
                    "why": "Move work to available capacity",
                },
            ],
            evidence_ids=[f"lane:{lane.lane}"],
            impact=min(1.0, lane.gap_hours / 10),
            controllability=0.7,
        )

    def _create_person_overload_move(self, person: PersonData) -> CapacityMove:
        """Create a person overload move."""
        return CapacityMove(
            move_id=f"move-person-{person.person_id.lower().replace(' ', '-')}",
            type=MoveType.PERSON_OVERLOAD,
            label=f"{person.name} overloaded",
            score=0.0,
            time_to_consequence_hours=None,
            impact_hours=person.gap_hours,
            confidence=person.confidence,
            why_low=person.why_low,
            primary_action={
                "risk": ActionRisk.PROPOSE.value,
                "label": "Reassign tasks",
                "idempotency_key": f"action-reassign-{person.person_id}",
                "payload": {"person_id": person.person_id},
                "why": f"{person.name} has {person.gap_hours:.1f}h overload",
            },
            secondary_actions=[],
            evidence_ids=[f"person:{person.person_id}"],
            impact=min(1.0, person.gap_hours / 6),
            controllability=0.7,
        )

    def _create_meeting_overload_move(self, meeting_hours: float, threshold: float) -> CapacityMove:
        """Create a meeting overload move."""
        excess = meeting_hours - threshold
        return CapacityMove(
            move_id="move-meeting-overload",
            type=MoveType.MEETING_OVERLOAD,
            label=f"Meeting overload ({meeting_hours:.1f}h)",
            score=0.0,
            time_to_consequence_hours=None,
            impact_hours=excess,
            confidence=Confidence.HIGH,
            why_low=[],
            primary_action={
                "risk": ActionRisk.PROPOSE.value,
                "label": "Review meetings",
                "idempotency_key": "action-review-meetings",
                "payload": {"excess_hours": excess},
                "why": f"{meeting_hours:.1f}h meetings vs {threshold:.1f}h threshold",
            },
            secondary_actions=[
                {
                    "risk": ActionRisk.PROPOSE.value,
                    "label": "Decline optional meetings",
                    "idempotency_key": "action-decline-optional",
                    "payload": {},
                    "why": "Reclaim focus time",
                },
            ],
            evidence_ids=["calendar:meetings"],
            impact=min(1.0, excess / 4),
            controllability=0.4,  # Meetings harder to control
        )

    def _create_fragmentation_move(self, largest_focus: float) -> CapacityMove:
        """Create a fragmentation move."""
        return CapacityMove(
            move_id="move-fragmentation",
            type=MoveType.FRAGMENTATION,
            label=f"No focus blocks (max {largest_focus:.1f}h)",
            score=0.0,
            time_to_consequence_hours=None,
            impact_hours=1.5 - largest_focus,
            confidence=Confidence.HIGH if self.calendar_last_sync_at else Confidence.LOW,
            why_low=[] if self.calendar_last_sync_at else ["no calendar sync"],
            primary_action={
                "risk": ActionRisk.AUTO.value,
                "label": "Suggest focus block",
                "idempotency_key": "action-suggest-focus",
                "payload": {"min_hours": 1.5},
                "why": "Create contiguous work time",
            },
            secondary_actions=[],
            evidence_ids=["calendar:gaps"],
            impact=0.6,
            controllability=1.0,  # Fully controllable
        )

    def _create_schedule_gap_move(self, reality_gap: float) -> CapacityMove:
        """Create a schedule gap move."""
        return CapacityMove(
            move_id="move-schedule-gap",
            type=MoveType.SCHEDULE_GAP,
            label=f"Schedule gap ({reality_gap:.1f}h unscheduled)",
            score=0.0,
            time_to_consequence_hours=None,
            impact_hours=reality_gap,
            confidence=self.reality_gap_confidence,
            why_low=getattr(self, "_why_low", []),
            primary_action={
                "risk": ActionRisk.PROPOSE.value,
                "label": "Schedule focus blocks",
                "idempotency_key": "action-schedule-focus",
                "payload": {"hours": reality_gap},
                "why": f"{reality_gap:.1f}h planned but not scheduled",
            },
            secondary_actions=[],
            evidence_ids=["calendar:schedule"],
            impact=min(1.0, reality_gap / 6),
            controllability=1.0,
        )

    def _create_unknown_triage_move(self, missing_count: int) -> CapacityMove:
        """Create an unknown triage move for missing data."""
        return CapacityMove(
            move_id="move-unknown-triage",
            type=MoveType.UNKNOWN_TRIAGE,
            label=f"{missing_count} tasks need triage",
            score=0.0,
            time_to_consequence_hours=None,
            impact_hours=0,
            confidence=Confidence.LOW,
            why_low=["missing lane or duration"],
            primary_action={
                "risk": ActionRisk.AUTO.value,
                "label": "Fix task data",
                "idempotency_key": "action-fix-tasks",
                "payload": {"count": missing_count},
                "why": "Complete missing task metadata",
            },
            secondary_actions=[],
            evidence_ids=["tasks:incomplete"],
            impact=0.4,  # Fixed per §5.1
            controllability=0.4,
        )

    def _get_missing_data_count(self) -> int:
        """Count tasks missing lane or duration."""
        return (
            self._query_scalar("""
            SELECT COUNT(*) FROM tasks
            WHERE status NOT IN ('done', 'completed')
            AND (lane IS NULL OR lane = '' OR duration_min IS NULL OR duration_min <= 0)
        """)
            or 0
        )

    def _score_move(self, move: CapacityMove):
        """Score a move per §5."""
        # Impact already set on move
        impact = move.impact

        # Urgency per §5.2
        if move.time_to_consequence_hours is not None:
            urgency = max(0, min(1, 1 - (move.time_to_consequence_hours / 24)))
        else:
            urgency = {
                Horizon.NOW: 1.0,
                Horizon.TODAY: 0.8,
                Horizon.THIS_WEEK: 0.6,
            }.get(self.horizon, 0.7)
        move.urgency = urgency

        # Confidence factor
        conf_factor = {
            Confidence.HIGH: 1.0,
            Confidence.MED: 0.7,
            Confidence.LOW: 0.35,
        }.get(move.confidence, 0.7)

        # Base score
        base_score = (
            self.W_I * impact
            + self.W_U * urgency
            + self.W_C * move.controllability
            + self.W_Q * conf_factor
        )

        # Mode multiplier
        multiplier = self.MODE_MULTIPLIERS.get(self.mode, {}).get(move.type, 1.0)

        move.score = round(base_score * multiplier, 3)

    # ==========================================================================
    # FIXES (§Zone F)
    # ==========================================================================

    def build_fixes(self, lanes: list[LaneData]) -> dict:
        """Build fixes panel data."""
        # Invalid lane baselines
        invalid_baselines = []
        for lane in lanes:
            if lane.weekly_hours <= 0:
                invalid_baselines.append(
                    {
                        "lane": lane.lane,
                        "weekly_hours": lane.weekly_hours,
                    }
                )

        # Missing lane tasks
        missing_lane = (
            self._query_scalar("""
            SELECT COUNT(*) FROM tasks
            WHERE status NOT IN ('done', 'completed')
            AND (lane IS NULL OR lane = '')
        """)
            or 0
        )

        # Missing duration tasks
        missing_duration = (
            self._query_scalar("""
            SELECT COUNT(*) FROM tasks
            WHERE status NOT IN ('done', 'completed')
            AND (duration_min IS NULL OR duration_min <= 0)
        """)
            or 0
        )

        # Suggested actions
        actions = []
        if invalid_baselines:
            actions.append(
                {
                    "risk": ActionRisk.AUTO.value,
                    "label": "Set lane baselines",
                    "idempotency_key": "action-set-baselines",
                    "payload": {"lanes": [b["lane"] for b in invalid_baselines]},
                    "why": f"{len(invalid_baselines)} lanes have invalid capacity",
                }
            )

        if missing_lane > 0:
            actions.append(
                {
                    "risk": ActionRisk.AUTO.value,
                    "label": f"Assign lanes to {missing_lane} tasks",
                    "idempotency_key": "action-assign-lanes",
                    "payload": {"count": missing_lane},
                    "why": "Tasks need lane assignment for capacity tracking",
                }
            )

        if missing_duration > 0:
            actions.append(
                {
                    "risk": ActionRisk.AUTO.value,
                    "label": f"Add durations to {missing_duration} tasks",
                    "idempotency_key": "action-add-durations",
                    "payload": {"count": missing_duration},
                    "why": "Tasks need time estimates",
                }
            )

        return {
            "invalid_lane_baselines": invalid_baselines,
            "missing_lane_tasks": missing_lane,
            "missing_duration_tasks": missing_duration,
            "suggested_actions": actions[: self.MAX_FIXES_ACTIONS],
        }

    # ==========================================================================
    # DRAWERS (§7)
    # ==========================================================================

    def build_drawers(
        self, lanes: list[LaneData], people: list[PersonData], moves: list[CapacityMove]
    ) -> dict:
        """Build drawer data for entities."""
        entities = {}

        # Lane drawers
        for lane in lanes:
            key = f"lane:{lane.lane.lower()}"

            # Get top 5 tasks driving demand
            lane_tasks = [t for t in self._tasks_cache if t.get("resolved_lane") == lane.lane]
            lane_tasks.sort(key=lambda t: -(t.get("duration_min") or 0))

            evidence = [
                {"type": "task", "id": t["id"], "label": t.get("title", "")[:40]}
                for t in lane_tasks[: self.MAX_DRAWER_EVIDENCE]
            ]

            entities[key] = {
                "summary": f"{lane.lane} has {lane.hours_needed:.1f}h needed vs {lane.hours_available:.1f}h available. Gap: {lane.gap_hours:.1f}h.",
                "evidence": evidence,
                "actions": [
                    {
                        "risk": ActionRisk.PROPOSE.value,
                        "label": "Redistribute work",
                        "idempotency_key": f"action-redistribute-{lane.lane}",
                        "payload": {"lane": lane.lane},
                        "why": "Balance capacity across lanes",
                    },
                ],
                "reason": f"{self.horizon.value} | LANE_BOTTLENECK | driver=gap_hours",
            }

        # Person drawers
        for person in people:
            key = f"person:{person.person_id.lower()}"

            person_tasks = [t for t in self._tasks_cache if t.get("assignee") == person.person_id]
            person_tasks.sort(key=lambda t: -(t.get("duration_min") or 0))

            evidence = [
                {"type": "task", "id": t["id"], "label": t.get("title", "")[:40]}
                for t in person_tasks[: self.MAX_DRAWER_EVIDENCE]
            ]

            entities[key] = {
                "summary": f"{person.name} has {person.hours_needed:.1f}h assigned vs {person.hours_available:.1f}h capacity. Gap: {person.gap_hours:.1f}h.",
                "evidence": evidence,
                "actions": [
                    {
                        "risk": ActionRisk.PROPOSE.value,
                        "label": "Reassign tasks",
                        "idempotency_key": f"action-reassign-{person.person_id}",
                        "payload": {"person_id": person.person_id},
                        "why": "Reduce overload",
                    },
                ],
                "reason": f"{self.horizon.value} | PERSON_OVERLOAD | driver=gap_hours",
            }

        # Move drawers
        for move in moves:
            key = f"move:{move.move_id}"
            entities[key] = {
                "summary": move.label,
                "evidence": [{"type": "ref", "id": eid, "label": eid} for eid in move.evidence_ids],
                "actions": [move.primary_action] + move.secondary_actions,
                "reason": f"{self.horizon.value} | {move.type.value} | score={move.score:.2f}",
            }

        return {"entities": entities}

    # ==========================================================================
    # MAIN GENERATE (§8)
    # ==========================================================================

    def generate(self) -> dict:
        """Generate complete capacity_command snapshot per §8."""
        self._load_trust_state()

        # Build lanes
        lanes = self.build_lanes()

        # Build people overview
        people = self.build_people_overview()

        # Build tiles
        tiles = self.build_tiles(lanes)

        # Build moves
        moves = self.build_moves(lanes, people, tiles)

        # Build fixes
        fixes = self.build_fixes(lanes)

        # Build drawers
        drawers = self.build_drawers(lanes, people, moves)

        # Build timeline
        meeting_hours, focus_hours, largest_focus, meeting_count, focus_count = (
            self._load_calendar_events()
        )

        # Find bottleneck lane
        bottleneck_lane = lanes[0] if lanes else None

        return {
            "meta": {
                "generated_at": self.now.isoformat(),
                "mode": self.mode.value,
                "horizon": self.horizon.value,
                "trust": self._get_trust_dict(),
            },
            "tiles": tiles,
            "allocation": {
                "lanes": [
                    {
                        "lane": lane.lane,
                        "hours_needed": round(lane.hours_needed, 1),
                        "hours_available": round(lane.hours_available, 1),
                        "gap_hours": round(lane.gap_hours, 1),
                        "gap_ratio": round(lane.gap_ratio, 2),
                        "confidence": lane.confidence.value,
                        "why_low": lane.why_low,
                    }
                    for lane in lanes
                ],
                "bottleneck_lane": {
                    "lane": bottleneck_lane.lane if bottleneck_lane else None,
                    "gap_ratio": round(bottleneck_lane.gap_ratio, 2) if bottleneck_lane else 0,
                }
                if bottleneck_lane
                else None,
            },
            "timeline": {
                "focus_blocks_count": focus_count,
                "focus_hours": round(focus_hours, 1),
                "meetings_count": meeting_count,
                "meeting_hours": round(meeting_hours, 1),
                "largest_contiguous_focus_hours": round(largest_focus, 1),
            },
            "moves": [
                {
                    "move_id": m.move_id,
                    "type": m.type.value,
                    "label": m.label,
                    "score": m.score,
                    "time_to_consequence_hours": m.time_to_consequence_hours,
                    "impact_hours": round(m.impact_hours, 1),
                    "confidence": m.confidence.value,
                    "why_low": m.why_low,
                    "primary_action": m.primary_action,
                    "secondary_actions": m.secondary_actions,
                    "evidence_ids": m.evidence_ids,
                }
                for m in moves
            ],
            "people_overview": [
                {
                    "person_id": p.person_id,
                    "name": p.name,
                    "lane": p.lane,
                    "hours_needed": round(p.hours_needed, 1),
                    "hours_available": round(p.hours_available, 1),
                    "gap_hours": round(p.gap_hours, 1),
                    "risk_band": p.risk_band.value,
                    "confidence": p.confidence.value,
                    "why_low": p.why_low,
                }
                for p in people
            ],
            "fixes": fixes,
            "drawer": drawers,
        }


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    import json

    engine = CapacityCommandPage7Engine()
    snapshot = engine.generate()
    logger.info(json.dumps(snapshot, indent=2, default=str))
