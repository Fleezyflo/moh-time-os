"""
Conversational Intelligence — MOH TIME OS

Natural language query interface for synthesizing intelligence across
all domains. Rule-based intent classification, entity resolution,
cross-domain synthesis, and action routing.

Brief 25 (CI), Tasks CI-1.1 through CI-3.1

"How's Client X doing?" → synthesized answer from health, revenue,
signals, trajectory, communications, and interaction history.
"""

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Optional LLM support — enhances intent classification when available
try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# Intent types
INTENT_ENTITY_LOOKUP = "entity_lookup"
INTENT_METRIC_QUERY = "metric_query"
INTENT_COMPARISON = "comparison"
INTENT_PREDICTION = "prediction"
INTENT_ACTION_REQUEST = "action_request"
INTENT_HISTORY_LOOKUP = "history_lookup"
INTENT_RANKED_SUMMARY = "ranked_summary"
INTENT_UNKNOWN = "unknown"

# Intent classification patterns (rule-based, no ML)
INTENT_PATTERNS = [
    # Action requests — check first (most specific)
    (
        INTENT_ACTION_REQUEST,
        [
            r"(?:draft|write|send|create|schedule|prepare|make)\s+(?:an?\s+)?(?:email|message|task|meeting|follow.?up|invoice|report)",
            r"(?:set\s+up|book|arrange)\s+(?:a\s+)?(?:meeting|call|review|session)",
        ],
    ),
    # History lookup
    (
        INTENT_HISTORY_LOOKUP,
        [
            r"(?:what\s+did\s+i|when\s+did\s+i|last\s+time\s+i)\s+(?:decide|do|discuss|review|meet|talk)",
            r"(?:history|decisions?|past\s+actions?)\s+(?:for|about|on|regarding)",
            r"(?:previous|prior|last)\s+(?:decision|review|meeting|interaction)",
        ],
    ),
    # Comparison
    (
        INTENT_COMPARISON,
        [
            r"compare\s+(?:.*?)\s+(?:and|vs\.?|versus|with|to)\s+",
            r"(?:how\s+does|difference\s+between)\s+(?:.*?)\s+(?:and|vs\.?|compare)",
            r"(?:this\s+(?:week|month|quarter))\s+(?:compare|vs\.?|versus)\s+(?:last|previous)",
        ],
    ),
    # Prediction
    (
        INTENT_PREDICTION,
        [
            r"what\s+(?:if|happens?\s+if|would\s+happen)",
            r"(?:predict|forecast)\s+",
            r"\bproject(?:ion|ed|ing)\b",
            r"(?:what\s+will|where\s+will)\s+(?:.*?)(?:be|go|end\s+up)",
            r"(?:scenario|simulate)\s+",
        ],
    ),
    # Ranked summary
    (
        INTENT_RANKED_SUMMARY,
        [
            r"what\s+should\s+i\s+(?:worry|focus|work\s+on|prioritize|look\s+at)",
            r"(?:top|biggest|most\s+(?:urgent|important|critical))\s+(?:issues?|risks?|concerns?|problems?)",
            r"(?:attention|priority)\s+(?:queue|list)",
            r"(?:weekly|daily|morning)\s+(?:summary|briefing|overview|report)",
        ],
    ),
    # Metric query
    (
        INTENT_METRIC_QUERY,
        [
            r"(?:what(?:'s| is| are)\s+(?:my|our|the))\s+(?:revenue|profit|margin|cost|utilization|capacity|cash|balance|invoic)",
            r"(?:how\s+much)\s+(?:revenue|profit|cash|money|cost)",
            r"(?:total|average|current)\s+(?:revenue|profit|margin|cost|utilization|capacity)",
            r"(?:revenue|profit|margin|cost|utilization)\s+(?:this|last|current)\s+(?:week|month|quarter|year)",
        ],
    ),
    # Entity lookup — broadest pattern, check last
    (
        INTENT_ENTITY_LOOKUP,
        [
            r"(?:how\s+is|how(?:'s| are))\s+(?:client\s+)?(?:\w+)",
            r"(?:tell\s+me\s+about|show\s+me|what\s+about|status\s+of|update\s+on)\s+",
            r"(?:check\s+on|look\s+up|pull\s+up|give\s+me)\s+",
        ],
    ),
]


