"""
Wave 4-6 Intelligence API Router — MOH TIME OS

Exposes the Wave 4-6 intelligence modules via REST API:
  - Notification Intelligence (Brief 21)
  - Predictive Intelligence (Brief 24)
  - Attention Tracking (Brief 30)
  - Intelligence Index / Dashboard (Brief 12)
  - Conversational Intelligence (Brief 25)
  - Autonomous Operations (Brief 10)
  - Security Hardening (Brief 13)
  - Performance & Scale (Brief 14)
  - Data Governance (Brief 16)

Usage in server.py:
    from api.wave2_router import wave2_router
    app.include_router(wave2_router, prefix="/api/v2/ops")
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from api.auth import require_auth
from lib import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.db_path()

wave2_router = APIRouter(
    tags=["Operations Intelligence"],
    dependencies=[Depends(require_auth)],
)


def _wrap(data, params=None):
    return {
        "status": "ok",
        "data": data,
        "computed_at": datetime.now().isoformat(),
        "params": params or {},
    }


# =============================================================================
# INTELLIGENCE INDEX / DASHBOARD (Brief 12)
# =============================================================================


@wave2_router.get("/dashboard/command-center")
def dashboard_command_center():
    """Command center view — top-level agency health."""
    try:
        from lib.intelligence.intelligence_index import IntelligenceIndex

        ix = IntelligenceIndex()
        view = ix.build_command_center(
            client_health={},
            signal_counts={"total": 0, "critical": 0},
            team_utilization=[],
            revenue_data={},
        )
        return _wrap(view.to_dict())
    except Exception as e:
        logger.exception("dashboard_command_center failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@wave2_router.get("/dashboard/full")
def dashboard_full():
    """Full dashboard index — all views combined."""
    try:
        from lib.intelligence.intelligence_index import IntelligenceIndex

        ix = IntelligenceIndex()
        index = ix.build_full_index(
            client_health={},
            signal_counts={"total": 0, "critical": 0},
            team_utilization=[],
            revenue_data={},
            resolution_items=[],
        )
        return _wrap(index.to_dict())
    except Exception as e:
        logger.exception("dashboard_full failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# CONVERSATIONAL INTELLIGENCE (Brief 25)
# =============================================================================


@wave2_router.post("/ask")
def conversational_query(
    query: str = Query(..., description="Natural language question"),
    session_id: str = Query("default", description="Session ID for context"),
):
    """Ask a natural language question about your data."""
    try:
        from lib.intelligence.conversational_intelligence import (
            ConversationalIntelligence,
        )

        ci = ConversationalIntelligence()
        result = ci.process_query(
            query=query,
            context={"session_id": session_id},
        )
        return _wrap(result)
    except Exception as e:
        logger.exception("conversational_query failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# NOTIFICATION INTELLIGENCE (Brief 21)
# =============================================================================


@wave2_router.get("/notifications/decide")
def notification_decide(
    entity_type: str = Query(..., description="Entity type"),
    entity_id: str = Query(..., description="Entity ID"),
    signal_id: str = Query("unknown", description="Signal ID"),
    urgency: str = Query("normal", description="Urgency level"),
):
    """Decide whether/how to deliver a notification."""
    try:
        from lib.intelligence.notification_intelligence import (
            NotificationIntelligence,
        )

        ni = NotificationIntelligence()
        decision = ni.decide(
            entity_type=entity_type,
            entity_id=entity_id,
            signal_id=signal_id,
            urgency=urgency,
        )
        return _wrap(decision.to_dict())
    except Exception as e:
        logger.exception("notification_decide failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@wave2_router.get("/notifications/fatigue")
def notification_fatigue(
    entity_id: str = Query("", description="Entity filter"),
):
    """Get notification fatigue state."""
    try:
        from lib.intelligence.notification_intelligence import (
            NotificationIntelligence,
        )

        ni = NotificationIntelligence()
        state = ni.get_fatigue_state(entity_id=entity_id or None)
        return _wrap(state.to_dict())
    except Exception as e:
        logger.exception("notification_fatigue failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# PREDICTIVE INTELLIGENCE (Brief 24)
# =============================================================================


@wave2_router.get("/predict/health/{entity_id}")
def predict_health(
    entity_id: str,
    entity_type: str = Query("client", description="Entity type"),
    periods: int = Query(3, description="Periods to forecast"),
):
    """Forecast entity health trajectory."""
    try:
        from lib.intelligence.predictive_intelligence import (
            PredictiveIntelligence,
        )

        pi = PredictiveIntelligence()
        forecast = pi.forecast_health(
            entity_type=entity_type,
            entity_id=entity_id,
            historical_scores=[],
            periods_ahead=periods,
        )
        return _wrap(
            forecast.to_dict(),
            {"entity_id": entity_id, "entity_type": entity_type, "periods": periods},
        )
    except Exception as e:
        logger.exception("predict_health failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@wave2_router.get("/predict/warnings")
def predict_warnings(
    entity_type: str = Query("client", description="Entity type"),
    entity_id: str = Query("", description="Entity ID"),
):
    """Generate early warnings for an entity."""
    try:
        from lib.intelligence.predictive_intelligence import (
            PredictiveIntelligence,
        )

        pi = PredictiveIntelligence()
        warnings = pi.generate_early_warnings(
            entity_type=entity_type,
            entity_id=entity_id or "all",
        )
        return _wrap([w.to_dict() for w in warnings])
    except Exception as e:
        logger.exception("predict_warnings failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# ATTENTION TRACKING (Brief 30)
# =============================================================================


@wave2_router.get("/attention/summary")
def attention_summary(
    entity_type: str = Query("", description="Entity type filter"),
    days: int = Query(7, description="Window in days"),
):
    """Get attention summary."""
    try:
        from lib.intelligence.attention_tracking import AttentionTracker

        at = AttentionTracker(db_path=DB_PATH)
        summary = at.get_attention_summary(
            entity_type=entity_type or None,
            days_back=days,
        )
        return _wrap(summary.to_dict(), {"entity_type": entity_type, "days": days})
    except Exception as e:
        logger.exception("attention_summary failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@wave2_router.get("/attention/neglected")
def attention_neglected(
    entity_type: str = Query("client", description="Entity type"),
    threshold_days: int = Query(14, description="Days without attention"),
):
    """Get neglected entities."""
    try:
        from lib.intelligence.attention_tracking import AttentionTracker

        at = AttentionTracker(db_path=DB_PATH)
        neglected = at.get_neglected_entities(
            entity_type=entity_type,
            known_entity_ids=[],
            days_threshold=threshold_days,
        )
        return _wrap(
            [n.to_dict() for n in neglected],
            {"entity_type": entity_type, "threshold_days": threshold_days},
        )
    except Exception as e:
        logger.exception("attention_neglected failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# AUTONOMOUS OPERATIONS (Brief 10)
# =============================================================================


@wave2_router.get("/ops/health")
def ops_system_health():
    """Get autonomous operations system health."""
    try:
        from lib.intelligence.autonomous_operations import AutonomousOperations

        ops = AutonomousOperations()
        report = ops.get_system_health()
        return _wrap(report.to_dict())
    except Exception as e:
        logger.exception("ops_system_health failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# PERFORMANCE (Brief 14)
# =============================================================================


@wave2_router.get("/perf/cache-stats")
def perf_cache_stats():
    """Get cache performance stats."""
    try:
        from lib.intelligence.performance_scale import InMemoryCache

        cache = InMemoryCache(max_entries=256, default_ttl_s=300)
        return _wrap(cache.get_stats().to_dict())
    except Exception as e:
        logger.exception("perf_cache_stats failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@wave2_router.get("/perf/baselines")
def perf_baselines():
    """Get performance baselines."""
    try:
        from lib.intelligence.performance_scale import PerformanceMonitor

        monitor = PerformanceMonitor()
        reports = monitor.get_all_reports()
        return _wrap([r.to_dict() for r in reports])
    except Exception as e:
        logger.exception("perf_baselines failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# DATA GOVERNANCE (Brief 16)
# =============================================================================


@wave2_router.get("/governance/catalog")
def governance_catalog():
    """Get data classification catalog."""
    try:
        from lib.intelligence.data_governance import DataCatalog

        catalog = DataCatalog()
        return _wrap(catalog.get_catalog_summary())
    except Exception as e:
        logger.exception("governance_catalog failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@wave2_router.get("/governance/compliance")
def governance_compliance():
    """Generate compliance report."""
    try:
        from lib.intelligence.data_governance import ComplianceReporter

        reporter = ComplianceReporter()
        report = reporter.generate_report()
        return _wrap(report.to_dict())
    except Exception as e:
        logger.exception("governance_compliance failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@wave2_router.get("/governance/retention")
def governance_retention():
    """Get retention policy summary."""
    try:
        from lib.intelligence.data_governance import RetentionEnforcer

        enforcer = RetentionEnforcer()
        return _wrap(enforcer.get_policy_summary())
    except Exception as e:
        logger.exception("governance_retention failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
