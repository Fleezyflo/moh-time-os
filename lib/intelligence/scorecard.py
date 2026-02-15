"""
Entity Scorecard Computation for MOH TIME OS.

Computes health scorecards for entities (Client, Project, Person, Portfolio)
using dimension definitions from scoring.py and data from query_engine.py.

EFFICIENCY: Bulk scoring functions load all data once, then score in memory.
Individual scoring functions are for single-entity use cases.

Reference: data/scoring_model_20260213.md
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from lib.intelligence.scoring import (
    EntityType,
    EntityScore,
    ScoringDimension,
    CLIENT_DIMENSIONS,
    PROJECT_DIMENSIONS,
    PERSON_DIMENSIONS,
    PORTFOLIO_DIMENSIONS,
    NormMethod,
    score_dimension,
    classify_score,
    normalize_percentile,
)
from lib.query_engine import QueryEngine

logger = logging.getLogger(__name__)


# =============================================================================
# CLIENT SCORING
# =============================================================================

def score_client(client_id: str, db_path: Optional[Path] = None) -> dict:
    """
    Compute full scorecard for a single client.
    
    For bulk scoring, use score_all_clients() which is more efficient.
    """
    engine = QueryEngine(db_path) if db_path else QueryEngine()
    
    # Get client data
    portfolio = engine.client_portfolio_overview()
    client_data = next((c for c in portfolio if c.get("client_id") == client_id), None)
    
    if not client_data:
        return _empty_scorecard(EntityType.CLIENT, client_id, "Unknown")
    
    # Get task summary
    task_summary = engine.client_task_summary(client_id)
    
    # Get 30-day metrics
    since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    until = datetime.now().strftime("%Y-%m-%d")
    period_metrics = engine.client_metrics_in_period(client_id, since, until)
    
    # Get trajectory (expensive - skip for bulk)
    try:
        trajectory = engine.client_trajectory(client_id, window_size_days=30, num_windows=3)
        trends = trajectory.get("trends", {})
    except Exception:
        trends = {}
    
    # Build metrics
    metrics = _build_client_metrics(client_data, task_summary, period_metrics, trends)
    
    # Get all comm counts for percentile
    all_comm_counts = [c.get("entity_links_count", 0) for c in portfolio]
    
    return _score_client_from_metrics(
        client_id,
        client_data.get("client_name", "Unknown"),
        metrics,
        all_comm_counts,
    )


def score_all_clients(db_path: Optional[Path] = None) -> list[dict]:
    """
    Score every client efficiently.
    
    Loads all data in bulk, then scores in memory.
    Returns list sorted by composite score ascending (worst first).
    """
    engine = QueryEngine(db_path) if db_path else QueryEngine()
    
    # BATCH LOAD: Get all client data at once
    portfolio = engine.client_portfolio_overview()
    
    if not portfolio:
        return []
    
    # Pre-compute percentile context
    all_comm_counts = [c.get("entity_links_count", 0) for c in portfolio]
    
    # Score each client using only portfolio data (fast path)
    # Skip expensive trajectory calls for bulk scoring
    scorecards = []
    for client in portfolio:
        client_id = client.get("client_id")
        if not client_id:
            continue
        
        # Build metrics from portfolio data only (no extra queries)
        metrics = {
            "total_invoiced": client.get("total_invoiced", 0),
            "total_paid": client.get("total_paid", 0),
            "total_outstanding": client.get("total_outstanding", 0),
            "financial_ar_overdue": client.get("financial_ar_overdue", 0),
            "entity_links_count": client.get("entity_links_count", 0),
            "communications_count": client.get("entity_links_count", 0),  # Proxy
            "active_tasks": client.get("active_tasks", 0),
            "total_tasks": client.get("total_tasks", 0),
            # Compute completion rate from available data
            "completion_rate": (
                ((client.get("total_tasks", 0) - client.get("active_tasks", 0)) / 
                 client.get("total_tasks", 1) * 100)
                if client.get("total_tasks", 0) > 0 else 50
            ),
            "overdue_tasks": 0,  # Not available in portfolio view
            "trend_score": 60,  # Neutral - no trajectory data in bulk mode
        }
        
        try:
            scorecard = _score_client_from_metrics(
                client_id,
                client.get("client_name", "Unknown"),
                metrics,
                all_comm_counts,
            )
            scorecards.append(scorecard)
        except Exception as e:
            logger.warning(f"Failed to score client {client_id}: {e}")
    
    # Sort by composite score ascending (worst first)
    scorecards.sort(key=lambda x: x.get("composite_score") or 0)
    
    return scorecards


def _build_client_metrics(
    client_data: dict, 
    task_summary: dict, 
    period_metrics: dict,
    trends: dict
) -> dict:
    """Build metrics dict from multiple data sources."""
    # Compute trend score from trajectory
    comm_trend = trends.get("communications_count", {})
    if comm_trend.get("direction") == "increasing":
        trend_score = 75 + min(25, abs(comm_trend.get("magnitude_pct", 0)) / 4)
    elif comm_trend.get("direction") == "declining":
        trend_score = 35 - min(35, abs(comm_trend.get("magnitude_pct", 0)) / 4)
    else:
        trend_score = 60
    
    return {
        "total_invoiced": client_data.get("total_invoiced", 0),
        "total_paid": client_data.get("total_paid", 0),
        "total_outstanding": client_data.get("total_outstanding", 0),
        "financial_ar_overdue": client_data.get("financial_ar_overdue", 0),
        "entity_links_count": client_data.get("entity_links_count", 0),
        "active_tasks": client_data.get("active_tasks", 0),
        "total_tasks": client_data.get("total_tasks", 0),
        "completion_rate": task_summary.get("completion_rate", 0),
        "overdue_tasks": task_summary.get("overdue_tasks", 0),
        "communications_count": period_metrics.get("communications_count", 0),
        "tasks_created": period_metrics.get("tasks_created", 0),
        "trend_score": trend_score,
    }


def _score_client_from_metrics(
    client_id: str,
    client_name: str,
    metrics: dict,
    all_comm_counts: list[float],
) -> dict:
    """Score a client from pre-loaded metrics."""
    dimension_scores = []
    
    for dim in CLIENT_DIMENSIONS:
        context = {}
        
        if dim.normalization == NormMethod.PERCENTILE:
            context["all_values"] = all_comm_counts
        elif dim.normalization == NormMethod.THRESHOLD:
            context["target"] = 100
            context["direction"] = "higher_is_better"
        elif dim.normalization == NormMethod.RELATIVE:
            context["baseline"] = 60
        
        score_result = score_dimension(dim, metrics, context)
        dimension_scores.append(score_result)
    
    return _build_scorecard(
        EntityType.CLIENT,
        client_id,
        client_name,
        dimension_scores,
        CLIENT_DIMENSIONS,
    )


# =============================================================================
# PROJECT SCORING
# =============================================================================

def score_project(project_id: str, db_path: Optional[Path] = None) -> dict:
    """Compute full scorecard for a single project."""
    engine = QueryEngine(db_path) if db_path else QueryEngine()
    
    project_data = engine.project_operational_state(project_id)
    
    if not project_data:
        return _empty_scorecard(EntityType.PROJECT, project_id, "Unknown")
    
    return _score_project_from_data(project_data)


def score_all_projects(db_path: Optional[Path] = None) -> list[dict]:
    """
    Score every project efficiently.
    
    Uses projects_by_health which returns all project data in one query.
    """
    engine = QueryEngine(db_path) if db_path else QueryEngine()
    
    # BATCH LOAD: Get all projects at once
    projects = engine.projects_by_health(min_tasks=1)
    
    scorecards = []
    for project in projects:
        try:
            scorecard = _score_project_from_data(project)
            scorecards.append(scorecard)
        except Exception as e:
            logger.warning(f"Failed to score project {project.get('project_id')}: {e}")
    
    scorecards.sort(key=lambda x: x.get("composite_score") or 0)
    return scorecards


def _score_project_from_data(project_data: dict) -> dict:
    """Score a project from pre-loaded data."""
    metrics = {
        "completion_rate_pct": project_data.get("completion_rate_pct", 0),
        "completed_tasks": project_data.get("completed_tasks", 0),
        "total_tasks": project_data.get("total_tasks", 0),
        "overdue_tasks": project_data.get("overdue_tasks", 0),
        "open_tasks": project_data.get("open_tasks", 0),
        "assigned_people_count": project_data.get("assigned_people_count", 0),
    }
    
    dimension_scores = []
    for dim in PROJECT_DIMENSIONS:
        context = {"target": 100, "direction": "higher_is_better"}
        score_result = score_dimension(dim, metrics, context)
        dimension_scores.append(score_result)
    
    return _build_scorecard(
        EntityType.PROJECT,
        project_data.get("project_id", "unknown"),
        project_data.get("project_name", "Unknown"),
        dimension_scores,
        PROJECT_DIMENSIONS,
    )


# =============================================================================
# PERSON SCORING
# =============================================================================

def score_person(person_id: str, db_path: Optional[Path] = None) -> dict:
    """Compute full scorecard for a single person."""
    engine = QueryEngine(db_path) if db_path else QueryEngine()
    
    person_data = engine.person_operational_profile(person_id)
    
    if not person_data:
        return _empty_scorecard(EntityType.PERSON, person_id, "Unknown")
    
    # Get all people for percentile
    all_people = engine.resource_load_distribution()
    all_dependency_scores = [
        (p.get("active_tasks", 0) * p.get("project_count", 1)) for p in all_people
    ]
    
    return _score_person_from_data(person_data, all_dependency_scores)


def score_all_persons(db_path: Optional[Path] = None) -> list[dict]:
    """
    Score every person efficiently.
    
    Loads all person data in one query.
    """
    engine = QueryEngine(db_path) if db_path else QueryEngine()
    
    # BATCH LOAD: Get all people at once
    all_people = engine.resource_load_distribution()
    
    if not all_people:
        return []
    
    # Pre-compute percentile context
    all_dependency_scores = [
        (p.get("active_tasks", 0) * p.get("project_count", 1)) for p in all_people
    ]
    
    scorecards = []
    for person in all_people:
        try:
            scorecard = _score_person_from_data(person, all_dependency_scores)
            scorecards.append(scorecard)
        except Exception as e:
            logger.warning(f"Failed to score person {person.get('person_id')}: {e}")
    
    scorecards.sort(key=lambda x: x.get("composite_score") or 0)
    return scorecards


def _score_person_from_data(person_data: dict, all_dependency_scores: list[float]) -> dict:
    """Score a person from pre-loaded data."""
    metrics = {
        "active_tasks": person_data.get("active_tasks", 0),
        "assigned_tasks": person_data.get("assigned_tasks", 0),
        "project_count": person_data.get("project_count", 0),
    }
    
    dimension_scores = []
    for dim in PERSON_DIMENSIONS:
        context = {"target": 100, "direction": "higher_is_better"}
        
        if dim.name == "availability_risk":
            context["all_values"] = all_dependency_scores
        
        score_result = score_dimension(dim, metrics, context)
        
        # Invert availability_risk: high dependency = low score
        if dim.name == "availability_risk" and score_result["score"] is not None:
            score_result["score"] = 100 - score_result["score"]
            score_result["classification"] = (
                "critical" if score_result["score"] <= 30
                else "warning" if score_result["score"] <= 60
                else "healthy"
            )
        
        dimension_scores.append(score_result)
    
    return _build_scorecard(
        EntityType.PERSON,
        person_data.get("person_id", "unknown"),
        person_data.get("person_name", "Unknown"),
        dimension_scores,
        PERSON_DIMENSIONS,
    )


# =============================================================================
# PORTFOLIO SCORING
# =============================================================================

def score_portfolio(db_path: Optional[Path] = None) -> dict:
    """
    Compute full scorecard for the entire portfolio.
    
    Uses efficient batch scoring for client health distribution.
    """
    engine = QueryEngine(db_path) if db_path else QueryEngine()
    
    # Get portfolio data
    clients = engine.client_portfolio_overview()
    capacity = engine.team_capacity_overview()
    
    # Revenue concentration
    total_invoiced = sum(c.get("total_invoiced", 0) for c in clients)
    if total_invoiced > 0:
        max_client_invoiced = max(c.get("total_invoiced", 0) for c in clients) if clients else 0
        top_client_share = max_client_invoiced / total_invoiced
    else:
        top_client_share = 0
    
    # Client health distribution - use efficient bulk scoring
    client_scores = score_all_clients(db_path)
    if client_scores:
        healthy_count = sum(1 for s in client_scores if (s.get("composite_score") or 0) > 60)
        healthy_client_pct = healthy_count / len(client_scores)
    else:
        healthy_client_pct = 0.5
    
    metrics = {
        "top_client_share": top_client_share,
        "max_tasks_per_person": capacity.get("max_tasks_per_person", 0),
        "avg_tasks_per_person": capacity.get("avg_tasks_per_person", 1),
        "healthy_client_pct": healthy_client_pct,
        "people_overloaded": capacity.get("people_overloaded", 0),
        "people_available": capacity.get("people_available", 0),
        "total_people": capacity.get("total_people", 1),
    }
    
    dimension_scores = []
    for dim in PORTFOLIO_DIMENSIONS:
        context = {"target": 100, "direction": "higher_is_better"}
        
        if dim.name == "revenue_concentration":
            context["direction"] = "lower_is_better"
            context["target"] = 0.3
        
        score_result = score_dimension(dim, metrics, context)
        dimension_scores.append(score_result)
    
    return _build_scorecard(
        EntityType.PORTFOLIO,
        "portfolio",
        "Agency Portfolio",
        dimension_scores,
        PORTFOLIO_DIMENSIONS,
    )


# =============================================================================
# HELPERS
# =============================================================================

def _build_scorecard(
    entity_type: EntityType,
    entity_id: str,
    entity_name: str,
    dimension_scores: list[dict],
    dimensions: list[ScoringDimension],
) -> dict:
    """Build final scorecard from dimension scores."""
    
    # Compute composite (weighted average of non-null dimensions)
    total_weight = 0
    weighted_sum = 0
    valid_count = 0
    
    for dim, score_result in zip(dimensions, dimension_scores):
        if score_result.get("score") is not None:
            weighted_sum += score_result["score"] * dim.weight
            total_weight += dim.weight
            valid_count += 1
    
    composite_score = weighted_sum / total_weight if total_weight > 0 else 50.0
    data_completeness = valid_count / len(dimensions) if dimensions else 0
    
    return {
        "entity_type": entity_type.value,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "composite_score": round(composite_score, 1),
        "composite_classification": classify_score(composite_score),
        "dimensions": dimension_scores,
        "scored_at": datetime.now().isoformat(),
        "data_completeness": round(data_completeness, 2),
    }


def _empty_scorecard(entity_type: EntityType, entity_id: str, entity_name: str) -> dict:
    """Return empty scorecard for entity not found."""
    return {
        "entity_type": entity_type.value,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "composite_score": None,
        "composite_classification": "data_unavailable",
        "dimensions": [],
        "scored_at": datetime.now().isoformat(),
        "data_completeness": 0,
    }


# =============================================================================
# CLASSIFICATION HELPERS
# =============================================================================

def get_entities_by_classification(
    entity_type: EntityType, 
    classification: str,
    db_path: Optional[Path] = None
) -> list[dict]:
    """Get all entities of a type matching a classification."""
    if entity_type == EntityType.CLIENT:
        all_scores = score_all_clients(db_path)
    elif entity_type == EntityType.PROJECT:
        all_scores = score_all_projects(db_path)
    elif entity_type == EntityType.PERSON:
        all_scores = score_all_persons(db_path)
    elif entity_type == EntityType.PORTFOLIO:
        portfolio_score = score_portfolio(db_path)
        if portfolio_score.get("composite_classification") == classification:
            return [portfolio_score]
        return []
    else:
        return []
    
    return [s for s in all_scores if s.get("composite_classification") == classification]


def get_score_distribution(entity_type: EntityType, db_path: Optional[Path] = None) -> dict:
    """Get distribution statistics for an entity type."""
    if entity_type == EntityType.CLIENT:
        all_scores = score_all_clients(db_path)
    elif entity_type == EntityType.PROJECT:
        all_scores = score_all_projects(db_path)
    elif entity_type == EntityType.PERSON:
        all_scores = score_all_persons(db_path)
    else:
        return {"entity_type": entity_type.value, "count": 0}
    
    if not all_scores:
        return {"entity_type": entity_type.value, "count": 0}
    
    scores = [s.get("composite_score") for s in all_scores if s.get("composite_score") is not None]
    
    if not scores:
        return {"entity_type": entity_type.value, "count": len(all_scores), "valid_scores": 0}
    
    scores_sorted = sorted(scores)
    n = len(scores)
    
    return {
        "entity_type": entity_type.value,
        "count": len(all_scores),
        "valid_scores": n,
        "min_score": round(min(scores), 1),
        "max_score": round(max(scores), 1),
        "mean_score": round(sum(scores) / n, 1),
        "median_score": round(scores_sorted[n // 2], 1),
        "by_classification": {
            "critical": sum(1 for s in all_scores if s.get("composite_classification") == "critical"),
            "at_risk": sum(1 for s in all_scores if s.get("composite_classification") == "at_risk"),
            "stable": sum(1 for s in all_scores if s.get("composite_classification") == "stable"),
            "healthy": sum(1 for s in all_scores if s.get("composite_classification") == "healthy"),
            "strong": sum(1 for s in all_scores if s.get("composite_classification") == "strong"),
        },
    }


# =============================================================================
# SCORE HISTORY (Persistence for Trend Analysis)
# =============================================================================

import json
import sqlite3
from lib import paths


def record_score(scorecard: dict, db_path: Optional[Path] = None) -> bool:
    """
    Record a scorecard to history for trend analysis.
    
    Uses REPLACE to ensure one record per entity per day.
    Call this after computing scores to build historical data.
    
    Args:
        scorecard: A scorecard dict from score_* functions
        db_path: Optional path to database
        
    Returns:
        True if recorded successfully, False otherwise
    """
    if not scorecard or scorecard.get("composite_score") is None:
        return False
    
    db = db_path or paths.db_path()
    now = datetime.now()
    
    try:
        conn = sqlite3.connect(str(db))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO score_history 
            (entity_type, entity_id, composite_score, dimensions_json, 
             data_completeness, recorded_at, recorded_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            scorecard.get("entity_type"),
            scorecard.get("entity_id"),
            scorecard.get("composite_score"),
            json.dumps(scorecard.get("dimensions", [])),
            scorecard.get("data_completeness", 0),
            now.isoformat(),
            now.strftime("%Y-%m-%d"),
        ))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.warning(f"Failed to record score: {e}")
        return False


def record_all_scores(db_path: Optional[Path] = None) -> dict:
    """
    Record scores for all entities.
    
    This should be called once per day (e.g., via cron) to build
    historical trend data.
    
    Returns:
        dict with counts of recorded scores by entity type
    """
    results = {
        "clients": 0,
        "projects": 0,
        "persons": 0,
        "portfolio": 0,
        "errors": [],
    }
    
    try:
        # Score and record all clients
        for scorecard in score_all_clients(db_path):
            if record_score(scorecard, db_path):
                results["clients"] += 1
        
        # Score and record all projects
        for scorecard in score_all_projects(db_path):
            if record_score(scorecard, db_path):
                results["projects"] += 1
        
        # Score and record all persons
        for scorecard in score_all_persons(db_path):
            if record_score(scorecard, db_path):
                results["persons"] += 1
        
        # Score and record portfolio
        portfolio_scorecard = score_portfolio(db_path)
        if record_score(portfolio_scorecard, db_path):
            results["portfolio"] = 1
            
    except Exception as e:
        logger.error(f"Error in record_all_scores: {e}")
        results["errors"].append(str(e))
    
    logger.info(f"Recorded scores: {results}")
    return results


def get_score_trend(
    entity_type: str,
    entity_id: str,
    days: int = 30,
    db_path: Optional[Path] = None,
) -> dict:
    """
    Get score trend for an entity over time.
    
    Args:
        entity_type: 'client', 'project', 'person', or 'portfolio'
        entity_id: The entity's ID
        days: Number of days of history to retrieve
        db_path: Optional path to database
        
    Returns:
        dict with:
        - entity_type, entity_id
        - history: list of {date, score, classification} ordered by date
        - trend: 'improving', 'declining', 'stable', or 'insufficient_data'
        - change_pct: percentage change from first to last score
        - current_score: most recent score
        - period_high: highest score in period
        - period_low: lowest score in period
    """
    db = db_path or paths.db_path()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    try:
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT recorded_date, composite_score, dimensions_json, data_completeness
            FROM score_history
            WHERE entity_type = ? AND entity_id = ? AND recorded_date >= ?
            ORDER BY recorded_date ASC
        """, (entity_type, entity_id, cutoff))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "days": days,
                "history": [],
                "trend": "insufficient_data",
                "change_pct": None,
                "current_score": None,
                "period_high": None,
                "period_low": None,
            }
        
        history = []
        scores = []
        
        for row in rows:
            score = row["composite_score"]
            scores.append(score)
            history.append({
                "date": row["recorded_date"],
                "score": round(score, 1),
                "classification": classify_score(score),
            })
        
        # Compute trend
        first_score = scores[0]
        last_score = scores[-1]
        
        if len(scores) < 3:
            trend = "insufficient_data"
        elif last_score > first_score + 5:
            trend = "improving"
        elif last_score < first_score - 5:
            trend = "declining"
        else:
            trend = "stable"
        
        change_pct = ((last_score - first_score) / first_score * 100) if first_score > 0 else 0
        
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "days": days,
            "history": history,
            "trend": trend,
            "change_pct": round(change_pct, 1),
            "current_score": round(last_score, 1),
            "period_high": round(max(scores), 1),
            "period_low": round(min(scores), 1),
            "data_points": len(scores),
        }
        
    except Exception as e:
        logger.error(f"Error getting score trend: {e}")
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "days": days,
            "history": [],
            "trend": "error",
            "error": str(e),
        }