@dataclass
class ClassifiedIntent:
    """Result of intent classification."""

    intent_type: str
    confidence: float
    raw_query: str
    extracted_entities: list[str] = field(default_factory=list)
    extracted_metrics: list[str] = field(default_factory=list)
    extracted_action: str = ""
    extracted_timeframe: str = ""

    def to_dict(self) -> dict:
        return {
            "intent_type": self.intent_type,
            "confidence": round(self.confidence, 2),
            "raw_query": self.raw_query,
            "extracted_entities": self.extracted_entities,
            "extracted_metrics": self.extracted_metrics,
            "extracted_action": self.extracted_action,
            "extracted_timeframe": self.extracted_timeframe,
        }


@dataclass
class ResolvedEntity:
    """An entity resolved from a query string."""

    entity_type: str  # client | project | person | invoice
    entity_id: str
    entity_name: str
    match_confidence: float
    match_method: str  # exact | fuzzy | alias

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "match_confidence": round(self.match_confidence, 2),
            "match_method": self.match_method,
        }


@dataclass
class SynthesizedResponse:
    """A synthesized intelligence response to a query."""

    headline: str
    supporting_points: list[dict[str, Any]] = field(default_factory=list)
    trend_interpretation: str = ""
    open_items: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "supporting_points": self.supporting_points,
            "trend_interpretation": self.trend_interpretation,
            "open_items": self.open_items,
            "suggested_actions": self.suggested_actions,
            "sources": self.sources,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class ActionCard:
    """A prepared action generated from a conversational request."""

    action_type: str  # email | task | meeting | follow_up
    entity_type: str
    entity_id: str
    title: str
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "prepared"  # prepared | approved | dismissed

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "title": self.title,
            "description": self.description,
            "context": self.context,
            "status": self.status,
        }


@dataclass
class ConversationState:
    """Session state for conversational context."""

    current_entity_type: str = ""
    current_entity_id: str = ""
    current_entity_name: str = ""
    query_history: list[str] = field(default_factory=list)
    pending_actions: list[ActionCard] = field(default_factory=list)
    last_intent: str = ""

    def update_context(
        self,
        entity_type: str = "",
        entity_id: str = "",
        entity_name: str = "",
        query: str = "",
        intent: str = "",
    ) -> None:
        """Update conversation context after a query."""
        if entity_type:
            self.current_entity_type = entity_type
        if entity_id:
            self.current_entity_id = entity_id
        if entity_name:
            self.current_entity_name = entity_name
        if query:
            self.query_history.append(query)
            # Keep last 20 queries
            if len(self.query_history) > 20:
                self.query_history = self.query_history[-20:]
        if intent:
            self.last_intent = intent

    def to_dict(self) -> dict:
        return {
            "current_entity_type": self.current_entity_type,
            "current_entity_id": self.current_entity_id,
            "current_entity_name": self.current_entity_name,
            "query_count": len(self.query_history),
            "pending_actions": len(self.pending_actions),
            "last_intent": self.last_intent,
        }


def classify_intent(query: str) -> ClassifiedIntent:
    """
    Classify a natural language query into an intent type.

    Rule-based classification using pattern matching.
    """
    query_lower = query.lower().strip()

    if not query_lower:
        return ClassifiedIntent(
            intent_type=INTENT_UNKNOWN,
            confidence=0.0,
            raw_query=query,
        )

    # Try each intent pattern
    for intent_type, patterns in INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, query_lower):
                result = ClassifiedIntent(
                    intent_type=intent_type,
                    confidence=0.8,
                    raw_query=query,
                )
                _extract_entities_from_query(query_lower, result)
                _extract_metrics_from_query(query_lower, result)
                _extract_timeframe_from_query(query_lower, result)
                _extract_action_from_query(query_lower, result)
                return result

    # Regex didn't match — try LLM classification if available
    llm_result = _classify_with_llm(query)
    if llm_result and llm_result.intent_type != INTENT_UNKNOWN:
        return llm_result

    # Final fallback: unknown intent
    result = ClassifiedIntent(
        intent_type=INTENT_UNKNOWN,
        confidence=0.3,
        raw_query=query,
    )
    _extract_entities_from_query(query_lower, result)
    return result


