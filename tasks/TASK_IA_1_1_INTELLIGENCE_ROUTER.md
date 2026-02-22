# IA-1.1: Intelligence Router & Response Envelope

## Objective

Create the base FastAPI router for intelligence endpoints with a consistent response envelope, freshness tracking, and error handling. This becomes the foundation all other IA-* tasks build on.

## What Exists

- `api/spec_router.py` — current v2.9 API router (not intelligence-aware)
- `lib/intelligence/persistence.py` — reads from `score_history`, `pattern_snapshots`, `cost_snapshots`, `intelligence_events`
- `lib/intelligence/health_unifier.py` — reads from `score_history`
- `lib/state_store.py` — `StateStore` singleton with `db_path`

## Deliverables

### New file: `api/intelligence_router.py`

```python
# Response envelope — every intelligence endpoint returns this shape
class IntelligenceMeta(BaseModel):
    computed_at: str          # ISO timestamp of when the data was last computed
    freshness_seconds: int    # seconds since computation
    stale: bool              # True if freshness > threshold (configurable, default 900s = 15min)
    cycle_id: Optional[str]  # daemon cycle that produced this data
    data_completeness: float  # 0.0-1.0, how complete the underlying data is

class IntelligenceResponse(BaseModel, Generic[T]):
    data: T
    meta: IntelligenceMeta
    errors: list[str] = []   # non-fatal warnings (e.g., "cost data unavailable for 3 clients")

class IntelligenceErrorResponse(BaseModel):
    error: str
    code: str                # machine-readable error code
    entity_type: Optional[str]
    entity_id: Optional[str]
```

### Router registration

```python
intelligence_router = APIRouter(prefix="/api/v3/intelligence", tags=["intelligence"])
```

### Freshness computation

Reads `last_successful_cycle` from the daemon's cycle log or the most recent `recorded_at` in `score_history`. Returns `stale=True` if the data is older than the configured threshold.

### Error handling

- 404 for unknown entity_type/entity_id
- 503 if intelligence has never run (no data in persistence tables)
- 200 with `errors` list for partial data (some modules succeeded, others didn't)

### Dependency injection

```python
def get_db_path() -> Path:
    """FastAPI dependency that provides the DB path."""
    return Path(StateStore().db_path)
```

## Integration Point

Register `intelligence_router` in the main FastAPI app alongside `spec_router`. Both coexist — v2.9 for legacy UI, v3 for intelligence-aware UI.

## Validation

- Router mounts without import errors
- Response envelope serializes correctly with all fields
- Freshness computation returns accurate staleness
- 404 for nonexistent entity
- 503 when no intelligence data exists
- Generic type parameter works for different data shapes

## Estimated Effort

~250 lines