def get_score_history_summary(db_path: Optional[Path] = None) -> dict:
    """
    Get summary of score history data.
    
    Useful for monitoring data collection health.
    """
    db = db_path or paths.db_path()
    
    try:
        conn = sqlite3.connect(str(db))
        cursor = conn.cursor()
        
        # Total records
        cursor.execute("SELECT COUNT(*) FROM score_history")
        total_records = cursor.fetchone()[0]
        
        # Records by entity type
        cursor.execute("""
            SELECT entity_type, COUNT(*) as count, 
                   MIN(recorded_date) as first_date,
                   MAX(recorded_date) as last_date
            FROM score_history
            GROUP BY entity_type
        """)
        by_type = {
            row[0]: {"count": row[1], "first_date": row[2], "last_date": row[3]}
            for row in cursor.fetchall()
        }
        
        # Recent activity
        cursor.execute("""
            SELECT recorded_date, COUNT(*) as count
            FROM score_history
            WHERE recorded_date >= date('now', '-7 days')
            GROUP BY recorded_date
            ORDER BY recorded_date DESC
        """)
        recent_days = [{"date": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "total_records": total_records,
            "by_entity_type": by_type,
            "recent_days": recent_days,
        }
        
    except Exception as e:
        logger.error(f"Error getting score history summary: {e}")
        return {"error": str(e)}