_LLM_CLASSIFY_PROMPT = """Classify this user query about their business into one intent type.
Return ONLY a JSON object with these fields:
- intent_type: one of entity_lookup, metric_query, comparison, prediction, action_request, history_lookup, ranked_summary
- entities: list of entity names mentioned (client names, project names, people names)
- metrics: list of metric keywords (revenue, utilization, health, etc.)
- timeframe: one of today, yesterday, this_week, last_week, this_month, last_month, this_quarter, last_quarter, this_year, or empty string
- action: for action_request only — one of email, task, meeting, follow_up, invoice, report, or empty string

Query: {query}

JSON:"""


def _classify_with_llm(query: str) -> ClassifiedIntent | None:
    """
    Classify intent using Claude Haiku for ambiguous queries.

    Returns None if LLM is unavailable or errors — caller falls back to regex.
    """
    if not HAS_ANTHROPIC:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": _LLM_CLASSIFY_PROMPT.format(query=query[:500]),
                }
            ],
        )

        result_text = response.content[0].text.strip()

        # Parse JSON from response
        parsed = None
        if result_text.startswith("{"):
            parsed = json.loads(result_text)
        else:
            match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())

        if not parsed:
            return None

        intent_type = parsed.get("intent_type", INTENT_UNKNOWN)
        # Validate intent type
        valid_intents = {
            INTENT_ENTITY_LOOKUP,
            INTENT_METRIC_QUERY,
            INTENT_COMPARISON,
            INTENT_PREDICTION,
            INTENT_ACTION_REQUEST,
            INTENT_HISTORY_LOOKUP,
            INTENT_RANKED_SUMMARY,
        }
        if intent_type not in valid_intents:
            intent_type = INTENT_UNKNOWN

        return ClassifiedIntent(
            intent_type=intent_type,
            confidence=0.9,
            raw_query=query,
            extracted_entities=parsed.get("entities", []),
            extracted_metrics=parsed.get("metrics", []),
            extracted_action=parsed.get("action", ""),
            extracted_timeframe=parsed.get("timeframe", ""),
        )

    except (sqlite3.Error, ValueError, OSError) as e:
        logger.debug("LLM classification failed, using regex fallback: %s", e)
        return None


def _extract_entities_from_query(query: str, result: ClassifiedIntent) -> None:
    """Extract entity names from query text."""
    # Match "Client X", "Project Y", etc.
    entity_patterns = [
        r"client\s+([A-Za-z][A-Za-z0-9\s&'-]+?)(?:\s+(?:and|vs|versus|with|to|is|are|doing|status)|[?.!,]|$)",
        r"project\s+([A-Za-z][A-Za-z0-9\s&'-]+?)(?:\s+(?:and|vs|versus|with|to|is|are|doing|status)|[?.!,]|$)",
        r"(?:about|on|for|with|to)\s+([A-Z][A-Za-z0-9\s&'-]+?)(?:\s+(?:and|vs|versus|is|are|doing)|[?.!,]|$)",
    ]
    for pattern in entity_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        for m in matches:
            name = m.strip().rstrip(".")
            if (
                name
                and len(name) > 1
                and name.lower()
                not in (
                    "me",
                    "my",
                    "our",
                    "the",
                    "this",
                    "that",
                    "it",
                )
            ):
                result.extracted_entities.append(name)

    # Deduplicate
    seen = set()
    unique = []
    for e in result.extracted_entities:
        key = e.lower()
        if key not in seen:
            seen.add(key)
            unique.append(e)
    result.extracted_entities = unique


