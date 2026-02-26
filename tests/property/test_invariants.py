"""
Property-based tests for core invariants using Hypothesis.

These tests stress system invariants with random inputs to find edge cases.
"""

import json

from hypothesis import assume, given, settings
from hypothesis import strategies as st

# ============================================================================
# Schema Assertion Properties
# ============================================================================


@given(st.text(min_size=1, max_size=100))
def test_json_roundtrip_preserves_strings(s: str):
    """JSON encode/decode preserves all valid strings."""
    assume("\x00" not in s)  # Null bytes aren't valid JSON
    encoded = json.dumps(s)
    decoded = json.loads(encoded)
    assert decoded == s


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=20).filter(lambda x: x.isidentifier()),
        values=st.one_of(
            st.text(max_size=100),
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans(),
            st.none(),
        ),
        max_size=10,
    )
)
def test_json_roundtrip_preserves_dicts(d: dict):
    """JSON encode/decode preserves dictionary structure."""
    encoded = json.dumps(d)
    decoded = json.loads(encoded)
    assert decoded == d


# ============================================================================
# Normalization Idempotence
# ============================================================================


def normalize_client_id(raw: str) -> str:
    """Example normalizer - lowercase, strip, collapse spaces."""
    return " ".join(raw.lower().strip().split())


@given(st.text(min_size=1, max_size=100))
def test_normalization_idempotent(raw: str):
    """Applying normalization twice gives same result as once."""
    once = normalize_client_id(raw)
    twice = normalize_client_id(once)
    assert once == twice


# ============================================================================
# Timestamp Invariants
# ============================================================================


@given(st.datetimes())
def test_timestamp_iso_roundtrip(dt):
    """ISO timestamp format roundtrips correctly."""
    from datetime import datetime

    iso = dt.isoformat()
    parsed = datetime.fromisoformat(iso)
    assert parsed == dt


# ============================================================================
# ID Generation Invariants
# ============================================================================


@given(st.integers(min_value=1, max_value=1000))
def test_request_ids_unique(n: int):
    """Request ID generation produces unique IDs."""
    import uuid

    ids = [f"req-{uuid.uuid4().hex[:16]}" for _ in range(n)]
    assert len(set(ids)) == n


# ============================================================================
# Health Score Invariants
# ============================================================================


@given(
    st.floats(min_value=0, max_value=100),
    st.floats(min_value=0, max_value=100),
    st.floats(min_value=0, max_value=100),
)
def test_health_score_bounded(a: float, b: float, c: float):
    """Weighted health scores remain in valid range."""
    weights = [0.4, 0.3, 0.3]
    scores = [a, b, c]
    weighted = sum(w * s for w, s in zip(weights, scores, strict=False))
    assert 0 <= weighted <= 100


# ============================================================================
# Contract Tests
# ============================================================================


@given(st.lists(st.floats(min_value=0, max_value=1000000), min_size=0, max_size=100))
def test_ar_totals_sum_correctly(amounts: list[float]):
    """AR totals sum correctly regardless of order."""
    total1 = sum(amounts)
    total2 = sum(reversed(amounts))
    # Float precision: use approximate equality
    assert abs(total1 - total2) < 0.01


@given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=50))
def test_deduplication_is_idempotent(items: list[str]):
    """Deduplication applied twice gives same result as once."""

    def dedupe(lst):
        seen = set()
        result = []
        for item in lst:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    once = dedupe(items)
    twice = dedupe(once)

    # Idempotent: applying twice = applying once
    assert once == twice
    # All items unique
    assert len(once) == len(set(once))


# ============================================================================
# DB Round-Trip Invariants
# ============================================================================


@given(
    st.dictionaries(
        keys=st.sampled_from(["id", "name", "status", "value"]),
        values=st.one_of(
            st.text(max_size=50),
            st.integers(min_value=-1000000, max_value=1000000),
        ),
        min_size=1,
        max_size=4,
    )
)
@settings(max_examples=50)
def test_dict_serialization_roundtrip(data: dict):
    """Dictionary serialization for DB storage roundtrips correctly."""
    # Simulate DB storage (JSON serialize)
    serialized = json.dumps(data, sort_keys=True)
    deserialized = json.loads(serialized)

    # Re-serialize should be identical (deterministic)
    reserialized = json.dumps(deserialized, sort_keys=True)
    assert serialized == reserialized
