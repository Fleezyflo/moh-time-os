#!/usr/bin/env python3
"""
Trace correlation smoke test.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.observability.tracing import SpanContext, get_trace_id

with SpanContext("test_span", attributes={"test": "smoke"}) as ctx:
    trace_id = get_trace_id()
    print(f"Trace ID: {trace_id}")
    assert trace_id is not None, "Trace ID should be set"

print("✅ Trace correlation working")