def _extract_metrics_from_query(query: str, result: ClassifiedIntent) -> None:
    """Extract metric references from query."""
    metric_keywords = [
        "revenue",
        "profit",
        "margin",
        "cost",
        "utilization",
        "capacity",
        "cash",
        "health",
        "score",
        "invoice",
        "budget",
        "expense",
        "balance",
        "outstanding",
    ]
    for kw in metric_keywords:
        if kw in query:
            result.extracted_metrics.append(kw)


def _extract_timeframe_from_query(query: str, result: ClassifiedIntent) -> None:
    """Extract timeframe references."""
    timeframe_patterns = {
        "this week": "this_week",
        "last week": "last_week",
        "this month": "this_month",
        "last month": "last_month",
        "this quarter": "this_quarter",
        "last quarter": "last_quarter",
        "this year": "this_year",
        "today": "today",
        "yesterday": "yesterday",
    }
    for phrase, code in timeframe_patterns.items():
        if phrase in query:
            result.extracted_timeframe = code
            return


def _extract_action_from_query(query: str, result: ClassifiedIntent) -> None:
    """Extract action type from action requests."""
    action_map = {
        "email": "email",
        "message": "email",
        "follow-up": "follow_up",
        "follow up": "follow_up",
        "followup": "follow_up",
        "task": "task",
        "meeting": "meeting",
        "call": "meeting",
        "review": "meeting",
        "invoice": "invoice",
        "report": "report",
    }
    for keyword, action in action_map.items():
        if keyword in query:
            result.extracted_action = action
            return


class EntityResolver:
    """
    Resolves entity references to actual entity IDs.

    Supports exact match, case-insensitive match, and fuzzy matching.
    """

    def __init__(
        self,
        entity_registry: list[dict[str, str]] | None = None,
    ) -> None:
        """
        Args:
            entity_registry: List of dicts with entity_type, entity_id, entity_name
        """
        self.registry = entity_registry or []

    def resolve(
        self,
        query_name: str,
        entity_type: str | None = None,
    ) -> ResolvedEntity | None:
        """Resolve a name to an entity."""
        if not query_name or not self.registry:
            return None

        query_lower = query_name.lower().strip()

        # Exact match
        for entry in self.registry:
            if entity_type and entry.get("entity_type") != entity_type:
                continue
            if entry.get("entity_name", "").lower() == query_lower:
                return ResolvedEntity(
                    entity_type=entry["entity_type"],
                    entity_id=entry["entity_id"],
                    entity_name=entry["entity_name"],
                    match_confidence=1.0,
                    match_method="exact",
                )

        # Partial match (name contains query or query contains name)
        best_match = None
        best_score = 0.0
        for entry in self.registry:
            if entity_type and entry.get("entity_type") != entity_type:
                continue
            entry_lower = entry.get("entity_name", "").lower()
            if query_lower in entry_lower or entry_lower in query_lower:
                # Score by overlap ratio
                overlap = len(query_lower) / max(len(entry_lower), 1)
                score = min(0.9, overlap + 0.3)
                if score > best_score:
                    best_score = score
                    best_match = entry

        if best_match and best_score >= 0.5:
            return ResolvedEntity(
                entity_type=best_match["entity_type"],
                entity_id=best_match["entity_id"],
                entity_name=best_match["entity_name"],
                match_confidence=best_score,
                match_method="fuzzy",
            )

        return None

    def resolve_multiple(
        self,
        names: list[str],
        entity_type: str | None = None,
    ) -> list[ResolvedEntity]:
        """Resolve multiple entity references."""
        results = []
        for name in names:
            resolved = self.resolve(name, entity_type)
            if resolved:
                results.append(resolved)
        return results


