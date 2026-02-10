"""
Comms/Commitments Command Engine - Page 4 locked spec implementation.

Produces agency_snapshot.comms_commitments per locked schema.

Key contracts (locked):
- Thread-based view (not inbox)
- Response status: OVERDUE > DUE > WAITING > OK
- expected_response_by derivation (fallback order per §4.2.1)
- Base score: 35% Urgency + 25% Impact + 20% Controllability + 20% Confidence
- Commitment breach: deadline passed + status open
- Hard caps: hot_list 9/25, snippets 8, commitments 5, actions 7/10
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path

from lib import paths

from .scoring import Horizon, Mode

logger = logging.getLogger(__name__)

DB_PATH = paths.db_path()


class ResponseStatus(Enum):
    OVERDUE = "OVERDUE"
    DUE = "DUE"
    WAITING = "WAITING"
    OK = "OK"


class ThreadType(Enum):
    CLIENT_ASK = "Client Ask"
    WE_OWE = "We Owe"
    PAYMENT = "Payment"
    DELIVERY_BLOCKER = "Delivery Blocker"
    RELATIONSHIP = "Relationship"
    INTERNAL_ONLY = "Internal-only"
    UNKNOWN_TRIAGE = "Unknown triage"


class CommitmentType(Enum):
    PROMISE = "promise"
    REQUEST = "request"


class CommitmentStatus(Enum):
    OPEN = "open"
    FULFILLED = "fulfilled"
    BROKEN = "broken"
    CANCELLED = "cancelled"


@dataclass
class Commitment:
    commitment_id: str
    type: str  # promise | request
    text: str
    deadline: str | None
    status: str  # open | fulfilled | broken | cancelled
    confidence: float
    thread_id: str | None = None
    client_id: str | None = None


@dataclass
class ThreadSnippet:
    at: str
    direction: str  # inbound | outbound | unknown
    from_addr: str
    text: str


@dataclass
class LinkedObject:
    type: str  # task | project | invoice | commitment
    id: str
    label: str


@dataclass
class ThreadData:
    thread_id: str
    client_id: str | None
    client_name: str | None
    tier: str | None
    vip: bool
    subject: str
    thread_type: str
    response_status: str
    expected_response_by: str | None
    age_hours: float
    base_score: float
    confidence: str
    why_low: list[str]
    top_reason: str
    # Detail fields
    summary: str = ""
    snippets: list[ThreadSnippet] = field(default_factory=list)
    commitments: list[Commitment] = field(default_factory=list)
    linked_objects: list[LinkedObject] = field(default_factory=list)
    last_inbound_at: datetime | None = None
    link_status: str = "linked"


@dataclass
class CommsAction:
    action_id: str
    risk_level: str  # auto | propose | approval
    label: str
    entity_type: str
    entity_id: str
    idempotency_key: str
    payload: dict
    why: str


class CommsCommitmentsEngine:
    """
    Comms/Commitments Command Engine per Page 4 spec.

    Produces comms_commitments snapshot section with:
    - Executive strip (4 counters)
    - Hot list (ranked threads)
    - Selected thread detail (Thread Room)
    - Global actions
    """

    # Hard caps per §2 (locked)
    MAX_HOT_LIST_DEFAULT = 9
    MAX_HOT_LIST_EXPANDED = 25
    MAX_SNIPPETS = 8
    MAX_COMMITMENTS = 5
    MAX_LINKED_OBJECTS = 5
    MAX_THREAD_ACTIONS = 7
    MAX_GLOBAL_ACTIONS = 10
    MAX_COMMITMENT_RADAR_DEFAULT = 12
    MAX_COMMITMENT_RADAR_EXPANDED = 30

    # Response deadline defaults per §4.2.1 (hours)
    DEADLINE_VIP_HOURS = 6
    DEADLINE_TIER_A_HOURS = 12
    DEADLINE_TIER_B_HOURS = 24
    DEADLINE_TIER_C_HOURS = 48
    DEADLINE_UNLINKED_HOURS = 24

    # Keywords for thread type classification
    PAYMENT_KEYWORDS = [
        "invoice",
        "payment",
        "overdue",
        "billing",
        "po ",
        "purchase order",
        "remittance",
        "receipt",
    ]
    BLOCKER_KEYWORDS = [
        "need",
        "waiting",
        "blocked",
        "missing",
        "asset",
        "approval",
        "feedback",
        "sign off",
        "confirm",
    ]
    RELATIONSHIP_KEYWORDS = [
        "disappointed",
        "unhappy",
        "concerned",
        "escalate",
        "issue",
        "problem",
        "complaint",
        "urgent",
    ]
    REQUEST_KEYWORDS = [
        "can you",
        "could you",
        "please",
        "requesting",
        "need",
        "want",
        "require",
        "asap",
    ]
    PROMISE_KEYWORDS = [
        "will send",
        "i will",
        "we will",
        "i'll",
        "we'll",
        "by tomorrow",
        "by end of",
        "committed",
    ]

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

        # Trust state (set externally)
        self.data_integrity = True
        self.commitment_ready_pct = 100.0
        self.client_coverage_pct = 100.0
        self.comms_link_rate = 100.0
        self.last_gmail_sync_at: str | None = None

        # VIP domains (configurable)
        self.vip_domains: list[str] = []

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _query_one(self, sql: str, params: tuple = ()) -> dict | None:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def generate(
        self, selected_thread_id: str | None = None, expanded: bool = False
    ) -> dict:
        """
        Generate complete comms_commitments section per §8 schema.
        """
        # Get all threads with communications
        threads = self._get_all_threads()

        # Get all commitments
        all_commitments = self._get_all_commitments()

        # Link commitments to threads
        self._link_commitments_to_threads(threads, all_commitments)

        # Compute derived fields for each thread
        for thread in threads:
            self._compute_thread_fields(thread)

        # Filter by eligibility gates
        eligible_threads = self._filter_eligible_threads(threads)

        # Rank threads per §6.4
        ranked_threads = self._rank_threads(eligible_threads)

        # Apply caps
        hot_list_limit = (
            self.MAX_HOT_LIST_EXPANDED if expanded else self.MAX_HOT_LIST_DEFAULT
        )
        hot_list = ranked_threads[:hot_list_limit]

        # Build summary
        summary = self._build_summary(threads, all_commitments)

        # Select thread (default to top)
        if not selected_thread_id and hot_list:
            selected_thread_id = hot_list[0].thread_id

        selected_thread = None
        if selected_thread_id:
            selected_thread = self._build_selected_thread(selected_thread_id, threads)

        # Build global actions
        global_actions = self._build_global_actions(hot_list, all_commitments)

        return {
            "meta": {
                "generated_at": self.now.isoformat(),
                "mode": self.mode.value,
                "horizon": self.horizon.value,
                "trust": {
                    "data_integrity": self.data_integrity,
                    "commitment_ready_pct": self.commitment_ready_pct,
                    "client_coverage_pct": self.client_coverage_pct,
                    "comms_link_rate": self.comms_link_rate,
                    "last_gmail_sync_at": self.last_gmail_sync_at,
                },
            },
            "summary": summary,
            "hot_list": [self._thread_to_hot_list_dict(t) for t in hot_list],
            "selected_thread": self._selected_thread_to_dict(selected_thread)
            if selected_thread
            else None,
            "global_actions": [self._action_to_dict(a) for a in global_actions],
        }

    def _get_all_threads(self) -> list[ThreadData]:
        """Get all communications grouped by thread."""
        # Query communications with client info
        # Adapt to actual schema (from_email not from_address, is_starred/is_important not starred/important)
        rows = self._query_all("""
            SELECT
                c.commitment_id,
                c.thread_id,
                c.from_email,
                c.subject,
                c.snippet,
                c.body_text,
                COALESCE(c.received_at, c.created_at) as received_at,
                c.client_id,
                COALESCE(c.expected_response_by, c.response_deadline) as response_deadline,
                c.requires_response,
                c.link_status,
                COALESCE(c.is_important, 0) as important,
                COALESCE(c.is_starred, 0) as starred,
                COALESCE(c.is_vip, 0) as is_vip_flag,
                cl.name as client_name,
                cl.tier
            FROM communications c
            LEFT JOIN clients cl ON cl.id = c.client_id
            WHERE c.received_at IS NOT NULL OR c.created_at IS NOT NULL
            ORDER BY COALESCE(c.received_at, c.created_at) DESC
        """)

        # Group by thread_id
        threads_map: dict[str, dict] = {}

        for row in rows:
            thread_id = row.get("thread_id") or row.get("commitment_id")

            if thread_id not in threads_map:
                threads_map[thread_id] = {
                    "thread_id": thread_id,
                    "client_id": row.get("client_id"),
                    "client_name": row.get("client_name"),
                    "tier": row.get("tier"),
                    "subject": row.get("subject") or "(No Subject)",
                    "messages": [],
                    "response_deadline": row.get("response_deadline"),
                    "important": row.get("important"),
                    "starred": row.get("starred"),
                    "is_vip_flag": row.get("is_vip_flag"),
                }

            # Add message to thread
            threads_map[thread_id]["messages"].append(
                {
                    "id": row.get("commitment_id"),
                    "from_email": row.get("from_email"),
                    "received_at": row.get("received_at"),
                    "direction": row.get(
                        "link_status"
                    ),  # Using link_status as direction proxy
                    "snippet": row.get("snippet"),
                    "body_text": row.get("body_text"),
                }
            )

            # Update client info if better
            if not threads_map[thread_id]["client_id"] and row.get("client_id"):
                threads_map[thread_id]["client_id"] = row.get("client_id")
                threads_map[thread_id]["client_name"] = row.get("client_name")
                threads_map[thread_id]["tier"] = row.get("tier")

        # Convert to ThreadData objects
        threads = []
        for _tid, data in threads_map.items():
            thread = self._create_thread_data(data)
            threads.append(thread)

        return threads

    def _create_thread_data(self, data: dict) -> ThreadData:
        """Create ThreadData from grouped messages."""
        messages = data.get("messages", [])

        # Determine VIP status per §4.3
        vip = self._is_vip(data)

        # Determine link status
        link_status = "linked" if data.get("client_id") else "unlinked"

        # Find last inbound message
        last_inbound_at = None
        for msg in messages:
            direction = msg.get("direction", "").lower()
            # Inbound = received from external
            if direction == "inbound" or (not direction and msg.get("from_email")):
                try:
                    ts = datetime.fromisoformat(
                        msg["received_at"].replace("Z", "+00:00")
                    )
                    if last_inbound_at is None or ts > last_inbound_at:
                        last_inbound_at = ts.replace(tzinfo=None)
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse received_at: {e}")

        # Fallback to most recent message
        if not last_inbound_at and messages:
            try:
                last_inbound_at = datetime.fromisoformat(
                    messages[0]["received_at"].replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logger.debug(f"Could not parse fallback received_at: {e}")
                last_inbound_at = self.now

        # Compute age
        age_hours = 0.0
        if last_inbound_at:
            age_hours = (self.now - last_inbound_at).total_seconds() / 3600

        # Build snippets
        snippets = []
        for msg in messages[: self.MAX_SNIPPETS]:
            direction = msg.get("direction", "unknown")
            if not direction:
                # Infer direction from email
                direction = "unknown"

            text = msg.get("snippet") or (msg.get("body_text") or "")[:200] or ""

            snippets.append(
                ThreadSnippet(
                    at=msg.get("received_at", ""),
                    direction=direction,
                    from_addr=msg.get("from_email", ""),
                    text=text[:500],  # Cap snippet length
                )
            )

        # Classify thread type
        thread_type = self._classify_thread_type(data, messages)

        return ThreadData(
            thread_id=data["thread_id"],
            client_id=data.get("client_id"),
            client_name=data.get("client_name"),
            tier=data.get("tier"),
            vip=vip,
            subject=data.get("subject", "(No Subject)"),
            thread_type=thread_type,
            response_status="OK",  # Will be computed later
            expected_response_by=data.get("response_deadline"),
            age_hours=age_hours,
            base_score=0.0,  # Will be computed later
            confidence="HIGH",  # Will be computed later
            why_low=[],
            top_reason="",
            summary="",
            snippets=snippets,
            commitments=[],
            linked_objects=[],
            last_inbound_at=last_inbound_at,
            link_status=link_status,
        )

    def _is_vip(self, data: dict) -> bool:
        """Determine VIP status per §4.3 (locked)."""
        # Tier A
        if data.get("tier") == "A":
            return True

        # Important/starred flag
        if data.get("important") or data.get("starred"):
            return True

        # Explicit VIP flag from database
        if data.get("is_vip_flag"):
            return True

        # VIP domain
        messages = data.get("messages", [])
        for msg in messages:
            from_email = msg.get("from_email", "")
            if from_email:
                domain = from_email.split("@")[-1].lower() if "@" in from_email else ""
                if domain in self.vip_domains:
                    return True

        return False

    def _classify_thread_type(self, data: dict, messages: list[dict]) -> str:
        """Classify thread type per §5 (locked taxonomy)."""
        # Combine all text for analysis
        all_text = " ".join(
            [
                (data.get("subject") or "").lower(),
                *[(m.get("snippet") or "").lower() for m in messages],
                *[(m.get("body_text") or "")[:500].lower() for m in messages],
            ]
        )

        # Check for unlinked
        if not data.get("client_id"):
            # Check if actionable per §4.5
            if self._is_actionable_unlinked(all_text, data):
                return ThreadType.UNKNOWN_TRIAGE.value
            return ThreadType.INTERNAL_ONLY.value

        # Payment/Finance keywords
        if any(kw in all_text for kw in self.PAYMENT_KEYWORDS):
            return ThreadType.PAYMENT.value

        # Delivery blocker keywords
        if any(kw in all_text for kw in self.BLOCKER_KEYWORDS):
            # Need to verify it's actually blocking something
            if "waiting" in all_text or "need" in all_text or "blocked" in all_text:
                return ThreadType.DELIVERY_BLOCKER.value

        # Relationship/churn risk
        if any(kw in all_text for kw in self.RELATIONSHIP_KEYWORDS):
            return ThreadType.RELATIONSHIP.value

        # Request inbound (Client Ask)
        if any(kw in all_text for kw in self.REQUEST_KEYWORDS):
            return ThreadType.CLIENT_ASK.value

        # Promise/obligation (We Owe)
        if any(kw in all_text for kw in self.PROMISE_KEYWORDS):
            return ThreadType.WE_OWE.value

        # Default: if linked, assume Client Ask; if unlinked, Unknown triage
        if data.get("client_id"):
            return ThreadType.CLIENT_ASK.value

        return ThreadType.UNKNOWN_TRIAGE.value

    def _is_actionable_unlinked(self, text: str, data: dict) -> bool:
        """Check if unlinked comm is actionable per §4.5."""
        # Check text length
        has_body = len(text) >= 50

        # Check important/vip flag
        is_marked = data.get("important") or data.get("starred")

        if not (has_body or is_marked):
            return False

        # Check for actionable indicators
        has_request = any(
            kw in text for kw in self.REQUEST_KEYWORDS + self.PROMISE_KEYWORDS
        )
        has_payment = any(kw in text for kw in self.PAYMENT_KEYWORDS)
        has_blocker = any(kw in text for kw in self.BLOCKER_KEYWORDS)

        return has_request or has_payment or has_blocker

    def _get_all_commitments(self) -> list[Commitment]:
        """Get all commitments from database."""
        # Adapt to actual schema: source_id/source_type instead of thread_id
        rows = self._query_all("""
            SELECT
                id as commitment_id,
                type,
                text,
                deadline,
                status,
                confidence,
                source_id,
                source_type,
                client_id
            FROM commitments
            WHERE status IN ('open', 'fulfilled', 'broken')
            ORDER BY deadline ASC NULLS LAST
        """)

        commitments = []
        for row in rows:
            # Map source_id to thread_id if source_type is communication
            thread_id = None
            if row.get("source_type") == "communication":
                thread_id = row.get("source_id")

            commitments.append(
                Commitment(
                    commitment_id=row.get("commitment_id", ""),
                    type=row.get("type", "request"),
                    text=row.get("commitment_text", ""),
                    deadline=row.get("due_at"),
                    status=row.get("status", "open"),
                    confidence=row.get("confidence") or 0.5,
                    thread_id=thread_id,
                    client_id=row.get("client_id"),
                )
            )

        return commitments

    def _link_commitments_to_threads(
        self, threads: list[ThreadData], commitments: list[Commitment]
    ):
        """Link commitments to their threads."""
        thread_map = {t.thread_id: t for t in threads}

        for commit in commitments:
            if commit.thread_id and commit.thread_id in thread_map:
                thread_map[commit.thread_id].commitments.append(commit)

    def _compute_thread_fields(self, thread: ThreadData):
        """Compute derived fields for a thread."""
        # Derive expected_response_by per §4.2.1 (fallback order)
        if not thread.expected_response_by:
            thread.expected_response_by = self._derive_expected_response_by(thread)

        # Compute response status per §4.2
        thread.response_status = self._compute_response_status(thread)

        # Compute base score per §6.2
        thread.base_score = self._compute_base_score(thread)

        # Compute confidence per §6.3
        thread.confidence, thread.why_low = self._compute_confidence(thread)

        # Generate top reason
        thread.top_reason = self._generate_top_reason(thread)

        # Generate summary
        thread.summary = self._generate_summary(thread)

        # Link related objects
        thread.linked_objects = self._get_linked_objects(thread)

    def _derive_expected_response_by(self, thread: ThreadData) -> str | None:
        """
        Derive expected_response_by per §4.2.1 (locked fallback order).

        1. If stored: use it
        2. If commitment with deadline: min(deadline)
        3. If VIP: +6h
        4. If tier A: +12h
        5. If tier B: +24h
        6. If tier C: +48h
        7. If unlinked: +24h
        """
        # 1. Already have stored value
        if thread.expected_response_by:
            return thread.expected_response_by

        # 2. Min commitment deadline
        if thread.commitments:
            deadlines = [
                c.due_at for c in thread.commitments if c.due_at and c.status == "open"
            ]
            if deadlines:
                return min(deadlines)

        # 3-7. Derive from tier/VIP
        base_time = thread.last_inbound_at or self.now

        if thread.vip:
            hours = self.DEADLINE_VIP_HOURS
        elif thread.tier == "A":
            hours = self.DEADLINE_TIER_A_HOURS
        elif thread.tier == "B":
            hours = self.DEADLINE_TIER_B_HOURS
        elif thread.tier == "C":
            hours = self.DEADLINE_TIER_C_HOURS
        elif thread.link_status == "unlinked":
            hours = self.DEADLINE_UNLINKED_HOURS
        else:
            hours = self.DEADLINE_TIER_B_HOURS  # Default

        deadline = base_time + timedelta(hours=hours)
        return deadline.isoformat()

    def _compute_response_status(self, thread: ThreadData) -> str:
        """
        Compute response status per §4.2 (locked).

        - OVERDUE: expected_response_by exists and now > expected_response_by
        - DUE: expected_response_by exists and now ≤ expected_response_by and within horizon
        - WAITING: last message was outbound and open commitment awaiting reply
        - OK: none of the above
        """
        if not thread.expected_response_by:
            return ResponseStatus.OK.value

        try:
            expected = datetime.fromisoformat(
                thread.expected_response_by.replace("Z", "+00:00")
            )
            expected = expected.replace(tzinfo=None)
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"Could not parse expected_response_by: {e}")
            return ResponseStatus.OK.value

        # OVERDUE
        if self.now > expected:
            return ResponseStatus.OVERDUE.value

        # DUE (within horizon)
        hours_to_expected = (expected - self.now).total_seconds() / 3600

        if self.horizon == Horizon.NOW:
            threshold = 12
        elif self.horizon == Horizon.TODAY:
            # End of day
            eod = datetime.combine(self.today, datetime.max.time())
            threshold = (eod - self.now).total_seconds() / 3600
        else:  # THIS_WEEK
            threshold = 7 * 24

        if hours_to_expected <= threshold:
            return ResponseStatus.DUE.value

        # Check for WAITING (last outbound + open commitment)
        if thread.snippets:
            last_direction = thread.snippets[0].direction
            if last_direction == "outbound":
                open_commits = [c for c in thread.commitments if c.status == "open"]
                if open_commits:
                    return ResponseStatus.WAITING.value

        return ResponseStatus.OK.value

    def _compute_base_score(self, thread: ThreadData) -> float:
        """
        Compute base thread score per §6.2 (locked).

        BaseScore = 100 * (0.35*Urgency + 0.25*Impact + 0.20*Controllability + 0.20*Confidence)
        """
        urgency = self._compute_urgency(thread)
        impact = self._compute_impact(thread)
        controllability = self._compute_controllability(thread)
        confidence = self._compute_confidence_factor(thread)

        score = 100 * (
            0.35 * urgency + 0.25 * impact + 0.20 * controllability + 0.20 * confidence
        )

        return max(0.0, min(100.0, score))

    def _compute_urgency(self, thread: ThreadData) -> float:
        """Compute urgency factor (0-1) per §6.2."""
        if not thread.expected_response_by:
            return 0.3  # Default low urgency

        try:
            expected = datetime.fromisoformat(
                thread.expected_response_by.replace("Z", "+00:00")
            )
            expected = expected.replace(tzinfo=None)
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"Could not parse expected_response_by for urgency: {e}")
            return 0.3

        hours_diff = (expected - self.now).total_seconds() / 3600

        if hours_diff < 0:
            # Overdue: 0.5 + (hours_overdue / 48), capped at 1
            hours_overdue = abs(hours_diff)
            return min(1.0, 0.5 + hours_overdue / 48)
        # Due: 1 - (hours_to_expected / 48)
        return max(0.0, min(1.0, 1 - hours_diff / 48))

    def _compute_impact(self, thread: ThreadData) -> float:
        """Compute impact factor (0-1) per §6.2."""
        thread_type = thread.thread_type
        tier = thread.tier

        # Tier weights
        tier_weight = {"A": 1.0, "B": 0.7, "C": 0.5}.get(tier, 0.5)

        if thread_type == ThreadType.PAYMENT.value:
            # Check if client has overdue AR
            if thread.client_id:
                has_overdue = self._client_has_overdue_ar(thread.client_id)
                return 1.0 if has_overdue else 0.6
            return 0.6

        if thread_type == ThreadType.DELIVERY_BLOCKER.value:
            return 0.8

        if thread_type == ThreadType.RELATIONSHIP.value:
            return tier_weight

        if thread_type == ThreadType.CLIENT_ASK.value:
            return 0.6 * tier_weight

        if thread_type == ThreadType.UNKNOWN_TRIAGE.value:
            return 0.4

        return 0.5

    def _client_has_overdue_ar(self, client_id: str) -> bool:
        """Check if client has overdue AR."""
        row = self._query_one(
            """
            SELECT COUNT(*) as cnt FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND payment_date IS NULL
            AND due_date < date('now')
        """,
            (client_id,),
        )

        return row and row.get("cnt", 0) > 0

    def _compute_controllability(self, thread: ThreadData) -> float:
        """Compute controllability factor (0-1) per §6.2."""
        # 1 if we can act (reply, assign, schedule)
        # 0.5 if needs third party but we can nudge
        # 0.2 if blocked on them

        if thread.response_status == ResponseStatus.WAITING.value:
            return 0.2  # Waiting on them

        if thread.thread_type == ThreadType.DELIVERY_BLOCKER.value:
            # Check if we're waiting for external input
            text = " ".join([s.text.lower() for s in thread.snippets])
            if "waiting for" in text or "need from" in text:
                return 0.5

        return 1.0  # We can act

    def _compute_confidence_factor(self, thread: ThreadData) -> float:
        """Compute confidence factor (0-1)."""
        base = 1.0

        if thread.link_status == "unlinked":
            base -= 0.3

        if self.commitment_ready_pct < 50:
            base -= 0.2

        # Check body text availability
        has_body = any(s.text and len(s.text) > 50 for s in thread.snippets)
        if not has_body:
            base -= 0.2

        return max(0.0, base)

    def _compute_confidence(self, thread: ThreadData) -> tuple[str, list[str]]:
        """
        Compute confidence label per §6.3 (locked).

        HIGH: linked + commitment_ready >= 50% + has body_text
        MED: linked but limited body_text OR commitment_ready < 50%
        LOW: unlinked OR missing body_text and no strong metadata
        """
        why_low = []

        has_body = any(s.text and len(s.text) > 50 for s in thread.snippets)
        is_linked = thread.link_status == "linked"

        if not is_linked:
            why_low.append("Thread not linked to client")

        if not has_body:
            why_low.append("Limited message content")

        if self.commitment_ready_pct < 50:
            why_low.append(f"Commitment extraction at {self.commitment_ready_pct:.0f}%")

        # Determine level
        if is_linked and self.commitment_ready_pct >= 50 and has_body:
            return "HIGH", []
        if is_linked and (not has_body or self.commitment_ready_pct < 50):
            return "MED", why_low[:3]
        return "LOW", why_low[:3]

    def _generate_top_reason(self, thread: ThreadData) -> str:
        """Generate top reason phrase for thread card."""
        if thread.response_status == ResponseStatus.OVERDUE.value:
            return f"Response overdue ({thread.age_hours:.0f}h)"

        if thread.vip:
            return "VIP requires attention"

        # Commitment at risk
        at_risk = [c for c in thread.commitments if c.status == "open" and c.due_at]
        if at_risk:
            return f"{len(at_risk)} commitment(s) at risk"

        if thread.thread_type == ThreadType.PAYMENT.value:
            return "Payment/billing thread"

        if thread.thread_type == ThreadType.DELIVERY_BLOCKER.value:
            return "Blocking delivery"

        if thread.thread_type == ThreadType.RELATIONSHIP.value:
            return "Relationship risk"

        if thread.link_status == "unlinked":
            return "Needs triage (unlinked)"

        return f"Response due ({thread.response_status})"

    def _generate_summary(self, thread: ThreadData) -> str:
        """Generate 2-3 sentence summary."""
        parts = []

        # What they want / what's happening
        if thread.thread_type == ThreadType.CLIENT_ASK.value:
            parts.append(f"Client request from {thread.client_name or 'unknown'}.")
        elif thread.thread_type == ThreadType.PAYMENT.value:
            parts.append(
                f"Payment/billing thread with {thread.client_name or 'unknown'}."
            )
        elif thread.thread_type == ThreadType.DELIVERY_BLOCKER.value:
            parts.append(f"Delivery blocker from {thread.client_name or 'unknown'}.")
        elif thread.thread_type == ThreadType.RELATIONSHIP.value:
            parts.append(
                f"Potential relationship issue with {thread.client_name or 'unknown'}."
            )
        else:
            parts.append(f"Thread: {thread.subject[:50]}.")

        # What we owe
        if thread.commitments:
            open_commits = [c for c in thread.commitments if c.status == "open"]
            if open_commits:
                parts.append(f"{len(open_commits)} open commitment(s).")

        # Why it matters
        if thread.response_status == ResponseStatus.OVERDUE.value:
            parts.append(f"Response is {thread.age_hours:.0f}h overdue.")
        elif thread.vip:
            parts.append("Flagged as VIP priority.")

        return " ".join(parts)

    def _get_linked_objects(self, thread: ThreadData) -> list[LinkedObject]:
        """Get linked objects for a thread."""
        objects = []

        if not thread.client_id:
            return objects

        # Linked tasks
        tasks = self._query_all(
            """
            SELECT id, title FROM tasks
            WHERE client_id = ? AND status NOT IN ('done', 'completed')
            ORDER BY due_date ASC NULLS LAST
            LIMIT 2
        """,
            (thread.client_id,),
        )

        for t in tasks:
            objects.append(LinkedObject(type="task", id=t["id"], label=t["title"][:40]))

        # Linked projects
        projects = self._query_all(
            """
            SELECT id, name FROM projects
            WHERE client_id = ? AND status NOT IN ('complete', 'cancelled')
            LIMIT 2
        """,
            (thread.client_id,),
        )

        for p in projects:
            objects.append(
                LinkedObject(type="project", id=p["id"], label=p["name"][:40])
            )

        # Linked invoices (overdue)
        invoices = self._query_all(
            """
            SELECT id, external_id, amount FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue') AND payment_date IS NULL
            ORDER BY due_date ASC
            LIMIT 1
        """,
            (thread.client_id,),
        )

        for inv in invoices:
            label = f"Invoice {inv.get('external_id') or inv['id'][:8]} - AED {inv.get('amount', 0):,.0f}"
            objects.append(LinkedObject(type="invoice", id=inv["id"], label=label))

        return objects[: self.MAX_LINKED_OBJECTS]

    def _filter_eligible_threads(self, threads: list[ThreadData]) -> list[ThreadData]:
        """Filter threads by eligibility gates per §6.1."""
        eligible = []

        for thread in threads:
            if self._is_eligible(thread):
                eligible.append(thread)

        return eligible

    def _is_eligible(self, thread: ThreadData) -> bool:
        """Check if thread is eligible for horizon per §6.1."""
        # Internal-only never qualifies unless explicitly included
        if thread.thread_type == ThreadType.INTERNAL_ONLY.value:
            return False

        # Unknown triage only if actionable_unlinked
        if (
            thread.thread_type == ThreadType.UNKNOWN_TRIAGE.value
            and thread.link_status != "unlinked"
        ):
            return False

        # Horizon gates
        if self.horizon == Horizon.NOW:
            if thread.response_status == ResponseStatus.OVERDUE.value:
                return True
            if thread.expected_response_by:
                try:
                    expected = datetime.fromisoformat(
                        thread.expected_response_by.replace("Z", "+00:00")
                    )
                    if (
                        expected.replace(tzinfo=None) - self.now
                    ).total_seconds() / 3600 <= 12:
                        return True
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse expected_response_by: {e}")
            # VIP with age >= 4h
            if thread.vip and thread.age_hours >= 4:
                return True
            # Commitment deadline within 12h
            for c in thread.commitments:
                if c.status == "open" and c.due_at:
                    try:
                        dl = datetime.fromisoformat(c.due_at.replace("Z", "+00:00"))
                        if (
                            dl.replace(tzinfo=None) - self.now
                        ).total_seconds() / 3600 <= 12:
                            return True
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.debug(f"Could not parse commitment deadline: {e}")
            return False

        if self.horizon == Horizon.TODAY:
            if thread.response_status in (
                ResponseStatus.OVERDUE.value,
                ResponseStatus.DUE.value,
            ):
                return True
            # Tier A with age >= 8h
            if thread.tier == "A" and thread.age_hours >= 8:
                return True
            # Commitment deadline before EOD
            eod = datetime.combine(self.today, datetime.max.time())
            for c in thread.commitments:
                if c.status == "open" and c.due_at:
                    try:
                        dl = datetime.fromisoformat(c.due_at.replace("Z", "+00:00"))
                        if dl.replace(tzinfo=None) <= eod:
                            return True
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.debug(f"Could not parse commitment deadline: {e}")
            return False

        # THIS_WEEK
        # Response due within 7 days
        if thread.expected_response_by:
            try:
                expected = datetime.fromisoformat(
                    thread.expected_response_by.replace("Z", "+00:00")
                )
                if (
                    expected.replace(tzinfo=None) - self.now
                ).total_seconds() / 3600 <= 7 * 24:
                    return True
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"Could not parse expected_response_by: {e}")
        # Commitment deadline within 7 days
        for c in thread.commitments:
            if c.status == "open" and c.due_at:
                try:
                    dl = datetime.fromisoformat(c.due_at.replace("Z", "+00:00"))
                    if (
                        dl.replace(tzinfo=None) - self.now
                    ).total_seconds() / 3600 <= 7 * 24:
                        return True
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse commitment deadline: {e}")
        # Special types unresolved
        return thread.thread_type in (
            ThreadType.PAYMENT.value,
            ThreadType.DELIVERY_BLOCKER.value,
            ThreadType.RELATIONSHIP.value,
        )

    def _rank_threads(self, threads: list[ThreadData]) -> list[ThreadData]:
        """
        Rank threads per §6.4 (locked ordering).

        1. response_status severity: OVERDUE > DUE > WAITING > OK
        2. BaseScore desc
        3. VIP first
        4. shortest time_to_expected
        5. confidence HIGH > MED > LOW
        """
        status_order = {
            ResponseStatus.OVERDUE.value: 0,
            ResponseStatus.DUE.value: 1,
            ResponseStatus.WAITING.value: 2,
            ResponseStatus.OK.value: 3,
        }

        conf_order = {"HIGH": 0, "MED": 1, "LOW": 2}

        def sort_key(t: ThreadData):
            # Time to expected (for sorting)
            ttx = 99999
            if t.expected_response_by:
                try:
                    expected = datetime.fromisoformat(
                        t.expected_response_by.replace("Z", "+00:00")
                    )
                    ttx = (
                        expected.replace(tzinfo=None) - self.now
                    ).total_seconds() / 3600
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse expected_response_by for sort: {e}")

            return (
                status_order.get(t.response_status, 3),
                -t.base_score,
                0 if t.vip else 1,
                ttx,
                conf_order.get(t.confidence, 2),
            )

        threads.sort(key=sort_key)
        return threads

    def _build_summary(
        self, threads: list[ThreadData], commitments: list[Commitment]
    ) -> dict:
        """Build executive strip summary per §3 Zone B."""
        # Count overdue replies
        overdue_replies = sum(
            1 for t in threads if t.response_status == ResponseStatus.OVERDUE.value
        )

        # Count VIP waiting
        vip_waiting = sum(
            1
            for t in threads
            if t.vip
            and t.response_status
            in (ResponseStatus.OVERDUE.value, ResponseStatus.DUE.value)
        )

        # Count commitments at risk / broken
        commitments_at_risk = 0
        for c in commitments:
            if c.status != "open":
                continue
            if c.due_at:
                try:
                    dl = datetime.fromisoformat(c.due_at.replace("Z", "+00:00"))
                    # At risk if within horizon or past
                    hours_to_dl = (
                        dl.replace(tzinfo=None) - self.now
                    ).total_seconds() / 3600
                    horizon_hours = {
                        Horizon.NOW: 12,
                        Horizon.TODAY: 24,
                        Horizon.THIS_WEEK: 168,
                    }.get(self.horizon, 24)
                    if hours_to_dl <= horizon_hours:
                        commitments_at_risk += 1
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse commitment deadline: {e}")

        # Count unlinked actionable
        unlinked_actionable = sum(
            1
            for t in threads
            if t.link_status == "unlinked"
            and t.thread_type == ThreadType.UNKNOWN_TRIAGE.value
        )

        # Risk band
        if overdue_replies >= 3 or commitments_at_risk >= 2:
            risk_band = "HIGH"
        elif overdue_replies >= 1 or vip_waiting >= 1 or commitments_at_risk >= 1:
            risk_band = "MED"
        else:
            risk_band = "LOW"

        # Top driver sentence
        top_driver = self._generate_top_driver_sentence(
            overdue_replies, vip_waiting, commitments_at_risk, unlinked_actionable
        )

        return {
            "overdue_replies": overdue_replies,
            "vip_waiting": vip_waiting,
            "commitments_at_risk": commitments_at_risk,
            "unlinked_actionable": unlinked_actionable,
            "risk_band": risk_band,
            "top_driver_sentence": top_driver,
        }

    def _generate_top_driver_sentence(
        self, overdue: int, vip: int, at_risk: int, unlinked: int
    ) -> str:
        """Generate top driver sentence."""
        if overdue >= 3:
            return f"Comms risk is HIGH because {overdue} replies are overdue."
        if at_risk >= 2:
            return f"Comms risk is HIGH because {at_risk} commitments are at risk."
        if vip >= 1:
            return f"Comms risk is MED because {vip} VIP thread(s) need attention."
        if overdue >= 1:
            return f"Comms risk is MED because {overdue} reply is overdue."
        if unlinked >= 3:
            return f"Comms risk is MED because {unlinked} threads need triage."

        return "Comms risk is LOW — no critical loops open."

    def _build_selected_thread(
        self, thread_id: str, threads: list[ThreadData]
    ) -> ThreadData | None:
        """Build full detail for selected thread (Thread Room)."""
        thread = next((t for t in threads if t.thread_id == thread_id), None)
        if not thread:
            return None

        # Cap collections
        thread.snippets = thread.snippets[: self.MAX_SNIPPETS]
        thread.commitments = thread.commitments[: self.MAX_COMMITMENTS]
        thread.linked_objects = thread.linked_objects[: self.MAX_LINKED_OBJECTS]

        return thread

    def _build_global_actions(
        self, hot_list: list[ThreadData], commitments: list[Commitment]
    ) -> list[CommsAction]:
        """Build global actions per §7."""
        actions = []

        # Overdue threads
        overdue = [
            t for t in hot_list if t.response_status == ResponseStatus.OVERDUE.value
        ]

        for thread in overdue[:3]:
            actions.append(
                CommsAction(
                    action_id=f"reply_{thread.thread_id}",
                    risk_level="propose",
                    label="Draft reply",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"reply_{thread.thread_id}_{self.today.isoformat()}",
                    payload={
                        "thread_id": thread.thread_id,
                        "client_id": thread.client_id,
                        "action": "draft_reply",
                    },
                    why=f"Response overdue ({thread.age_hours:.0f}h)",
                )
            )

        # VIP threads
        vip_threads = [t for t in hot_list if t.vip and t not in overdue]
        for thread in vip_threads[:2]:
            actions.append(
                CommsAction(
                    action_id=f"followup_{thread.thread_id}",
                    risk_level="auto",
                    label="Create follow-up task",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"followup_{thread.thread_id}",
                    payload={
                        "thread_id": thread.thread_id,
                        "client_id": thread.client_id,
                        "action": "create_task",
                    },
                    why="VIP thread requires follow-up",
                )
            )

        # Unlinked threads
        unlinked = [t for t in hot_list if t.link_status == "unlinked"]
        for thread in unlinked[:2]:
            actions.append(
                CommsAction(
                    action_id=f"fix_{thread.thread_id}",
                    risk_level="auto",
                    label="Create resolution item: comm_unlinked",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"fix_unlinked_{thread.thread_id}",
                    payload={
                        "thread_id": thread.thread_id,
                        "issue": "comm_unlinked",
                        "action": "create_resolution",
                    },
                    why="Thread not linked to client",
                )
            )

        # Commitment extraction coverage
        if self.commitment_ready_pct < 50:
            actions.append(
                CommsAction(
                    action_id="improve_extraction",
                    risk_level="propose",
                    label="Improve extraction coverage",
                    entity_type="system",
                    entity_id="commitment_extraction",
                    idempotency_key=f"improve_extraction_{self.today.isoformat()}",
                    payload={"action": "improve_extraction"},
                    why=f"Commitment extraction at {self.commitment_ready_pct:.0f}%",
                )
            )

        return actions[: self.MAX_GLOBAL_ACTIONS]

    def _build_thread_actions(self, thread: ThreadData) -> list[CommsAction]:
        """Build actions for a specific thread per §7."""
        actions = []

        # OVERDUE/DUE threads
        if thread.response_status in (
            ResponseStatus.OVERDUE.value,
            ResponseStatus.DUE.value,
        ):
            actions.append(
                CommsAction(
                    action_id=f"reply_{thread.thread_id}",
                    risk_level="propose",
                    label="Draft reply",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"reply_{thread.thread_id}_{self.today.isoformat()}",
                    payload={
                        "thread_id": thread.thread_id,
                        "client_id": thread.client_id,
                        "subject": thread.subject,
                        "action": "draft_reply",
                    },
                    why=f"Response {thread.response_status.lower()}",
                )
            )

            actions.append(
                CommsAction(
                    action_id=f"task_{thread.thread_id}",
                    risk_level="auto",
                    label="Create follow-up task",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"task_{thread.thread_id}",
                    payload={
                        "thread_id": thread.thread_id,
                        "client_id": thread.client_id,
                        "action": "create_task",
                    },
                    why="Ensure follow-through",
                )
            )

            actions.append(
                CommsAction(
                    action_id=f"call_{thread.thread_id}",
                    risk_level="propose",
                    label="Schedule call",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"call_{thread.thread_id}_{self.today.isoformat()}",
                    payload={
                        "thread_id": thread.thread_id,
                        "client_id": thread.client_id,
                        "action": "schedule_call",
                    },
                    why="Direct communication may resolve faster",
                )
            )

        # Payment/Finance threads
        if thread.thread_type == ThreadType.PAYMENT.value:
            actions.append(
                CommsAction(
                    action_id=f"reminder_{thread.thread_id}",
                    risk_level="propose",
                    label="Send payment reminder",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"reminder_{thread.thread_id}_{self.today.isoformat()}",
                    payload={
                        "thread_id": thread.thread_id,
                        "client_id": thread.client_id,
                        "action": "payment_reminder",
                    },
                    why="Payment thread requires reminder",
                )
            )

            actions.append(
                CommsAction(
                    action_id=f"terms_{thread.thread_id}",
                    risk_level="approval",
                    label="Offer revised terms / due date",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"terms_{thread.thread_id}_{self.today.isoformat()}",
                    payload={
                        "thread_id": thread.thread_id,
                        "client_id": thread.client_id,
                        "action": "revise_terms",
                    },
                    why="Financial changes require approval",
                )
            )

        # Delivery blockers
        if thread.thread_type == ThreadType.DELIVERY_BLOCKER.value:
            actions.append(
                CommsAction(
                    action_id=f"request_{thread.thread_id}",
                    risk_level="propose",
                    label="Request missing asset/info",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"request_{thread.thread_id}_{self.today.isoformat()}",
                    payload={
                        "thread_id": thread.thread_id,
                        "client_id": thread.client_id,
                        "action": "request_asset",
                    },
                    why="Delivery blocked pending input",
                )
            )

            actions.append(
                CommsAction(
                    action_id=f"blocker_{thread.thread_id}",
                    risk_level="auto",
                    label="Mark blocker + create blocking task",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"blocker_{thread.thread_id}",
                    payload={
                        "thread_id": thread.thread_id,
                        "client_id": thread.client_id,
                        "action": "create_blocker",
                    },
                    why="Track blocker formally",
                )
            )

        # Unlinked / Unknown triage
        if thread.link_status == "unlinked":
            actions.append(
                CommsAction(
                    action_id=f"fix_{thread.thread_id}",
                    risk_level="auto",
                    label="Create resolution item: comm_unlinked",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"fix_{thread.thread_id}",
                    payload={
                        "thread_id": thread.thread_id,
                        "issue": "comm_unlinked",
                        "action": "create_resolution",
                    },
                    why="Thread not linked to client",
                )
            )

            actions.append(
                CommsAction(
                    action_id=f"identity_{thread.thread_id}",
                    risk_level="propose",
                    label="Create identity (domain/email) for client",
                    entity_type="thread",
                    entity_id=thread.thread_id,
                    idempotency_key=f"identity_{thread.thread_id}",
                    payload={
                        "thread_id": thread.thread_id,
                        "action": "create_identity",
                    },
                    why="Map sender to client record",
                )
            )

        return actions[: self.MAX_THREAD_ACTIONS]

    def _thread_to_hot_list_dict(self, thread: ThreadData) -> dict:
        """Convert ThreadData to hot list dict."""
        return {
            "thread_id": thread.thread_id,
            "client_id": thread.client_id,
            "client_name": thread.client_name,
            "tier": thread.tier,
            "vip": thread.vip,
            "thread_type": thread.thread_type,
            "response_status": thread.response_status,
            "expected_response_by": thread.expected_response_by,
            "age_hours": round(thread.age_hours, 1),
            "base_score": round(thread.base_score, 1),
            "confidence": thread.confidence,
            "why_low": thread.why_low,
            "top_reason": thread.top_reason,
        }

    def _selected_thread_to_dict(self, thread: ThreadData) -> dict:
        """Convert ThreadData to selected_thread dict per §8.1."""
        actions = self._build_thread_actions(thread)

        # Build reason line
        reason = f"{self.horizon.value} | {thread.thread_type} | top_driver={thread.top_reason}"

        return {
            "thread_id": thread.thread_id,
            "header": {
                "client_id": thread.client_id,
                "client_name": thread.client_name,
                "tier": thread.tier,
                "vip": thread.vip,
                "subject": thread.subject,
                "thread_type": thread.thread_type,
                "response_status": thread.response_status,
                "expected_response_by": thread.expected_response_by,
                "confidence": {
                    "level": thread.confidence,
                    "why_low": thread.why_low,
                },
            },
            "summary": thread.summary,
            "evidence": {
                "linked_objects": [
                    {"type": o.type, "id": o.id, "label": o.label}
                    for o in thread.linked_objects
                ],
                "gates": {
                    "data_integrity": self.data_integrity,
                    "commitment_ready": self.commitment_ready_pct >= 50,
                },
            },
            "snippets": [
                {
                    "at": s.at,
                    "direction": s.direction,
                    "from": s.from_addr,
                    "commitment_text": s.text,
                }
                for s in thread.snippets
            ],
            "commitments": [
                {
                    "commitment_id": c.commitment_id,
                    "type": c.type,
                    "commitment_text": c.text,
                    "due_at": c.due_at,
                    "status": c.status,
                    "confidence": c.confidence,
                }
                for c in thread.commitments
            ],
            "actions": [self._action_to_dict(a) for a in actions],
            "reason": reason,
        }

    def _action_to_dict(self, action: CommsAction) -> dict:
        """Convert CommsAction to dict."""
        return {
            "action_id": action.action_id,
            "risk_level": action.risk_level,
            "label": action.label,
            "entity_type": action.entity_type,
            "entity_id": action.entity_id,
            "idempotency_key": action.idempotency_key,
            "payload": action.payload,
            "why": action.why,
        }


def generate_comms_commitments(
    mode: str = "Ops Head",
    horizon: str = "TODAY",
    selected_thread_id: str | None = None,
    expanded: bool = False,
) -> dict:
    """Convenience function to generate comms_commitments section."""
    from .scoring import Horizon, Mode

    mode_enum = Mode(mode) if mode in [m.value for m in Mode] else Mode.OPS_HEAD
    horizon_enum = (
        Horizon(horizon) if horizon in [h.value for h in Horizon] else Horizon.TODAY
    )

    engine = CommsCommitmentsEngine(mode=mode_enum, horizon=horizon_enum)
    return engine.generate(selected_thread_id=selected_thread_id, expanded=expanded)


if __name__ == "__main__":
    logger.info("Generating Comms/Commitments Command snapshot...")
    result = generate_comms_commitments()

    logger.info("\nSummary:")
    summary = result.get("summary", {})
    logger.info(f"  Overdue Replies: {summary.get('overdue_replies', 0)}")
    logger.info(f"  VIP Waiting: {summary.get('vip_waiting', 0)}")
    logger.info(f"  Commitments at Risk: {summary.get('commitments_at_risk', 0)}")
    logger.info(f"  Unlinked Actionable: {summary.get('unlinked_actionable', 0)}")
    logger.info(f"  Risk Band: {summary.get('risk_band', 'N/A')}")
    logger.info(f"  {summary.get('top_driver_sentence', '')}")
    logger.info(f"\nHot List ({len(result.get('hot_list', []))} threads):")
    for t in result.get("hot_list", [])[:5]:
        client = t.get("client_name") or "Unlinked"
        logger.info(
            f"  {client}: {t['response_status']} | {t['thread_type']} | Score: {t['base_score']:.0f}"
        )
    logger.info(f"\nGlobal Actions ({len(result.get('global_actions', []))}):")
    for a in result.get("global_actions", [])[:3]:
        logger.info(f"  [{a['risk_level']}] {a['label']} - {a['why']}")