class CrossDomainSynthesizer:
    """
    Synthesizes data from multiple intelligence domains into
    coherent, human-readable responses.
    """

    def __init__(self) -> None:
        pass

    def synthesize_entity_lookup(
        self,
        entity_type: str,
        entity_id: str,
        entity_name: str,
        health_data: dict[str, Any] | None = None,
        revenue_data: dict[str, Any] | None = None,
        signal_data: list[dict[str, Any]] | None = None,
        trajectory_data: dict[str, Any] | None = None,
        communication_data: dict[str, Any] | None = None,
    ) -> SynthesizedResponse:
        """Synthesize a comprehensive entity lookup response."""
        health = health_data or {}
        revenue = revenue_data or {}
        signals = signal_data or []
        trajectory = trajectory_data or {}
        comms = communication_data or {}

        # Build headline
        health_score = health.get("score", 50)
        health_label = _health_label(health_score)
        headline = f"{entity_name}: {health_label} health ({health_score:.0f}/100)"

        # Supporting points
        points = []
        if revenue.get("monthly_revenue"):
            points.append(
                {
                    "domain": "revenue",
                    "text": f"Revenue: {revenue['monthly_revenue']:,.0f} AED/month ({revenue.get('trend', 'stable')})",
                    "source": "revenue_analytics",
                }
            )

        if trajectory.get("velocity") is not None:
            vel = trajectory["velocity"]
            direction = "improving" if vel > 0 else "declining" if vel < 0 else "stable"
            points.append(
                {
                    "domain": "trajectory",
                    "text": f"Trajectory: {direction} (velocity {vel:+.1f})",
                    "source": "trajectory_engine",
                }
            )

        if signals:
            critical = sum(1 for s in signals if s.get("severity") == "CRITICAL")
            warning = sum(1 for s in signals if s.get("severity") == "WARNING")
            text = f"Signals: {len(signals)} active"
            if critical:
                text += f" ({critical} critical)"
            if warning:
                text += f" ({warning} warnings)"
            points.append(
                {
                    "domain": "signals",
                    "text": text,
                    "source": "signal_engine",
                }
            )

        if comms.get("meeting_frequency"):
            points.append(
                {
                    "domain": "communication",
                    "text": f"Communication: {comms['meeting_frequency']} meetings/week",
                    "source": "communication_analysis",
                }
            )

        # Trend interpretation
        trend = _interpret_trend(health_score, trajectory, signals)

        # Open items
        open_items = []
        for s in signals:
            if s.get("severity") in ("CRITICAL", "WARNING"):
                open_items.append(s.get("description", s.get("signal_type", "")))

        # Suggested actions
        actions = []
        if health_score < 50:
            actions.append("Schedule a health review meeting")
        if any(s.get("severity") == "CRITICAL" for s in signals):
            actions.append("Address critical signals immediately")
        if trajectory.get("velocity", 0) < -5:
            actions.append("Investigate declining trajectory")

        sources = list({p["source"] for p in points})

        return SynthesizedResponse(
            headline=headline,
            supporting_points=points,
            trend_interpretation=trend,
            open_items=open_items,
            suggested_actions=actions,
            sources=sources,
            confidence=min(0.9, len(points) * 0.15 + 0.3),
        )

    def synthesize_metric_query(
        self,
        metrics: list[str],
        data: dict[str, Any],
    ) -> SynthesizedResponse:
        """Synthesize a metric query response."""
        points = []
        for metric in metrics:
            value = data.get(metric)
            if value is not None:
                if isinstance(value, int | float):
                    points.append(
                        {
                            "domain": "metrics",
                            "text": f"{metric.replace('_', ' ').title()}: {value:,.2f}",
                            "source": "metrics_store",
                        }
                    )
                else:
                    points.append(
                        {
                            "domain": "metrics",
                            "text": f"{metric.replace('_', ' ').title()}: {value}",
                            "source": "metrics_store",
                        }
                    )

        headline = f"Metrics overview: {len(points)} data points"
        if len(points) == 1:
            headline = points[0]["text"]

        return SynthesizedResponse(
            headline=headline,
            supporting_points=points,
            sources=["metrics_store"],
            confidence=0.7 if points else 0.3,
        )

    def synthesize_ranked_summary(
        self,
        attention_queue: list[dict[str, Any]],
        active_warnings: list[dict[str, Any]] | None = None,
    ) -> SynthesizedResponse:
        """Synthesize a 'what should I worry about' response."""
        warnings = active_warnings or []

        if not attention_queue and not warnings:
            return SynthesizedResponse(
                headline="All clear — no urgent items requiring attention",
                confidence=0.7,
            )

        items = []
        for i, item in enumerate(attention_queue[:5]):
            items.append(
                {
                    "domain": "priority",
                    "text": (
                        f"#{i + 1}: {item.get('entity_name', item.get('entity_id', 'Unknown'))} "
                        f"— {item.get('reason', 'needs attention')}"
                    ),
                    "source": "priority_scorer",
                }
            )

        headline = f"{len(attention_queue)} items need your attention"
        if attention_queue:
            top = attention_queue[0]
            headline = (
                f"Top priority: {top.get('entity_name', top.get('entity_id', 'Unknown'))} "
                f"({top.get('urgency_level', 'elevated')})"
            )

        open_items = [w.get("description", "") for w in warnings[:3]]

        return SynthesizedResponse(
            headline=headline,
            supporting_points=items,
            open_items=open_items,
            suggested_actions=["Review top priority items", "Address critical warnings first"],
            sources=["priority_scorer", "early_warnings"],
            confidence=0.8,
        )

    def synthesize_comparison(
        self,
        entity_a: dict[str, Any],
        entity_b: dict[str, Any],
    ) -> SynthesizedResponse:
        """Synthesize an entity comparison response."""
        name_a = entity_a.get("entity_name", entity_a.get("entity_id", "A"))
        name_b = entity_b.get("entity_name", entity_b.get("entity_id", "B"))

        points = []
        comparison_fields = [
            ("health_score", "Health Score"),
            ("monthly_revenue", "Monthly Revenue"),
            ("active_signals", "Active Signals"),
            ("trend_direction", "Trend"),
        ]

        for field_key, label in comparison_fields:
            val_a = entity_a.get(field_key)
            val_b = entity_b.get(field_key)
            if val_a is not None and val_b is not None:
                if isinstance(val_a, int | float):
                    points.append(
                        {
                            "domain": "comparison",
                            "text": f"{label}: {name_a}={val_a:,.1f} vs {name_b}={val_b:,.1f}",
                            "source": "entity_profiles",
                        }
                    )
                else:
                    points.append(
                        {
                            "domain": "comparison",
                            "text": f"{label}: {name_a}={val_a} vs {name_b}={val_b}",
                            "source": "entity_profiles",
                        }
                    )

        # Determine which is doing better
        ha = entity_a.get("health_score", 50)
        hb = entity_b.get("health_score", 50)
        if abs(ha - hb) > 10:
            better = name_a if ha > hb else name_b
            headline = f"{better} is performing better overall"
        else:
            headline = f"{name_a} and {name_b} are performing similarly"

        return SynthesizedResponse(
            headline=headline,
            supporting_points=points,
            sources=["entity_profiles"],
            confidence=0.7,
        )


def _health_label(score: float) -> str:
    """Human-readable health label."""
    if score >= 80:
        return "strong"
    if score >= 65:
        return "good"
    if score >= 50:
        return "moderate"
    if score >= 35:
        return "concerning"
    return "critical"


def _interpret_trend(
    health_score: float,
    trajectory: dict[str, Any],
    signals: list[dict[str, Any]],
) -> str:
    """Build a trend interpretation sentence."""
    velocity = trajectory.get("velocity", 0)
    critical_count = sum(1 for s in signals if s.get("severity") == "CRITICAL")

    parts = []
    if velocity > 3:
        parts.append("improving trajectory")
    elif velocity < -3:
        parts.append("declining trajectory")
    else:
        parts.append("stable trajectory")

    if health_score >= 70:
        parts.append("healthy position")
    elif health_score < 40:
        parts.append("needs urgent attention")

    if critical_count > 0:
        parts.append(f"{critical_count} critical issue{'s' if critical_count > 1 else ''}")

    return "; ".join(parts).capitalize() if parts else "No significant trends"


class ConversationalIntelligence:
    """
    Main conversational interface.

    Classifies queries, resolves entities, routes to appropriate
    data sources, and synthesizes responses.
    """

    def __init__(
        self,
        entity_registry: list[dict[str, str]] | None = None,
    ) -> None:
        self.resolver = EntityResolver(entity_registry)
        self.synthesizer = CrossDomainSynthesizer()
        self.state = ConversationState()

    def process_query(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process a natural language query end-to-end.

        Returns a dict with:
        - intent: classified intent
        - entities: resolved entities
        - response: synthesized response (if data provided in context)
        - action: prepared action (if action_request)
        - state: updated conversation state
        """
        context = context or {}

        # Step 1: Classify intent
        intent = classify_intent(query)

        # Step 2: Resolve entities
        resolved = self.resolver.resolve_multiple(
            intent.extracted_entities,
        )

        # Use conversation context for pronoun resolution
        if not resolved and self.state.current_entity_id:
            resolved = [
                ResolvedEntity(
                    entity_type=self.state.current_entity_type,
                    entity_id=self.state.current_entity_id,
                    entity_name=self.state.current_entity_name,
                    match_confidence=0.6,
                    match_method="context",
                )
            ]

        # Step 3: Update conversation state
        if resolved:
            self.state.update_context(
                entity_type=resolved[0].entity_type,
                entity_id=resolved[0].entity_id,
                entity_name=resolved[0].entity_name,
                query=query,
                intent=intent.intent_type,
            )
        else:
            self.state.update_context(query=query, intent=intent.intent_type)

        # Step 4: Route and synthesize
        response = None
        action = None

        if intent.intent_type == INTENT_ENTITY_LOOKUP and resolved:
            entity_data = context.get("entity_data", {})
            response = self.synthesizer.synthesize_entity_lookup(
                entity_type=resolved[0].entity_type,
                entity_id=resolved[0].entity_id,
                entity_name=resolved[0].entity_name,
                health_data=entity_data.get("health"),
                revenue_data=entity_data.get("revenue"),
                signal_data=entity_data.get("signals"),
                trajectory_data=entity_data.get("trajectory"),
                communication_data=entity_data.get("communication"),
            )

        elif intent.intent_type == INTENT_METRIC_QUERY:
            metric_data = context.get("metric_data", {})
            response = self.synthesizer.synthesize_metric_query(
                intent.extracted_metrics,
                metric_data,
            )

        elif intent.intent_type == INTENT_RANKED_SUMMARY:
            response = self.synthesizer.synthesize_ranked_summary(
                context.get("attention_queue", []),
                context.get("active_warnings", []),
            )

        elif intent.intent_type == INTENT_COMPARISON and len(resolved) >= 2:
            entity_a = context.get("entity_a", {})
            entity_b = context.get("entity_b", {})
            response = self.synthesizer.synthesize_comparison(entity_a, entity_b)

        elif intent.intent_type == INTENT_ACTION_REQUEST and resolved:
            action = ActionCard(
                action_type=intent.extracted_action or "follow_up",
                entity_type=resolved[0].entity_type,
                entity_id=resolved[0].entity_id,
                title=f"{intent.extracted_action or 'Follow-up'} for {resolved[0].entity_name}",
                description=query,
                context={"original_query": query},
            )
            self.state.pending_actions.append(action)

        result = {
            "intent": intent.to_dict(),
            "entities": [e.to_dict() for e in resolved],
            "state": self.state.to_dict(),
        }
        if response:
            result["response"] = response.to_dict()
        if action:
            result["action"] = action.to_dict()

        return result
